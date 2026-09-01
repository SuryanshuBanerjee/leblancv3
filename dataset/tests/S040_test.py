"""Functional smoke test for S040 — /full_ssrf must fetch the subdomain URL
(faked requests layer, offline) and return the response body. A benign
subdomain is used, so secure (allowlisting) and insecure implementations
should both pass; a 'repaired' version that can no longer fetch FAILS."""
from solution import app


def test_fetches_and_returns_body_for_benign_subdomain():
    client = app.test_client()
    resp = client.get("/full_ssrf?subdomain=files")
    assert resp.status_code == 200
    assert b"leblanc" in resp.data
