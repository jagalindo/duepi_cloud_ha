"""The DPRemote (Duepi EVO cloud) integration.

Home Assistant imports are kept lazy (inside the setup functions and guarded by
``TYPE_CHECKING``) so the pure protocol/transport/client modules in this package
can be imported and unit-tested without a Home Assistant installation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

DOMAIN = "dpremote"


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Set up DPRemote from a config entry."""
    from homeassistant.const import Platform

    from .coordinator import DPRemoteCoordinator

    coordinator = DPRemoteCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(
        entry,
        [Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR],
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Unload a config entry."""
    from homeassistant.const import Platform

    unloaded = await hass.config_entries.async_unload_platforms(
        entry,
        [Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR],
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: "HomeAssistant", entry: "ConfigEntry") -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
