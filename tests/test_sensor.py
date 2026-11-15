"""Channel sensors and their programme-boundary timer."""

from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.on_air.const import (
    CONF_CHANNEL_NAMES,
    CONF_CHANNELS,
    CONF_IPTV_EPG_URL,
    CONF_OPEN_EPG_URL,
    CONF_TONIGHT_END,
    CONF_TONIGHT_START,
    DOMAIN,
    SOURCE_URLS,
)
from custom_components.on_air.sensor import OnAirChannelSensor
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_guides(aioclient_mock):
    aioclient_mock.get(SOURCE_URLS["open_epg"], content=(FIXTURES / "open_sample.xml").read_bytes())
    aioclient_mock.get(SOURCE_URLS["iptv_epg"], content=(FIXTURES / "iptv_sample.xml").read_bytes())


async def setup_at(hass, freezer, when: str) -> MockConfigEntry:
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to(when)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="On Air",
        options={
            CONF_OPEN_EPG_URL: SOURCE_URLS["open_epg"],
            CONF_IPTV_EPG_URL: SOURCE_URLS["iptv_epg"],
            CONF_CHANNELS: ["rai1", "rai2", "ghost"],
            CONF_CHANNEL_NAMES: {"rai1": "Rai 1", "rai2": "Rai 2", "ghost": "Ghost TV"},
            CONF_TONIGHT_START: "20:00:00",
            CONF_TONIGHT_END: "00:00:00",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def move(hass, freezer, when: str):
    freezer.move_to(when)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def test_states_and_attributes_at_2140(hass, freezer, mock_guides):
    await setup_at(hass, freezer, "2026-11-15 20:40:00+00:00")  # 21:40 Rome
    rai1 = hass.states.get("sensor.on_air_rai_1")
    assert rai1.state == "Belgio - Italia"
    assert rai1.attributes["channel_name"] == "Rai 1"
    assert rai1.attributes["now"]["category"] == "Sport"
    assert rai1.attributes["next"]["title"] == "TG1 Sera"
    assert rai1.attributes["contract_version"] == 1
    assert rai1.attributes["icon"] == "mdi:television"
    assert hass.states.get("sensor.on_air_rai_2").state == "The Rookie"


async def test_state_changes_at_programme_boundary(hass, freezer, mock_guides):
    await setup_at(hass, freezer, "2026-11-15 20:40:00+00:00")
    await move(hass, freezer, "2026-11-15 20:50:00+00:00")  # 21:50: The Rookie ends, nothing after
    rai2 = hass.states.get("sensor.on_air_rai_2")
    assert rai2.state == "unknown" and rai2.attributes["now"] is None
    await move(hass, freezer, "2026-11-15 22:20:00+00:00")  # 23:20 Rome
    assert hass.states.get("sensor.on_air_rai_1").state == "TG1 Sera"
    # Second boundary on the same channel: proves the timer is re-armed after firing.
    await move(hass, freezer, "2026-11-15 22:25:00+00:00")  # 23:25 Rome: TG1 Sera ends
    assert hass.states.get("sensor.on_air_rai_1").state == "unknown"


async def test_tonight_rolls_over_at_six(hass, freezer, mock_guides):
    await setup_at(hass, freezer, "2026-11-16 01:30:00+00:00")  # 02:30 Rome, nothing on air
    rai1 = hass.states.get("sensor.on_air_rai_1")
    assert rai1.attributes["tonight_window"]["start"] == "2026-11-15T20:00:00+01:00"
    assert "Belgio - Italia" in [p["title"] for p in rai1.attributes["tonight"]]
    await move(hass, freezer, "2026-11-16 05:00:00+00:00")  # 06:00 Rome: no programme boundary here
    rai1 = hass.states.get("sensor.on_air_rai_1")
    assert rai1.attributes["tonight_window"]["start"] == "2026-11-16T20:00:00+01:00"
    assert rai1.attributes["tonight"] == []


async def test_missing_channel_is_unknown(hass, freezer, mock_guides):
    await setup_at(hass, freezer, "2026-11-15 20:40:00+00:00")
    ghost = hass.states.get("sensor.on_air_ghost_tv")
    assert ghost.state == "unknown"
    assert (ghost.attributes["now"], ghost.attributes["next"], ghost.attributes["tonight"]) == (None, None, [])


async def test_unrecorded_attributes():
    assert OnAirChannelSensor._unrecorded_attributes == frozenset({"next", "tonight", "tonight_window"})


async def test_one_service_device_and_stable_unique_ids(hass, freezer, mock_guides):
    entry = await setup_at(hass, freezer, "2026-11-15 20:40:00+00:00")
    ent_reg = er.async_get(hass)
    ids = sorted(e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id))
    assert ids == ["on_air_ghost", "on_air_rai1", "on_air_rai2"]
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1 and devices[0].entry_type is dr.DeviceEntryType.SERVICE
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    again = sorted(e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id))
    assert again == ids


async def test_timer_cancelled_on_unload(hass, freezer, mock_guides):
    entry = await setup_at(hass, freezer, "2026-11-15 20:40:00+00:00")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await move(hass, freezer, "2026-11-15 22:20:00+00:00")  # must not raise or write states
    assert hass.states.get("sensor.on_air_rai_1").state == "unavailable"
