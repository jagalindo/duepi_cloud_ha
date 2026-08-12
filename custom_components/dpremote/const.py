"""Constants for the DPRemote (Duepi EVO cloud) integration."""

from __future__ import annotations

DOMAIN = "dpremote"

# Config / options keys (host/port/username/password/name/scan_interval come
# from homeassistant.const).
CONF_DEVICE_CODE = "device_code"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_AUTO_RESET = "auto_reset"

DEFAULT_NAME = "DPRemote Stove"
DEFAULT_SERVER = "duepiwebserver.com"
DEFAULT_PORT = 3000
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MIN_TEMP = 16.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_AUTO_RESET = False

# Sensor / attribute keys.
ATTR_BURNER_STATUS = "burner_status"
ATTR_ERROR_CODE = "error_code"
ATTR_EXH_FAN_SPEED = "exh_fan_speed"
ATTR_FLU_GAS_TEMP = "flu_gas_temp"
ATTR_PELLET_SPEED = "pellet_speed"
ATTR_POWER_LEVEL = "power_level"
ATTR_PCB_TEMP = "pcb_temp"
ATTR_TOTAL_BURN_TIME = "total_burn_time"
ATTR_BURN_TIME_SINCE_RESET = "burn_time_since_reset"
ATTR_PRESSURE_SWITCH = "pressure_switch"


def entry_unique_id(device_code: str) -> str:
    """Build a stable config-entry unique ID from the module device code."""
    return f"dpremote:{device_code}"


def climate_unique_id(device_code: str) -> str:
    """Build a stable climate entity unique ID from the device code."""
    return f"{entry_unique_id(device_code)}:climate"
