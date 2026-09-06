"""
fp_audit.py — build the false-positive audit worksheet (and score it once filled).

WHY THIS EXISTS
---------------
Every vulnerability number in this project rests on Bandit and Semgrep being
right. Static analysers are not always right. `docs/01_RESEARCH_QUESTIONS.md`
therefore requires a stratified 10% sample of findings to be labelled TP/FP
before any RQ result is trusted, with the false-positive rate reported and RQ
interpretations hedged if it exceeds 20%. This script does the mechanical half:
draw a reproducible stratified sample, print the finding *next to the actual
line of code it fired on*, and emit a worksheet ready for labelling.

    python analysis/fp_audit.py --sample            # draw the worksheet
    python analysis/fp_audit.py --sample --pct 10   # a different sample size
    python analysis/fp_audit.py --score             # once labels are filled in

The sample is deterministic (fixed seed + stable sort), so re-running it gives
the same rows and two people can label the same worksheet independently without
coordinating.

LABELLING PROTOCOL
------------------
Open `analysis/output/fp_audit_worksheet.md` and set each row's verdict column to:

    TP   the finding describes a real weakness in that code
    FP   the code is fine; the rule misfired (wrong context, safe sink, test code)
    ?    genuinely unclear — counted separately, never silently as TP

Two annotators should label the SAME worksheet in separate copies
(`..._A.md`, `..._B.md`) so Cohen's kappa is meaningful. `--score` computes the
FP rate and, if both copies exist, kappa. If only one copy exists it says so
explicitly in the output rather than pretending the protocol was followed —
a single-annotator pass is a triage, not an inter-rater reliability measurement,
and the paper must describe it as such.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from database import get_all_runs  # noqa: E402

SEED = 20260907          # fixed so the sample is reproducible for both annotators
OUT = os.path.join(HERE, "output")
WORKSHEET = os.path.join(OUT, "fp_audit_worksheet.md")


def collect_findings():
    """Every finding in the DB, carried with enough context to judge it."""
    rows = []
    for r in get_all_runs():
        code = r.get("clean_code") or ""
        lines = code.split("\n")
        for f in (r.get("scan_results") or []):
            ln = f.get("line", 0) or 0
            snippet = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""
            ctx = "\n".join(lines[max(0, ln - 3):ln + 2]) if lines else ""
            rows.append({
                "run_id": r["id"], "prompt_id": r["prompt_id"], "model": r["model"],
                "mode": r["mode"], "tool": f.get("tool"), "rule": f.get("rule"),
                "cwes": ",".join(f.get("cwes") or []), "severity": f.get("severity"),
                "category": f.get("category"), "line": ln,
                "message": (f.get("message") or "").replace("\n", " ")[:220],
                "code_line": snippet[:200], "context": ctx,
            })
    return rows


def stratified_sample(rows, pct):
    """Stratify by (tool, category) so no analyser or CWE family dominates the sample."""
    rng = random.Random(SEED)
    strata = defaultdict(list)
    for r in rows:
        strata[(r["tool"], r["category"])].append(r)
    target = max(1, round(len(rows) * pct / 100))
    picked = []
    # proportional allocation, at least one per stratum that exists
    for key, group in sorted(strata.items(), key=lambda kv: str(kv[0])):
        group = sorted(group, key=lambda r: (r["run_id"], r["line"], r["rule"]))
        k = max(1, round(len(group) / len(rows) * target))
        picked.extend(rng.sample(group, min(k, len(group))))
    return sorted(picked, key=lambda r: (r["tool"], r["category"], r["run_id"], r["line"]))


def write_worksheet(sample, total, pct):
    os.makedirs(OUT, exist_ok=True)
    by_tool = Counter(r["tool"] for r in sample)
    by_cat = Counter(r["category"] for r in sample)
    L = [
        "# False-positive audit worksheet",
        "",
        f"Sample: **{len(sample)} of {total} findings** ({pct}% target, stratified by "
        f"tool x category, seed `{SEED}` — re-running the sampler reproduces this exact set).",
        f"By tool: {dict(by_tool)} · by category: {dict(by_cat)}",
        "",
        "## How to label",
        "",
        "Set `verdict` on every row to `TP`, `FP`, or `?`. Add a short `why` — one clause is",
        "enough (\"user input reaches the sink\", \"constant string, not attacker-controlled\").",
        "Do not skip rows: an unlabelled row is not the same as `?` and will be reported as",
        "missing, not as agreement.",
        "",
        "Two annotators: copy this file to `fp_audit_worksheet_A.md` and `_B.md`, label",
        "independently (no conferring — that is what makes kappa mean anything), then run",
        "`python analysis/fp_audit.py --score`.",
        "",
        "---",
        "",
    ]
    for i, r in enumerate(sample, 1):
        L += [
            f"### {i}. `{r['tool']}:{r['rule']}` — {r['cwes']} ({r['severity']}) — "
            f"{r['category']}",
            f"- run `{r['run_id']}` · prompt `{r['prompt_id']}` · model `{r['model']}` "
            f"· mode `{r['mode']}` · line {r['line']}",
            f"- message: {r['message']}",
            "",
            "```python",
            r["context"] or r["code_line"] or "(no code captured)",
            "```",
            "",
            "- verdict: `` <!-- TP | FP | ? -->",
            "- why: ",
            "",
        ]
    with open(WORKSHEET, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return WORKSHEET


VERDICT_RE = re.compile(r"^- verdict:\s*`?\s*(TP|FP|\?)?\s*`?", re.I | re.M)


def read_verdicts(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        text = f.read()
    out = []
    for m in VERDICT_RE.finditer(text):
        v = (m.group(1) or "").upper()
        out.append(v if v in ("TP", "FP", "?") else "")
    return out


def cohen_kappa(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x and y]
    if not pairs:
        return None, 0
    cats = sorted({v for p in pairs for v in p})
    n = len(pairs)
    po = sum(1 for x, y in pairs if x == y) / n
    pa = Counter(x for x, _ in pairs)
    pb = Counter(y for _, y in pairs)
    pe = sum((pa[c] / n) * (pb[c] / n) for c in cats)
    if pe == 1:
        return 1.0, n
    return round((po - pe) / (1 - pe), 4), n


def score():
    single = read_verdicts(WORKSHEET)
    a = read_verdicts(WORKSHEET.replace(".md", "_A.md"))
    b = read_verdicts(WORKSHEET.replace(".md", "_B.md"))
    report = {"protocol": None, "fp_rate_pct": None, "kappa": None}

    def rate(labels, who):
        done = [v for v in labels if v]
        if not done:
            print(f"  {who}: no verdicts filled in yet")
            return None
        c = Counter(done)
        fp = round(c["FP"] / len(done) * 100, 1)
        print(f"  {who}: {len(done)}/{len(labels)} labelled · TP={c['TP']} FP={c['FP']} "
              f"?={c['?']} · FP rate = {fp}%")
        return fp

    print("False-positive audit status\n")
    if a and b:
        report["protocol"] = "two-annotator (per docs/01 validity protocol)"
        fa, fb = rate(a, "annotator A"), rate(b, "annotator B")
        k, n = cohen_kappa(a, b)
        report.update({"fp_rate_pct": None if None in (fa, fb) else round((fa + fb) / 2, 1),
                       "kappa": k, "kappa_n": n})
        print(f"\n  Cohen's kappa = {k} over {n} jointly-labelled rows")
    elif single and any(single):
        report["protocol"] = ("SINGLE-ANNOTATOR TRIAGE — not the two-annotator protocol in "
                              "docs/01; report it as triage, no kappa exists")
        report["fp_rate_pct"] = rate(single, "single annotator")
        # ASCII only in console output: Windows terminals default to cp1252 and
        # will raise UnicodeEncodeError on arrows/emoji. Files stay UTF-8.
        print("\n  [!] Only one labelled worksheet found. This is a triage pass, NOT the")
        print("      inter-rater protocol. The paper must say so - there is no kappa here.")
    else:
        print("  No labelled worksheet found. Run with --sample first, then label it.")
        return report

    fp = report["fp_rate_pct"]
    if fp is not None:
        print(f"\n  => false-positive rate: {fp}%")
        if fp > 20:
            print("     ABOVE the 20% threshold in docs/01 - report prominently and hedge "
                  "every RQ interpretation accordingly.")
        else:
            print("     within the 20% threshold in docs/01.")
        # Which rules drive the noise? This is the actionable half: an FP rate is a
        # number, but a ranked list of offending rules is a decision.
        rows = collect_findings()
        by_rule = Counter(f"{r['tool']}:{r['rule']}" for r in rows)
        print("\n  most frequent rules across ALL findings (check the FP-heavy ones "
              "against the worksheet):")
        for rule, n in by_rule.most_common(8):
            print(f"     {n:4d}  {rule}")
        report["rule_frequency"] = dict(by_rule.most_common(20))
    with open(os.path.join(OUT, "fp_audit_result.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    return report


def main():
    ap = argparse.ArgumentParser(description="False-positive audit sampler / scorer")
    ap.add_argument("--sample", action="store_true", help="draw the stratified worksheet")
    ap.add_argument("--score", action="store_true", help="score filled-in worksheets")
    ap.add_argument("--pct", type=float, default=10.0, help="sample percentage (default 10)")
    args = ap.parse_args()

    if args.score:
        score()
        return
    if not args.sample:
        ap.error("choose --sample or --score")

    rows = collect_findings()
    if not rows:
        print("No findings in the database yet — run the experiment first.")
        return
    sample = stratified_sample(rows, args.pct)
    path = write_worksheet(sample, len(rows), args.pct)
    print(f"{len(rows)} findings in DB · sampled {len(sample)} ({args.pct}%)")
    print(f"worksheet: {path}")
    print("Label it, then: python analysis/fp_audit.py --score")


if __name__ == "__main__":
    main()
