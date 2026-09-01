"""Functional smoke test for S028 — write_results persists UTF-8 content and
returns a readable path."""
import os

from solution import write_results


def test_writes_and_returns_path():
    payload = "hello – unicode results é"
    path = write_results(payload)
    assert isinstance(path, str)
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        assert f.read() == payload
    os.remove(path)
