# 01 — Research Questions (exact)

Notation: a *run* = one (prompt, model, mode, rep). `vuln(r) = 1` if Engine B reports ≥1
medium+ finding on the final code of run r. `pass(r) = 1` if Engine D's functional tests pass.
All rates reported with Wilson 95% confidence intervals.

Generation buckets (defined in 03_METHODOLOGY): **G1** (2023–24 small open),
**G2** (2024 mid-tier), **G3** (2025–26 current).

---

## RQ1 — Baseline generational gap
**Question:** How does the plain-prompt vulnerability rate differ across model generations
on identical security-sensitive tasks?

- **Metric:** `VR(model) = Σ vuln(r) / N` over mode=plain runs.
- **Test:** χ² test of independence across G1/G2/G3 pooled rates; pairwise odds ratios
  between buckets with 95% CIs.
- **Hypothesis H1:** VR(G3) < VR(G2) < VR(G1), with VR(G1) − VR(G3) ≥ 20 percentage points.

## RQ2 — Does enrichment still matter?
**Question:** Does CWE-aware prompt enrichment reduce vulnerability rates, and does its
marginal benefit shrink as models get newer?

- **Metric:** `ΔE(model) = VR_plain(model) − VR_enriched(model)` (paired by prompt×rep).
- **Test:** McNemar's test per model on paired (plain, enriched) outcomes;
  interaction check: compare ΔE across generation buckets (logistic regression
  `vuln ~ mode * generation + category`, model as fixed effect).
- **Hypothesis H2:** ΔE is large and significant for G1 (≥15pp), small or non-significant
  for G3 (<5pp). *This is the "scaffolding obsolescence" claim.*

## RQ3 — Does repair still matter, and how fast?
**Question:** What fraction of initially-vulnerable generations converge to static-clean
within 3 repair iterations, and does convergence speed differ by generation?

- **Metrics:**
  - `CR(model) = # (repair runs reaching vuln=0) / # (repair runs with initial vuln=1)`
  - `IT(model) = mean iterations to converge` (converged runs only)
  - Non-convergence rate reported explicitly (it is data, not failure).
- **Test:** χ² on CR across buckets; Mann-Whitney U on iteration counts G1 vs G3.
- **Hypothesis H3:** CR(G3) > CR(G1) and IT(G3) < IT(G1).

## RQ4 — The residual failure catalog (what still breaks in 2026)
**Question:** Which CWE categories remain vulnerable in the NEWEST generation even after
full scaffolding (enriched + repair)?

- **Metric:** per (category, G3): `RVR(cat) = residual vuln rate after enriched_repair`.
  Output artifact: a ranked **residual-risk table** — category × generation heatmap.
- **Test:** descriptive + Fisher's exact for small cells. No hypothesis; this is the
  exploratory catalog and the practitioner-facing payoff of the paper.

## RQ5 — Repair inflation (the headline)
**Question:** How much do repair success rates overstate reality when functional
correctness is not checked?

- **Metrics:**
  - `secure(r)` = static-clean final code (the naive claim, what v2 and most prior work measure)
  - `secure-pass(r)` = static-clean AND functional tests pass (the honest claim,
    per CODEGUARD+/CodeSecEval)
  - **Repair Inflation Rate:** `RIR(model) = P(¬pass | secure, mode=enriched_repair, repaired>0)`
    — the fraction of "successfully repaired" runs whose code no longer works.
- **Test:** report RIR per model with CIs; McNemar's on secure vs secure-pass; qualitative
  coding of HOW repairs break functionality (deletion, stub-out, API change) on a 20-run sample.
