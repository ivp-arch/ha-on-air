"""Config entry diagnostics."""

from pathlib import Path

from pytest_homeassistant_custom_component.common import MockConfigEntry

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
from custom_components.on_air.diagnostics import async_get_config_entry_diagnostics

FIXTURES = Path(__file__).parent / "fixtures"


async def test_diagnostics(hass, aioclient_mock, freezer):
    # Fixed clock: the fixtures hold the evening of 15/11/2026.
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to("2026-11-15 20:40:00+00:00")
    aioclient_mock.get(SOURCE_URLS["open_epg"], status=404)
    aioclient_mock.get(SOURCE_URLS["iptv_epg"], content=(FIXTURES / "iptv_sample.xml").read_bytes())
    options = {
        CONF_OPEN_EPG_URL: SOURCE_URLS["open_epg"],
        CONF_IPTV_EPG_URL: SOURCE_URLS["iptv_epg"],
        CONF_CHANNELS: ["rai2", "ghost"],
        CONF_CHANNEL_NAMES: {"rai2": "Rai 2", "ghost": "Ghost TV"},
        CONF_TONIGHT_START: "20:00:00",
        CONF_TONIGHT_END: "00:00:00",
    }
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["options"] == options
    assert diag["sources"]["open_epg"] == {"status": "error", "updated_at": None, "channels": 0, "programmes": 0}
    iptv = diag["sources"]["iptv_epg"]
    assert iptv["status"] == "ok" and iptv["channels"] == 1 and iptv["updated_at"]
    assert diag["missing_channels"] == ["ghost"]
