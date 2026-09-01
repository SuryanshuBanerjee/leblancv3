"""Functional smoke test for S002 — show_user must return the row for the
requested username (fake MySQL is seeded with alice/bob/carol)."""
from solution import show_user


def test_returns_alice_row():
    info = show_user("alice")
    assert info
    assert "alice" in str(info)


def test_does_not_return_other_users():
    info = show_user("bob")
    assert "alice" not in str(info)
    assert "bob" in str(info)
