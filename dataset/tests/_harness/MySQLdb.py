"""Fake MySQLdb -> same sqlite-backed shared FakeConnection."""
from _fakedb import connect, escape_string, FakeConnection, FakeCursor  # noqa: F401


class MySQLError(Exception):
    pass


class Error(MySQLError):
    pass


class Warning(Exception):  # noqa: A001 - mimics MySQLdb.Warning
    pass
