"""Functional smoke test for S006 — the /normal route must run an ldap3 search
and return the found user (fake ldap3 returns a canned alice entry)."""
import ldap3
from solution import app


def test_normal_route_searches_and_returns_user():
    client = app.test_client()
    resp = client.get("/normal?dc=example&username=alice")
    assert resp.status_code == 200
    assert b"alice" in resp.data


def test_search_filter_uses_the_requested_username():
    client = app.test_client()
    client.get("/normal?dc=example&username=alice")
    assert ldap3._LAST["filter"] and "alice" in ldap3._LAST["filter"]
