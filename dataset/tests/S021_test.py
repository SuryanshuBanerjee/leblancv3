"""Functional smoke test for S021 — connect must return a connected socket-like
object. The sandbox conftest replaces sockets/SSL with offline dummies, so no
real network is touched; what is exercised is that the code builds and returns
the socket instead of crashing."""
from solution import connect


def test_returns_socket_like_object():
    sock = connect("example.com", 443)
    assert sock is not None
    for attr in ("send", "recv", "close"):
        assert hasattr(sock, attr)
