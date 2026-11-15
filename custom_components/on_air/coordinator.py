"""Download the XMLTV guides and keep the merged guide for the selected channels."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, time, timedelta
from functools import partial
import logging
import xml.etree.ElementTree as ET
import zlib

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CHANNEL_NAMES,
    CONF_CHANNELS,
    CONF_IPTV_EPG_URL,
    CONF_OPEN_EPG_URL,
    DAY_ROLLOVER_HOUR,
    DOMAIN,
    KEEP_BEFORE,
    SOURCE_ORDER,
    UPDATE_INTERVAL,
)
from .merge import merge_guides
from .models import GuideData, SourceGuide, SourceStatus
from .xmltv import parse_xmltv

_LOGGER = logging.getLogger(__name__)

FETCH_TIMEOUT = aiohttp.ClientTimeout(total=120)
# Errors that mean "this source's file is unusable" (bad gzip, bad XML).
_PARSE_ERRORS = (ET.ParseError, OSError, EOFError, zlib.error, ValueError)


class SourceFetchError(Exception):
    """A guide source could not be downloaded or read."""


async def async_fetch_source(hass: HomeAssistant, url: str) -> bytes:
    """Download one guide file."""
    session = async_get_clientsession(hass)
    try:
        response = await session.get(url, timeout=FETCH_TIMEOUT)
        response.raise_for_status()
        return await response.read()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise SourceFetchError(type(err).__name__) from err


async def _async_load_guide(hass: HomeAssistant, source: str, url: str, **parse_kwargs) -> SourceGuide:
    data = await async_fetch_source(hass, url)
    try:
        return await hass.async_add_executor_job(
            partial(parse_xmltv, data, source=source, **parse_kwargs)
        )
    except _PARSE_ERRORS as err:
        raise SourceFetchError(type(err).__name__) from err


def source_urls(options: Mapping[str, object]) -> dict[str, str]:
    """Enabled sources (non-empty URL) in priority order."""
    urls = {
        "open_epg": str(options.get(CONF_OPEN_EPG_URL) or ""),
        "iptv_epg": str(options.get(CONF_IPTV_EPG_URL) or ""),
    }
    return {source: urls[source] for source in SOURCE_ORDER if urls.get(source)}


async def async_fetch_catalog(hass: HomeAssistant, urls: Mapping[str, str]) -> dict[str, str]:
    """Return channel key -> readable name from every reachable source.

    Raises SourceFetchError when no source can be read.
    """
    guides: list[SourceGuide] = []
    for source, url in urls.items():
        if not url:
            continue
        try:
            guides.append(await _async_load_guide(hass, source, url, channels_only=True))
        except SourceFetchError as err:
            _LOGGER.warning("Guide source %s unavailable for the channel list: %s", source, err)
    if not guides:
        raise SourceFetchError("no guide source reachable")
    names, _ = merge_guides(guides, SOURCE_ORDER)
    return names


class OnAirCoordinator(DataUpdateCoordinator[GuideData]):
    """Downloads the guides every UPDATE_INTERVAL and merges them."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._guides: dict[str, SourceGuide] = {}
        self._status: dict[str, SourceStatus] = {}

    async def _async_update_data(self) -> GuideData:
        options = self.config_entry.options
        urls = source_urls(options)
        selected: set[str] = set(options.get(CONF_CHANNELS, []))
        tz = dt_util.get_default_time_zone()
        now = dt_util.now()
        window = (
            now - KEEP_BEFORE,
            datetime.combine(now.date() + timedelta(days=1), time(DAY_ROLLOVER_HOUR), tzinfo=tz),
        )

        for source, url in urls.items():
            try:
                guide = await _async_load_guide(
                    self.hass,
                    source,
                    url,
                    keep=selected.__contains__,
                    window=window,
                    default_tz=tz,
                )
            except SourceFetchError as err:
                _LOGGER.warning("Guide source %s failed: %s", source, err)
                previous = self._status.get(source)
                self._status[source] = SourceStatus(
                    "error", previous.updated_at if previous else None
                )
            else:
                self._guides[source] = guide
                self._status[source] = SourceStatus("ok", now)

        guides = [self._guides[source] for source in urls if source in self._guides]
        if not guides:
            raise UpdateFailed("No guide data from any source")

        names, programmes = merge_guides(guides, SOURCE_ORDER)
        stored_names: Mapping[str, str] = options.get(CONF_CHANNEL_NAMES, {})
        statuses = {source: self._status[source] for source in urls}
        updated_at = max(s.updated_at for s in statuses.values() if s.updated_at)
        return GuideData(
            channels={k: names.get(k) or stored_names.get(k, k) for k in selected},
            programmes={k: programmes[k] for k in selected if k in programmes},
            sources=statuses,
            updated_at=updated_at,
        )
