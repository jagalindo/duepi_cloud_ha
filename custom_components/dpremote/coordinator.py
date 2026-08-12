"""Coordinator that polls the stove through the DPRemote cloud relay."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from . import protocol as p, recorder
from .client import ClientError, DuepiClient
from .const import (
    CONF_DEVICE_CODE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_AUTO_RESET,
    CONF_LOG_TO_FILE,
    DEFAULT_AUTO_RESET,
    DEFAULT_LOG_TO_FILE,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SERVER,
    DOMAIN,
    LOG_SUBDIR,
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
    min_temp = float(options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP))
    max_temp = float(options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP))

    def transport_factory() -> CloudRelayTransport:
        return CloudRelayTransport(device_code, host=server, port=port)

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

        self._log_path: str | None = None
        if bool(entry.options.get(CONF_LOG_TO_FILE, DEFAULT_LOG_TO_FILE)):
            filename = f"{slugify(entry.title) or entry.entry_id}.csv"
            self._log_path = hass.config.path(LOG_SUBDIR, filename)

    async def _async_update_data(self) -> p.StoveState:
        """Fetch the latest snapshot from the stove via the cloud relay."""
        try:
            state = await self.hass.async_add_executor_job(self.client.fetch_state)
            if self.auto_reset and state.error_code in p.AUTO_RESET_ERRORS:
                await self.hass.async_add_executor_job(self.client.remote_reset)
                state = await self.hass.async_add_executor_job(self.client.fetch_state)
        except ClientError as err:
            raise UpdateFailed(str(err)) from err

        if self._log_path is not None:
            await self.hass.async_add_executor_job(
                recorder.append_snapshot, self._log_path, state
            )
        return state