- **Hypothesis H5:** RIR ≥ 15% on average — i.e., naive repair metrics (including prior
  work's) meaningfully overstate success. *No prior work measures this inside an iterative
  scanner-feedback loop; this is our sharpest contribution.*

---

## How to read a result — decision bands (added 2026-09-01)

The hypotheses above say what we *expect*; this section says, in advance, what number
would make us say **"yes,"** **"no,"** or **"mixed / not enough data yet."** Written before
we've looked at the full dataset, on purpose — deciding the bands after seeing the numbers
would be p-hacking with extra steps. If a real result falls outside every band below, report
it as a surprise and describe it plainly; don't force it into the nearest bucket.

**First check, always:** `metrics.py` flags any rate computed from fewer than `MIN_N = 5`
runs as `insufficient`. A band verdict on an insufficient cell isn't a real verdict — it's
noise with a percentage sign on it. Wait for more reps before reading anything into it.

| RQ | Metric | 🟢 "Yes" | 🟡 "Partial / mixed" | 🔴 "No" |
|---|---|---|---|---|
| RQ1 | VR(G1) − VR(G3), gap in the ordered rates | gap ≥ 20pp **and** VR(G1) ≥ VR(G2) ≥ VR(G3) holds | gap is 10–20pp, or the ordering is roughly right but noisy | gap < 10pp, or the ordering is scrambled (e.g. G3 *more* vulnerable than G1 on some slice) — itself a finding, not a failure |
| RQ2 | ΔE(model), paired plain vs. enriched | ΔE(G1) ≥ 15pp **and** McNemar p < 0.05 | ΔE is positive and significant but under 15pp, or significant for only some G1/G2 models | ΔE(G3) < 5pp — this half is expected and *is* "yes" for the obsolescence half of H2, not a failure |
| | | | **watch for:** ΔE clearly negative (enrichment made things worse) — flag by name, never average it away | |
| RQ3 | CR(model), IT(model) | CR(G3) − CR(G1) ≥ 15pp **and** IT(G3) < IT(G1) | CR/IT roughly flat across generations — repair effectiveness turns out generation-agnostic, a real and reportable result | CR(G1) > CR(G3) (a reversal) — don't smooth this over, dig into *why* before writing a headline |
| | Non-convergence rate | < 15% for a model | 15–30% | > 30% — report prominently, this is a real limitation of the repair loop for that model, not noise |
| RQ4 | RVR(category, G3) | < 10% — "essentially solved" for current models | 10–30% — partially mitigated, scaffolding narrows it but doesn't close it | ≥ 30% — still a real, unsolved risk category; this is the paper's practitioner-guidance payoff, so don't undersell a red cell |
| RQ5 | RIR(model) | ≥ 15% — H5 confirmed, naive "repair succeeded" claims (including prior work's) meaningfully overstate reality | 5–15% — inflation is real and worth a sentence, but not dramatic enough alone to indict naive metrics broadly | < 5% — repair claims are basically trustworthy for this model; the "security theater" concern doesn't apply here |

Two rules for using this table honestly:
1. **A band is read per model / per category, never pooled first.** "G3 overall looks fine" can
   hide one G3 model or one CWE category sitting in the red band — RQ4's whole point is that
   the residual risk is exactly where the average stops being useful.
2. **"No" is a real, publishable answer.** If RQ1–RQ3 land in 🔴 across the board, that's not a
   failed experiment — it's evidence the scaffolding-obsolescence story is *wrong*, which is
   just as citable as if it were right. Don't let the bands quietly pressure a result toward 🟢.

## Validity protocol (non-negotiable)

1. **False-positive audit:** stratified 10% sample of all findings, independently labeled
   TP/FP by two annotators (Suryanshu + Ayushi), Cohen's κ reported. If FP rate > 20%,
   it is prominently reported and RQ interpretations hedged accordingly.
2. **Repetitions:** 3 reps per cell, temperature 0.7 (raised from 0.2 so reps are
   genuine independent samples, not near-duplicates). Per-rep variance reported;
   a result that flips across reps is reported as unstable, not cherry-picked.
3. **Extraction failures** are their own outcome class — never counted as clean, never
   silently dropped (v2 already did this right; keep it).
4. **Dead-model integrity:** every API error is logged with the raw error; a cell with
   >10% llm_error is rerun or the model is dropped fleet-wide (no partial cells).
