"""What is on now, next and tonight. Pure module: no Home Assistant imports.

All functions expect ``programmes`` sorted by start and without overlaps, as
produced by ``merge.merge_programmes``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, time, timedelta

from .models import Programme

# Before this local hour, "tonight" still means the previous evening.
DAY_ROLLOVER_HOUR = 6


def now_next(
    programmes: Sequence[Programme], at: datetime
) -> tuple[Programme | None, Programme | None]:
    """Return (programme on air at ``at``, the one after it).

    ``now`` has ``start <= at < end``. ``next`` is the first programme starting at
    or after the end of ``now`` (or after ``at`` when nothing is on air).
    """
    now = next((p for p in programmes if p.start <= at < p.end), None)
    ref = now.end if now else at
    nxt = next((p for p in programmes if p.start >= ref and p is not now), None)
    return now, nxt


def overlapping(
    programmes: Sequence[Programme], start: datetime, end: datetime
) -> list[Programme]:
    """Programmes that overlap [start, end)."""
    return [p for p in programmes if p.start < end and p.end > start]


def tonight_window(
    at: datetime, start: time, end: time, rollover_hour: int = DAY_ROLLOVER_HOUR
) -> tuple[datetime, datetime]:
    """Return the evening window that "tonight" means at ``at`` (aware, local).

    Before ``rollover_hour`` it is still the previous evening. When ``end`` is not
    after ``start`` (e.g. 20:00-00:00) the window ends on the following day.
    """
    day = at.date() if at.hour >= rollover_hour else at.date() - timedelta(days=1)
    tz = at.tzinfo
    w_start = datetime.combine(day, start, tzinfo=tz)
    w_end = datetime.combine(day, end, tzinfo=tz)
    if w_end <= w_start:
        w_end = datetime.combine(day + timedelta(days=1), end, tzinfo=tz)
    return w_start, w_end


def next_boundary(programmes: Sequence[Programme], at: datetime) -> datetime | None:
    """Earliest instant after ``at`` when what is on air changes, or None."""
    candidates = [p.end for p in programmes if p.start <= at < p.end]
    candidates += [p.start for p in programmes if p.start > at][:1]
    return min(candidates, default=None)


def next_rollover(at: datetime, rollover_hour: int = DAY_ROLLOVER_HOUR) -> datetime:
    """Next instant (after ``at``) when "tonight" moves to the new day."""
    candidate = datetime.combine(at.date(), time(rollover_hour), tzinfo=at.tzinfo)
    if candidate <= at:
        candidate = datetime.combine(
            at.date() + timedelta(days=1), time(rollover_hour), tzinfo=at.tzinfo
        )
    return candidate
