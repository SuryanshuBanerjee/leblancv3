"""
Engine D v3 — functional smoke-test runner (the honesty layer, NEW in v3).

Runs the per-prompt pytest file from dataset/tests/<id>_test.py against the final
generated code, in an isolated subprocess with a hard timeout.

Outcomes:
  pass      — tests ran and all passed
  fail      — tests ran, at least one failed/errored (secure-but-broken candidate)
  no_tests  — no test file exists for this prompt yet (M2 not done)
  timeout   — exceeded hard limit
  harness_error — the runner itself broke (investigate, never count as pass/fail)
"""
import os
import shutil
import subprocess
import sys
import tempfile

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset")
TESTS_DIR = os.path.join(DATASET_DIR, "tests")
HARNESS_DIR = os.path.join(TESTS_DIR, "_harness")
HARD_TIMEOUT = 30  # seconds for the whole pytest session (per-test guards live in tests)


def _install_harness(sandbox):
    """Copy the offline harness (conftest + fake mysql/MySQLdb/ldap/ldap3/network
    layer) into the sandbox so DB/LDAP/network-dependent code runs with no
    services and no egress. pytest auto-loads the conftest before the solution
    module is imported."""
    if os.path.isdir(HARNESS_DIR):
        shutil.copytree(HARNESS_DIR, sandbox, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def run_functional_tests(prompt_id, final_code):
    """Returns dict: {status, detail}."""
    test_file = os.path.join(TESTS_DIR, f"{prompt_id}_test.py")
    if not os.path.exists(test_file):
        return {"status": "no_tests", "detail": ""}
    if not final_code:
        return {"status": "fail", "detail": "no code to test"}

    sandbox = tempfile.mkdtemp(prefix=f"leblanc_{prompt_id}_")
    try:
        _install_harness(sandbox)
        with open(os.path.join(sandbox, "solution.py"), "w", encoding="utf-8") as f:
            f.write(final_code)
        shutil.copy(test_file, os.path.join(sandbox, "test_solution.py"))

        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["LEBLANC_SANDBOX"] = "1"  # tests may use this to guard network use

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-x", "-q", "--no-header",
             "-p", "no:cacheprovider", "test_solution.py"],
            cwd=sandbox, env=env, capture_output=True, text=True, timeout=HARD_TIMEOUT,
        )
        out = (result.stdout or "") + (result.stderr or "")
        status = "pass" if result.returncode == 0 else "fail"
        return {"status": status, "detail": out[-1500:]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "detail": f"exceeded {HARD_TIMEOUT}s"}
    except Exception as e:
        return {"status": "harness_error", "detail": str(e)[:500]}
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    print(run_functional_tests("L001", "def x():\n    return 1\n"))
