"""The On Air integration: what's on TV now and tonight."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import OnAirCoordinator

type OnAirConfigEntry = ConfigEntry[OnAirCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: OnAirConfigEntry) -> bool:
    """Set up On Air from a config entry."""
    coordinator = OnAirCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: OnAirConfigEntry) -> None:
    """Reload after the options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OnAirConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
