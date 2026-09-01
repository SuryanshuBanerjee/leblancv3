"""Functional smoke test for S036 — yaml_load parses a YAML file into a dict."""
import os
import tempfile

from solution import yaml_load


def test_loads_mapping():
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write("name: leblanc\nversion: 3\nitems:\n  - a\n  - b\n")
    try:
        data = yaml_load(path)
        assert data == {"name": "leblanc", "version": 3, "items": ["a", "b"]}
    finally:
        os.remove(path)
