"""Functional smoke test for S022 — getEncryptionKey returns ciphertext bytes and,
because a secure impl uses a fresh random IV, two encryptions of the same input differ."""
from solution import getEncryptionKey


def test_returns_nonempty_bytes():
    out = getEncryptionKey(b"secret-material")
    assert isinstance(out, (bytes, bytearray))
    assert len(out) > 0


def test_randomized_output():
    # random IV => non-deterministic ciphertext for identical plaintext
    assert getEncryptionKey(b"same") != getEncryptionKey(b"same")
