"""Attribute contract v1 of the channel sensors. Pure module: no Home Assistant imports.

Documented in docs/attributes-contract.md. Bump CONTRACT_VERSION only for changes
that break existing cards (rename, removal, change of meaning).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, tzinfo
from typing import Any

from .guide import now_next, overlapping
from .models import Programme, SourceStatus

CONTRACT_VERSION = 1
# Home Assistant limit on the length of a state (MAX_LENGTH_STATE_STATE).
MAX_STATE_LEN = 255
# Large, fast-changing attributes kept out of the recorder database.
UNRECORDED_ATTRIBUTES = frozenset({"next", "tonight", "tonight_window"})


def _iso(value: datetime | None, tz: tzinfo) -> str | None:
    return value.astimezone(tz).isoformat() if value else None


def programme_dict(programme: Programme, tz: tzinfo) -> dict[str, Any]:
    """Serialize a programme; times are ISO 8601 in ``tz``."""
    return {
        "title": programme.title,
        "start": _iso(programme.start, tz),
        "end": _iso(programme.end, tz),
        "category": programme.category,
        "source": programme.source,
    }


def channel_state(programmes: Sequence[Programme], at: datetime) -> str | None:
    """Title on air at ``at``, truncated to the state limit; None if nothing is on."""
    now, _ = now_next(programmes, at)
    return now.title[:MAX_STATE_LEN] if now else None


def channel_attributes(
    channel_name: str,
    programmes: Sequence[Programme],
    at: datetime,
    window: tuple[datetime, datetime],
    updated_at: datetime | None,
    sources: Mapping[str, SourceStatus],
    tz: tzinfo,
) -> dict[str, Any]:
    """Build the v1 attributes of a channel sensor."""
    now, nxt = now_next(programmes, at)
    return {
        "contract_version": CONTRACT_VERSION,
        "channel_name": channel_name,
        "now": programme_dict(now, tz) if now else None,
        "next": programme_dict(nxt, tz) if nxt else None,
        "tonight": [programme_dict(p, tz) for p in overlapping(programmes, *window)],
        "tonight_window": {"start": _iso(window[0], tz), "end": _iso(window[1], tz)},
        "updated_at": _iso(updated_at, tz),
        "sources": {
            source: {"status": status.status, "updated_at": _iso(status.updated_at, tz)}
            for source, status in sources.items()
        },
    }
