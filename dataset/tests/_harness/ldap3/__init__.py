"""Fake `ldap3` package for the sandbox. Canned search results; real filter
escaping lives in ldap3.utils.conv so secure generated code runs unmodified."""
SUBTREE = "SUBTREE"
BASE = "BASE"
LEVEL = "LEVEL"
ALL = "ALL"
ALL_ATTRIBUTES = "*"
SIMPLE = "SIMPLE"
SYNC = "SYNC"
SAFE_SYNC = "SAFE_SYNC"
ANONYMOUS = "ANONYMOUS"

_LAST = {"filter": None, "base": None}


class LDAPException(Exception):
    pass


class Server:
    def __init__(self, *a, **k):
        pass


class Connection:
    def __init__(self, *a, **k):
        self.entries = []
        self.response = []
        self.result = {"description": "success"}
        self.bound = False

    def bind(self):
        self.bound = True
        return True

    def open(self):
        return True

    def search(self, search_base=None, search_filter=None, *a, **k):
        _LAST["base"] = search_base
        _LAST["filter"] = search_filter
        self.response = [{"dn": "uid=alice,dc=example,dc=com",
                          "attributes": {"uid": "alice", "cn": "Alice"}}]
        self.entries = self.response
        return True

    def unbind(self):
        self.bound = False
        return True

    def __enter__(self):
        self.bind()
        return self

    def __exit__(self, *a):
        self.unbind()


from . import utils  # noqa: E402,F401


class _Any:
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return self

    def __getattr__(self, _):
        return _Any()


def __getattr__(name):
    # Permissive fallback so Tls(...), NTLM, strategy constants etc. don't crash.
    return _Any()
