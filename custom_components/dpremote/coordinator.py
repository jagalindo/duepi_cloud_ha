"""Coordinator that polls the stove through the DPRemote cloud relay."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import protocol as p
from .client import ClientError, DuepiClient
from .const import (
    CONF_DEVICE_CODE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_AUTO_RESET,
    DEFAULT_AUTO_RESET,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SERVER,
    DOMAIN,
)
from .transport import CloudRelayTransport

_LOGGER = logging.getLogger(__name__)


def build_client(entry: ConfigEntry) -> DuepiClient:
    """Build a cloud-backed DuepiClient from a config entry."""
    data = entry.data
    options = entry.options

    device_code = data[CONF_DEVICE_CODE]
    server = data.get(CONF_HOST, DEFAULT_SERVER)
    port = data.get(CONF_PORT, DEFAULT_PORT)
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)
    min_temp = float(options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP))
    max_temp = float(options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP))

    def transport_factory() -> CloudRelayTransport:
        return CloudRelayTransport(
            device_code,
            username=username,
            password=password,
            host=server,
            port=port,
        )

    return DuepiClient(
        transport_factory,
        min_temp=min_temp,
        max_temp=max_temp,
    )


class DPRemoteCoordinator(DataUpdateCoordinator[p.StoveState]):
    """Central coordinator that owns a cloud DuepiClient."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry.title}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.entry = entry
        self.client = build_client(entry)
        self.auto_reset = bool(entry.options.get(CONF_AUTO_RESET, DEFAULT_AUTO_RESET))

    async def _async_update_data(self) -> p.StoveState:
        """Fetch the latest snapshot from the stove via the cloud relay."""
        try:
            state = await self.hass.async_add_executor_job(self.client.fetch_state)
            if self.auto_reset and state.error_code in p.AUTO_RESET_ERRORS:
                await self.hass.async_add_executor_job(self.client.remote_reset)
                state = await self.hass.async_add_executor_job(self.client.fetch_state)
            return state
        except ClientError as err:
            raise UpdateFailed(str(err)) from err
