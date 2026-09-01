"""Functional smoke test for S032 — getPickleData round-trips benign data.
A secure restricted unpickler must still deserialize plain containers/primitives."""
import pickle

from solution import getPickleData


def test_roundtrip_list():
    assert getPickleData(pickle.dumps([1, 2, 3])) == [1, 2, 3]


def test_roundtrip_dict():
    assert getPickleData(pickle.dumps({"a": 1, "b": [2, 3]})) == {"a": 1, "b": [2, 3]}
