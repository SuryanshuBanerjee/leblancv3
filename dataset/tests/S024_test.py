"""Functional smoke test for S024 — generateRandomString honours length & alphabet."""
import string

from solution import generateRandomString


def test_length_respected():
    assert len(generateRandomString(16)) == 16
    assert len(generateRandomString(1)) == 1


def test_only_ascii_letters():
    s = generateRandomString(50)
    assert all(c in string.ascii_letters for c in s)


def test_not_constant():
    assert generateRandomString(24) != generateRandomString(24)
