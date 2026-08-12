"""Coordinator that polls the stove through the DPRemote cloud relay."""

from __future__ import annotations

from datetime import timedelta
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from . import polling, protocol as p, recorder
from .client import ClientError, DuepiClient
from .const import (
    CONF_DEVICE_CODE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_AUTO_RESET,
    CONF_IDLE_SCAN_INTERVAL,
    CONF_LOG_TO_FILE,
    CONF_OFF_GRACE_PERIOD,
    DEFAULT_AUTO_RESET,
    DEFAULT_IDLE_SCAN_INTERVAL,
    DEFAULT_LOG_TO_FILE,
    DEFAULT_OFF_GRACE_PERIOD,
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
        self._active_seconds = int(
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        self._idle_seconds = int(
            entry.options.get(CONF_IDLE_SCAN_INTERVAL, DEFAULT_IDLE_SCAN_INTERVAL)
        )
        self._off_grace_seconds = int(
            entry.options.get(CONF_OFF_GRACE_PERIOD, DEFAULT_OFF_GRACE_PERIOD)
        )
        # Monotonic timestamp of the last reading in which the stove was active;
        # None until we've seen it active (so an at-startup off state backs off
        # immediately instead of getting a false grace window).
        self._last_active_monotonic: float | None = None
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry.title}",
            # Start at the active interval so the first state is picked up promptly;
            # the interval then adapts to the burner status after each poll.
            update_interval=timedelta(seconds=self._active_seconds),
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

        self._apply_adaptive_interval(state.burner_status)
        return state

    def _apply_adaptive_interval(self, burner_status: str) -> None:
        """Slow polling while the stove is off, speed it up while it's on.

        A grace window after shut-off keeps the fast rate briefly so a quick
        off→on is caught almost immediately.
        """
        now = time.monotonic()
        if polling.is_stove_active(burner_status):
            self._last_active_monotonic = now
            seconds_since_active = 0.0
        elif self._last_active_monotonic is None:
            seconds_since_active = float("inf")
        else:
            seconds_since_active = now - self._last_active_monotonic

        seconds = polling.choose_interval_seconds(
            burner_status,
            self._active_seconds,
            self._idle_seconds,
            seconds_since_active,
            self._off_grace_seconds,
        )
        new_interval = timedelta(seconds=seconds)
        if new_interval != self.update_interval:
            _LOGGER.debug(
                "%s: burner '%s' -> polling every %ss",
                self.name,
                burner_status,
                seconds,
            )
            # Picked up by the coordinator when it schedules the next refresh.
            self.update_interval = new_interval
