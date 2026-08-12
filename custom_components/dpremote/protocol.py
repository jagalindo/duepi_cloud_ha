"""Pure Duepi EVO wire protocol codec.

This module contains only the framing/parsing logic for the Duepi EVO command
set. It has no I/O and no Home Assistant dependencies so it can be unit tested
in isolation and reused across transports (local TCP bridge or the DPRemote
cloud relay).

The command set and parsing are derived from the reverse-engineered local
integration ``aceindy/Duepi_EVO`` (GPL-3.0). The cloud relay tunnels these same
frames, so the codec is shared verbatim; only the transport differs.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Burner status flags (bitmask over the 8 hex digits of a status reply) ---
STATE_ACK = 0x00000020
STATE_OFF = 0x00000020
STATE_START = 0x01000000
STATE_ON = 0x02000000
STATE_CLEAN = 0x04000000
STATE_COOL = 0x08000000
STATE_ECO = 0x10000000

# --- Read commands (payload part, before framing) ---
GET_SETPOINT = "C6000"
GET_PRESSURE_SWITCH = "C0000"
GET_FLUGASTEMP = "D0000"
GET_TEMPERATURE = "D1000"
GET_POWERLEVEL = "D3000"
GET_PELLETSPEED = "D4000"
REMOTE_RESET = "D6000"
GET_STATUS = "D9000"
GET_ERRORSTATE = "DA000"
GET_PCBTEMP = "DF000"
GET_TOTAL_BURN_TIME = "ED000"
GET_BURN_TIME = "EE000"
GET_EXHFANSPEED = "EF000"
GET_INITCOMMAND = "DC000"

# --- Write commands (with placeholders substituted before framing) ---
SET_POWERLEVEL = "F00x0"  # single hex digit replaces "x"
SET_TEMPERATURE = "F2xx0"  # two hex digits replace "xx"

# --- Fan / power levels ---
FAN_MODES = ["Off", "Min", "Low", "Medium", "High", "Max"]
FAN_MODE_MAP = {"Off": 0, "Min": 1, "Low": 2, "Medium": 3, "High": 4, "Max": 5}
FAN_MODE_MAP_REV = {value: key for key, value in FAN_MODE_MAP.items()}

# --- Pressure switch payloads ---
PRESSURE_SWITCH_OK = 0x0100
PRESSURE_SWITCH_PRESSURE = 0x0300

# --- HVAC hints (plain strings; the HA layer maps these to HVACMode) ---
HVAC_OFF = "off"
HVAC_HEAT = "heat"

ERROR_CODE_MAP = {
    0: "All OK",
    1: "Ignition failure",
    2: "Defective suction",
    3: "Insufficient air intake",
    4: "Water temperature",
    5: "Out of pellets",
    6: "Defective pressure switch",
    7: "Unknown",
    8: "No current",
    9: "Exhaust motor failure",
    10: "Card surge",
    11: "Date expired",
    12: "Unknown",
    13: "Suction regulating sensor error",
    14: "Overheating",
}

AUTO_RESET_ERRORS = {"Out of pellets", "Ignition failure"}


class ProtocolError(Exception):
    """Raised when a response frame cannot be parsed or validated."""


@dataclass(slots=True)
class StoveState:
    """Normalized stove state, independent of transport and of Home Assistant."""

    burner_status: str
    error_code: str
    exh_fan_speed_rpm: int | None
    flu_gas_temp_c: int | None
    pellet_speed: int | None
    power_level: str
    pcb_temp_c: int | None
    total_burn_time_h: int | None
    burn_time_since_reset_h: int | None
    pressure_switch_active: bool | None
    current_temp_c: float | None
    target_temp_c: float | None
    hvac_mode: str
    heating: bool


def checksum(payload: str) -> int:
    """Return the 8-bit checksum of ``"R" + payload``."""
    formatted = "R" + payload
    return sum(ord(char) for char in formatted) & 0xFF


def build_command(payload: str) -> str:
    """Frame a command payload: ESC + "R" + payload + 2-hex checksum + "&"."""
    formatted = "R" + payload
    return "\x1b" + formatted + f"{checksum(payload):02X}" + "&"


def set_powerlevel_command(fan_mode: str) -> str:
    """Build the framed SET_POWERLEVEL command for a named fan mode."""
    if fan_mode not in FAN_MODE_MAP:
        raise ProtocolError(f"Unsupported fan mode: {fan_mode}")
    power_hex = hex(FAN_MODE_MAP[fan_mode])[2:3]
    return build_command(SET_POWERLEVEL.replace("x", power_hex))


def set_temperature_command(target_temperature: float) -> str:
    """Build the framed SET_TEMPERATURE command for a target temperature."""
    set_point_hex = f"{int(target_temperature):02X}"
    return build_command(SET_TEMPERATURE.replace("xx", set_point_hex))


def read_hex_field(response: str, digits: int) -> int:
    """Parse a hex field of ``digits`` length starting at offset 1 of a reply."""
    return int(response[1 : 1 + digits], 16)


def validate_frame(response: str) -> str:
    """Validate minimal response framing and return it unchanged."""
    if len(response) < 9:
        raise ProtocolError(f"Malformed response: {response!r}")
    return response


def is_ack(response: str) -> bool:
    """Return True if the ACK flag is set in a status/ack reply."""
    return bool(STATE_ACK & int(response[1:9], 16))


def decode_status(current_state: int) -> str:
    """Decode a burner status bitmask into a human-readable status."""
    if STATE_START & current_state:
        return "Ignition starting"
    if STATE_ON & current_state:
        return "Flame On"
    if STATE_CLEAN & current_state:
        return "Cleaning"
    if STATE_ECO & current_state:
        return "Eco idle"
    if STATE_COOL & current_state:
        return "Cooling down"
    if STATE_OFF & current_state:
        return "Off"
    return "Unknown state"


def hvac_from_status(status: str) -> tuple[str, bool]:
    """Return (hvac_mode, heating) for a burner status string."""
    if status == "Off":
        return HVAC_OFF, False
    if status == "Cooling down":
        return HVAC_HEAT, False
    return HVAC_HEAT, True


def decode_pressure_switch(response: str) -> bool | None:
    """Decode the pressure switch reply into active True/False, or None if odd."""
    pressure_state = read_hex_field(response, 4)
    if pressure_state == PRESSURE_SWITCH_OK:
        return False
    if pressure_state == PRESSURE_SWITCH_PRESSURE:
        return True
    return None


def error_text(code_decimal: int) -> str:
    """Map a decimal error code to text, falling back to the raw number."""
    return ERROR_CODE_MAP.get(code_decimal, str(code_decimal))
