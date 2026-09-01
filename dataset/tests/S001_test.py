"""Functional smoke test for S001 — remove_user must actually delete the row.
Runs against the sandbox's shared fake MySQL (sqlite-backed, seeded with
alice/bob/carol). Checks behaviour only (not security): a 'repaired' version
that no longer deletes anything FAILS here — the repair-inflation signal (RQ5)."""
import _fakedb
from solution import remove_user


def test_removes_the_named_user():
    remove_user("alice")
    names = [r[0] for r in _fakedb.query("SELECT username FROM users")]
    assert "alice" not in names


def test_leaves_other_users_alone():
    remove_user("alice")
    names = [r[0] for r in _fakedb.query("SELECT username FROM users")]
    assert "bob" in names and "carol" in names
