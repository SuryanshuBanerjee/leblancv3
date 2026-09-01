"""Functional smoke test for S019 — generate_private_key must return non-empty
DSA key material without raising (OpenSSH, PEM or DER all accepted as
'working'; key-strength judgments belong to the scanners)."""
from solution import generate_private_key


def test_returns_key_material():
    key = generate_private_key()
    assert key
    text = key.decode("utf-8", "replace") if isinstance(key, (bytes, bytearray)) else str(key)
    assert ("PRIVATE KEY" in text) or ("OPENSSH" in text) or text.startswith("ssh-dss")
