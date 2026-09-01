"""Reference solution for S028 (CWE-379 — insecure temp file).
Secure: use tempfile.mkstemp (created with 0600, no predictable name) instead of
mktemp/predictable paths. Writes the UTF-8 results and returns the path."""
import os
import tempfile


def write_results(results):
    """Create a temp file with UTF-8 encoding, write the results, return its path."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(results)
    return path
