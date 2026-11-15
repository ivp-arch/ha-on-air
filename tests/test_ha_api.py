"""Fail fast if a Home Assistant API used by this integration is missing."""

import inspect

from custom_components.on_air.const import MAX_STATE_LEN


def test_ha_apis_exist():
    from homeassistant.components.recorder.db_schema import MAX_STATE_ATTRS_BYTES
    from homeassistant.config_entries import ConfigFlow
    from homeassistant.const import MAX_LENGTH_STATE_STATE
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.event import async_track_point_in_time  # noqa: F401
    from homeassistant.helpers.selector import (  # noqa: F401
        SelectSelector,
        SelectSelectorConfig,
        TimeSelector,
    )

    assert "multiple" in SelectSelectorConfig.__annotations__
    assert hasattr(Entity, "_unrecorded_attributes")
    assert MAX_STATE_ATTRS_BYTES == 16384 and MAX_LENGTH_STATE_STATE == 255
    assert "options" in inspect.signature(ConfigFlow.async_create_entry).parameters


def test_max_state_len_matches_ha():
    from homeassistant.const import MAX_LENGTH_STATE_STATE

    assert MAX_STATE_LEN == MAX_LENGTH_STATE_STATE
