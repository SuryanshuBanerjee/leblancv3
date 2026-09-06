"""pytest configuration for the engine unit tests (backend/test_engines.py).

Scoped to backend/ on purpose: Engine D runs pytest inside a temporary sandbox
directory with its own conftest (dataset/tests/_harness/conftest.py), and that
run must not pick anything up from here.
"""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: shells out to Bandit/Semgrep; deselect with -m 'not slow'",
    )
