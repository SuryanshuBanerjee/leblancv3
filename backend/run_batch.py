"""
run_batch.py — the experiment runner (idempotent, resumable, preflight-gated).

Usage:
  python run_batch.py --preflight                 # check every model responds; do nothing else
  python run_batch.py --report                    # print cell-completeness matrix
  python run_batch.py --models gpt-oss-20b gemini-2.5-flash --modes plain --reps 1
  python run_batch.py --models all --modes all --reps 3            # the full experiment
  python run_batch.py --models all --modes all --reps 3 --category Injection
  python run_batch.py ... --retry-errors          # also redo cells that ended in llm_error

Completed (non-error) cells are skipped automatically — rerun the same command
after a crash and it continues where it left off.
"""
import argparse
import json
import os
import sys
import time

from database import init_db, save_run, has_run, get_all_runs
from engine_a_enrich import enrich_prompt
from engine_b_scan import scan_code, scanner_provenance
from engine_c_repair import repair_loop
from engine_d_functest import run_functional_tests
from llm_client import MODEL_CONFIGS, call_llm, preflight

DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "dataset", "leblanc_v3_prompts.json")
MODES = ["plain", "enriched", "enriched_repair"]

# $ per 1M tokens (input, output). 0 = genuinely free tier. Update when pricing changes.
#
# 2026-09-07: gemini-2.5-flash moved from (0, 0) to paid rates. It was on Google's
# free tier when the 2026-09-01 pilot ran, and is not any more — leaving it at (0, 0)
# would have made the cost gate wave through a Gemini-inclusive batch as "$0, no
# confirmation needed", which is exactly the silent-spend case the gate exists to
# prevent. The 2026-09-01 pilot's $0 cost is therefore a historical fact about that
# run, not a claim about re-running it today (see docs/03_METHODOLOGY.md).
PRICES = {
    "gpt-oss-20b": (0, 0), "gpt-oss-120b": (0, 0),      # Groq free tier
    "gemini-2.5-flash": (0.30, 2.50),                    # paid as of 2026-09-07
    "gpt-4o-mini": (0.15, 0.60), "claude-haiku-4.5": (1.00, 5.00), "deepseek-chat": (0.27, 1.10),
}
EST_IN_TOK, EST_OUT_TOK = 1500, 1000   # per LLM call, rough
REPAIR_CALL_FACTOR = 1.6               # avg extra calls per enriched_repair cell


def estimate_cost(models, modes, n_prompts, reps):
    """Returns (total_calls, usd) — deliberately pessimistic."""
    total_calls, usd = 0, 0.0
    for m in models:
        calls = 0
        for mode in modes:
            per_cell = 1 + (REPAIR_CALL_FACTOR if mode == "enriched_repair" else 0)
            calls += n_prompts * reps * per_cell
        total_calls += calls
        pin, pout = PRICES.get(m, (5.0, 15.0))  # unknown model -> assume expensive
        usd += calls * (EST_IN_TOK * pin + EST_OUT_TOK * pout) / 1_000_000
    return int(total_calls), round(usd, 2)


def load_dataset(category=None, ids=None):
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if category:
        data = [p for p in data if p["category"].lower() == category.lower()]
    if ids:
        wanted = {i.upper() for i in ids}
        data = [p for p in data if p["id"].upper() in wanted]
    return data


def run_cell(p, model, mode, rep):
    """One full pipeline run. Returns the saved record dict."""
    gen_bucket = MODEL_CONFIGS[model]["gen"]
    base = {
        "prompt_id": p["id"], "model": model, "mode": mode, "rep": rep,
        "generation": gen_bucket, "category": p["category"], "prompt_text": p["prompt"],
        # Which analyser versions and which pinned ruleset produced this row.
        # Without it, "our results are reproducible because the ruleset is pinned"
        # is unverifiable after the fact — see engine_b_scan.scanner_provenance().
        "provenance": scanner_provenance(),
    }

    # Engine A
    if mode in ("enriched", "enriched_repair"):
        enriched, cwes, _kws, details = enrich_prompt(p["prompt"])
    else:
        enriched, cwes, details = p["prompt"], [], []
    base.update({"enriched_prompt": enriched, "matched_cwes": cwes, "match_details": details})

    # LLM generation
    try:
        raw = call_llm(enriched, model)
    except Exception as e:
        base.update({
            "generated_code": "", "clean_code": "", "final_code": "",
            "scan_results": [], "scanners": [], "vuln_count": 0, "repair_result": {},
            "functest_status": "", "final_status": "llm_error",
            "total_iterations": 0, "llm_error": str(e)[:500],
        })
        save_run(base)
        return base

    # Engine B
    vulns, clean_code, scanners = scan_code(raw)
    extraction_failed = not clean_code
    base.update({
        "generated_code": raw, "clean_code": clean_code,
        "scan_results": vulns, "scanners": scanners, "vuln_count": len(vulns),
    })

    # Engine C
    final_code = clean_code
    if mode == "enriched_repair" and vulns and not extraction_failed:
        rr = repair_loop(clean_code, vulns, model, security_context=cwes or None)
        final_code = rr["final_code"]
        base.update({"repair_result": rr, "final_status": rr["final_status"],
                     "total_iterations": rr["total_iterations"]})
    else:
        base.update({"repair_result": {}, "total_iterations": 0})
        if extraction_failed:
            base["final_status"] = "extraction_failed"
        else:
            base["final_status"] = "clean" if not vulns else "vulnerable"

    # Engine D — functional verdict on whatever code we ended with.
    # An extraction failure yields `no_code`, NOT `fail`: there was never a
    # candidate to test, and counting it as functionally broken would inflate
    # RQ5's numerator with runs that produced nothing at all. (Fixed 2026-09-07.)
    base["final_code"] = final_code
    ft = run_functional_tests(p["id"], final_code) if not extraction_failed else \
        {"status": "no_code", "detail": "extraction failed upstream; no code to test"}
    base["functest_status"] = ft["status"]
    base["functest_detail"] = ft["detail"]

    save_run(base)
    return base


