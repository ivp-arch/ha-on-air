"""Streaming XMLTV parser. Pure module: no Home Assistant imports."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, tzinfo
import gzip
import io
import re
import xml.etree.ElementTree as ET

from .channels import channel_key
from .models import Programme, SourceGuide

_GZIP_MAGIC = b"\x1f\x8b"
_TIME = re.compile(r"^\s*(\d{14})(?:\s*([+-])(\d{2})(\d{2}))?\s*$")
# Hourly fillers some sources put where they have no data.
_PLACEHOLDERS = frozenset({"no data"})


def parse_time(value: str, default_tz: tzinfo) -> datetime | None:
    """Parse an XMLTV time ("YYYYMMDDHHMMSS [+-HHMM]") into an aware UTC datetime.

    Without an offset the time is read in ``default_tz``. Returns None if malformed.
    """
    match = _TIME.match(value or "")
    if not match:
        return None
    digits, sign, hours, minutes = match.groups()
    try:
        naive = datetime.strptime(digits, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    if sign is None:
        return naive.replace(tzinfo=default_tz).astimezone(UTC)
    offset = timedelta(hours=int(hours), minutes=int(minutes))
    if sign == "-":
        offset = -offset
    return (naive - offset).replace(tzinfo=UTC)


def _first_text(elem: ET.Element, tag: str) -> str | None:
    for child in elem.iter(tag):
        text = (child.text or "").strip()
        if text:
            return text
    return None


def parse_xmltv(
    data: bytes,
    *,
    source: str,
    keep: Callable[[str], bool] | None = None,
    window: tuple[datetime, datetime] | None = None,
    default_tz: tzinfo = UTC,
    channels_only: bool = False,
) -> SourceGuide:
    """Parse XMLTV (plain or gzip) into a SourceGuide keyed by channel key.

    - ``keep(key)`` false: the channel and its programmes are ignored.
    - ``window``: only programmes overlapping [start, end) are kept.
    - ``channels_only``: stop at the first programme (XMLTV lists channels first).
    Bad rows (no title, placeholder title, malformed time, undeclared channel) are
    skipped. A programme without stop ends when the next one starts; the last one
    of a channel without stop is dropped. When two channels of the same source map
    to the same key, the one with more programmes wins (ties: first declared).
    """
    if data[:2] == _GZIP_MAGIC:
        data = gzip.decompress(data)

    id_key: dict[str, str] = {}
    id_name: dict[str, str] = {}
    # xml channel id -> [(start, stop or None, title, category)]
    rows: dict[str, list[tuple[datetime, datetime | None, str, str | None]]] = {}

    for _, elem in ET.iterparse(io.BytesIO(data), events=("end",)):
        if elem.tag == "channel":
            cid = elem.get("id")
            if cid:
                name = _first_text(elem, "display-name") or cid
                key = channel_key(name)
                if key and (keep is None or keep(key)):
                    id_key[cid] = key
                    id_name[cid] = name
            elem.clear()
        elif elem.tag == "programme":
            if channels_only:
                break
            cid = elem.get("channel")
            if cid in id_key:
                title = _first_text(elem, "title")
                start = parse_time(elem.get("start", ""), default_tz)
                if title and start and title.casefold() not in _PLACEHOLDERS:
                    stop_raw = elem.get("stop")
                    stop = parse_time(stop_raw, default_tz) if stop_raw else None
                    rows.setdefault(cid, []).append(
                        (start, stop, title, _first_text(elem, "category"))
                    )
            elem.clear()

    by_id: dict[str, list[Programme]] = {}
    for cid, items in rows.items():
        items.sort(key=lambda r: r[0])
        progs: list[Programme] = []
        for i, (start, stop, title, category) in enumerate(items):
            end = stop
            if end is None and i + 1 < len(items):
                end = items[i + 1][0]
            if end is None or end <= start:
                continue
            if window and not (start < window[1] and end > window[0]):
                continue
            progs.append(Programme(title, start, end, category, source))
        by_id[cid] = progs

    channels: dict[str, str] = {}
    programmes: dict[str, list[Programme]] = {}
    for cid, key in id_key.items():  # declaration order
        progs = by_id.get(cid, [])
        if key in channels and len(progs) <= len(programmes.get(key, [])):
            continue
        channels[key] = id_name[cid]
        if progs:
            programmes[key] = progs
        else:
            programmes.pop(key, None)

    return SourceGuide(source=source, channels=channels, programmes=programmes)
