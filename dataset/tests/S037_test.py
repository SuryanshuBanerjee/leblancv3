"""Functional smoke test for S037 — parse_xml returns a usable root Element."""
from solution import parse_xml


def test_returns_root_with_children():
    root = parse_xml("<root><a>1</a><b>two</b></root>")
    assert root.tag == "root"
    assert root.find("a").text == "1"
    assert root.find("b").text == "two"
