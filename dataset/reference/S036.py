"""Reference solution for S036 (CWE-020 / CWE-502 — unsafe YAML load).
Secure: yaml.safe_load instead of yaml.load(Loader=FullLoader/unsafe)."""
import yaml


def yaml_load(filename):
    """Open the file, load its YAML contents safely, and return them."""
    with open(filename, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
