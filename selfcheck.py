"""
selfcheck.py — prove the system is healthy, in one command, before you trust it.

    python selfcheck.py            # everything (~60s, free, offline)
    python selfcheck.py --quick    # skip the slow scanner round-trips (~10s)
    python selfcheck.py --keys     # also check which API keys work (tiny calls)

WHY. "It worked last week" is not evidence. Before an overnight run, before
believing a number, or after touching anything, this answers one question with a
green/red: is the pipeline actually intact right now? Every check is free,
offline (except --keys), and read-only — nothing here writes to the database or
calls a model unless you ask for --keys.

Exit code is 0 if everything passed and 1 if anything failed, so it works in CI
or a pre-run hook.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "backend"))

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def check(name):
    """Decorator: run a check, catch anything it throws, record the verdict."""
    def wrap(fn):
        t0 = time.time()
        try:
            detail = fn()
            results.append((PASS, name, detail or "", time.time() - t0))
        except SkipCheck as e:
            results.append((SKIP, name, str(e), time.time() - t0))
        except Exception as e:
            results.append((FAIL, name, f"{type(e).__name__}: {e}", time.time() - t0))
        return fn
    return wrap


class SkipCheck(Exception):
    """Raised by a check that cannot run here (missing optional tool, no keys)."""


def main():
    ap = argparse.ArgumentParser(description="LeBlanc health check")
    ap.add_argument("--quick", action="store_true", help="skip slow scanner round-trips")
    ap.add_argument("--keys", action="store_true", help="also verify API keys (tiny calls)")
    args = ap.parse_args()

    # ---------------------------------------------------------- dependencies
    @check("dependencies importable")
    def _deps():
        alias = {"python-dotenv": "dotenv", "google-genai": "google.genai",
                 "flask-cors": "flask_cors", "pyyaml": "yaml"}
        reqs = [l.split("#")[0].strip()
                for l in open(os.path.join(HERE, "backend", "requirements.txt"), encoding="utf-8")
                if l.strip() and not l.startswith("#")]
        missing = [r for r in reqs
                   if importlib.util.find_spec(alias.get(r, r).split(".")[0]) is None]
        if missing:
            raise RuntimeError(f"missing: {missing} — run: pip install -r backend/requirements.txt")
        return f"{len(reqs)} packages"

    @check("all modules import")
    def _mods():
        sys.path.insert(0, os.path.join(HERE, "analysis"))
        mods = ("database metrics run_batch llm_client mcp_server cwe_categories "
                "engine_a_enrich engine_b_scan engine_c_repair engine_d_functest "
                "app validate_m2 rq_analysis fp_audit").split()
        for m in mods:
            importlib.import_module(m)
        return f"{len(mods)} modules"

    # ---------------------------------------------------------------- data
    @check("dataset intact")
    def _dataset():
        path = os.path.join(HERE, "dataset", "leblanc_v3_prompts.json")
        data = json.load(open(path, encoding="utf-8"))
        ids = [p["id"] for p in data]
        if len(ids) != len(set(ids)):
            raise RuntimeError("duplicate prompt IDs — the dataset is supposed to be unique")
        required = {"id", "prompt", "target_cwes", "category", "source"}
        for p in data:
            missing = required - set(p)
            if missing:
                raise RuntimeError(f"{p.get('id', '?')} missing fields {missing}")
        return f"{len(data)} prompts, all unique, all fields present"

    @check("functional tests have reference solutions")
    def _tests_refs():
        tdir = os.path.join(HERE, "dataset", "tests")
        rdir = os.path.join(HERE, "dataset", "reference")
        tests = {f[:-len("_test.py")] for f in os.listdir(tdir) if f.endswith("_test.py")}
        refs = {f[:-3] for f in os.listdir(rdir) if f.endswith(".py")}
        if tests - refs:
            raise RuntimeError(f"tests with no reference solution: {sorted(tests - refs)}")
        if refs - tests:
            raise RuntimeError(f"reference solutions with no test: {sorted(refs - tests)}")
        return f"{len(tests)} tested prompts, each with a reference"

    # -------------------------------------------------------------- engines
    @check("Engine A — enrichment fires on every dataset prompt")
    def _engine_a():
        from engine_a_enrich import enrich_prompt
        data = json.load(open(os.path.join(HERE, "dataset", "leblanc_v3_prompts.json"),
                              encoding="utf-8"))
        silent = [p["id"] for p in data if not enrich_prompt(p["prompt"])[1]]
        if silent:
            raise RuntimeError(f"no CWE matched for {silent} — plain and enriched would be "
                               "identical for these, contributing noise to RQ2")
        a = enrich_prompt(data[0]["prompt"])
        if a != enrich_prompt(data[0]["prompt"]):
            raise RuntimeError("enrichment is not deterministic")
        return f"{len(data)}/{len(data)} prompts matched, deterministic"

    @check("Engine B — scanners present and finding real issues")
    def _engine_b():
        if args.quick:
            raise SkipCheck("--quick")
        from engine_b_scan import scan_code, scanner_provenance
        findings, clean, scanners = scan_code(
            "```python\nimport subprocess\nsubprocess.call('ls ' + input(), shell=True)\n```")
        if not clean:
            raise RuntimeError("valid Python failed to extract")
        if "bandit" not in scanners:
            raise RuntimeError("Bandit did not run — findings would be silently incomplete")
        if not any("CWE-78" in f["cwes"] for f in findings):
            raise RuntimeError("shell-injection was not detected; scanners may be misconfigured")
        prov = scanner_provenance()
        sg = "semgrep" in scanners
        return (f"bandit {prov['bandit'].split()[-1]}"
                + (f" + semgrep {prov['semgrep']}" if sg else " (semgrep NOT installed —"
                   " runs will degrade to Bandit-only and say so)"))

    @check("Engine B — cross-tool duplicates still merge")
    def _dedup():
        from engine_b_scan import dedupe_findings
        merged = dedupe_findings([
            {"tool": "bandit", "rule": "B201", "cwes": ["CWE-94"], "line": 9,
             "severity": "HIGH", "category": "Injection", "message": ""},
            {"tool": "semgrep", "rule": "debug-enabled", "cwes": ["CWE-489"], "line": 9,
             "severity": "WARNING", "category": "Other", "message": ""},
        ])
        if len(merged) != 1:
            raise RuntimeError("the same weakness from two tools was counted twice — "
                               "this is the 2026-09-07 regression")
        return "cross-tool merge working"

    @check("Engine B — a broken scanner is not silently reported as clean")
    def _scanner_honesty():
        import engine_b_scan as eb
        real = eb.subprocess.run

        def explode(cmd, **kw):
            if "bandit" in " ".join(map(str, cmd)):
                raise OSError("simulated")
            return real(cmd, **kw)
        eb.subprocess.run = explode
        try:
            _, clean, scanners = eb.scan_code("```python\nx = 1\n```")
        finally:
            eb.subprocess.run = real
        if "bandit" in scanners:
            raise RuntimeError("a crashed Bandit still claimed coverage")
        return "failed scanners drop out of scanners_used"

    @check("Engine D — sandbox runs, times out, and classifies correctly")
    def _engine_d():
        if args.quick:
            raise SkipCheck("--quick")
        from engine_d_functest import run_functional_tests
        if run_functional_tests("ZZZ_no_such_prompt", "x = 1")["status"] != "no_tests":
            raise RuntimeError("a missing test file should be no_tests")
        if run_functional_tests("S002", "")["status"] != "no_code":
            raise RuntimeError("absent code must be no_code, never fail")
        ref = open(os.path.join(HERE, "dataset", "reference", "S002.py"), encoding="utf-8").read()
        if run_functional_tests("S002", ref)["status"] != "pass":
            raise RuntimeError("the S002 reference solution no longer passes its own test")
        return "reference passes, outcome classes distinct"

    # -------------------------------------------------------------- metrics
    @check("metrics — statistics behave")
    def _metrics():
        from metrics import wilson_ci, mcnemar_exact, _is_vuln_final
        r, lo, hi = wilson_ci(3, 10)
        if not (lo < r < hi):
            raise RuntimeError("Wilson CI does not bracket its point estimate")
        if wilson_ci(0, 0) != (None, None, None):
            raise RuntimeError("empty sample should yield no rate")
        if mcnemar_exact(15, 1) >= 0.05 or mcnemar_exact(5, 5) != 1.0:
            raise RuntimeError("McNemar is misbehaving")
        if _is_vuln_final({"mode": "enriched_repair", "vuln_count": 4,
                           "repair_result": {"final_status": "clean"}}):
            raise RuntimeError("a successfully repaired run is being counted as vulnerable")
        return "Wilson, McNemar, verdict logic ok"

    @check("database — schema present and readable")
    def _db():
        from database import init_db, get_all_runs
        init_db()
        runs = get_all_runs()
        if runs:
            missing_prov = sum(1 for r in runs if not r.get("provenance"))
            return (f"{len(runs)} runs"
                    + (f"; {missing_prov} predate provenance capture" if missing_prov else
                       "; all carry provenance"))
        return "empty (expected before the first run)"

    @check("analysis — regenerates cleanly from whatever is in the DB")
    def _analysis():
        if args.quick:
            raise SkipCheck("--quick")
        out = subprocess.run([sys.executable, os.path.join(HERE, "analysis", "rq_analysis.py")],
                             capture_output=True, text=True, cwd=HERE, stdin=subprocess.DEVNULL)
        if out.returncode != 0:
            raise RuntimeError(f"analysis exited {out.returncode}: {out.stderr[-300:]}")
        lines = out.stdout.strip().splitlines()
        summary = next((l for l in lines if l.startswith(("wrote", "No runs"))), "ran")
        return summary[:80]

    # ----------------------------------------------------------------- keys
    @check("API keys")
    def _keys():
        if not args.keys:
            raise SkipCheck("not requested (use --keys)")
        from llm_client import preflight
        res = preflight()
        ok = [k for k, v in res.items() if v == "ok"]
        bad = {k: v[:60] for k, v in res.items() if v != "ok"}
        if not ok:
            raise RuntimeError(f"no model responded: {bad}")
        return f"{len(ok)} model(s) responding: {', '.join(ok)}" + (f"; unavailable: {list(bad)}" if bad else "")

    # ---------------------------------------------------------------- report
    width = max(len(n) for _, n, _, _ in results)
    print()
    for status, name, detail, secs in results:
        mark = {PASS: "[ok]", FAIL: "[!!]", SKIP: "[--]"}[status]
        print(f"  {mark} {name:<{width}}  {detail}")
    failed = [r for r in results if r[0] == FAIL]
    skipped = [r for r in results if r[0] == SKIP]
    print()
    print(f"  {len(results) - len(failed) - len(skipped)} passed, {len(failed)} failed, "
          f"{len(skipped)} skipped")
    if failed:
        print("\n  SOMETHING IS BROKEN — do not start a run until this is green.")
        return 1
    print("\n  System healthy. See RUNBOOK.md for what to run next.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
