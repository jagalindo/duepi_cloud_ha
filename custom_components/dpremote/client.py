"""Transport-agnostic Duepi EVO client.

Sequences the protocol commands to read a full stove snapshot and to issue
control commands. It talks through a :class:`~.transport.Transport`, so the same
logic drives the local TCP bridge and the DPRemote cloud relay.
"""

from __future__ import annotations

import logging

from . import protocol as p
from .transport import Transport, TransportError, TransportTimeout

_LOGGER = logging.getLogger(__name__)


class ClientError(Exception):
    """Base client error."""


class DuepiClient:
    """Reads and controls a Duepi EVO stove over a supplied transport factory."""

    def __init__(
        self,
        transport_factory,
        *,
        min_temp: float,
        max_temp: float,
        init_command: bool = False,
    ) -> None:
        # transport_factory() must return a fresh, unconnected Transport.
        self._make_transport = transport_factory
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.init_command = init_command

    # -- helpers ----------------------------------------------------------

    def _send_init_if_needed(self, transport: Transport) -> None:
        if not self.init_command:
            return
        transport.send(p.build_command(p.GET_INITCOMMAND))
        consumed = transport.drain_optional()
        if consumed:
            _LOGGER.debug("init_command response consumed: %s", consumed)

    def _request(self, transport: Transport, payload: str) -> str:
        transport.send(p.build_command(payload))
        return p.validate_frame(transport.recv())

    def _request_ack(self, transport: Transport, framed_command: str) -> None:
        transport.send(framed_command)
        response = p.validate_frame(transport.recv())
        if not p.is_ack(response):
            raise ClientError(f"No ACK for command, response={response!r}")

    def _optional(self, transport: Transport, payload: str, parser, description: str):
        try:
            response = self._request(transport, payload)
            return parser(response)
        except (p.ProtocolError, TransportError, ValueError) as err:
            _LOGGER.debug("Optional %s read failed: %s", description, err)
            return None

    # -- public API -------------------------------------------------------

    def fetch_state(self) -> p.StoveState:
        """Fetch and parse a full stove snapshot."""
        try:
            with self._make_transport() as transport:
                self._send_init_if_needed(transport)

                status_response = self._request(transport, p.GET_STATUS)
                burner_state = int(status_response[1:9], 16)
                burner_status = p.decode_status(burner_state)

                if burner_status == "Off":
                    power_code = p.FAN_MODE_MAP["Off"]
                else:
                    power_response = self._request(transport, p.GET_POWERLEVEL)
                    power_code = p.read_hex_field(power_response, 4)
                power_level = p.FAN_MODE_MAP_REV.get(power_code)
                if power_level is None:
                    _LOGGER.warning("Unknown fan mode value %s, falling back to Off", power_code)
                    power_level = "Off"

                ambient = self._request(transport, p.GET_TEMPERATURE)
                current_temp = p.read_hex_field(ambient, 4) / 10.0

                pellet = self._request(transport, p.GET_PELLETSPEED)
                pellet_speed = p.read_hex_field(pellet, 4)

                flugas = self._request(transport, p.GET_FLUGASTEMP)
                flu_gas_temp = p.read_hex_field(flugas, 4)

                exhaust = self._request(transport, p.GET_EXHFANSPEED)
                exh_fan_speed = p.read_hex_field(exhaust, 4) * 10

                error = self._request(transport, p.GET_ERRORSTATE)
                error_code = p.error_text(p.read_hex_field(error, 4))

                setpoint = self._request(transport, p.GET_SETPOINT)
                setpoint_raw = p.read_hex_field(setpoint, 4)
                target_temp = None
                if setpoint_raw != 0 and self.min_temp <= setpoint_raw <= self.max_temp:
                    target_temp = float(setpoint_raw)

                pcb_temp = self._optional(
                    transport, p.GET_PCBTEMP,
                    lambda r: p.read_hex_field(r, 4), "PCB temperature",
                )
                total_burn = self._optional(
                    transport, p.GET_TOTAL_BURN_TIME,
                    lambda r: p.read_hex_field(r, 6), "total burn time",
                )
                burn_since_reset = self._optional(
                    transport, p.GET_BURN_TIME,
                    lambda r: p.read_hex_field(r, 6), "burn time since reset",
                )
                pressure_active = self._optional(
                    transport, p.GET_PRESSURE_SWITCH,
                    p.decode_pressure_switch, "pressure switch",
                )

                hvac_mode, heating = p.hvac_from_status(burner_status)

                return p.StoveState(
                    burner_status=burner_status,
                    error_code=error_code,
                    exh_fan_speed_rpm=exh_fan_speed,
                    flu_gas_temp_c=flu_gas_temp,
                    pellet_speed=pellet_speed,
                    power_level=power_level,
                    pcb_temp_c=pcb_temp,
                    total_burn_time_h=total_burn,
                    burn_time_since_reset_h=burn_since_reset,
                    pressure_switch_active=pressure_active,
                    current_temp_c=current_temp,
                    target_temp_c=target_temp,
                    hvac_mode=hvac_mode,
                    heating=heating,
                )
        except TransportTimeout as err:
            raise ClientError(f"Timeout polling stove: {err}") from err
        except ValueError as err:
            raise ClientError(f"Invalid numeric payload: {err}") from err

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set the stove fan/power level by name."""
        command = p.set_powerlevel_command(fan_mode)
        with self._make_transport() as transport:
            self._send_init_if_needed(transport)
            self._request_ack(transport, command)

    def set_temperature(self, target_temperature: float) -> None:
        """Set the target temperature."""
        command = p.set_temperature_command(target_temperature)
        with self._make_transport() as transport:
            self._send_init_if_needed(transport)
            self._request_ack(transport, command)

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Map an HVAC mode to a Duepi power level."""
        if hvac_mode == p.HVAC_OFF:
            self.set_fan_mode("Off")
        elif hvac_mode == p.HVAC_HEAT:
            self.set_fan_mode("Min")
        else:
            raise ClientError(f"Unsupported HVAC mode: {hvac_mode}")

    def remote_reset(self) -> None:
        """Send the remote reset command."""
        command = p.build_command(p.REMOTE_RESET)
        with self._make_transport() as transport:
            self._send_init_if_needed(transport)
            self._request_ack(transport, command)
