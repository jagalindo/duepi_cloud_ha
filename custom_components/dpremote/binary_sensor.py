"""Binary sensors for DPRemote (Duepi EVO cloud)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import protocol as p
from .const import (
    ATTR_PRESSURE_SWITCH,
    CONF_DEVICE_CODE,
    DEFAULT_NAME,
    DOMAIN,
    entry_unique_id,
)
from .coordinator import DPRemoteCoordinator
from .device import build_device_info


@dataclass(frozen=True, kw_only=True)
class DPRemoteBinarySensorDescription(BinarySensorEntityDescription):
    """Description of one DPRemote binary sensor."""

    value_fn: Callable[[p.StoveState], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[DPRemoteBinarySensorDescription, ...] = (
    DPRemoteBinarySensorDescription(
        key=ATTR_PRESSURE_SWITCH,
        name="Pressure Switch",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.pressure_switch_active,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DPRemote binary sensors from a config entry."""
    coordinator: DPRemoteCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    unique_base = entry_unique_id(entry.data[CONF_DEVICE_CODE])

    async_add_entities(
        DPRemoteBinarySensorEntity(coordinator, description, name, unique_base)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class DPRemoteBinarySensorEntity(CoordinatorEntity[DPRemoteCoordinator], BinarySensorEntity):
    """Coordinator-backed DPRemote binary sensor."""

    entity_description: DPRemoteBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DPRemoteCoordinator,
        description: DPRemoteBinarySensorDescription,
        name: str,
        unique_base: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_name = name
        self._unique_base = unique_base
        self._attr_unique_id = f"{unique_base}:binary_sensor:{description.key}"

    @property
    def is_on(self) -> bool | None:
        state = self.coordinator.data
        if state is None:
            return None
        return self.entity_description.value_fn(state)

    @property
    def device_info(self):
        return build_device_info(self._unique_base, self._device_name)
