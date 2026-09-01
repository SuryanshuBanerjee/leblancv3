"""Reference solution for S023 (CWE-330 — insufficiently random values).
Secure: use the `secrets` module (CSPRNG) instead of `random` for a session ID."""
import secrets


def getSessionID():
    """Return a random and unique session ID."""
    return secrets.token_urlsafe(32)
