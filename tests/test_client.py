"""Tests for the transport-agnostic client using a scripted fake transport."""

import pytest

from dpremote import protocol as p
from dpremote.client import ClientError, DuepiClient
from dpremote.transport import Transport


def _payload_of(frame: str) -> str:
    """Extract the command payload from a framed command."""
    # frame = ESC + "R" + payload + 2-hex checksum + "&"
    return frame[2:-3]


class FakeTransport(Transport):
    """A transport that answers each command from a payload->response map."""

    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.sent: list[str] = []
        self.connected = False
        self.closed = False

    def connect(self) -> None:
        self.connected = True

    def send(self, frame: str) -> None:
        self.sent.append(frame)
        self._last_payload = _payload_of(frame)

    def recv(self, size: int = 10) -> str:
        return self.responses[self._last_payload]

    def close(self) -> None:
        self.closed = True


def _flame_on_responses() -> dict[str, str]:
    return {
        p.GET_STATUS: f"X{p.STATE_ON:08X}&",       # Flame On
        p.GET_POWERLEVEL: "X0003xxxx&",            # Medium (3)
        p.GET_TEMPERATURE: "X00D2xxxx&",           # 210 -> 21.0 C
        p.GET_PELLETSPEED: "X0005xxxx&",           # 5
        p.GET_FLUGASTEMP: "X0078xxxx&",            # 120 C
        p.GET_EXHFANSPEED: "X00A0xxxx&",           # 160 * 10 = 1600 rpm
        p.GET_ERRORSTATE: "X0000xxxx&",            # All OK
        p.GET_SETPOINT: "X0015xxxx&",              # 21
        p.GET_PCBTEMP: "X0028xxxx&",               # 40
        p.GET_TOTAL_BURN_TIME: "X000123xxx&",      # 0x000123
        p.GET_BURN_TIME: "X000045xxx&",            # 0x000045
        p.GET_PRESSURE_SWITCH: f"X{p.PRESSURE_SWITCH_OK:04X}xxx&",
    }


def _client(transport):
    return DuepiClient(lambda: transport, min_temp=16.0, max_temp=30.0)


def test_fetch_state_flame_on():
    t = FakeTransport(_flame_on_responses())
    state = _client(t).fetch_state()

    assert state.burner_status == "Flame On"
    assert state.power_level == "Medium"
    assert state.current_temp_c == 21.0
    assert state.pellet_speed == 5
    assert state.flu_gas_temp_c == 120
    assert state.exh_fan_speed_rpm == 1600
    assert state.error_code == "All OK"
    assert state.target_temp_c == 21.0
    assert state.pcb_temp_c == 40
    assert state.total_burn_time_h == 0x000123
    assert state.burn_time_since_reset_h == 0x000045
    assert state.pressure_switch_active is False
    assert state.hvac_mode == p.HVAC_HEAT
    assert state.heating is True
    assert t.closed is True


def test_fetch_state_off_skips_powerlevel_query():
    responses = _flame_on_responses()
    responses[p.GET_STATUS] = f"X{p.STATE_OFF:08X}&"
    t = FakeTransport(responses)
    state = _client(t).fetch_state()

    assert state.burner_status == "Off"
    assert state.power_level == "Off"
    assert state.hvac_mode == p.HVAC_OFF
    assert state.heating is False
    # GET_POWERLEVEL must NOT have been queried when the stove is Off.
    payloads = [_payload_of(f) for f in t.sent]
    assert p.GET_POWERLEVEL not in payloads


def test_fetch_state_optional_read_failure_is_tolerated():
    responses = _flame_on_responses()
    responses[p.GET_PCBTEMP] = "bad"  # too short -> ProtocolError, tolerated
    t = FakeTransport(responses)
    state = _client(t).fetch_state()
    assert state.pcb_temp_c is None
    # Required fields still parsed.
    assert state.current_temp_c == 21.0


def test_setpoint_out_of_range_is_none():
    responses = _flame_on_responses()
    responses[p.GET_SETPOINT] = "X00FFxxxx&"  # 255, outside 16..30
    t = FakeTransport(responses)
    state = _client(t).fetch_state()
    assert state.target_temp_c is None


def test_set_temperature_sends_ack_command():
    ack = f"X{p.STATE_ACK:08X}&"
    t = FakeTransport({"F2150": ack})  # 21 -> 0x15
    _client(t).set_temperature(21)
    assert t.sent[0] == p.set_temperature_command(21)
    assert t.closed is True


def test_set_fan_mode_ack():
    ack = f"X{p.STATE_ACK:08X}&"
    t = FakeTransport({"F0030": ack})  # Medium -> 3
    _client(t).set_fan_mode("Medium")
    assert t.sent[0] == p.set_powerlevel_command("Medium")


def test_set_temperature_no_ack_raises():
    t = FakeTransport({"F2150": "X00000000&"})  # ACK bit clear
    with pytest.raises(ClientError):
        _client(t).set_temperature(21)


def test_set_hvac_mode_maps_to_fan():
    ack = f"X{p.STATE_ACK:08X}&"
    t_off = FakeTransport({"F0000": ack})  # Off -> 0
    _client(t_off).set_hvac_mode(p.HVAC_OFF)
    assert t_off.sent[0] == p.set_powerlevel_command("Off")

    t_heat = FakeTransport({"F0010": ack})  # Min -> 1
    _client(t_heat).set_hvac_mode(p.HVAC_HEAT)
    assert t_heat.sent[0] == p.set_powerlevel_command("Min")


def test_remote_reset_ack():
    ack = f"X{p.STATE_ACK:08X}&"
    t = FakeTransport({p.REMOTE_RESET: ack})
    _client(t).remote_reset()
    assert t.sent[0] == p.build_command(p.REMOTE_RESET)
