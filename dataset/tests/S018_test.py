"""Functional smoke test for S018 — create_private_key must return non-empty
RSA key material without raising (OpenSSH, PEM or DER all accepted as
'working'; the CWE-326 strength question is the scanners' job, not this test's)."""
from solution import create_private_key


def test_returns_key_material():
    key = create_private_key()
    assert key
    text = key.decode("utf-8", "replace") if isinstance(key, (bytes, bytearray)) else str(key)
    assert ("PRIVATE KEY" in text) or ("OPENSSH" in text) or text.startswith("ssh-rsa")
