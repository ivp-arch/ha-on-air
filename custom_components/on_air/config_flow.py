"""Config and options flows for On Air."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .channels import DEFAULT_CHANNELS, GROUPS, channels_in_groups
from .const import (
    CONF_CHANNEL_NAMES,
    CONF_CHANNELS,
    CONF_GROUPS,
    CONF_IPTV_EPG_URL,
    CONF_OPEN_EPG_URL,
    CONF_TONIGHT_END,
    CONF_TONIGHT_START,
    DEFAULT_TONIGHT_END,
    DEFAULT_TONIGHT_START,
    DOMAIN,
    SOURCE_URLS,
)
from .coordinator import SourceFetchError, async_fetch_catalog, source_urls

_URL_KEYS = (CONF_OPEN_EPG_URL, CONF_IPTV_EPG_URL)
_URL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))
DEFAULT_URLS = {
    CONF_OPEN_EPG_URL: SOURCE_URLS["open_epg"],
    CONF_IPTV_EPG_URL: SOURCE_URLS["iptv_epg"],
}


def _urls_from(user_input: Mapping[str, Any]) -> dict[str, str]:
    """An empty or missing URL disables that source."""
    return {key: str(user_input.get(key) or "").strip() for key in _URL_KEYS}


def _chosen(catalog: Mapping[str, str], user_input: Mapping[str, Any]) -> list[str]:
    """Channels picked one by one, then the groups' channels, without duplicates."""
    picked = list(user_input.get(CONF_CHANNELS) or [])
    grouped = channels_in_groups(catalog, user_input.get(CONF_GROUPS) or [])
    return list(dict.fromkeys([*picked, *grouped]))


def _url_fields() -> dict[Any, Any]:
    return {vol.Optional(key): _URL_SELECTOR for key in _URL_KEYS}


def _channel_fields(catalog: Mapping[str, str]) -> dict[Any, Any]:
    options = [
        SelectOptionDict(value=key, label=name)
        for key, name in sorted(catalog.items(), key=lambda kv: kv[1].casefold())
    ]
    return {
        vol.Optional(CONF_GROUPS): SelectSelector(
            SelectSelectorConfig(options=list(GROUPS), multiple=True, translation_key="groups")
        ),
        vol.Optional(CONF_CHANNELS): SelectSelector(
            SelectSelectorConfig(options=options, multiple=True, mode=SelectSelectorMode.DROPDOWN)
        ),
    }


class OnAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up On Air: guide sources, then channels."""

    VERSION = 1

    def __init__(self) -> None:
        self._urls: dict[str, str] = {}
        self._catalog: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            urls = _urls_from(user_input)
            if not any(urls.values()):
                errors["base"] = "no_sources"
            else:
                try:
                    self._catalog = await async_fetch_catalog(self.hass, source_urls(urls))
                except SourceFetchError:
                    errors["base"] = "cannot_connect"
                else:
                    self._urls = urls
                    return await self.async_step_channels()
        schema = self.add_suggested_values_to_schema(
            vol.Schema(_url_fields()), user_input or DEFAULT_URLS
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_channels(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = _chosen(self._catalog, user_input)
            if chosen:
                return self.async_create_entry(
                    title="On Air",
                    data={},
                    options={
                        **self._urls,
                        CONF_CHANNELS: chosen,
                        CONF_CHANNEL_NAMES: {k: self._catalog.get(k, k) for k in chosen},
                        CONF_TONIGHT_START: DEFAULT_TONIGHT_START,
                        CONF_TONIGHT_END: DEFAULT_TONIGHT_END,
                    },
                )
            errors["base"] = "no_channels"
        preset = [key for key in DEFAULT_CHANNELS if key in self._catalog]
        schema = self.add_suggested_values_to_schema(
            vol.Schema(_channel_fields(self._catalog)), {CONF_CHANNELS: preset}
        )
        return self.async_show_form(step_id="channels", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return OnAirOptionsFlow()


class OnAirOptionsFlow(OptionsFlow):
    """Options as a menu: edit channels, start channels from scratch, sources and evening.

    Every step saves the complete options (HA replaces them, it does not merge).
    """

    def __init__(self) -> None:
        self._catalog: dict[str, str] | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init", menu_options=["channels", "reset_channels", "settings"]
        )

    async def _async_catalog(self) -> dict[str, str]:
        if self._catalog is None:
            options = self.config_entry.options
            names: dict[str, str] = dict(options.get(CONF_CHANNEL_NAMES, {}))
            current = {k: names.get(k, k) for k in options.get(CONF_CHANNELS, [])}
            try:
                fetched = await async_fetch_catalog(self.hass, source_urls(options))
            except SourceFetchError:
                fetched = {}
            # Keep the selected channels even when the sources do not list them now.
            self._catalog = {**current, **fetched}
        return self._catalog

    async def _async_channels_step(
        self, step_id: str, user_input: dict[str, Any] | None, preselected: list[str]
    ) -> ConfigFlowResult:
        catalog = await self._async_catalog()
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = _chosen(catalog, user_input)
            if chosen:
                return self.async_create_entry(
                    data={
                        **self.config_entry.options,
                        CONF_CHANNELS: chosen,
                        CONF_CHANNEL_NAMES: {k: catalog.get(k, k) for k in chosen},
                    }
                )
            errors["base"] = "no_channels"
        schema = self.add_suggested_values_to_schema(
            vol.Schema(_channel_fields(catalog)), user_input or {CONF_CHANNELS: preselected}
        )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    async def async_step_channels(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = list(self.config_entry.options.get(CONF_CHANNELS, []))
        return await self._async_channels_step("channels", user_input, current)

    async def async_step_reset_channels(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_channels_step("reset_channels", user_input, [])

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = self.config_entry.options
        errors: dict[str, str] = {}
        if user_input is not None:
            urls = _urls_from(user_input)
            if any(urls.values()):
                return self.async_create_entry(
                    data={
                        **options,
                        **urls,
                        CONF_TONIGHT_START: user_input.get(CONF_TONIGHT_START, DEFAULT_TONIGHT_START),
                        CONF_TONIGHT_END: user_input.get(CONF_TONIGHT_END, DEFAULT_TONIGHT_END),
                    }
                )
            errors["base"] = "no_sources"
        schema = vol.Schema(
            {
                **_url_fields(),
                vol.Required(CONF_TONIGHT_START): TimeSelector(),
                vol.Required(CONF_TONIGHT_END): TimeSelector(),
            }
        )
        current = {
            **{key: options.get(key, "") for key in _URL_KEYS},
            CONF_TONIGHT_START: options.get(CONF_TONIGHT_START, DEFAULT_TONIGHT_START),
            CONF_TONIGHT_END: options.get(CONF_TONIGHT_END, DEFAULT_TONIGHT_END),
        }
        return self.async_show_form(
            step_id="settings",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or current),
            errors=errors,
        )
