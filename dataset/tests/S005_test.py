"""Functional smoke test for S005 — the /normal route must run an LDAP search
and return the found user. The sandbox's fake `ldap` records the search and
returns a canned alice entry; real filter/DN escaping helpers are provided so
secure implementations run unmodified."""
import ldap
from solution import app


def test_normal_route_searches_and_returns_user():
    client = app.test_client()
    resp = client.get("/normal?dc=example&username=alice")
    assert resp.status_code == 200
    assert b"alice" in resp.data


def test_search_filter_uses_the_requested_username():
    client = app.test_client()
    client.get("/normal?dc=example&username=alice")
    assert ldap._LAST["filter"] and "alice" in ldap._LAST["filter"]
