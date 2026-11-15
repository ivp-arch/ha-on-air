"""Diagnostics for On Air. The guides are public data: nothing to redact."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import OnAirConfigEntry
from .const import CONF_CHANNELS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OnAirConfigEntry
) -> dict[str, Any]:
    """Return options, per-source status and counts, and channels found nowhere."""
    coordinator = entry.runtime_data
    data = coordinator.data
    guides = coordinator.source_guides
    sources: dict[str, Any] = {}
    for source, status in data.sources.items():
        guide = guides.get(source)
        sources[source] = {
            "status": status.status,
            "updated_at": status.updated_at.isoformat() if status.updated_at else None,
            "channels": len(guide.channels) if guide else 0,
            "programmes": sum(len(p) for p in guide.programmes.values()) if guide else 0,
        }
    return {
        "options": dict(entry.options),
        "sources": sources,
        "missing_channels": [
            key for key in entry.options.get(CONF_CHANNELS, []) if key not in data.programmes
        ],
    }
