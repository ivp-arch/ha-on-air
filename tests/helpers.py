"""Small helpers shared by tests."""

from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.on_air.models import Programme

ROME = ZoneInfo("Europe/Rome")


def rome(y: int, mo: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    """Aware datetime in Europe/Rome."""
    return datetime(y, mo, d, h, mi, tzinfo=ROME)


def prog(title: str, start: datetime, end: datetime, category: str | None = None,
         source: str = "open_epg") -> Programme:
    return Programme(title, start, end, category, source)
