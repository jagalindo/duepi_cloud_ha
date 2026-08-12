"""Config and options flow for DPRemote (Duepi EVO cloud)."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback

from .client import ClientError, DuepiClient
from .const import (
    CONF_AUTO_RESET,
    CONF_DEVICE_CODE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    DEFAULT_AUTO_RESET,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SERVER,
    DOMAIN,
    entry_unique_id,
)
from .transport import CloudRelayTransport, TransportError

_LOGGER = logging.getLogger(__name__)


def _make_probe_client(user_input: dict[str, Any]) -> DuepiClient:
    """Build a throwaway client to validate the entered settings."""
    device_code = user_input[CONF_DEVICE_CODE]
    server = user_input.get(CONF_HOST, DEFAULT_SERVER)
    port = user_input.get(CONF_PORT, DEFAULT_PORT)

    def factory() -> CloudRelayTransport:
        return CloudRelayTransport(device_code, host=server, port=port)

    return DuepiClient(factory, min_temp=DEFAULT_MIN_TEMP, max_temp=DEFAULT_MAX_TEMP)


class DPRemoteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DPRemote."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return DPRemoteOptionsFlow(config_entry)

    async def _async_validate(self, user_input: dict[str, Any]) -> str | None:
        """Return an error key, or None if the settings validate."""
        client = _make_probe_client(user_input)
        try:
            await self.hass.async_add_executor_job(client.fetch_state)
            return None
        except (ClientError, TransportError):
            return "cannot_connect"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        defaults = {
            CONF_NAME: DEFAULT_NAME,
            CONF_HOST: DEFAULT_SERVER,
            CONF_PORT: DEFAULT_PORT,
        }

        if user_input is not None:
            device_code = user_input[CONF_DEVICE_CODE]
            await self.async_set_unique_id(entry_unique_id(device_code))
            self._abort_if_unique_id_configured()

            error = await self._async_validate(user_input)
            if error is None:
                data = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_DEVICE_CODE: device_code,
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
                options = {
                    CONF_MIN_TEMP: DEFAULT_MIN_TEMP,
                    CONF_MAX_TEMP: DEFAULT_MAX_TEMP,
                    CONF_AUTO_RESET: DEFAULT_AUTO_RESET,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                }
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=data, options=options
                )
            errors["base"] = error
            defaults.update(user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=defaults[CONF_NAME]): str,
                vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=defaults[CONF_PORT]): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required(CONF_DEVICE_CODE, default=defaults.get(CONF_DEVICE_CODE, "")): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class DPRemoteOptionsFlow(config_entries.OptionsFlow):
    """Handle DPRemote options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self._config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MIN_TEMP, default=opts.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)
                ): vol.Coerce(float),
                vol.Required(
                    CONF_MAX_TEMP, default=opts.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)
                ): vol.Coerce(float),
                vol.Required(
                    CONF_AUTO_RESET, default=opts.get(CONF_AUTO_RESET, DEFAULT_AUTO_RESET)
                ): bool,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=15)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
