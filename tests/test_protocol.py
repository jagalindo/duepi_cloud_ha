"""Unit tests for the pure Duepi EVO protocol codec."""

import pytest

from dpremote import protocol as p


def test_checksum_and_frame_status():
    # "RD9000" -> sum of ords & 0xFF. Frame = ESC + RD9000 + checksum + &.
    frame = p.build_command(p.GET_STATUS)
    assert frame.startswith("\x1b")
    assert frame.endswith("&")
    assert frame[1:7] == "RD9000"
    expected = sum(ord(c) for c in "RD9000") & 0xFF
    assert frame[7:9] == f"{expected:02X}"


def test_checksum_known_vector():
    assert p.checksum(p.GET_STATUS) == (sum(ord(c) for c in "RD9000") & 0xFF)


def test_set_temperature_command_encodes_hex():
    frame = p.set_temperature_command(21)
    # 21 -> 0x15 -> "15" substituted into F2xx0 payload.
    assert frame[1:7] == "RF2150"


def test_set_powerlevel_command_encodes_level():
    frame = p.set_powerlevel_command("Medium")  # level 3
    assert frame[1:7] == "RF0030"


def test_set_powerlevel_rejects_unknown_mode():
    with pytest.raises(p.ProtocolError):
        p.set_powerlevel_command("Turbo")


def test_read_hex_field():
    assert p.read_hex_field("X00FA0000", 4) == 0x00FA


def test_validate_frame_rejects_short():
    with pytest.raises(p.ProtocolError):
        p.validate_frame("short")


def test_is_ack():
    ack = f"X{p.STATE_ACK:08X}"
    assert p.is_ack(ack) is True
    assert p.is_ack("X00000000") is False


@pytest.mark.parametrize(
    "flag,expected",
    [
        (p.STATE_START, "Ignition starting"),
        (p.STATE_ON, "Flame On"),
        (p.STATE_CLEAN, "Cleaning"),
        (p.STATE_ECO, "Eco idle"),
        (p.STATE_COOL, "Cooling down"),
        (p.STATE_OFF, "Off"),
        (0, "Unknown state"),
    ],
)
def test_decode_status(flag, expected):
    assert p.decode_status(flag) == expected


def test_hvac_from_status():
    assert p.hvac_from_status("Off") == (p.HVAC_OFF, False)
    assert p.hvac_from_status("Cooling down") == (p.HVAC_HEAT, False)
    assert p.hvac_from_status("Flame On") == (p.HVAC_HEAT, True)


def test_decode_pressure_switch():
    assert p.decode_pressure_switch(f"X{p.PRESSURE_SWITCH_OK:04X}") is False
    assert p.decode_pressure_switch(f"X{p.PRESSURE_SWITCH_PRESSURE:04X}") is True
    assert p.decode_pressure_switch("X0000") is None


def test_error_text():
    assert p.error_text(5) == "Out of pellets"
    assert p.error_text(0) == "All OK"
    assert p.error_text(99) == "99"
