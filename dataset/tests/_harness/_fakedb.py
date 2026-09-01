"""Shared fake SQL backend for the sandbox.

Backed by a real in-memory sqlite3 database so parameterized SQL is genuinely
executed (behaviour is tested, not mocked away). Presents a DB-API surface close
enough to mysql-connector / MySQLdb that generated code runs unmodified:
  - %s placeholders are translated to sqlite's ? placeholders
  - %(name)s placeholders are translated to :name placeholders
  - a `users(id, userid, username, password)` table is pre-seeded

The database is SHARED across all connections in the process (like a real MySQL
server), so a test can call the solution and then observe its effect through the
`query()` helper. The sandbox conftest resets it before each test.
"""
import re
import sqlite3

_SEED = [
    (1, 1, "alice", "hash_alice"),
    (2, 2, "bob", "hash_bob"),
    (3, 3, "carol", "hash_carol"),
]

_shared = None


def _new_db():
    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.execute(
        "CREATE TABLE users ("
        "id INTEGER PRIMARY KEY, userid INTEGER, username TEXT, password TEXT)"
    )
    con.executemany("INSERT INTO users VALUES (?,?,?,?)", _SEED)
    con.commit()
    return con


def _current():
    global _shared
    if _shared is None:
        _shared = _new_db()
    return _shared


def reset():
    """Restore the pristine seeded database (conftest calls this per test)."""
    global _shared
    _shared = _new_db()


def query(sql, params=()):
    """Test helper: inspect the same DB the solution wrote to."""
    return _current().execute(_translate(sql), params).fetchall()


def _translate(sql):
    sql = re.sub(r"%\((\w+)\)s", r":\1", sql)  # %(name)s -> :name
    return sql.replace("%s", "?")              # %s       -> ?


def _seq(params):
    if params is None:
        return []
    if isinstance(params, (list, tuple, dict)):
        return params
    return [params]  # some drivers accept a bare scalar


class FakeCursor:
    def __init__(self):
        self._cur = _current().cursor()
        self.lastrowid = None

    def execute(self, sql, params=None):
        self._cur.execute(_translate(sql), _seq(params))
        self.lastrowid = self._cur.lastrowid
        return self

    def executemany(self, sql, seq):
        self._cur.executemany(_translate(sql), seq)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=1):
        return self._cur.fetchmany(size)

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def close(self):
        self._cur.close()

    def __iter__(self):
        return iter(self._cur.fetchall())

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeConnection:
    def cursor(self, *a, **k):
        return FakeCursor()

    def commit(self):
        _current().commit()

    def rollback(self):
        _current().rollback()

    def close(self):
        pass

    def is_connected(self):  # mysql.connector API
        return True

    def escape_string(self, s):  # MySQLdb connection API
        return escape_string(s)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def escape_string(s):
    if isinstance(s, (bytes, bytearray)):
        s = s.decode("utf-8", "replace")
    return (str(s).replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"'))


def connect(*args, **kwargs):
    """Drop-in for mysql.connector.connect / MySQLdb.connect."""
    return FakeConnection()
