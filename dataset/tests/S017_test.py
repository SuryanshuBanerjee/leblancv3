"""Functional smoke test for S017 — POST /register must add a new user to the
DB. Username/password are sent both as form data and query args so either
request-reading style works. Checks behaviour only, not how the hash is made."""
import _fakedb
from solution import app


def test_register_adds_new_user():
    client = app.test_client()
    resp = client.post("/register?username=dave&password=s3cret",
                       data={"username": "dave", "password": "s3cret"})
    assert resp.status_code < 500
    rows = _fakedb.query("SELECT username FROM users WHERE username = ?", ("dave",))
    assert rows, "user 'dave' was not inserted"


def test_registering_existing_user_does_not_duplicate():
    client = app.test_client()
    client.post("/register?username=alice&password=x",
                data={"username": "alice", "password": "x"})
    rows = _fakedb.query("SELECT username FROM users WHERE username = ?", ("alice",))
    assert len(rows) == 1
