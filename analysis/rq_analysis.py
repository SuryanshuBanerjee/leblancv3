"""
rq_analysis.py — the M5 analysis layer. Turns the raw run database into every
number, table, and figure the paper needs. Nothing here is hand-typed; if a
value appears in the paper it came out of this file.

    python analysis/rq_analysis.py                  # analyse the whole DB
    python analysis/rq_analysis.py --models gpt-oss-20b gemini-2.5-flash
    python analysis/rq_analysis.py --out somewhere/ # default: analysis/output/

Free, offline, deterministic, no API calls — it only reads backend/leblanc_v3.db.
Safe to run on partial data: every rate computed from fewer than MIN_N runs is
labelled `insufficient` and is never plotted as though it were a result.

WHAT IT PRODUCES  (in analysis/output/)
    figures/rq1_baseline_vr.png        RQ1 — baseline vulnerability rate per model, Wilson CIs
    figures/rq2_enrichment_delta.png   RQ2 — plain vs enriched, paired, per model
    figures/rq3_convergence.png        RQ3 — repair convergence rate + mean iterations
    figures/rq4_residual_heatmap.png   RQ4 — residual risk, category x generation
    figures/rq5_repair_inflation.png   RQ5 — how often "repaired" code fails its tests
    figures/outcome_breakdown.png      the honest outcome census per model
    tables/rq{1..5}.tex / .md          the same numbers as paper-ready tables
    results.json                       every computed value, machine-readable
    SUMMARY.md                         plain-English readout + decision-band verdicts

THE STATISTICS  (exactly as specified in docs/01_RESEARCH_QUESTIONS.md and
docs/03_METHODOLOGY.md — this file implements that spec, it does not invent one)
    Wilson 95% CIs on every proportion            (backend/metrics.py)
    Exact McNemar on paired plain/enriched        (backend/metrics.py)
    chi-square / Fisher across generation buckets (scipy)
    Mann-Whitney U on iteration counts, G1 vs G3  (scipy)
    Logistic regression: vuln ~ mode * generation + category  (statsmodels)

DECISION BANDS. docs/01 fixes, in advance, what counts as "yes" / "mixed" / "no"
per RQ. Those thresholds are encoded in BANDS below and applied mechanically, so
the verdict cannot drift to suit the data after the fact. A band verdict on an
`insufficient` cell is reported as "not enough data", never as a verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))

import matplotlib
matplotlib.use("Agg")  # no display needed; write PNGs straight to disk
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from database import get_all_runs                      # noqa: E402
from llm_client import MODEL_CONFIGS                   # noqa: E402
from metrics import MIN_N, compute_all, wilson_ci, mcnemar_exact  # noqa: E402

# ---------------------------------------------------------------- presentation
# Same validated palette the dashboard uses (see frontend/index.html): the
# generation buckets get categorical identity colours, NOT a red-to-green
# quality gradient — G1 is not "bad" for being older, and a palette that
# implies otherwise would prejudge RQ1.
GEN_COLOR = {"G1": "#2a78d6", "G2": "#eb6834", "G3": "#1baf7a", "?": "#898781"}
INK, INK_2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
RISK_RED, VIOLET = "#a32b2b", "#4a3aa7"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "grid.color": GRID,
    "font.family": "sans-serif", "font.size": 10, "axes.grid": True,
    "axes.axisbelow": True, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "figure.dpi": 140,
})

# ------------------------------------------------------------- decision bands
# Verbatim from docs/01_RESEARCH_QUESTIONS.md § "How to read a result".
BANDS = {
    "rq1": {"metric": "VR(G1) - VR(G3), percentage points",
            "yes": "gap >= 20pp AND ordering G1 >= G2 >= G3 holds",
            "mixed": "gap 10-20pp, or ordering roughly right but noisy",
            "no": "gap < 10pp, or ordering scrambled (itself a finding)"},
    "rq2": {"metric": "delta-E(model), paired plain vs enriched",
            "yes": "delta-E(G1) >= 15pp AND McNemar p < 0.05",
            "mixed": "positive and significant but under 15pp",
            "no": "delta-E(G3) < 5pp — expected; this IS 'yes' for the obsolescence half of H2"},
    "rq3": {"metric": "CR(model), IT(model)",
            "yes": "CR(G3) - CR(G1) >= 15pp AND IT(G3) < IT(G1)",
            "mixed": "CR/IT roughly flat across generations",
            "no": "CR(G1) > CR(G3) — a reversal; investigate before writing a headline"},
    "rq4": {"metric": "RVR(category, G3)",
            "yes": "< 10% — essentially solved",
            "mixed": "10-30% — partially mitigated",
            "no": ">= 30% — a real unsolved risk category (the practitioner payoff)"},
    "rq5": {"metric": "RIR(model)",
            "yes": ">= 15% — H5 confirmed, naive repair metrics overstate reality",
            "mixed": "5-15% — real but not dramatic",
            "no": "< 5% — repair claims are basically trustworthy for this model"},
}


def _verdict(rq: str, value, extra=None) -> str:
    """Mechanically apply the pre-registered band. Returns 'yes'|'mixed'|'no'|'insufficient'."""
    if value is None:
        return "insufficient"
    if rq == "rq1":
        ordered = bool(extra)
        if value >= 20 and ordered:
            return "yes"
        return "mixed" if 10 <= value < 20 else "no"
    if rq == "rq2":
        p = extra
        if value >= 15 and p is not None and p < 0.05:
            return "yes"
        if value > 0 and p is not None and p < 0.05:
            return "mixed"
        return "no"
    if rq == "rq3":
        return "yes" if value >= 15 else ("no" if value < 0 else "mixed")
    if rq == "rq4":
        return "yes" if value < 10 else ("mixed" if value < 30 else "no")
    if rq == "rq5":
        return "yes" if value >= 15 else ("mixed" if value >= 5 else "no")
    return "insufficient"


# ------------------------------------------------------------------ data prep
def load_frame(models=None) -> pd.DataFrame:
    """One row per run, with the derived booleans the RQs are defined on."""
    runs = get_all_runs()
    if models:
        runs = [r for r in runs if r["model"] in models]
    gens = {m: c["gen"] for m, c in MODEL_CONFIGS.items()}
    rows = []
    for r in runs:
        rr = r.get("repair_result") or {}
        # "valid" mirrors metrics._valid: llm_error and extraction_failed runs are
        # excluded from vulnerability-rate denominators and reported separately.
        valid = r["final_status"] not in ("llm_error", "extraction_failed")
        vuln_initial = (r["vuln_count"] or 0) > 0
        if r["mode"] == "enriched_repair" and rr:
            vuln_final = rr.get("final_status") != "clean" and vuln_initial
        else:
            vuln_final = vuln_initial
        rows.append({
            "id": r["id"], "prompt_id": r["prompt_id"], "model": r["model"],
            "generation": gens.get(r["model"], "?"), "mode": r["mode"],
            "rep": r["rep"], "category": r["category"] or "Other",
            "valid": valid, "final_status": r["final_status"],
            "vuln_initial": vuln_initial, "vuln_final": vuln_final,
            "vuln_count": r["vuln_count"] or 0,
            "repair_status": rr.get("final_status"),
            "iterations": r["total_iterations"] or 0,
            "functest": r["functest_status"] or "",
            "scanners": "+".join(r.get("scanners") or []),
        })
    return pd.DataFrame(rows)


# -------------------------------------------------------------------- figures
def _annotate_bars(ax, bars, values, suffix="%"):
    for b, v in zip(bars, values):
        if v is None:
            continue
        ax.annotate(f"{v:.1f}{suffix}", (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=8.5, color=INK_2,
                    xytext=(0, 2), textcoords="offset points")


def fig_rq1(m, outdir):
    """RQ1 figure: baseline vulnerability rate per model with Wilson error bars."""
    per = {k: v for k, v in m["rq1"]["per_model"].items() if v["rate"] is not None}
    if not per:
        return None
    names = list(per)
    rates = [per[n]["rate"] for n in names]
    lo = [max(0, per[n]["rate"] - (per[n]["ci"][0] or per[n]["rate"])) for n in names]
    hi = [max(0, (per[n]["ci"][1] or per[n]["rate"]) - per[n]["rate"]) for n in names]
    colors = [GEN_COLOR.get(per[n]["gen"], MUTED) for n in names]

    fig, ax = plt.subplots(figsize=(7.2, 4))
    bars = ax.bar(names, rates, color=colors, width=0.6)
    ax.errorbar(names, rates, yerr=[lo, hi], fmt="none", ecolor=INK_2, capsize=4, lw=1.1)
    _annotate_bars(ax, bars, rates)
    ax.set_ylabel("vulnerability rate, plain prompts (%)")
    ax.set_ylim(0, 100)
    ax.set_title("RQ1 — baseline vulnerability rate per model (Wilson 95% CI)",
                 loc="left", fontsize=11, color=INK)
    for n, lbl in zip(names, [per[n]["gen"] for n in names]):
        ax.annotate(lbl, (n, 0), xytext=(0, -28), textcoords="offset points",
                    ha="center", fontsize=8, color=MUTED)
    plt.xticks(rotation=12, ha="right")
    fig.tight_layout()
    p = os.path.join(outdir, "figures", "rq1_baseline_vr.png")
    fig.savefig(p); plt.close(fig)
    return p


def fig_rq2(m, outdir):
    """RQ2 figure: paired plain-vs-enriched bars, annotated with delta and significance."""
    per = {k: v for k, v in m["rq2"]["per_model"].items() if v["delta_pp"] is not None}
    if not per:
        return None
    names = list(per)
    x = np.arange(len(names))
    plain = [per[n]["vr_plain"] for n in names]
    enr = [per[n]["vr_enriched"] for n in names]

    fig, ax = plt.subplots(figsize=(8, 4.2))
    b1 = ax.bar(x - 0.2, plain, 0.38, label="plain", color=MUTED)
    b2 = ax.bar(x + 0.2, enr, 0.38, label="enriched",
                color=[GEN_COLOR.get(per[n]["gen"], MUTED) for n in names])
    _annotate_bars(ax, b1, plain); _annotate_bars(ax, b2, enr)
    for i, n in enumerate(names):
        d, p = per[n]["delta_pp"], per[n]["mcnemar_p"]
        sig = "" if p is None else (" *" if p < 0.05 else "")
        ax.annotate(f"Δ{d:+.1f}pp{sig}", (i, max(plain[i], enr[i])), xytext=(0, 16),
                    textcoords="offset points", ha="center", fontsize=8.5,
                    color=INK if not sig else VIOLET, weight="bold" if sig else "normal")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=12, ha="right")
    ax.set_ylabel("vulnerability rate (%)"); ax.set_ylim(0, 105)
    ax.set_title("RQ2 — does CWE-aware enrichment still help?  (* = McNemar p < 0.05)",
                 loc="left", fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    p = os.path.join(outdir, "figures", "rq2_enrichment_delta.png")
    fig.savefig(p); plt.close(fig)
    return p


def fig_rq3(m, outdir):
    """RQ3 figure: convergence rate and mean iterations, side by side against the 3-round cap."""
    per = {k: v for k, v in m["rq3"]["per_model"].items() if v["convergence_rate"] is not None}
    if not per:
        return None
    names = list(per)
    cr = [per[n]["convergence_rate"] for n in names]
    it = [per[n]["avg_iterations"] or 0 for n in names]
    colors = [GEN_COLOR.get(per[n]["gen"], MUTED) for n in names]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    b = a1.bar(names, cr, color=colors, width=0.6); _annotate_bars(a1, b, cr)
    a1.set_ylabel("convergence rate (%)"); a1.set_ylim(0, 100)
    a1.set_title("repair reaches scanner-clean", loc="left", fontsize=10.5, color=INK)
    b2 = a2.bar(names, it, color=colors, width=0.6); _annotate_bars(a2, b2, it, suffix="")
    a2.set_ylabel("mean iterations (converged runs)"); a2.set_ylim(0, 3.2)
    a2.axhline(3, color=RISK_RED, lw=1, ls="--")
    a2.annotate("3-iteration cap", (0, 3), xytext=(4, 4), textcoords="offset points",
                fontsize=8, color=RISK_RED)
    a2.set_title("how many rounds it takes", loc="left", fontsize=10.5, color=INK)
    for ax in (a1, a2):
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=12, ha="right")
    fig.suptitle("RQ3 — does scanner-guided repair converge, and how fast?",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    p = os.path.join(outdir, "figures", "rq3_convergence.png")
    fig.savefig(p); plt.close(fig)
    return p


def fig_rq4(m, outdir):
    """RQ4 figure: category x generation residual-risk heatmap, single-hue red ramp.

    Cells below MIN_N are marked with an asterisk rather than hidden — a pale cell
    that means "no data" must not read as a cell that means "no risk".
    """
    grid, cats, gens = m["rq4"]["grid"], m["rq4"]["categories"], m["rq4"]["generations"]
    if not cats:
        return None
    mat = np.full((len(cats), len(gens)), np.nan)
    for i, c in enumerate(cats):
        for j, g in enumerate(gens):
            r = grid[c][g]["rate"]
            if r is not None:
                mat[i, j] = r

    fig, ax = plt.subplots(figsize=(1.9 * len(gens) + 3.2, 0.62 * len(cats) + 2.2))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("risk", ["#ffffff", RISK_RED])
    im = ax.imshow(mat, cmap=cmap, vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(gens))); ax.set_xticklabels(gens)
    ax.set_yticks(range(len(cats))); ax.set_yticklabels(cats)
    ax.grid(False)
    for i, c in enumerate(cats):
        for j, g in enumerate(gens):
            cell = grid[c][g]
            txt = "—" if cell["rate"] is None else f"{cell['rate']:.0f}%"
            sub = f"n={cell['n']}" + ("*" if cell["insufficient"] else "")
            val = 0 if np.isnan(mat[i, j]) else mat[i, j]
            col = "white" if val > 45 else INK
            ax.annotate(f"{txt}\n{sub}", (j, i), ha="center", va="center",
                        fontsize=9, color=col)
    ax.set_title("RQ4 — residual vulnerability after the FULL loop (enrichment + repair)\n"
                 "redder = still failing; * = below MIN_N, not a verdict",
                 loc="left", fontsize=10.5, color=INK)
    fig.colorbar(im, ax=ax, label="residual vulnerability rate (%)", fraction=0.035)
    fig.tight_layout()
    p = os.path.join(outdir, "figures", "rq4_residual_heatmap.png")
    fig.savefig(p); plt.close(fig)
    return p


def fig_rq5(m, outdir):
    """RQ5 figure: repair inflation per model against the 15% H5 threshold."""
    per = {k: v for k, v in m["rq5"]["per_model"].items()
           if v["repair_inflation_rate"] is not None}
    if not per:
        return None
    names = list(per)
    rir = [per[n]["repair_inflation_rate"] for n in names]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    bars = ax.bar(names, rir, color=VIOLET, width=0.6)
    _annotate_bars(ax, bars, rir)
    ax.axhline(15, color=RISK_RED, lw=1, ls="--")
    ax.annotate("H5 threshold (15%)", (0, 15), xytext=(4, 4), textcoords="offset points",
                fontsize=8, color=RISK_RED)
    ax.set_ylabel("repair inflation rate (%)")
    ax.set_ylim(0, max(40, max(rir) * 1.25 if rir else 40))
    ax.set_title("RQ5 — how often is a scanner-clean 'repair' functionally broken?",
                 loc="left", fontsize=11, color=INK)
    for i, n in enumerate(names):
        ax.annotate(f"n={per[n]['functionally_tested']} tested",
                    (i, 0), xytext=(0, -30), textcoords="offset points",
                    ha="center", fontsize=8, color=MUTED)
    plt.xticks(rotation=12, ha="right")
    fig.tight_layout()
    p = os.path.join(outdir, "figures", "rq5_repair_inflation.png")
    fig.savefig(p); plt.close(fig)
    return p


def fig_outcomes(df, outdir):
    """The honest census: every outcome class per model, nothing folded together."""
    if df.empty:
        return None
    order = ["clean", "vulnerable", "not_converged", "extraction_failed", "llm_error"]
    colors = {"clean": "#1baf7a", "vulnerable": RISK_RED, "not_converged": "#eb6834",
              "extraction_failed": "#fab219", "llm_error": MUTED}
    piv = (df.groupby(["model", "final_status"]).size().unstack(fill_value=0))
    for c in order:
        if c not in piv.columns:
            piv[c] = 0
    piv = piv[[c for c in order if c in piv.columns]]

    fig, ax = plt.subplots(figsize=(8, 4.2))
    bottom = np.zeros(len(piv))
    for c in piv.columns:
        ax.bar(piv.index, piv[c], bottom=bottom, label=c, color=colors.get(c, MUTED), width=0.6)
        bottom += piv[c].values
    ax.set_ylabel("runs"); ax.legend(frameon=False, fontsize=8.5, ncol=3)
    ax.set_title("Outcome census per model — failure classes are never folded into 'clean'",
                 loc="left", fontsize=11, color=INK)
    plt.xticks(rotation=12, ha="right")
    fig.tight_layout()
    p = os.path.join(outdir, "figures", "outcome_breakdown.png")
    fig.savefig(p); plt.close(fig)
    return p


# ----------------------------------------------------------------- statistics
def gen_contingency_test(df, value_col="vuln_initial", mode="plain"):
    """chi-square across generation buckets; Fisher if any expected cell is small."""
    sub = df[(df["mode"] == mode) & df["valid"]]
    if sub.empty:
        return {"test": None, "note": f"no valid {mode}-mode runs"}
    table = pd.crosstab(sub["generation"], sub[value_col])
    if table.shape[0] < 2 or table.shape[1] < 2:
        return {"test": None, "note": "need >= 2 generations and both outcomes present"}
    chi2, p, dof, expected = stats.chi2_contingency(table)
    small = bool((expected < 5).any())
    out = {"test": "chi2", "chi2": round(float(chi2), 3), "p": round(float(p), 4),
           "dof": int(dof), "small_expected_cells": small,
           "table": table.to_dict()}
    if small and table.shape == (2, 2):
        _, pf = stats.fisher_exact(table.values)
        out.update({"test": "fisher_exact (2x2, small cells)", "p": round(float(pf), 4)})
    return out


def iterations_mannwhitney(df, g_a="G1", g_b="G3"):
    """Mann-Whitney U on iterations-to-converge, oldest vs newest bucket."""
    conv = df[(df["mode"] == "enriched_repair") & (df["repair_status"] == "clean")]
    a = conv[conv["generation"] == g_a]["iterations"].dropna()
    b = conv[conv["generation"] == g_b]["iterations"].dropna()
    if len(a) < 3 or len(b) < 3:
        return {"test": None, "note": f"need >= 3 converged runs each; have {len(a)} / {len(b)}"}
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {"test": "mann-whitney U", "U": float(u), "p": round(float(p), 4),
            f"median_{g_a}": float(a.median()), f"median_{g_b}": float(b.median()),
            f"n_{g_a}": int(len(a)), f"n_{g_b}": int(len(b))}


# Rule families the false-positive audit identified as systematically noisy for
# THIS study's question (analysis/fp_audit_pilot_triage.md, 2026-09-07). They are
# excluded only in the sensitivity analysis, never silently from the headline:
#   B413                        Bandit cannot distinguish maintained pycryptodome from
#                               abandoned pycrypto — both import as `Crypto`
#   B104 / avoid_app_run_...    binding 0.0.0.0 is correct and required in a container
#   insufficient-rsa-key-size   demands >=3072; RSA-2048 is NIST-acceptable to 2030
NOISY_RULES = {
    "bandit:B413",
    "bandit:B104", "semgrep:avoid_app_run_with_bad_host",
    "semgrep:insufficient-rsa-key-size",
}

SCAFFOLD_RE = re.compile(r"app\.run\(|if\s+__name__\s*==")


def benjamini_hochberg(pvals, alpha=0.05):
    """FDR correction over a family of tests.

    We run one McNemar per model for RQ2 and a Fisher per cell for RQ4. With six
    models and a dozen category cells, the chance of at least one p < 0.05 arising
    from nothing is substantial, and reporting the surviving one as "significant"
    is the oldest mistake in applied statistics. Benjamini-Hochberg controls the
    false-discovery rate across the family and is the right instrument here (less
    brutal than Bonferroni, which would cost us real effects at this sample size).

    Returns (adjusted_pvals, rejected_flags) aligned with the input order; None
    entries pass through untouched.
    """
    idx = [i for i, p in enumerate(pvals) if p is not None]
    if not idx:
        return list(pvals), [False] * len(pvals)
    m = len(idx)
    ordered = sorted(idx, key=lambda i: pvals[i])
    adj = list(pvals)
    prev = 1.0
    for rank, i in enumerate(reversed(ordered), start=1):
        k = m - rank + 1
        val = min(prev, pvals[i] * m / k)
        adj[i] = round(min(1.0, val), 4)
        prev = val
    return adj, [adj[i] is not None and adj[i] < alpha if i in idx else False
                 for i in range(len(pvals))]


def cluster_bootstrap_ci(df, value_col, n_boot=2000, seed=20260907):
    """95% CI that respects the fact that repetitions are nested inside prompts.

    Wilson intervals assume independent observations. Ours are not: 3 repetitions
    of the same prompt are 3 looks at the same task, so the effective sample size
    is closer to the 50 prompts than to the 150 runs. Treating them as independent
    makes every interval too narrow and every p-value too small — a real
    overstatement of confidence, and exactly the kind of thing a methods reviewer
    checks for. Resampling whole PROMPTS (not runs) with replacement gives an
    interval that carries the clustering honestly.
    """
    if df.empty:
        return None, None, None
    rng = np.random.default_rng(seed)
    prompts = df["prompt_id"].unique()
    groups = {p: df.loc[df["prompt_id"] == p, value_col].to_numpy() for p in prompts}
    point = float(df[value_col].mean()) * 100
    boots = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.choice(prompts, size=len(prompts), replace=True)
        vals = np.concatenate([groups[p] for p in pick])
        boots[b] = vals.mean()
    lo, hi = np.percentile(boots, [2.5, 97.5]) * 100
    return round(point, 1), round(float(lo), 1), round(float(hi), 1)


def clustered_rates(df):
    """Per-model baseline vulnerability rate with prompt-clustered CIs, next to
    the naive Wilson interval, so the difference is visible rather than assumed
    away."""
    out = {}
    plain = df[(df["mode"] == "plain") & df["valid"]]
    for m, sub in plain.groupby("model"):
        k = int(sub["vuln_initial"].sum())
        n = int(len(sub))
        w_rate, w_lo, w_hi = wilson_ci(k, n)
        c_rate, c_lo, c_hi = cluster_bootstrap_ci(sub.assign(v=sub["vuln_initial"].astype(int)), "v")
        naive_w = None if None in (w_lo, w_hi) else round(w_hi - w_lo, 1)
        clust_w = None if None in (c_lo, c_hi) else round(c_hi - c_lo, 1)
        out[m] = {
            "n_runs": n, "n_prompts": int(sub["prompt_id"].nunique()),
            "rate": w_rate,
            "wilson_ci": [w_lo, w_hi], "wilson_width_pp": naive_w,
            "cluster_bootstrap_ci": [c_lo, c_hi], "cluster_width_pp": clust_w,
            "widening_pp": None if None in (naive_w, clust_w) else round(clust_w - naive_w, 1),
        }
    return {"per_model": out,
            "reading": "cluster_bootstrap_ci is the honest interval; wilson_ci assumes the "
                       "repetitions are independent observations, which they are not. If the "
                       "widening is large, quote the clustered interval in the paper."}


def extraction_sensitivity(df):
    """How much does the treatment of extraction failures move RQ1?

    Extraction failures are excluded from the vulnerability-rate denominator (a
    model that emitted unparseable text produced no code to judge). That is
    defensible, but it is a CHOICE, and it is not neutral when the failure rate
    differs sharply by model: in the pilot, gemini-2.5-flash failed extraction on
    ~31% of runs against ~3% for the gpt-oss pair, so it is being graded on the
    subset of its output that parsed. If parseability correlates with task
    difficulty, that flatters it.

    So report all three conventions and let the reader see the spread:
      excluded          — the headline convention
      counted_clean     — most generous to the failing model
      counted_vulnerable— most punitive
    """
    out = {}
    for m, sub in df[df["mode"] == "plain"].groupby("model"):
        ef = sub[sub["final_status"] == "extraction_failed"]
        valid = sub[sub["valid"]]
        k, n = int(valid["vuln_initial"].sum()), int(len(valid))
        n_all = int(len(sub))
        out[m] = {
            "extraction_failures": int(len(ef)),
            "extraction_failure_pct": round(len(ef) / n_all * 100, 1) if n_all else None,
            "vr_excluded": wilson_ci(k, n)[0],
            "vr_failures_counted_clean": wilson_ci(k, n_all)[0],
            "vr_failures_counted_vulnerable": wilson_ci(k + len(ef), n_all)[0],
        }
    spread = [v["vr_failures_counted_vulnerable"] - v["vr_excluded"]
              for v in out.values()
              if None not in (v["vr_failures_counted_vulnerable"], v["vr_excluded"])]
    return {"per_model": out,
            "max_spread_pp": round(max(spread), 1) if spread else None,
            "reading": "If max_spread_pp is large, RQ1's model ordering depends on a "
                       "methodological choice rather than on the models, and the paper must "
                       "report the ordering under all three conventions."}


def rule_sensitivity(df):
    """Vulnerability rate recomputed with the noisy and scaffolding findings removed.

    Two independent problems, deliberately separated:
      NOISY   — rules the FP audit judged wrong for our question (false positives)
      SCAFFOLD— findings on `app.run(...)` / `__main__` lines: real weaknesses, but
                in the demo runner the model volunteers, not in the function that
                was requested. Whether they count is a question about what the
                study measures, not about whether the analyser was right.
    """
    runs = {r["id"]: r for r in get_all_runs()}
    variants = {"headline": 0, "excl_noisy": 0, "excl_scaffold": 0, "excl_both": 0}
    per_model = {}
    for _, row in df[(df["mode"] == "plain") & df["valid"]].iterrows():
        r = runs.get(row["id"])
        if r is None:
            continue
        code = (r.get("clean_code") or "").split("\n")
        keeps = {k: False for k in variants}
        for f in (r.get("scan_results") or []):
            rule = f"{f.get('tool')}:{f.get('rule')}"
            ln = f.get("line", 0) or 0
            line_txt = code[ln - 1] if 0 < ln <= len(code) else ""
            noisy = any(part in NOISY_RULES
                        for part in [rule] + [f"{t}:{f.get('rule')}"
                                              for t in str(f.get("tool", "")).split("+")])
            scaffold = bool(SCAFFOLD_RE.search(line_txt))
            keeps["headline"] = True
            if not noisy:
                keeps["excl_noisy"] = True
            if not scaffold:
                keeps["excl_scaffold"] = True
            if not noisy and not scaffold:
                keeps["excl_both"] = True
        d = per_model.setdefault(row["model"], {k: [0, 0] for k in variants})
        for k in variants:
            d[k][1] += 1
            if keeps[k]:
                d[k][0] += 1

    out = {}
    for m, d in per_model.items():
        out[m] = {k: {"vulnerable": kk, "n": nn, "rate": wilson_ci(kk, nn)[0]}
                  for k, (kk, nn) in d.items()}
        base = out[m]["headline"]["rate"]
        both = out[m]["excl_both"]["rate"]
        out[m]["drop_pp"] = None if None in (base, both) else round(base - both, 1)
    return {"per_model": out, "noisy_rules_excluded": sorted(NOISY_RULES),
            "reading": "excl_both is the conservative rate: only findings that are neither "
                       "audit-flagged noise nor located in volunteered scaffolding. If it is "
                       "far below the headline, say so in the abstract, not just in Threats."}


def finding_composition(limit=10):
    """What is the vulnerability rate actually made of?

    A rate of "60% of runs are vulnerable" means something very different if 80%
    of the underlying findings are one noisy rule firing on the `app.run(...)`
    boilerplate the model appends after answering, rather than on the function the
    prompt asked for. This breaks the findings down by rule so that is visible
    instead of buried, and separately counts findings that landed on a
    `__main__` / `app.run` scaffolding line.
    """
    from collections import Counter as C
    rows = []
    for r in get_all_runs():
        code = (r.get("clean_code") or "").split("\n")
        for f in (r.get("scan_results") or []):
            ln = f.get("line", 0) or 0
            line_txt = code[ln - 1] if 0 < ln <= len(code) else ""
            # scaffolding = the demo runner an LLM tacks on, not the answer itself
            scaffold = bool(re.search(r"app\.run\(|if\s+__name__\s*==", line_txt))
            rows.append({"rule": f"{f.get('tool')}:{f.get('rule')}",
                         "cwes": ",".join(f.get("cwes") or []),
                         "severity": f.get("severity"), "scaffold": scaffold})
    if not rows:
        return {"total_findings": 0}
    total = len(rows)
    by_rule = C(r["rule"] for r in rows)
    scaffold_n = sum(1 for r in rows if r["scaffold"])
    return {
        "total_findings": total,
        "top_rules": [{"rule": k, "n": v, "pct": round(v / total * 100, 1)}
                      for k, v in by_rule.most_common(limit)],
        "top3_share_pct": round(sum(v for _, v in by_rule.most_common(3)) / total * 100, 1),
        "on_scaffolding_lines": scaffold_n,
        "on_scaffolding_pct": round(scaffold_n / total * 100, 1),
        "reading": "Findings on app.run()/__main__ scaffolding are weaknesses in code the "
                   "model volunteered, not in the function the prompt asked for. Report "
                   "them, but say which they are — a reviewer will ask.",
    }


def logistic_model(df):
    """The headline model from docs/03: vuln ~ mode * generation + category."""
    sub = df[df["valid"]].copy()
    if sub.empty or sub["mode"].nunique() < 2 or sub["generation"].nunique() < 2:
        return {"fitted": False, "note": "need >= 2 modes and >= 2 generation buckets"}
    sub["y"] = sub["vuln_final"].astype(int)
    if sub["y"].nunique() < 2:
        return {"fitted": False, "note": "outcome has no variance (all runs identical)"}
    try:
        import statsmodels.formula.api as smf
        # Cluster-robust by prompt: the 3 repetitions of a prompt are not three
        # independent draws, and default standard errors would treat them as such,
        # producing p-values that are too small. Falls back to classical SEs only
        # if the clustered fit fails, and says which was used.
        cov = {"cov_type": "cluster", "cov_kwds": {"groups": sub["prompt_id"]}}
        try:
            fit = smf.logit("y ~ C(mode) * C(generation) + C(category)",
                            data=sub).fit(disp=False, **cov)
            se_kind = "cluster-robust by prompt_id"
        except Exception:
            fit = smf.logit("y ~ C(mode) * C(generation) + C(category)", data=sub).fit(disp=False)
            se_kind = "classical (clustered fit failed — treat p-values as optimistic)"
        # A logit that hit the iteration limit still returns coefficients — they are
        # just not trustworthy (usually perfect separation from sparse cells, i.e.
        # some mode/generation/category combination is all-vulnerable or all-clean).
        # Report that loudly instead of letting unstable numbers reach the paper.
        converged = bool(fit.mle_retvals.get("converged", True))
        if not converged:
            return {"fitted": False, "converged": False,
                    "note": "maximum-likelihood optimisation did not converge — almost "
                            "always perfect separation from too few runs per cell. "
                            "Re-run after the full 3-rep experiment; do NOT report these "
                            "coefficients.",
                    "n": int(fit.nobs)}
        return {"fitted": True, "converged": True, "n": int(fit.nobs),
                "standard_errors": se_kind,
                "n_clusters": int(sub["prompt_id"].nunique()),
                "pseudo_r2": round(float(fit.prsquared), 4),
                "coefficients": {k: round(float(v), 4) for k, v in fit.params.items()},
                "p_values": {k: round(float(v), 4) for k, v in fit.pvalues.items()},
                "odds_ratios": {k: round(float(np.exp(v)), 4) for k, v in fit.params.items()},
                "summary_text": str(fit.summary())}
    except Exception as e:  # separation, singular design matrix, sparse cells...
        return {"fitted": False, "note": f"model did not fit: {type(e).__name__}: {e}"}


def secure_vs_securepass(df):
    """RQ5's paired view: static-clean vs static-clean-AND-tests-pass (McNemar).

    Reported in two slices, because they answer different questions and conflating
    them would overstate RQ5:

      repaired_only  — runs where Engine C actually ran at least one repair round.
                       This is the RQ5 claim proper: "the repair broke it."
      all_repair_mode — every enriched_repair run, including code that was already
                       clean and never touched by Engine C. A gap here that is
                       absent in `repaired_only` means our functional tests are
                       strict (or the prompt is hard), NOT that repair does damage.
    """
    def slice_stats(sub, label):
        if sub.empty:
            return {"label": label, "test": None, "note": "no functionally-tested runs in this slice"}
        secure = ~sub["vuln_final"]
        secure_pass = secure & (sub["functest"] == "pass")
        b = int((secure & ~secure_pass).sum())   # scanner-clean but functionally broken
        c = int((~secure & secure_pass).sum())   # impossible by construction; sanity check
        return {"label": label, "test": "exact McNemar (secure vs secure-pass)",
                "n": int(len(sub)), "secure": int(secure.sum()),
                "secure_pass": int(secure_pass.sum()), "secure_but_broken": b,
                "impossible_cell_c": c, "p": mcnemar_exact(b, c),
                "secure_but_broken_pct": round(b / int(secure.sum()) * 100, 1)
                if int(secure.sum()) else None}

    tested = df[(df["mode"] == "enriched_repair") & df["valid"] &
                (df["functest"].isin(["pass", "fail", "timeout"]))].copy()
    return {"repaired_only": slice_stats(tested[tested["iterations"] > 0], "repaired_only"),
            "all_repair_mode": slice_stats(tested, "all_repair_mode")}


def repair_attribution(df):
    """Isolate what the REPAIR is responsible for — the control RQ5 needs.

    Raw RIR ("scanner-clean code that fails its test, after repair") is not by
    itself evidence that repair broke anything: code the model wrote clean on the
    first try, with Engine C never invoked, also fails functional tests at some
    baseline rate (strict tests, hard prompts, sandbox mismatches). The honest
    quantity is the DIFFERENCE:

        attributable = P(fail | clean, repaired) - P(fail | clean, never repaired)

    Report the raw rate for comparability with prior work if you like, but the
    attributable figure is the one that supports the causal claim in the title.
    A near-zero attributable gap with a high raw rate means the finding is
    "scanner-clean code is often broken", NOT "repair breaks code" — still
    publishable, but a different sentence.
    """
    t = df[df["valid"] & df["functest"].isin(["pass", "fail", "timeout"])].copy()
    if t.empty:
        return {"note": "no functionally-tested runs yet"}
    clean = t[~t["vuln_final"]]
    repaired = clean[(clean["mode"] == "enriched_repair") & (clean["iterations"] > 0)]
    untouched = clean[(clean["mode"] != "enriched_repair") | (clean["iterations"] == 0)]

    def rate(sub):
        if sub.empty:
            return None, 0, 0
        broken = int((sub["functest"] != "pass").sum())
        return round(broken / len(sub) * 100, 1), broken, int(len(sub))

    r_rep, b_rep, n_rep = rate(repaired)
    r_unt, b_unt, n_unt = rate(untouched)
    attributable = None if (r_rep is None or r_unt is None) else round(r_rep - r_unt, 1)

    fisher_p = None
    if n_rep and n_unt:
        _, fisher_p = stats.fisher_exact([[b_rep, n_rep - b_rep], [b_unt, n_unt - b_unt]])
        fisher_p = round(float(fisher_p), 4)

    return {"repaired_clean_broken_pct": r_rep, "repaired_n": n_rep,
            "never_repaired_clean_broken_pct": r_unt, "never_repaired_n": n_unt,
            "attributable_to_repair_pp": attributable, "fisher_p": fisher_p,
            "insufficient": (n_rep < MIN_N or n_unt < MIN_N),
            "reading": "attributable_to_repair_pp is the causal RQ5 quantity; the raw "
                       "repaired rate alone is not evidence that repair caused the breakage"}


# --------------------------------------------------------------------- tables
def _table(headers, rows, title):
    md = [f"**{title}**", "", "| " + " | ".join(headers) + " |",
          "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        md.append("| " + " | ".join("—" if v is None else str(v) for v in r) + " |")
    col = "l" + "r" * (len(headers) - 1)
    tex = ["\\begin{table}[t]", "\\centering", f"\\caption{{{title}}}",
           f"\\begin{{tabular}}{{{col}}}", "\\toprule",
           " & ".join(h.replace("%", "\\%").replace("_", "\\_") for h in headers) + " \\\\",
           "\\midrule"]
    for r in rows:
        tex.append(" & ".join("--" if v is None else str(v).replace("%", "\\%").replace("_", "\\_")
                              for v in r) + " \\\\")
    tex += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    return "\n".join(md) + "\n", "\n".join(tex) + "\n"


def write_tables(m, outdir, tests=None):
    """Emit every RQ table as both LaTeX (for the paper) and Markdown (for docs).

    Same numbers, two renderings, one source — so a table in the paper and a table
    in the README cannot disagree.
    """
    t = os.path.join(outdir, "tables")
    specs = []

    rows = [[n, v["gen"], v["n"], v["vulnerable"], v["rate"],
             f'[{v["ci"][0]}, {v["ci"][1]}]' if v["ci"][0] is not None else None,
             "yes" if v["insufficient"] else ""]
            for n, v in m["rq1"]["per_model"].items()]
    specs.append(("rq1", ["Model", "Gen", "n", "Vulnerable", "VR (%)", "95% CI", "Low n"], rows,
                  "RQ1 --- baseline vulnerability rate on plain prompts"))

    rows = [[n, v["gen"], v["paired_n"], v["vr_plain"], v["vr_enriched"], v["delta_pp"],
             v["mcnemar_p"], v["discordant"]["fixed_by_enrichment"],
             v["discordant"]["broken_by_enrichment"]]
            for n, v in m["rq2"]["per_model"].items()]
    specs.append(("rq2", ["Model", "Gen", "Pairs", "VR plain (%)", "VR enriched (%)",
                          "delta-E (pp)", "McNemar p", "Fixed", "Broken"], rows,
                  "RQ2 --- effect of CWE-aware enrichment, paired by (prompt, rep)"))

    rows = [[n, v["gen"], v["initially_vulnerable"], v["converged"], v["convergence_rate"],
             f'[{v["ci"][0]}, {v["ci"][1]}]' if v["ci"][0] is not None else None,
             v["avg_iterations"]]
            for n, v in m["rq3"]["per_model"].items()]
    specs.append(("rq3", ["Model", "Gen", "Vulnerable starts", "Converged", "CR (%)",
                          "95% CI", "Mean iters"], rows,
                  "RQ3 --- convergence of the scanner-guided repair loop (cap = 3)"))

    rows = []
    for cat in m["rq4"]["categories"]:
        for g in m["rq4"]["generations"]:
            c = m["rq4"]["grid"][cat][g]
            rows.append([cat, g, c["n"], c["residual_vuln"], c["rate"],
                         "yes" if c["insufficient"] else ""])
    specs.append(("rq4", ["Category", "Gen", "n", "Still vulnerable", "RVR (%)", "Low n"], rows,
                  "RQ4 --- residual risk after full scaffolding, by category and generation"))

    rows = [[n, v["gen"], v["repair_success_claims"], v["functionally_tested"],
             v["secretly_broken"], v["repair_inflation_rate"],
             f'[{v["ci"][0]}, {v["ci"][1]}]' if v["ci"][0] is not None else None,
             v["awaiting_tests"]]
            for n, v in m["rq5"]["per_model"].items()]
    specs.append(("rq5", ["Model", "Gen", "Repair claims", "Tested", "Broken", "RIR (%)",
                          "95% CI", "Untested"], rows,
                  "RQ5 --- repair inflation: scanner-clean but functionally broken"))

    # Sensitivity table — belongs in the paper, not only in the readout, because it
    # is the honest range around the headline rather than a footnote about it.
    if tests and tests.get("sensitivity_rules", {}).get("per_model"):
        rows = []
        rsm = tests["sensitivity_rules"]["per_model"]
        exm = tests["sensitivity_extraction"]["per_model"]
        clm = tests["sensitivity_clustering"]["per_model"]
        for mm in rsm:
            v, e, c = rsm[mm], exm.get(mm, {}), clm.get(mm, {})
            rows.append([mm, v["headline"]["rate"], v["excl_noisy"]["rate"],
                         v["excl_scaffold"]["rate"], v["excl_both"]["rate"],
                         e.get("vr_failures_counted_vulnerable"),
                         str(c.get("cluster_bootstrap_ci", "--"))])
        specs.append(("sensitivity",
                      ["Model", "Headline VR (%)", "Excl. noisy (%)", "Excl. scaffold (%)",
                       "Excl. both (%)", "Extr. counted vuln (%)", "Cluster CI"], rows,
                      "Sensitivity of the baseline vulnerability rate to analysis choices"))

    written = []
    for key, headers, rows, title in specs:
        md, tex = _table(headers, rows, title)
        for ext, body in (("md", md), ("tex", tex)):
            p = os.path.join(t, f"{key}.{ext}")
            with open(p, "w", encoding="utf-8") as f:
                f.write(body)
            written.append(p)
    return written


# -------------------------------------------------------------------- summary
def build_summary(m, df, tests, figs):
    """Render SUMMARY.md: the plain-English readout a human actually reads.

    Applies the pre-registered decision bands mechanically and states the verdict
    per RQ, flags any dataset with fewer than 3 repetitions, and surfaces every
    sensitivity analysis inline rather than leaving them in results.json where
    nobody would look.
    """
    s = m["summary"]
    L = ["# LeBlanc — analysis readout", "",
         f"Generated by `analysis/rq_analysis.py` from `backend/leblanc_v3.db`. "
         f"**Every number below is computed, never typed.**", "",
         f"- runs in database: **{s['total_runs']}** "
         f"({s['completeness_pct']}% of the planned {s['planned_cells']})",
         f"- models present: {', '.join(s['models']) or '—'}",
         f"- dual-scanner (Bandit + Semgrep) runs: {s['dual_scanner_runs']}",
         f"- outcome census: {json.dumps(s['status_counts'])}", ""]

    reps = sorted(df["rep"].unique()) if not df.empty else []
    if reps and max(reps) < 3:
        L += ["> ⚠️ **This dataset has fewer than the planned 3 repetitions per cell "
              f"(max rep = {max(reps)}).** Every rate below is a single sample of a "
              "randomised process. Directional signal only — do not publish a number "
              "from this state.", ""]

    L += ["## Verdicts against the pre-registered decision bands", "",
          "Bands come from `docs/01_RESEARCH_QUESTIONS.md`, fixed *before* the data existed. "
          "A verdict on an `insufficient` cell is not a verdict.", ""]

    # RQ1
    gr = m["rq1"]["per_generation"]
    g1, g3 = gr.get("G1", {}).get("rate"), gr.get("G3", {}).get("rate")
    gap = None if (g1 is None or g3 is None) else round(g1 - g3, 1)
    ordered = all(x is not None for x in (g1, gr.get("G2", {}).get("rate"), g3)) and \
        g1 >= gr["G2"]["rate"] >= g3
    v1 = _verdict("rq1", gap, ordered)
    L += [f"**RQ1 — generational gap:** `{v1.upper()}`. "
          f"VR(G1)={g1}%, VR(G2)={gr.get('G2', {}).get('rate')}%, VR(G3)={g3}%, "
          f"gap={gap}pp, ordering holds: {ordered}. Band: {BANDS['rq1'][v1] if v1 in BANDS['rq1'] else 'not enough data'}.",
          f"  - across-generation test: `{json.dumps(tests['rq1_gen_test'])}`", ""]

    # RQ2
    L.append("**RQ2 — does enrichment still help?**")
    for n, v in m["rq2"]["per_model"].items():
        if v["insufficient"] or v["delta_pp"] is None:
            L.append(f"  - {n} ({v['gen']}): not enough paired data (n={v['paired_n']})")
            continue
        vv = _verdict("rq2", v["delta_pp"], v["mcnemar_p"])
        L.append(f"  - {n} ({v['gen']}): ΔE={v['delta_pp']:+}pp, McNemar p={v['mcnemar_p']} → `{vv.upper()}`"
                 + ("  ⚠️ **enrichment made this model worse**" if v["delta_pp"] < 0 else ""))
    L.append("")

    # RQ3
    L.append("**RQ3 — does repair converge?**")
    crs = {v["gen"]: v["convergence_rate"] for v in m["rq3"]["per_model"].values()
           if v["convergence_rate"] is not None}
    d3 = None if not ("G1" in crs and "G3" in crs) else round(crs["G3"] - crs["G1"], 1)
    L.append(f"  - CR(G3) − CR(G1) = {d3 if d3 is not None else '—'}pp → `{_verdict('rq3', d3).upper()}`")
    for n, v in m["rq3"]["per_model"].items():
        if v["convergence_rate"] is None:
            continue
        nonconv = round(100 - v["convergence_rate"], 1)
        flag = " ⚠️ **>30% non-convergence — report prominently**" if nonconv > 30 else ""
        L.append(f"  - {n} ({v['gen']}): CR={v['convergence_rate']}%, "
                 f"non-convergence={nonconv}%, mean iters={v['avg_iterations']}{flag}")
    L += [f"  - iteration-count test: `{json.dumps(tests['rq3_iterations'])}`", ""]

    # RQ4
    L.append("**RQ4 — what still fails after everything (the practitioner payoff)?**")
    red = []
    for cat in m["rq4"]["categories"]:
        for g in m["rq4"]["generations"]:
            c = m["rq4"]["grid"][cat][g]
            if c["rate"] is None or c["insufficient"]:
                continue
            v4 = _verdict("rq4", c["rate"])
            if v4 == "no":
                red.append(f"    - **{cat} / {g}: {c['rate']}% still vulnerable** (n={c['n']}) — unsolved")
    L += (red or ["    - no category/generation cell is in the red band on current data"])
    L.append("")

    # RQ5
    L.append("**RQ5 — repair inflation (the headline):**")
    for n, v in m["rq5"]["per_model"].items():
        if v["repair_inflation_rate"] is None or v["insufficient"]:
            L.append(f"  - {n} ({v['gen']}): not enough functionally-tested repairs "
                     f"(tested={v['functionally_tested']}, awaiting tests={v['awaiting_tests']})")
            continue
        v5 = _verdict("rq5", v["repair_inflation_rate"])
        L.append(f"  - {n} ({v['gen']}): RIR={v['repair_inflation_rate']}% "
                 f"({v['secretly_broken']}/{v['functionally_tested']} 'repaired' runs fail their "
                 f"functional test) → `{v5.upper()}`")
    sp = tests["rq5_secure_pass"]
    for key in ("repaired_only", "all_repair_mode"):
        s5 = sp[key]
        if s5.get("test") is None:
            L.append(f"  - {key}: {s5.get('note')}")
            continue
        L.append(f"  - **{key}**: {s5['secure_but_broken']}/{s5['secure']} scanner-clean runs "
                 f"fail their functional test ({s5['secure_but_broken_pct']}%), "
                 f"McNemar p={s5['p']} (n={s5['n']})")
    L += ["    - `repaired_only` is the RQ5 claim proper (Engine C actually ran). A gap in "
          "`all_repair_mode` but not in `repaired_only` means our tests are strict, not that "
          "repair does damage — do not report the wider number as repair inflation.", ""]

    ra = tests["rq5_repair_attribution"]
    L += ["**RQ5 control — is it the repair's fault?** (the number that supports the causal claim)", ""]
    if ra.get("attributable_to_repair_pp") is None:
        L.append(f"  - not computable yet: {ra.get('note', 'need functionally-tested runs in both slices')}")
    else:
        L += [f"  - scanner-clean **after a repair**: {ra['repaired_clean_broken_pct']}% fail their "
              f"functional test (n={ra['repaired_n']})",
              f"  - scanner-clean **never repaired**: {ra['never_repaired_clean_broken_pct']}% fail "
              f"(n={ra['never_repaired_n']})",
              f"  - **attributable to repair: {ra['attributable_to_repair_pp']:+}pp** "
              f"(Fisher p={ra['fisher_p']})"
              + ("  ⚠️ below MIN_N — directional only" if ra["insufficient"] else ""),
              "",
              "  > If this attributable gap is near zero while the raw rate is high, the honest "
              "headline is *\"scanner-clean LLM code often does not work\"* — which is still a "
              "real, publishable finding — **not** *\"the repair loop breaks code\"*. Write the "
              "sentence the number supports."]
    L.append("")

    fc = tests["finding_composition"]
    if fc.get("total_findings"):
        L += ["## What the findings are actually made of", "",
              f"{fc['total_findings']} findings total. The top 3 rules account for "
              f"**{fc['top3_share_pct']}%** of them; **{fc['on_scaffolding_pct']}%** "
              f"({fc['on_scaffolding_lines']} findings) landed on `app.run(...)` / "
              "`__main__` scaffolding rather than on the function the prompt asked for.", "",
              "| rule | findings | share |", "|---|---:|---:|"]
        L += [f"| `{r['rule']}` | {r['n']} | {r['pct']}% |" for r in fc["top_rules"]]
        L += ["", f"> {fc['reading']}", ""]

    # ---- sensitivity analyses: where do the headline numbers depend on a choice?
    L += ["## Sensitivity — does the headline survive its own assumptions?", "",
          "Each block below re-computes a headline number under a different defensible "
          "choice. Where the answer moves a lot, the paper must report the range, not "
          "just the convenient end of it.", ""]

    cl = tests["sensitivity_clustering"]["per_model"]
    if cl:
        L += ["**Clustering — repetitions are not independent observations.**", "",
              "| model | runs | prompts | rate | Wilson CI (naive) | cluster-bootstrap CI | widening |",
              "|---|---:|---:|---:|---|---|---:|"]
        for mm, v in cl.items():
            widening = "—" if v["widening_pp"] is None else f"{v['widening_pp']:+}pp"
            L.append(f"| {mm} | {v['n_runs']} | {v['n_prompts']} | {v['rate']}% | "
                     f"{v['wilson_ci']} | {v['cluster_bootstrap_ci']} | {widening} |")
        L += ["", f"> {tests['sensitivity_clustering']['reading']}", ""]

    ex = tests["sensitivity_extraction"]
    if ex["per_model"]:
        L += ["**Extraction failures — excluded, or counted which way?**", "",
              "| model | extraction failures | VR (excluded) | VR (counted clean) | VR (counted vulnerable) |",
              "|---|---:|---:|---:|---:|"]
        for mm, v in ex["per_model"].items():
            L.append(f"| {mm} | {v['extraction_failures']} ({v['extraction_failure_pct']}%) | "
                     f"{v['vr_excluded']}% | {v['vr_failures_counted_clean']}% | "
                     f"{v['vr_failures_counted_vulnerable']}% |")
        L += ["", f"Widest single-model spread: **{ex['max_spread_pp']}pp**. {ex['reading']}", ""]

    rs = tests["sensitivity_rules"]
    if rs["per_model"]:
        L += ["**Which findings count — audit noise and volunteered scaffolding.**", "",
              "| model | headline VR | excl. noisy rules | excl. scaffolding | excl. both | drop |",
              "|---|---:|---:|---:|---:|---:|"]
        for mm, v in rs["per_model"].items():
            L.append(f"| {mm} | {v['headline']['rate']}% | {v['excl_noisy']['rate']}% | "
                     f"{v['excl_scaffold']['rate']}% | {v['excl_both']['rate']}% | "
                     f"{'—' if v['drop_pp'] is None else str(v['drop_pp']) + 'pp'} |")
        L += ["", f"> {rs['reading']}", "",
              f"> Noisy rules excluded: `{'`, `'.join(rs['noisy_rules_excluded'])}`", ""]

    mc = tests.get("multiple_comparisons")
    if mc and mc["n_tests"]:
        L += ["**Multiple comparisons.** " + mc["method"] +
              f" over {mc['n_tests']} tests ({mc['family']}).", "",
              "| model | raw p | FDR-adjusted p |", "|---|---:|---:|"]
        for mm in mc["raw_p"]:
            L.append(f"| {mm} | {mc['raw_p'][mm]} | {mc['adjusted_p'][mm]} |")
        L += ["", f"> {mc['reading']}", ""]

    lm = tests["logistic_model"]
    L += ["## Headline regression — `vuln ~ mode * generation + category`", ""]
    if lm.get("fitted"):
        L += [f"Fitted on n={lm['n']} valid runs, pseudo-R² = {lm['pseudo_r2']}.", "",
              "| term | coef | odds ratio | p |", "|---|---:|---:|---:|"]
        for k in lm["coefficients"]:
            L.append(f"| `{k}` | {lm['coefficients'][k]} | {lm['odds_ratios'][k]} | {lm['p_values'][k]} |")
    else:
        L.append(f"Not fitted: {lm.get('note')}")
    L += ["", "## Figures", ""]
    L += [f"- `{os.path.relpath(p, os.path.dirname(os.path.dirname(p)))}`" for p in figs if p]
    L += ["", "---", "",
          "*Regenerate: `python analysis/rq_analysis.py`. If a number in the paper "
          "disagrees with this file, the paper is wrong.*"]
    return "\n".join(L)


# ----------------------------------------------------------------------- main
def main():
    """Entry point: load, compute, test, plot, tabulate, summarise. Read-only."""
    ap = argparse.ArgumentParser(description="LeBlanc RQ1–RQ5 analysis (offline, free)")
    ap.add_argument("--models", nargs="+", help="restrict to these models")
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()

    outdir = os.path.abspath(args.out)
    for sub in ("figures", "tables"):
        os.makedirs(os.path.join(outdir, sub), exist_ok=True)

    df = load_frame(args.models)
    m = compute_all()
    if df.empty:
        print("No runs in the database yet. Run `python backend/run_batch.py ...` first.")
        return

    print(f"loaded {len(df)} runs · {df['model'].nunique()} models · "
          f"reps present: {sorted(df['rep'].unique())}")

    tests = {
        "rq1_gen_test": gen_contingency_test(df, "vuln_initial", "plain"),
        "rq3_iterations": iterations_mannwhitney(df),
        "rq5_secure_pass": secure_vs_securepass(df),
        "rq5_repair_attribution": repair_attribution(df),
        "finding_composition": finding_composition(),
        "logistic_model": logistic_model(df),
        # Sensitivity analyses — every one of these exists because a headline
        # number depends on a methodological choice, and the choice should be
        # visible rather than buried.
        "sensitivity_clustering": clustered_rates(df),
        "sensitivity_extraction": extraction_sensitivity(df),
        "sensitivity_rules": rule_sensitivity(df),
    }

    # Multiple-comparison correction across the RQ2 family (one McNemar per model).
    rq2_models = list(m["rq2"]["per_model"])
    raw_p = [m["rq2"]["per_model"][k]["mcnemar_p"] for k in rq2_models]
    adj_p, rejected = benjamini_hochberg(raw_p)
    for k, p_adj, rej in zip(rq2_models, adj_p, rejected):
        m["rq2"]["per_model"][k]["mcnemar_p_fdr"] = p_adj
        m["rq2"]["per_model"][k]["significant_after_fdr"] = bool(rej)
    tests["multiple_comparisons"] = {
        "family": "RQ2 McNemar, one test per model",
        "method": "Benjamini-Hochberg FDR, alpha=0.05",
        "n_tests": len([p for p in raw_p if p is not None]),
        "raw_p": dict(zip(rq2_models, raw_p)),
        "adjusted_p": dict(zip(rq2_models, adj_p)),
        "reading": "Quote the adjusted p in the paper. An effect that survives raw "
                   "p<0.05 but not FDR is not a finding, it is a coin that came up heads.",
    }

    figs = [fig_rq1(m, outdir), fig_rq2(m, outdir), fig_rq3(m, outdir),
            fig_rq4(m, outdir), fig_rq5(m, outdir), fig_outcomes(df, outdir)]
    tables = write_tables(m, outdir, tests)

    payload = {"metrics": m, "tests": {k: {kk: vv for kk, vv in v.items() if kk != "summary_text"}
                                       for k, v in tests.items()},
               "run_counts": {"total": int(len(df)),
                              "by_model": df["model"].value_counts().to_dict(),
                              "by_mode": df["mode"].value_counts().to_dict(),
                              "reps_present": [int(r) for r in sorted(df["rep"].unique())]}}
    with open(os.path.join(outdir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, default=str)

    summary = build_summary(m, df, tests, figs)
    with open(os.path.join(outdir, "SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write(summary)

    if tests["logistic_model"].get("fitted"):
        with open(os.path.join(outdir, "logistic_model.txt"), "w", encoding="utf-8") as f:
            f.write(tests["logistic_model"]["summary_text"])

    print(f"\nwrote {len([p for p in figs if p])} figures, {len(tables)} table files, "
          f"results.json and SUMMARY.md to {outdir}")
    print("\n--- SUMMARY.md (head) — full version in analysis/output/SUMMARY.md ---")
    head = "\n".join(summary.splitlines()[:30])
    # Windows consoles default to cp1252 and will crash on the arrows/emoji that
    # read fine in the written file; degrade the console copy, never the file.
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(head.encode(enc, errors="replace").decode(enc, errors="replace"))


if __name__ == "__main__":
    main()
