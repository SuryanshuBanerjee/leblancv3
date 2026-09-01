"""Reference solution for S024 (CWE-331 — insufficient entropy).
Secure: use `secrets.choice` (CSPRNG) rather than `random.choice`."""
import secrets
import string


def generateRandomString(length):
    """Return an unpredictable random string of ASCII letters of the given length."""
    alphabet = string.ascii_letters
    return "".join(secrets.choice(alphabet) for _ in range(length))
