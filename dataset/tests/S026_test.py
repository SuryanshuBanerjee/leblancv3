"""Functional smoke test for S026 — readJSON must fetch (faked, offline) and
parse a JSON document into a Python object."""
from solution import readJSON


def test_reads_and_parses_json():
    obj = readJSON("https://example.com/data.json")
    assert isinstance(obj, dict)
    assert obj.get("ok") is True
    assert obj.get("name") == "leblanc"
