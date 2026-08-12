"""Read-only sensors for DPRemote (Duepi EVO cloud)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import protocol as p
from .const import (
    ATTR_BURNER_STATUS,
    ATTR_BURN_TIME_SINCE_RESET,
    ATTR_ERROR_CODE,
    ATTR_EXH_FAN_SPEED,
    ATTR_FLU_GAS_TEMP,
    ATTR_PCB_TEMP,
    ATTR_PELLET_SPEED,
    ATTR_POWER_LEVEL,
    ATTR_TOTAL_BURN_TIME,
    CONF_DEVICE_CODE,
    DEFAULT_NAME,
    DOMAIN,
    entry_unique_id,
)
from .coordinator import DPRemoteCoordinator
from .device import build_device_info


@dataclass(frozen=True, kw_only=True)
class DPRemoteSensorDescription(SensorEntityDescription):
    """Description of one DPRemote sensor."""

    value_fn: Callable[[p.StoveState], Any]


SENSOR_DESCRIPTIONS: tuple[DPRemoteSensorDescription, ...] = (
    DPRemoteSensorDescription(
        key=ATTR_BURNER_STATUS,
        name="Burner Status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.burner_status,
    ),
    DPRemoteSensorDescription(
        key=ATTR_ERROR_CODE,
        name="Error Code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.error_code,
    ),
    DPRemoteSensorDescription(
        key=ATTR_EXH_FAN_SPEED,
        name="Exhaust Fan Speed",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.exh_fan_speed_rpm,
    ),
    DPRemoteSensorDescription(
        key=ATTR_FLU_GAS_TEMP,
        name="Flue Gas Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.flu_gas_temp_c,
    ),
    DPRemoteSensorDescription(
        key=ATTR_PELLET_SPEED,
        name="Pellet Speed",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.pellet_speed,
    ),
    DPRemoteSensorDescription(
        key=ATTR_POWER_LEVEL,
        name="Power Level",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.power_level,
    ),
    DPRemoteSensorDescription(
        key=ATTR_PCB_TEMP,
        name="PCB Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.pcb_temp_c,
    ),
    DPRemoteSensorDescription(
        key=ATTR_TOTAL_BURN_TIME,
        name="Total Burn Time",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="h",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.total_burn_time_h,
    ),
    DPRemoteSensorDescription(
        key=ATTR_BURN_TIME_SINCE_RESET,
        name="Burn Time Since Reset",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="h",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.burn_time_since_reset_h,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DPRemote sensors from a config entry."""
    coordinator: DPRemoteCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    unique_base = entry_unique_id(entry.data[CONF_DEVICE_CODE])

    async_add_entities(
        DPRemoteSensorEntity(coordinator, description, name, unique_base)
        for description in SENSOR_DESCRIPTIONS
    )


class DPRemoteSensorEntity(CoordinatorEntity[DPRemoteCoordinator], SensorEntity):
    """Coordinator-backed DPRemote sensor."""

    entity_description: DPRemoteSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DPRemoteCoordinator,
        description: DPRemoteSensorDescription,
        name: str,
        unique_base: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_name = name
        self._unique_base = unique_base
        self._attr_unique_id = f"{unique_base}:sensor:{description.key}"

    @property
    def native_value(self) -> Any:
        state = self.coordinator.data
        if state is None:
            return None
        return self.entity_description.value_fn(state)

    @property
    def device_info(self):
        return build_device_info(self._unique_base, self._device_name)
