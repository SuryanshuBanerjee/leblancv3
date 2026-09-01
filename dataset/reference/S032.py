"""Reference solution for S032 (CWE-502 — deserialization of untrusted data).
Secure: a restricted unpickler that only allows a small allow-list of safe builtin
types, so benign data round-trips but arbitrary object/callable construction is
blocked. Preserves the intended behaviour (return the deserialized data)."""
import io
import pickle

_SAFE = {
    ("builtins", "list"), ("builtins", "dict"), ("builtins", "set"),
    ("builtins", "tuple"), ("builtins", "str"), ("builtins", "int"),
    ("builtins", "float"), ("builtins", "bool"), ("builtins", "complex"),
    ("builtins", "bytes"), ("builtins", "frozenset"), ("builtins", "NoneType"),
}


class _RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in _SAFE:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"blocked global: {module}.{name}")


def getPickleData(pickled):
    """Return deserialized data (only safe primitive/container types allowed)."""
    return _RestrictedUnpickler(io.BytesIO(pickled)).load()