def report():
    runs = get_all_runs()
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        n_prompts = len(json.load(f))
    print(f"dataset prompts: {n_prompts}")
    done = {}
    for r in runs:
        key = (r["model"], r["mode"])
        done.setdefault(key, {"ok": 0, "err": 0})
        done[key]["err" if r["final_status"] == "llm_error" else "ok"] += 1
    print(f"{'model':20s} {'mode':17s} {'ok':>5s} {'err':>5s}")
    for (m, mode), c in sorted(done.items()):
        print(f"{m:20s} {mode:17s} {c['ok']:5d} {c['err']:5d}")
    if not done:
        print("(no runs yet)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=[])
    ap.add_argument("--modes", nargs="+", default=[])
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--category")
    ap.add_argument("--ids", nargs="+", help="run only these prompt IDs (e.g. L001 S007)")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--retry-errors", action="store_true")
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--yes", action="store_true",
                    help="accept the cost estimate and start (required when est. cost > $0)")
    args = ap.parse_args()

    init_db()

    if args.report:
        report()
        return

    models = list(MODEL_CONFIGS) if args.models == ["all"] else args.models
    for m in models:
        if m not in MODEL_CONFIGS:
            sys.exit(f"Unknown model '{m}'. Known: {list(MODEL_CONFIGS)}")

    if args.preflight or models:
        targets = models or list(MODEL_CONFIGS)
        print("preflight:", ", ".join(targets))
        pf = preflight(targets)
        for name, status in pf.items():
            print(f"  [{'+' if status == 'ok' else '!'}] {name:18s} {status}")
        if args.preflight:
            return
        bad = [n for n, s in pf.items() if s != "ok"]
        if bad and not args.skip_preflight:
            sys.exit(f"Preflight failed for {bad}. Fix or drop them (see docs/03). "
                     f"Use --skip-preflight only if you know what you're doing.")

    if not models:
        sys.exit("Nothing to do. Use --models / --preflight / --report.")

    modes = MODES if args.modes in ([], ["all"]) else args.modes
    prompts = load_dataset(args.category, args.ids)
    total = len(prompts) * len(models) * len(modes) * args.reps
    calls, usd = estimate_cost(models, modes, len(prompts), args.reps)
    print(f"\nplan: {len(prompts)} prompts x {len(models)} models x {len(modes)} modes "
          f"x {args.reps} reps = {total} cells")
    print(f"cost estimate: ~{calls} LLM calls, ~${usd:.2f} on paid models "
          f"(free-tier models cost $0; estimate is deliberately pessimistic)\n")
    if usd > 0 and not args.yes:
        sys.exit(f"This plan is estimated to cost ~${usd:.2f}. "
                 f"Re-run with --yes to accept, or drop the paid models.")

    t0, done_n, skip_n, err_n = time.time(), 0, 0, 0
    for p in prompts:
        for model in models:
            for mode in modes:
                for rep in range(1, args.reps + 1):
                    if not args.retry_errors and has_run(p["id"], model, mode, rep):
                        skip_n += 1
                        continue
                    tag = f"{p['id']} {model} {mode} rep{rep}"
                    try:
                        rec = run_cell(p, model, mode, rep)
                        done_n += 1
                        if rec["final_status"] == "llm_error":
                            err_n += 1
                            print(f"  [!] {tag}: llm_error {rec['llm_error'][:80]}")
                        else:
                            print(f"  [+] {tag}: {rec['final_status']} "
                                  f"vulns={rec['vuln_count']} func={rec['functest_status']}")
                    except KeyboardInterrupt:
                        print("\ninterrupted — rerun the same command to resume.")
                        return
                    except Exception as e:
                        err_n += 1
                        print(f"  [X] {tag}: harness error {str(e)[:120]}")

    mins = (time.time() - t0) / 60
    print(f"\ndone: {done_n} ran, {skip_n} skipped (already complete), "
          f"{err_n} errors, {mins:.1f} min")
    print("run `python run_batch.py --report` for the completeness matrix.")


if __name__ == "__main__":
    main()
