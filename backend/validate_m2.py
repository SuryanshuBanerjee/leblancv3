"""
validate_m2.py — the M2 acceptance gate.

For every prompt that has BOTH a functional test (dataset/tests/<id>_test.py) and a
reference solution (dataset/reference/<id>.py), run the test against the reference
using Engine D's *actual* runner. A test is only accepted into the frozen dataset
if it PASSES on its reference solution — otherwise the test (or reference) is wrong.

This spends no API money; it is pure local pytest. Run:
    python validate_m2.py
"""
import json
import os

from engine_d_functest import run_functional_tests

HERE = os.path.dirname(__file__)
DATASET = os.path.join(HERE, "..", "dataset")
TESTS_DIR = os.path.join(DATASET, "tests")
REF_DIR = os.path.join(DATASET, "reference")


def _ids_with_tests():
    if not os.path.isdir(TESTS_DIR):
        return []
    return sorted(f[:-len("_test.py")] for f in os.listdir(TESTS_DIR)
                  if f.endswith("_test.py"))


def main():
    with open(os.path.join(DATASET, "leblanc_v3_prompts.json"), encoding="utf-8") as f:
        n_prompts = len(json.load(f))

    ids = _ids_with_tests()
    if not ids:
        print("No test files found in dataset/tests/. M2 not started.")
        return

    ok, bad, missing_ref = [], [], []
    print(f"Validating {len(ids)} functional test(s) against their reference solutions:\n")
    for pid in ids:
        ref = os.path.join(REF_DIR, f"{pid}.py")
        if not os.path.exists(ref):
            missing_ref.append(pid)
            print(f"  [?] {pid}: test exists but no reference/{pid}.py")
            continue
        with open(ref, encoding="utf-8") as f:
            code = f.read()
        # Engine D expects a fenced block (it re-extracts); wrap the reference.
        res = run_functional_tests(pid, code)
        if res["status"] == "pass":
            ok.append(pid)
            print(f"  [+] {pid}: PASS on reference")
        else:
            bad.append((pid, res["status"]))
            print(f"  [X] {pid}: {res['status'].upper()} on reference")
            tail = (res.get("detail") or "").strip().splitlines()[-4:]
            for line in tail:
                print(f"        {line}")

    print(f"\n{'='*60}")
    print(f"dataset prompts:            {n_prompts}")
    print(f"prompts with functional test: {len(ids)}  "
          f"({round(len(ids)/n_prompts*100)}% -- the rest drive RQ1-RQ4 only)")
    print(f"tests passing on reference:  {len(ok)}")
    if bad:
        print(f"FAILING (fix before freeze): {[b[0] for b in bad]}")
    if missing_ref:
        print(f"missing reference solution:  {missing_ref}")
    print(f"{'='*60}")
    if bad or missing_ref:
        raise SystemExit(1)
    print("M2 gate GREEN.")


if __name__ == "__main__":
    main()
