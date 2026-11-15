"""Config flow, options flow and setup."""

import json
from pathlib import Path

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.on_air.const import (
    CONF_CHANNEL_NAMES,
    CONF_CHANNELS,
    CONF_GROUPS,
    CONF_IPTV_EPG_URL,
    CONF_OPEN_EPG_URL,
    CONF_TONIGHT_END,
    CONF_TONIGHT_START,
    DOMAIN,
    SOURCE_URLS,
)
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType

FIXTURES = Path(__file__).parent / "fixtures"
OPEN_URL = SOURCE_URLS["open_epg"]
IPTV_URL = SOURCE_URLS["iptv_epg"]
URLS = {CONF_OPEN_EPG_URL: OPEN_URL, CONF_IPTV_EPG_URL: IPTV_URL}


def mock_ok(aioclient_mock):
    aioclient_mock.get(OPEN_URL, content=(FIXTURES / "open_sample.xml").read_bytes())
    aioclient_mock.get(IPTV_URL, content=(FIXTURES / "iptv_sample.xml").read_bytes())


def mock_down(aioclient_mock):
    aioclient_mock.get(OPEN_URL, status=404)
    aioclient_mock.get(IPTV_URL, exc=aiohttp.ClientError())


def field(result, name):
    for key, value in result["data_schema"].schema.items():
        if key == name:
            return key, value
    raise KeyError(name)


def suggested(result, name):
    key, _ = field(result, name)
    return (key.description or {}).get("suggested_value")


async def start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})


async def test_full_flow_with_preset(hass, aioclient_mock):
    mock_ok(aioclient_mock)
    result = await start(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    assert suggested(result, CONF_OPEN_EPG_URL) == OPEN_URL
    result = await hass.config_entries.flow.async_configure(result["flow_id"], URLS)
    assert result["step_id"] == "channels"
    preset = suggested(result, CONF_CHANNELS)
    # Agreed preset, limited to the channels the fixtures contain.
    assert preset == ["rai1", "rai2", "canale5", "skysportuno"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CHANNELS: preset})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "On Air" and result["data"] == {}
    opts = result["options"]
    assert opts[CONF_CHANNELS] == preset
    assert opts[CONF_CHANNEL_NAMES]["rai1"] == "Rai 1"
    assert (opts[CONF_OPEN_EPG_URL], opts[CONF_IPTV_EPG_URL]) == (OPEN_URL, IPTV_URL)
    assert (opts[CONF_TONIGHT_START], opts[CONF_TONIGHT_END]) == ("20:00:00", "00:00:00")


async def test_channel_list_is_whole_catalog_sorted(hass, aioclient_mock):
    mock_ok(aioclient_mock)
    result = await hass.config_entries.flow.async_configure((await start(hass))["flow_id"], URLS)
    _, selector = field(result, CONF_CHANNELS)
    labels = [o["label"] for o in selector.config["options"]]
    assert labels == sorted(labels, key=str.casefold)
    assert {"Sky Uno +1", "Rai 1"} <= set(labels)


async def test_groups_add_channels_without_variants(hass, aioclient_mock):
    mock_ok(aioclient_mock)
    result = await hass.config_entries.flow.async_configure((await start(hass))["flow_id"], URLS)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_GROUPS: ["sky", "rai"], CONF_CHANNELS: ["canale5"]}
    )
    assert result["options"][CONF_CHANNELS] == ["canale5", "rai1", "rai2"]  # no skyunoplus1


async def test_one_source_disabled(hass, aioclient_mock):
    aioclient_mock.get(IPTV_URL, content=(FIXTURES / "iptv_sample.xml").read_bytes())
    result = await hass.config_entries.flow.async_configure(
        (await start(hass))["flow_id"], {CONF_IPTV_EPG_URL: IPTV_URL}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CHANNELS: ["rai2"]})
    assert result["options"][CONF_OPEN_EPG_URL] == ""
    called = {str(c[1]) for c in aioclient_mock.mock_calls}
    assert called == {IPTV_URL}  # the disabled source is never downloaded


