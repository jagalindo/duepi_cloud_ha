# reference_code

The DPRemote cloud protocol used by this integration was reverse‑engineered from
the official **MyDPremote** Android app:

- Package: `com.DPremote`
- Version analysed: **3.2.2** (APKPure build)
- Relevant binary: `lib/arm64-v8a/libdpremote_arm64-v8a.so` (Qt/C++), class
  `DeviceConnection`.

The APK itself is **intentionally not stored in this repository** (it is a large
third‑party binary and bloats clones/HACS installs). Download it yourself from an
official source if you want to reproduce the analysis.

The findings — server relay, `master:<code>#` handshake, and the Duepi‑EVO frame
format — are documented in [`../docs/PROTOCOL.md`](../docs/PROTOCOL.md).
