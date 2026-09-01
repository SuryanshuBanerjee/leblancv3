"""Sandbox conftest — installed into every Engine D / validate_m2 sandbox.

Makes network-dependent generated code runnable offline by replacing live network
calls with local fakes BEFORE the solution module is imported. This keeps the
sandbox airtight (no real egress) while still exercising the code's logic.
"""
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

_FAKE_JSON = {"ok": True, "id": 1, "name": "leblanc", "items": [1, 2, 3]}
_FAKE_BODY = json.dumps(_FAKE_JSON).encode("utf-8")


class _FakeHTTPResponse(io.BytesIO):
    def __init__(self, data=_FAKE_BODY):
        super().__init__(data)
        self.status = 200
        self.headers = {"Content-Type": "application/json"}

    def getcode(self):
        return 200

    def read(self, *a, **k):
        return super().read(*a, **k)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _fake_urlopen(url, *a, **k):
    return _FakeHTTPResponse()


class _FakeRequestsResponse:
    status_code = 200
    text = _FAKE_BODY.decode("utf-8")
    content = _FAKE_BODY
    headers = {"Content-Type": "application/json"}

    def json(self):
        return _FAKE_JSON

    def raise_for_status(self):
        return None


def _fake_requests_call(*a, **k):
    return _FakeRequestsResponse()


def _patch_network():
    # urllib
    try:
        import urllib.request as u
        u.urlopen = _fake_urlopen
    except Exception:
        pass
    # requests
    try:
        import requests
        for m in ("get", "post", "put", "delete", "head", "patch", "request"):
            setattr(requests, m, _fake_requests_call)
    except Exception:
        pass
    # raw sockets / ssl (S021-style): return a harmless dummy
    try:
        import socket
        class _DummySock:
            def connect(self, *a, **k): pass
            def send(self, *a, **k): return 0
            def recv(self, *a, **k): return b""
            def close(self, *a, **k): pass
            def __getattr__(self, _): return lambda *a, **k: None
        socket.socket = lambda *a, **k: _DummySock()
        socket.create_connection = lambda *a, **k: _DummySock()
        import ssl
        class _Ctx:
            check_hostname = True
            verify_mode = ssl.CERT_REQUIRED
            def wrap_socket(self, sock, *a, **k): return sock
            def __getattr__(self, _): return lambda *a, **k: None
        ssl.create_default_context = lambda *a, **k: _Ctx()
        ssl.SSLContext = lambda *a, **k: _Ctx()
        ssl.wrap_socket = lambda sock, *a, **k: sock
    except Exception:
        pass


_patch_network()


@pytest.fixture(autouse=True)
def _fresh_sandbox_state():
    """Give every test a pristine seeded fake database."""
    try:
        import _fakedb
        _fakedb.reset()
    except Exception:
        pass
    yield
