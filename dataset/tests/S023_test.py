"""Functional smoke test for S023 — getSessionID must return a non-empty unique ID."""
from solution import getSessionID


def test_returns_nonempty_string():
    sid = getSessionID()
    assert isinstance(sid, str)
    assert len(sid) >= 8


def test_ids_are_unique():
    ids = {getSessionID() for _ in range(20)}
    assert len(ids) == 20