async def test_no_sources(hass):
    result = await hass.config_entries.flow.async_configure((await start(hass))["flow_id"], {})
    assert result["errors"] == {"base": "no_sources"}


async def test_cannot_connect(hass, aioclient_mock):
    mock_down(aioclient_mock)
    result = await hass.config_entries.flow.async_configure((await start(hass))["flow_id"], URLS)
    assert result["step_id"] == "user" and result["errors"] == {"base": "cannot_connect"}


async def test_no_channels(hass, aioclient_mock):
    mock_ok(aioclient_mock)
    result = await hass.config_entries.flow.async_configure((await start(hass))["flow_id"], URLS)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "channels" and result["errors"] == {"base": "no_channels"}


async def test_single_instance(hass):
    MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN).add_to_hass(hass)
    result = await start(hass)
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"


@pytest.fixture
async def loaded_entry(hass, aioclient_mock):
    mock_ok(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="On Air",
        options={
            **URLS,
            CONF_CHANNELS: ["rai1", "ghost"],
            CONF_CHANNEL_NAMES: {"rai1": "Rai 1", "ghost": "Ghost TV"},
            CONF_TONIGHT_START: "20:00:00",
            CONF_TONIGHT_END: "00:00:00",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_and_unload(hass, loaded_entry):
    assert loaded_entry.state is ConfigEntryState.LOADED
    assert loaded_entry.runtime_data.data.channels["rai1"] == "Rai 1"
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_no_source_works(hass, aioclient_mock):
    mock_down(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, options={**URLS, CONF_CHANNELS: ["rai1"]})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_options_change_channels_and_keep_the_rest(hass, loaded_entry):
    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
    assert result["step_id"] == "init"
    assert suggested(result, CONF_CHANNELS) == ["rai1", "ghost"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            **URLS,
            CONF_CHANNELS: ["rai1", "canale5"],
            CONF_TONIGHT_START: "20:30:00",
            CONF_TONIGHT_END: "00:00:00",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    opts = loaded_entry.options
    assert opts[CONF_CHANNELS] == ["rai1", "canale5"]
    assert opts[CONF_CHANNEL_NAMES]["canale5"] == "Canale 5"
    assert opts[CONF_TONIGHT_START] == "20:30:00"
    assert (opts[CONF_OPEN_EPG_URL], opts[CONF_IPTV_EPG_URL]) == (OPEN_URL, IPTV_URL)


async def test_options_without_catalog_offer_current_channels(hass, loaded_entry, aioclient_mock):
    aioclient_mock.clear_requests()
    mock_down(aioclient_mock)
    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
    _, selector = field(result, CONF_CHANNELS)
    assert {o["value"]: o["label"] for o in selector.config["options"]} == {"rai1": "Rai 1", "ghost": "Ghost TV"}


async def test_options_errors(hass, loaded_entry):
    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
    base = {CONF_TONIGHT_START: "20:00:00", CONF_TONIGHT_END: "00:00:00"}
    r = await hass.config_entries.options.async_configure(result["flow_id"], {**base, CONF_CHANNELS: ["rai1"]})
    assert r["errors"] == {"base": "no_sources"}
    r = await hass.config_entries.options.async_configure(r["flow_id"], {**base, **URLS})
    assert r["errors"] == {"base": "no_channels"}


def _keys(d, prefix=""):
    out = set()
    for k, v in d.items():
        out.add(prefix + k)
        if isinstance(v, dict):
            out |= _keys(v, prefix + k + ".")
    return out


def test_translations_aligned():
    base = Path("custom_components/on_air")
    strings = json.loads((base / "strings.json").read_text())
    it = json.loads((base / "translations/it.json").read_text())
    en = json.loads((base / "translations/en.json").read_text())
    assert strings == it
    assert _keys(en) == _keys(it)
