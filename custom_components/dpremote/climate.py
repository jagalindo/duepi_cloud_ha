"""Climate support for DPRemote (Duepi EVO cloud) pellet stoves."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import protocol as p
from .client import ClientError
from .const import (
    CONF_DEVICE_CODE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DOMAIN,
    climate_unique_id,
    entry_unique_id,
)
from .coordinator import DPRemoteCoordinator
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)

SUPPORT_MODES = [HVACMode.HEAT, HVACMode.OFF]
SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)


def _hvac_mode(state: p.StoveState | None) -> HVACMode:
    """Map a StoveState hvac hint to an HVACMode."""
    if state is None or state.hvac_mode == p.HVAC_OFF:
        return HVACMode.OFF
    return HVACMode.HEAT


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate entity from a config entry."""
    coordinator: DPRemoteCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_code = entry.data[CONF_DEVICE_CODE]
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    min_temp = float(entry.options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP))
    max_temp = float(entry.options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP))

    async_add_entities(
        [
            DPRemoteClimateEntity(
                coordinator=coordinator,
                name=name,
                unique_base=entry_unique_id(device_code),
                unique_id=climate_unique_id(device_code),
                min_temp=min_temp,
                max_temp=max_temp,
            )
        ]
    )


class DPRemoteClimateEntity(CoordinatorEntity[DPRemoteCoordinator], ClimateEntity):
    """DPRemote climate entity backed by a DataUpdateCoordinator."""

    _attr_supported_features = SUPPORT_FLAGS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = SUPPORT_MODES
    _attr_fan_modes = p.FAN_MODES
    _attr_has_entity_name = True
    _attr_name = None  # entity takes the device name

    def __init__(
        self,
        coordinator: DPRemoteCoordinator,
        name: str,
        unique_base: str,
        unique_id: str,
        min_temp: float,
        max_temp: float,
    ) -> None:
        super().__init__(coordinator)
        self._device_name = name
        self._unique_base = unique_base
        self._attr_unique_id = unique_id
        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp
        self._last_target_temperature: float | None = None

    @property
    def device_info(self):
        """Return the parent stove device information."""
        return build_device_info(self._unique_base, self._device_name)

    @property
    def _state(self) -> p.StoveState | None:
        return self.coordinator.data

    @property
    def current_temperature(self) -> float | None:
        state = self._state
        return state.current_temp_c if state else None

    @property
    def target_temperature(self) -> float | None:
        state = self._state
        if state and state.target_temp_c is not None:
            return state.target_temp_c
        return self._last_target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        return _hvac_mode(self._state)

    @property
    def hvac_action(self) -> HVACAction:
        state = self._state
        if state is None:
            return HVACAction.OFF
        if state.burner_status in {"Eco idle", "Cooling down"}:
            return HVACAction.IDLE
        if state.heating:
            return HVACAction.HEATING
        if _hvac_mode(state) == HVACMode.HEAT:
            return HVACAction.IDLE
        return HVACAction.OFF

    @property
    def fan_mode(self) -> str:
        state = self._state
        return state.power_level if state else p.FAN_MODES[0]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan/power level and refresh."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_fan_mode, fan_mode
            )
        except ClientError as err:
            _LOGGER.error("Unable to set fan mode to %s (%s)", fan_mode, err)
            return
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature and refresh."""
        target = kwargs.get(ATTR_TEMPERATURE)
        if target is None:
            return
        target = float(target)
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_temperature, target
            )
        except ClientError as err:
            _LOGGER.error("Unable to set target temp to %s (%s)", target, err)
            return
        self._last_target_temperature = target
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode and refresh."""
        if hvac_mode not in SUPPORT_MODES:
            _LOGGER.error("Unsupported HVAC mode %s", hvac_mode)
            return
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_hvac_mode, hvac_mode.value
            )
        except ClientError as err:
            _LOGGER.error("Unable to set hvac mode to %s (%s)", hvac_mode, err)
            return
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)
