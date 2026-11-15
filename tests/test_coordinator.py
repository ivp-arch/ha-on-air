"""Guide download and coordinator."""

from pathlib import Path

import aiohttp
import pytest
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
from custom_components.on_air.coordinator import (
    OnAirCoordinator,
    SourceFetchError,
    async_fetch_catalog,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

FIXTURES = Path(__file__).parent / "fixtures"
OPEN_URL = SOURCE_URLS["open_epg"]
IPTV_URL = SOURCE_URLS["iptv_epg"]
OPEN_BYTES = (FIXTURES / "open_sample.xml").read_bytes()
IPTV_BYTES = (FIXTURES / "iptv_sample.xml").read_bytes()


def make_options(open_url=OPEN_URL, iptv_url=IPTV_URL, channels=None):
    return {
        CONF_OPEN_EPG_URL: open_url,
        CONF_IPTV_EPG_URL: iptv_url,
        CONF_CHANNELS: channels or ["rai1", "skysportuno", "canale5", "ghost"],
        CONF_CHANNEL_NAMES: {"ghost": "Ghost TV"},
        CONF_TONIGHT_START: "20:00:00",
        CONF_TONIGHT_END: "00:00:00",
    }


@pytest.fixture
async def rome_evening(hass, freezer):
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to("2026-11-15 20:40:00+00:00")  # 21:40 in Rome


def mock_both_ok(aioclient_mock):
    aioclient_mock.get(OPEN_URL, content=OPEN_BYTES)
    aioclient_mock.get(IPTV_URL, content=IPTV_BYTES)


async def refresh(hass, options=None, coordinator=None) -> OnAirCoordinator:
    if coordinator is None:
        entry = MockConfigEntry(domain=DOMAIN, options=options or make_options())
        entry.add_to_hass(hass)
        coordinator = OnAirCoordinator(hass, entry)
    await coordinator.async_refresh()
    return coordinator


async def test_both_sources_merged(hass, aioclient_mock, rome_evening):
    mock_both_ok(aioclient_mock)
    c = await refresh(hass)
    assert c.last_update_success
    rai1 = c.data.programmes["rai1"]
    assert [(p.title, p.category) for p in rai1][1] == ("Belgio - Italia", "Sport")
    assert c.data.channels["rai1"] == "Rai 1"
    assert {k: v.status for k, v in c.data.sources.items()} == {"open_epg": "ok", "iptv_epg": "ok"}


async def test_failed_source_keeps_previous_data(hass, aioclient_mock, rome_evening, freezer):
    mock_both_ok(aioclient_mock)
    c = await refresh(hass)
    first_open = c.data.sources["open_epg"]
    first_rai1 = c.data.programmes["rai1"]
    aioclient_mock.clear_requests()
    aioclient_mock.get(OPEN_URL, status=404)
    aioclient_mock.get(IPTV_URL, content=IPTV_BYTES)
    freezer.tick(3600)
    await refresh(hass, coordinator=c)
    assert c.last_update_success
    assert c.data.sources["open_epg"].status == "error"
    assert c.data.sources["open_epg"].updated_at == first_open.updated_at
    assert c.data.sources["iptv_epg"].updated_at > first_open.updated_at
    assert c.data.programmes["rai1"] == first_rai1


async def test_corrupt_gzip_is_a_source_error(hass, aioclient_mock, rome_evening):
    aioclient_mock.get(OPEN_URL, content=b"\x1f\x8bnot really gzip")
    aioclient_mock.get(IPTV_URL, content=IPTV_BYTES)
    c = await refresh(hass)
    assert c.last_update_success
    assert c.data.sources["open_epg"].status == "error"
    assert c.data.programmes["rai1"][1].title == "UEFA Nations League"


async def test_invalid_xml_is_a_source_error(hass, aioclient_mock, rome_evening):
    aioclient_mock.get(OPEN_URL, content=b"<tv><channel")
    aioclient_mock.get(IPTV_URL, content=IPTV_BYTES)
    c = await refresh(hass)
    assert c.data.sources["open_epg"].status == "error"


async def test_no_data_at_all_raises_update_failed(hass, aioclient_mock, rome_evening):
    aioclient_mock.get(OPEN_URL, exc=aiohttp.ClientError())
    aioclient_mock.get(IPTV_URL, status=500)
    c = await refresh(hass)
    assert not c.last_update_success
    assert isinstance(c.last_exception, UpdateFailed)


async def test_disabled_source_is_not_downloaded(hass, aioclient_mock, rome_evening):
    aioclient_mock.get(IPTV_URL, content=IPTV_BYTES)
    c = await refresh(hass, make_options(open_url=""))
    assert c.last_update_success
    assert [str(call[1]) for call in aioclient_mock.mock_calls] == [IPTV_URL]
    assert set(c.data.sources) == {"iptv_epg"}


async def test_missing_channel_uses_stored_name(hass, aioclient_mock, rome_evening):
    mock_both_ok(aioclient_mock)
    c = await refresh(hass)
    assert c.data.channels["ghost"] == "Ghost TV"
    assert c.data.programmes.get("ghost", []) == []


async def test_only_selected_channels_are_kept(hass, aioclient_mock, rome_evening):
    mock_both_ok(aioclient_mock)
    c = await refresh(hass)
    assert set(c.data.channels) == {"rai1", "skysportuno", "canale5", "ghost"}
    assert "rai2" not in c.data.programmes


async def test_catalog_unions_channels(hass, aioclient_mock):
    mock_both_ok(aioclient_mock)
    catalog = await async_fetch_catalog(hass, SOURCE_URLS)
    assert {"rai1", "rai2", "skysportuno", "skyunoplus1", "canale5"} <= set(catalog)
    assert catalog["rai1"] == "Rai 1" and catalog["skyunoplus1"] == "Sky Uno +1"


async def test_catalog_with_one_source_down(hass, aioclient_mock):
    aioclient_mock.get(OPEN_URL, status=404)
    aioclient_mock.get(IPTV_URL, content=IPTV_BYTES)
    assert "rai2" in await async_fetch_catalog(hass, SOURCE_URLS)


async def test_catalog_all_down_raises(hass, aioclient_mock):
    aioclient_mock.get(OPEN_URL, status=404)
    aioclient_mock.get(IPTV_URL, exc=aiohttp.ClientError())
    with pytest.raises(SourceFetchError):
        await async_fetch_catalog(hass, SOURCE_URLS)
