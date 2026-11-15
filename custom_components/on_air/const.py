"""Constants for the On Air integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "on_air"
PLATFORMS: Final = [Platform.SENSOR]

# Free XMLTV guides for Italy (verified reachable from the user's PC on 2026-11-15).
SOURCE_URLS: Final[dict[str, str]] = {
    "open_epg": "https://www.open-epg.com/files/italy.xml.gz",
    "iptv_epg": "https://iptv-epg.org/files/epg-it.xml",
}
# Title priority when merging sources: the first one with data wins.
SOURCE_ORDER: Final = ("open_epg", "iptv_epg")

CONF_CHANNELS: Final = "channels"
CONF_CHANNEL_NAMES: Final = "channel_names"
CONF_GROUPS: Final = "groups"
CONF_OPEN_EPG_URL: Final = "open_epg_url"
CONF_IPTV_EPG_URL: Final = "iptv_epg_url"
CONF_TONIGHT_START: Final = "tonight_start"
CONF_TONIGHT_END: Final = "tonight_end"

DEFAULT_TONIGHT_START: Final = "20:00:00"
DEFAULT_TONIGHT_END: Final = "00:00:00"

UPDATE_INTERVAL: Final = timedelta(hours=12)
# Programmes kept in memory: from now - KEEP_BEFORE to tomorrow at DAY_ROLLOVER_HOUR.
KEEP_BEFORE: Final = timedelta(hours=6)
# Before this local hour, "tonight" still means the previous evening.
DAY_ROLLOVER_HOUR: Final = 6
# Home Assistant limit on the length of a state (MAX_LENGTH_STATE_STATE).
MAX_STATE_LEN: Final = 255
