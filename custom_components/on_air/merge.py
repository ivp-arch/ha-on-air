"""Merge programmes from several guide sources. Pure module: no Home Assistant imports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta

from .channels import clean_name
from .models import Programme, SourceGuide

DEFAULT_TOLERANCE = timedelta(minutes=5)

_Gap = tuple[datetime | None, datetime | None]  # None = open-ended


def _ordered_sources(sources: Sequence[str] | Mapping[str, object], order: Sequence[str]) -> list[str]:
    present = list(sources)
    return [s for s in order if s in present] + [s for s in present if s not in order]


def _trim(programmes: list[Programme]) -> list[Programme]:
    """Sort by start and cut overlaps: a programme ends when the next one starts."""
    ordered = sorted(programmes, key=lambda x: x.start)
    out: list[Programme] = []
    for i, prog in enumerate(ordered):
        if i + 1 < len(ordered) and prog.end > ordered[i + 1].start:
            prog = replace(prog, end=ordered[i + 1].start)
        if prog.end > prog.start:
            out.append(prog)
    return out


def _gaps(programmes: list[Programme]) -> list[_Gap]:
    """Uncovered intervals of a sorted, non-overlapping timeline (open at both ends)."""
    gaps: list[_Gap] = []
    prev_end: datetime | None = None
    for prog in programmes:
        if prev_end is None:
            gaps.append((None, prog.start))
        elif prog.start > prev_end:
            gaps.append((prev_end, prog.start))
        prev_end = prog.end if prev_end is None else max(prev_end, prog.end)
    gaps.append((prev_end, None))
    return gaps


def _fit_in_gaps(
    prog: Programme, gaps: list[_Gap], tolerance: timedelta
) -> Programme | None:
    """Clip ``prog`` to the first gap it overlaps by at least ``tolerance``."""
    for g_start, g_end in gaps:
        start = prog.start if g_start is None else max(prog.start, g_start)
        end = prog.end if g_end is None else min(prog.end, g_end)
        if end - start >= tolerance:
            return replace(prog, start=start, end=end)
    return None


def merge_programmes(
    by_source: Mapping[str, Sequence[Programme]],
    order: Sequence[str],
    tolerance: timedelta = DEFAULT_TOLERANCE,
) -> list[Programme]:
    """Merge one channel's programmes from several sources.

    1. The primary source is the first in ``order`` with programmes: it gives the
       timeline (and the titles).
    2. Programmes of the next sources fill the uncovered intervals, clipped to the
       interval; pieces shorter than ``tolerance`` are dropped.
    3. A programme without category takes it from the programme of another source
       whose start is closest, within ``tolerance`` (inclusive); first source in
       ``order`` first.
    The result is sorted and has no overlaps.
    """
    sources = _ordered_sources(by_source, order)
    lists = {s: sorted(by_source[s], key=lambda x: x.start) for s in sources}
    primary = next((s for s in sources if lists[s]), None)
    if primary is None:
        return []

    result = _trim(lists[primary])
    for src in sources[sources.index(primary) + 1 :]:
        for prog in lists[src]:
            piece = _fit_in_gaps(prog, _gaps(result), tolerance)
            if piece is not None:
                result = sorted([*result, piece], key=lambda x: x.start)

    enriched: list[Programme] = []
    for prog in result:
        if prog.category is None:
            for src in sources:
                if src == prog.source:
                    continue
                candidates = [
                    other
                    for other in lists[src]
                    if other.category and abs(other.start - prog.start) <= tolerance
                ]
                match = min(candidates, key=lambda o: abs(o.start - prog.start), default=None)
                if match is not None:
                    prog = replace(prog, category=match.category)
                    break
        enriched.append(prog)
    return _trim(enriched)


def merge_guides(
    guides: Sequence[SourceGuide], order: Sequence[str]
) -> tuple[dict[str, str], dict[str, list[Programme]]]:
    """Merge whole source guides: channel key -> name, channel key -> programmes.

    The channel name comes from the first source in ``order`` that has the channel,
    cleaned with ``clean_name``.
    Channels without programmes in any source are named but have no programme list.
    """
    by_source = {g.source: g for g in guides}
    sources = _ordered_sources(by_source, order)
    names: dict[str, str] = {}
    for src in sources:
        for key, name in by_source[src].channels.items():
            names.setdefault(key, clean_name(name))
    programmes: dict[str, list[Programme]] = {}
    for key in names:
        merged = merge_programmes(
            {src: by_source[src].programmes.get(key, []) for src in sources}, sources
        )
        if merged:
            programmes[key] = merged
    return names, programmes
