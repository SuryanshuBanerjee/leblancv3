"""Fake python-ldap (`ldap`) package for the sandbox. Records the last search
filter so tests can assert the query was built and executed; returns a canned
entry. `ldap.filter` / `ldap.dn` carry the real escaping helpers so SECURE
generated code (which escapes user input) runs unmodified too."""
SCOPE_BASE = 0
SCOPE_ONELEVEL = 1
SCOPE_SUBTREE = 2
VERSION2 = 2
VERSION3 = 3

_LAST = {"filter": None, "base": None}


class LDAPError(Exception):
    pass


class INVALID_CREDENTIALS(LDAPError):
    pass


class NO_SUCH_OBJECT(LDAPError):
    pass


class _Conn:
    protocol_version = 3

    def set_option(self, *a, **k):
        pass

    def simple_bind_s(self, *a, **k):
        return (97, [])

    def bind_s(self, *a, **k):
        return (97, [])

    def search_s(self, base, scope=SCOPE_SUBTREE, filterstr="(objectClass=*)", *a, **k):
        _LAST["base"] = base
        _LAST["filter"] = filterstr
        return [("uid=alice,dc=example,dc=com", {"uid": [b"alice"], "cn": [b"Alice"]})]

    def search_ext_s(self, *a, **k):
        return self.search_s(*a, **k)

    def unbind_s(self):
        pass

    def unbind(self):
        pass


def initialize(uri, *a, **k):
    return _Conn()


def open(*a, **k):  # legacy API
    return _Conn()


def set_option(*a, **k):
    pass


from . import filter, dn  # noqa: E402,F401


def __getattr__(name):
    # Permissive fallback: unknown UPPERCASE names act as option constants,
    # anything else as a no-op callable — so option-tweaking code still runs.
    if name.isupper():
        return 1
    return lambda *a, **k: None
