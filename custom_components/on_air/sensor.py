"""One sensor per selected channel: what is on now, next and tonight."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import OnAirConfigEntry
from .const import (
    CONF_CHANNEL_NAMES,
    CONF_CHANNELS,
    CONF_TONIGHT_END,
    CONF_TONIGHT_START,
    DEFAULT_TONIGHT_END,
    DEFAULT_TONIGHT_START,
    DOMAIN,
)
from .contract import UNRECORDED_ATTRIBUTES, channel_attributes, channel_state
from .coordinator import OnAirCoordinator
from .guide import next_boundary, next_rollover, tonight_window
from .models import Programme


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OnAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one sensor per selected channel."""
    coordinator = entry.runtime_data
    async_add_entities(
        OnAirChannelSensor(coordinator, entry, key) for key in entry.options.get(CONF_CHANNELS, [])
    )


class OnAirChannelSensor(CoordinatorEntity[OnAirCoordinator], SensorEntity):
    """State = title on air; attributes = contract v1 (see docs/attributes-contract.md).

    No polling: the state is rewritten when the guide is refreshed, at every
    programme boundary and when "tonight" moves to the new day.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:television"
    _attr_should_poll = False
    _unrecorded_attributes = UNRECORDED_ATTRIBUTES

    def __init__(self, coordinator: OnAirCoordinator, entry: OnAirConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        stored: dict[str, str] = entry.options.get(CONF_CHANNEL_NAMES, {})
        self._channel_name = coordinator.data.channels.get(key) or stored.get(key, key)
        self._attr_name = self._channel_name
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="On Air",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._window_times = (
            time.fromisoformat(entry.options.get(CONF_TONIGHT_START, DEFAULT_TONIGHT_START)),
            time.fromisoformat(entry.options.get(CONF_TONIGHT_END, DEFAULT_TONIGHT_END)),
        )
        self._unsub_timer: Callable[[], None] | None = None

    @property
    def _programmes(self) -> list[Programme]:
        return self.coordinator.data.programmes.get(self._key, [])

    @property
    def native_value(self) -> str | None:
        return channel_state(self._programmes, dt_util.now())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now = dt_util.now()
        data = self.coordinator.data
        return channel_attributes(
            self._channel_name,
            self._programmes,
            now,
            tonight_window(now, *self._window_times),
            data.updated_at,
            data.sources,
            dt_util.get_default_time_zone(),
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._schedule_next_change()

    async def async_will_remove_from_hass(self) -> None:
        self._cancel_timer()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._schedule_next_change()
        super()._handle_coordinator_update()

    @callback
    def _cancel_timer(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _schedule_next_change(self) -> None:
        """Arm one timer at the next programme boundary or the 06:00 rollover."""
        self._cancel_timer()
        now = dt_util.now()
        boundary = next_boundary(self._programmes, now)
        rollover = next_rollover(now)
        when = min(boundary, rollover) if boundary else rollover
        self._unsub_timer = async_track_point_in_time(self.hass, self._handle_timer, when)

    @callback
    def _handle_timer(self, _now: datetime) -> None:
        self._unsub_timer = None
        self._schedule_next_change()
        self.async_write_ha_state()
