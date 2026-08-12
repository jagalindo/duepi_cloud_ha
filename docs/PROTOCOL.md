# DPRemote cloud protocol — reverse‑engineering notes

Source: `MyDPremote` Android app, package `com.DPremote`, version 3.2.2
(APKPure build). It is a **Qt 6 / C++** app; the connection logic is compiled
into `lib/arm64-v8a/libdpremote_arm64-v8a.so`. These notes were recovered by
static analysis (symbol table + targeted ARM64 disassembly with Capstone). They
are **not** from official documentation and may be incomplete.

## Relevant classes

- **`Device`** (QML type) — one stove. Properties: `address`, `port`, `code`,
  `id`, `name`, `localNetwork` (bool), `extendedProtocol` (bool).
- **`DeviceConnection`** — drives a `QTcpSocket`. Key methods:
  `connectDevice(Device*, bool)`, `onSocketConnected()`, `onSocketReadyRead()`,
  `onResponseReceived(bool, QString, QString)`, `sendCommand(QString)`,
  `sendNextCommand()`, `getCRC(QString)`, `checkCRC(QString)`,
  `switchOnDevice()`, `switchOffDevice()`, `changeTemperatureToSet(int)`,
  `changePowerToSet(int)`, `setEncryptionEnabled(bool)`.
- **`DeviceState`** — parsed telemetry: `environmentTemperature`,
  `boardTemperature`, `fanSpeed`, `cochleaSpeed` (auger), `errorCode`,
  `firmwareRelease`, `ciclePhase`, `cicleTime`, `boardType`, `day`, …
- **`TM_Util::QAESEncryption`** — optional AES (see below).

## Transport

- Plain **`QTcpSocket`** (not WebSocket; TLS backends exist but the device
  connection is a raw socket).
- Cloud server host literal: **`duepiwebserver.com`**, fallback IP
  **`62.141.46.29`** (both found in `connectDevice`).
- Port **3000** (`0xbb8`, referenced in `DeviceConnection::init`).

## Handshake (cloud / remote mode)

In `DeviceConnection::onSocketConnected()`, guarded by a "not local network"
flag, the app builds and sends a single line:

```
master:<device_code>#
```

Disassembly (abridged), `libdpremote_arm64-v8a.so`:

```
adrp/add x1, 'master:'        ; 7-char literal
QString::fromUtf8(len=7)      ; -> "master:"
append(<device code QString>) ; -> "master:<code>"
append('#', len=1)            ; -> "master:<code>#"
... log "Richiesta connessione a dispositivo remoto:" ...
QTcpSocket write               ; sent to the relay
```

Interpretation: the relay is a **master/slave bridge keyed by the module code**.
The WiFi module holds a `slave:` connection to the server; the app connects as
`master:` for the same code, and the server splices the two sockets. The relay
sends no dedicated ack line — it just begins bridging, after which the normal
Duepi‑EVO command frames flow in both directions.

`onResponseReceived` / `failedForRemoteDeviceNotRespond` indicate the app then
waits for the module to answer; if the relay cannot reach the module it flags a
"remote device not responding" condition.

## Command frames

Same as the local Duepi‑EVO protocol (see `custom_components/dpremote/protocol.py`
and `aceindy/Duepi_EVO`): `ESC('\x1b') + 'R' + <payload> + <2-hex checksum> + '&'`,
checksum = `sum(ord(c) for c in "R"+payload) & 0xFF`. `getCRC`/`checkCRC` in
`DeviceConnection` implement the same checksum.

## Optional AES layer (not implemented here)

The app bundles `QAESEncryption` and reads an `encryptionKey` setting with
`setEncryptionEnabled(bool)`. On the standard EVO path this is **off** and frames
are plaintext (consistent with the local integration). If a future module
mandates encryption, the key/mode/padding would need to be recovered (the key is
read from app settings, not an obvious global constant) and applied around the
frame bytes. Left as a TODO.

## Open questions / to verify against a live stove

- Confirm the relay accepts `master:<code>#` with no trailing newline and no
  credentials (username/password are app‑account concepts, not part of this
  line).
- Address/port are **user-configurable in the app** and per account/region.
  `duepiwebserver.com:3000` is only the hardcoded fallback in the binary; a real
  user's app screen showed `1.duepiwebserver1.com` : `2000`. The integration
  therefore treats address and port as required, user-entered fields.
- Confirm whether any module in the field turns the AES layer on by default.
