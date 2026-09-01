"""Fake mysql.connector -> sqlite-backed shared FakeConnection."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from _fakedb import connect, FakeConnection, FakeCursor  # noqa: E402


class Error(Exception):
    pass


class Warning(Exception):  # noqa: A001 - mimics mysql.connector.Warning
    pass


class errors:  # noqa: N801 - mimic mysql.connector.errors namespace
    Error = Error
    Warning = Warning
