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


def test_cloud_relay_handshake_sends_master_line():
    # On connect the relay transport must send "master:<code>#" to select the
    # remote device, then be ready to exchange frames.
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    received: dict[str, bytes] = {}

    def serve():
        conn, _ = server.accept()
        with conn:
            received["handshake"] = conn.recv(64)
            # After the handshake, bridge one status frame like the relay would.
            conn.recv(16)  # the GET_STATUS command frame
            conn.sendall(f"X{p.STATE_ON:08X}&".encode())

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    with CloudRelayTransport("ABC123", host=host, port=port, timeout=2.0) as t:
        t.send(p.build_command(p.GET_STATUS))
        response = t.recv()

    thread.join(timeout=2.0)
    server.close()

    assert received["handshake"] == b"master:ABC123#"
    assert p.decode_status(int(response[1:9], 16)) == "Flame On"


def test_cloud_relay_requires_device_code():
    t = CloudRelayTransport("", host="127.0.0.1", port=1, timeout=1.0)
    with pytest.raises(TransportError):
        t.connect()
