"""Functional smoke test for S011 — getConnection must return a usable DB
connection (cursor + query works against the seeded fake MySQL)."""
from solution import getConnection


def test_returns_a_usable_connection():
    conn = getConnection()
    assert conn is not None
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE id = %s", (1,))
    row = cur.fetchone()
    assert row and row[0] == "alice"
