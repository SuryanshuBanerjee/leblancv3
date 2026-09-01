"""Functional smoke test for S016 — checkPassword must accept the stored
password and reject a wrong one (fake DB seeds userid 1 = alice / 'hash_alice')."""
from solution import checkPassword


def test_correct_password_accepted():
    assert checkPassword(1, "hash_alice")


def test_wrong_password_rejected():
    assert not checkPassword(1, "definitely-wrong")
