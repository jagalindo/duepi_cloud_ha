"""Transport tests: a real-socket loopback for LocalTcpTransport, and the
cloud handshake guard."""

import socket
import threading

import pytest

from dpremote import protocol as p
from dpremote.transport import (
    CloudRelayTransport,
    LocalTcpTransport,
    TransportError,
)


def _serve_one(sock: socket.socket, reply: bytes) -> None:
    conn, _ = sock.accept()
    with conn:
        conn.recv(64)          # consume the command frame
        conn.sendall(reply)    # send a canned response


def test_local_tcp_transport_roundtrip():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    reply = f"X{p.STATE_ON:08X}&".encode()
    thread = threading.Thread(target=_serve_one, args=(server, reply), daemon=True)
    thread.start()

    with LocalTcpTransport(host, port, timeout=2.0) as t:
        t.send(p.build_command(p.GET_STATUS))
        response = t.recv()

    thread.join(timeout=2.0)
    server.close()

    assert p.decode_status(int(response[1:9], 16)) == "Flame On"


def test_local_tcp_transport_connection_refused():
    # Port 1 is (almost certainly) not listening -> connection error.
    t = LocalTcpTransport("127.0.0.1", 1, timeout=1.0)
    with pytest.raises(TransportError):
        t.connect()


def test_cloud_relay_handshake_not_yet_implemented():
    # The relay handshake is pending APK analysis; connect must fail loudly
    # rather than silently guess a protocol.
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    accepted = threading.Thread(target=lambda: server.accept(), daemon=True)
    accepted.start()

    t = CloudRelayTransport("ABC123", host=host, port=port, timeout=1.0)
    with pytest.raises(NotImplementedError):
        t.connect()

    server.close()
