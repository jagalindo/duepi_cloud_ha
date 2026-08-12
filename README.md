# DPRemote — Home Assistant integration for Duepi EVO pellet stoves (cloud)

Control a Duepi‑EVO based pellet stove/boiler from Home Assistant the way the
**MyDPremote** phone app does in *remote* mode — through Duepi's cloud relay —
so it works even when you're away and the stove's WiFi module only talks to the
cloud (local ports closed).

This is the cloud counterpart to the excellent local‑only integration
[`aceindy/Duepi_EVO`](https://github.com/aceindy/Duepi_EVO), whose reverse‑engineered
Duepi‑EVO command set this project reuses.

## Status

| Piece | State |
|---|---|
| Duepi‑EVO wire protocol codec (`protocol.py`) | ✅ done, unit‑tested |
| Transport‑agnostic client (`client.py`) | ✅ done, unit‑tested |
| Local TCP transport (`transport.py`) | ✅ done, loopback‑tested |
| Home Assistant entities (climate/sensors/binary_sensor) | ✅ done (syntax‑checked) |
| Config + options flow | ✅ done (syntax‑checked) |
| Cloud relay transport handshake | ⛔ blocked — needs the complete MyDPremote APK (or a packet capture) to pin down the exact login/handshake to `duepiwebserver1.com:3000` |
| Live end‑to‑end against a real stove | ⛔ blocked on the handshake |

## Architecture

The Duepi‑EVO protocol is the same whether you reach the stove over a local
serial‑to‑TCP bridge or over Duepi's cloud relay; only the transport differs. The
code is layered so the proven command logic is shared and the cloud specifics are
isolated:

- **`protocol.py`** — pure codec: command framing (`ESC + "R" + payload +
  checksum + "&"`), response parsing, status/error maps. No I/O, no HA imports.
- **`client.py`** — sequences commands to read a full snapshot and to issue
  set‑temperature / power‑level / reset. Talks through a `Transport`.
- **`transport.py`** — `LocalTcpTransport` (LAN bridge) and
  `CloudRelayTransport` (`duepiwebserver1.com:3000`). The cloud handshake is the
  only unknown; `connect()` raises `NotImplementedError` until it's implemented.
- **`__init__.py` / `coordinator.py` / `climate.py` / `sensor.py` /
  `binary_sensor.py` / `config_flow.py`** — the Home Assistant layer.

## Protocol reference (Duepi EVO)

Frame: `\x1b` + `R` + `<payload>` + `<2‑hex checksum>` + `&`, where the checksum
is `sum(ord(c) for c in "R"+payload) & 0xFF`.

| Command | Payload | Meaning |
|---|---|---|
| GET_STATUS | `D9000` | burner status bitmask |
| GET_POWERLEVEL | `D3000` | fan/power level |
| GET_TEMPERATURE | `D1000` | ambient temp (÷10 °C) |
| GET_SETPOINT | `C6000` | target temp |
| GET_FLUGASTEMP | `D0000` | flue‑gas temp |
| GET_EXHFANSPEED | `EF000` | exhaust fan (×10 rpm) |
| GET_PELLETSPEED | `D4000` | auger/pellet speed |
| GET_ERRORSTATE | `DA000` | fault code |
| GET_PRESSURE_SWITCH | `C0000` | pressure switch |
| SET_TEMPERATURE | `F2xx0` | set target (`xx` = hex °C) |
| SET_POWERLEVEL | `F00x0` | set fan level (`x` = 0..5) |
| REMOTE_RESET | `D6000` | clear fault / reset |

## Development

```bash
python -m pytest -q      # runs the protocol/client/transport tests (no HA needed)
```

## Credits

Command set and parsing derived from [`aceindy/Duepi_EVO`](https://github.com/aceindy/Duepi_EVO)
(GPL-3.0). This project is a derivative work and is therefore also licensed under
**GPL-3.0** (see `LICENSE`).
