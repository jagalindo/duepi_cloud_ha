"""Constants for the DPRemote (Duepi EVO cloud) integration."""

from __future__ import annotations

DOMAIN = "dpremote"

# Config / options keys (host/port/username/password/name/scan_interval come
# from homeassistant.const).
CONF_DEVICE_CODE = "device_code"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_AUTO_RESET = "auto_reset"
CONF_LOG_TO_FILE = "log_to_file"
CONF_IDLE_SCAN_INTERVAL = "idle_scan_interval"
CONF_OFF_GRACE_PERIOD = "off_grace_period"

DEFAULT_NAME = "DPRemote Stove"
# Defaults are only a starting hint: the address and port are per-account and
# must match what the MyDPremote app shows under DIRECCIÓN / PUERTA (they can
# include an instance prefix such as "1." and vary by port, e.g. 2000 or 3000).
DEFAULT_SERVER = "1.duepiwebserver1.com"
DEFAULT_PORT = 2000
DEFAULT_SCAN_INTERVAL = 60
# When the stove is fully off, poll this much less often (default 15 min). Kept
# non-zero so a remote/scheduled turn-on is still noticed within one idle cycle.
DEFAULT_IDLE_SCAN_INTERVAL = 900
# After the stove turns off, keep polling at the active interval for this long
# (default 15 min) before backing off to the idle interval, so a quick off→on
# is caught almost immediately. Set to 0 to back off as soon as it's off.
DEFAULT_OFF_GRACE_PERIOD = 900
DEFAULT_MIN_TEMP = 16.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_AUTO_RESET = False
# Append every successful poll to a CSV under <config>/dpremote/ for later
# analysis/optimization. On by default; disable in the integration options.
DEFAULT_LOG_TO_FILE = True
LOG_SUBDIR = "dpremote"

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
