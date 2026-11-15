"""Data models shared by the On Air modules. Standard library only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Programme:
    """One programme on one channel. ``start`` and ``end`` are aware, in UTC."""

    title: str
    start: datetime
    end: datetime
    category: str | None
    source: str


@dataclass(frozen=True)
class SourceGuide:
    """What one XMLTV source says: channel key -> name, channel key -> programmes."""

    source: str
    channels: dict[str, str]
    programmes: dict[str, list[Programme]]


@dataclass(frozen=True)
class SourceStatus:
    """Outcome of the last download of a source: ``status`` is "ok" or "error"."""

    status: str
    updated_at: datetime | None


@dataclass(frozen=True)
class GuideData:
    """Merged guide for the selected channels, as kept by the coordinator."""

    channels: dict[str, str]
    programmes: dict[str, list[Programme]]
    sources: dict[str, SourceStatus]
    updated_at: datetime
