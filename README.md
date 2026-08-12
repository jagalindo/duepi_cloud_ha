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
| Home Assistant entities (climate / sensors / binary_sensor) | ✅ done |
| Config + options flow | ✅ done |
| **Cloud relay handshake** (`master:<code>#` → `duepiwebserver.com:3000`) | ✅ implemented from the MyDPremote APK, loopback‑tested |
| Live end‑to‑end against a real stove | ⏳ needs your validation |

> The cloud handshake is reverse‑engineered and **not yet verified against a live
> stove**. If your module uses the optional AES layer, or a different port, please
> open an issue with what you see.

## Installation (HACS)

1. HACS → Integrations → ⋮ → *Custom repositories* → add
   `https://github.com/jagalindo/duepi_cloud_ha` (category *Integration*).
2. Install **DPRemote (Duepi EVO cloud)**, restart Home Assistant.
3. *Settings → Devices & Services → Add Integration → DPRemote*.
4. Enter the **same values the MyDPremote app shows** on its device screen:
   - **Address** (DIRECCIÓN) — e.g. `1.duepiwebserver1.com`
   - **Port** (PUERTA) — e.g. `2000`
   - **Device code** (CÓDIGO DE DISPOSITIVO) — the unique code printed on the
     back of the EVO Remote WiFi module, e.g. `m4g0b8f7cg`

   The address and port are **per account/region** (the app pre‑fills them; they
   can carry an instance prefix like `1.` and use port `2000` or `3000`), so copy
   them exactly from your app rather than assuming the defaults.

## How the cloud connection works

Reverse‑engineered from the MyDPremote app (`com.DPremote`, a Qt/C++ app; the
logic is the `DeviceConnection` class in `libdpremote_arm64-v8a.so`). Duepi's
server is a **master/slave TCP relay** on `duepiwebserver.com:3000` (fallback IP
`62.141.46.29`):

1. The stove's WiFi module keeps an outbound `slave:` connection to the relay,
   identified by its unique **code**.
2. A client opens a TCP socket to the relay and, on connect, sends one line to
   select the device:

   ```
   master:<device_code>#
   ```

3. The relay then bridges bytes transparently, and the **same Duepi‑EVO command
   frames** flow in both directions — so all the local protocol logic is reused.

The app also ships an optional AES layer (`encryptionEnabled` / `encryptionKey`),
off on the standard path and not implemented here.

## Architecture

The Duepi‑EVO protocol is identical whether you reach the stove over a local
serial‑to‑TCP bridge or over the cloud relay; only the transport differs. The code
is layered so the proven command logic is shared and the cloud specifics are
isolated:

- **`protocol.py`** — pure codec: command framing (`ESC + "R" + payload +
  checksum + "&"`), response parsing, status/error maps. No I/O, no HA imports.
- **`client.py`** — sequences commands to read a full snapshot and to issue
  set‑temperature / power‑level / reset. Talks through a `Transport`.
- **`transport.py`** — `LocalTcpTransport` (LAN bridge) and `CloudRelayTransport`
  (`duepiwebserver.com:3000`, `master:<code>#` handshake).
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

See [`docs/PROTOCOL.md`](docs/PROTOCOL.md) for the full reverse‑engineering notes.

## Development

```bash
python -m pytest -q      # protocol/client/transport tests (no Home Assistant needed)
```

## AI disclaimer

This integration was built with substantial help from an AI assistant (Claude),
including the reverse‑engineering of the MyDPremote APK and most of the code. It
is provided **as‑is, without warranty of any kind**. Treat it as community,
best‑effort software:

- The cloud protocol was recovered by static analysis of a third‑party app, not
  from official documentation; details may be incomplete or wrong.
- It controls a **combustion appliance**. Do not rely on it for safety‑critical
  behaviour, and never leave a pellet stove operating unattended on the basis of
  remote control. Keep your manufacturer‑provided safety devices in place.
- Review the code yourself before use. Bug reports and PRs are welcome.

Not affiliated with, endorsed by, or supported by Duepi Group srl. “Duepi”,
“EVO”, and “MyDPremote” are trademarks of their respective owners.

## Credits

Command set and parsing derived from [`aceindy/Duepi_EVO`](https://github.com/aceindy/Duepi_EVO)
(GPL-3.0). This project is a derivative work and is therefore also licensed under
**GPL-3.0** (see `LICENSE`).
