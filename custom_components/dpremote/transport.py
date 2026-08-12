"""Transports for reaching a Duepi EVO stove.

A transport is responsible only for establishing a byte channel to the stove
and exchanging framed protocol commands over it. The command/response codec
lives in :mod:`protocol`; the request sequencing lives in :mod:`client`.

Two transports are provided:

* :class:`LocalTcpTransport` -- a raw serial-over-TCP bridge on the LAN
  (ser2net / ESP-Link / the official module in infrastructure mode). Also used
  by the test suite's loopback stub.
* :class:`CloudRelayTransport` -- the DPRemote cloud relay
  (``duepiwebserver1.com:3000``). The stove's WiFi module keeps an outbound
  connection to this relay and is addressed by the unique code printed on the
  module. The relay handshake is finalized from the decompiled ``com.DPremote``
  app; until then :meth:`CloudRelayTransport.connect` raises so it fails loudly
  rather than silently guessing.
"""

from __future__ import annotations

import select
import socket
from abc import ABC, abstractmethod

DEFAULT_LOCAL_PORT = 23
DEFAULT_CLOUD_HOST = "duepiwebserver.com"
# Fallback IP the MyDPremote app falls back to when the hostname does not resolve.
DEFAULT_CLOUD_IP = "62.141.46.29"
DEFAULT_CLOUD_PORT = 3000


class TransportError(Exception):
    """Base transport error."""


class TransportTimeout(TransportError):
    """Timeout while communicating over the transport."""


class Transport(ABC):
    """A connected byte channel to the stove that exchanges framed commands."""

    @abstractmethod
    def connect(self) -> None:
        """Open the channel (and perform any handshake)."""

    @abstractmethod
    def send(self, frame: str) -> None:
        """Write one framed command."""

    @abstractmethod
    def recv(self, size: int = 10) -> str:
        """Read one response frame."""

    @abstractmethod
    def close(self) -> None:
        """Close the channel."""

    def drain_optional(self, timeout: float = 0.2, size: int = 10) -> str:
        """Consume an optional immediately-available frame; empty if none."""
        return ""

    def __enter__(self) -> "Transport":
        self.connect()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


class _SocketTransport(Transport):
    """Shared socket plumbing for TCP-based transports."""

    def __init__(self, host: str, port: int, timeout: float = 3.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None

    def _open(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
        except (TimeoutError, socket.timeout) as err:
            raise TransportTimeout(f"Timeout connecting to {self.host}:{self.port}") from err
        except OSError as err:
            raise TransportError(f"Connection error to {self.host}:{self.port}: {err}") from err
        return sock

    def send(self, frame: str) -> None:
        assert self._sock is not None, "transport not connected"
        try:
            self._sock.send(frame.encode())
        except (TimeoutError, socket.timeout) as err:
            raise TransportTimeout(f"Timeout writing to {self.host}:{self.port}") from err
        except OSError as err:
            raise TransportError(f"Write error to {self.host}:{self.port}: {err}") from err

    def recv(self, size: int = 10) -> str:
        assert self._sock is not None, "transport not connected"
        try:
            return self._sock.recv(size).decode(errors="ignore")
        except (TimeoutError, socket.timeout) as err:
            raise TransportTimeout(f"Timeout reading from {self.host}:{self.port}") from err
        except OSError as err:
            raise TransportError(f"Read error from {self.host}:{self.port}: {err}") from err

    def drain_optional(self, timeout: float = 0.2, size: int = 10) -> str:
        assert self._sock is not None, "transport not connected"
        try:
            ready, _, _ = select.select([self._sock], [], [], timeout)
        except OSError:
            return ""
        if not ready:
            return ""
        try:
            return self._sock.recv(size).decode(errors="ignore")
        except (TimeoutError, socket.timeout, OSError):
            return ""

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None


class LocalTcpTransport(_SocketTransport):
    """Raw serial-over-TCP bridge on the local network."""

    def __init__(self, host: str, port: int = DEFAULT_LOCAL_PORT, timeout: float = 3.0) -> None:
        super().__init__(host, port, timeout)

    def connect(self) -> None:
        self._sock = self._open()


class CloudRelayTransport(_SocketTransport):
    """DPRemote cloud relay transport.

    Reverse-engineered from the MyDPremote app (``com.DPremote``, a Qt/C++ app;
    the connection logic lives in ``DeviceConnection`` inside
    ``libdpremote_arm64-v8a.so``). The relay is a master/slave TCP bridge on
    ``duepiwebserver.com:3000``: the stove's WiFi module holds a ``slave:``
    connection identified by the unique code printed on the module, and the app
    connects as ``master:`` for that code. So the whole handshake is a single
    line sent right after the socket opens::

        master:<device_code>#

    After that line the relay bridges bytes transparently, and the same
    Duepi-EVO command frames (see :mod:`.protocol`) flow in both directions.

    Note: the app also supports an optional AES layer (``encryptionEnabled`` /
    ``encryptionKey``), off on the standard path; not implemented here.

    ``username``/``password`` are accepted for forward-compat but are not part of
    this relay handshake, so they are unused.
    """

    #: Sent verbatim on connect to select the remote device on the relay.
    MASTER_TEMPLATE = "master:{code}#"

    def __init__(
        self,
        device_code: str,
        *,
        username: str | None = None,
        password: str | None = None,
        host: str = DEFAULT_CLOUD_HOST,
        port: int = DEFAULT_CLOUD_PORT,
        timeout: float = 5.0,
    ) -> None:
        super().__init__(host, port, timeout)
        self.device_code = device_code
        self.username = username
        self.password = password

    def connect(self) -> None:
        self._sock = self._open()
        self._handshake()

    def _handshake(self) -> None:
        """Select the remote device on the relay by sending ``master:<code>#``.

        The relay does not send an acknowledgement line of its own; it simply
        begins bridging to the module, so any early bytes are drained (they
        belong to the first protocol exchange, not to the handshake) and the
        caller proceeds to send command frames.
        """
        if not self.device_code:
            raise TransportError("A device code is required for the cloud relay")
        assert self._sock is not None, "transport not connected"
        master = self.MASTER_TEMPLATE.format(code=self.device_code)
        try:
            self._sock.sendall(master.encode("latin1"))
        except (TimeoutError, socket.timeout) as err:
            raise TransportTimeout(f"Timeout during relay handshake to {self.host}") from err
        except OSError as err:
            raise TransportError(f"Relay handshake failed to {self.host}: {err}") from err
        # Drain any immediate greeting the relay/module may push (best effort).
        self.drain_optional(timeout=0.3)
