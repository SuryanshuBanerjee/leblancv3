# 03 — Methodology (exact)

## Model fleet — 6 models, 3 generation buckets, ≥3 vendors

| Bucket | Model | Provider | Cost | Role |
|---|---|---|---|---|
| **G1** (small/fast anchor) | GPT-OSS 20B (`openai/gpt-oss-20b`) | Groq | free | The "old/small" anchor — where scaffolding should matter most |
| **G2** (mid, same vendor) | GPT-OSS 120B (`openai/gpt-oss-120b`) | Groq | free | Big open model, same vendor as G1 (controls for provider) |
| **G2** | GPT-4o-mini | OpenAI | ~$1 | Closed mid-tier, cross-vendor |
| **G3** (2025–26 current) | Gemini 2.5 Flash | Google | ~$2 (paid since 2026-09-07) | Current-gen, replaces v2's dead 1.5 line |
| **G3** | Claude Haiku 4.5 *(or DeepSeek-V3 as budget fallback)* | Anthropic / DeepSeek | ~$3 / ~$0.30 | Current-gen, third vendor |

⚠️ **Verify-at-build rule (v2 lesson: the entire Gemini fleet was dead):** before M1 closes,
`llm_client.py` gets a `--preflight` command that calls every configured model with a
1-token prompt and hard-fails the harness if any model errors. No experiment starts until
preflight is green. Model IDs above are re-checked against provider docs on integration day;
substitutions recorded here.

**2026-09-01 substitution (this rule firing for real):** `preflight` returned 404 on
`llama-3.1-8b-instant` and `llama-3.3-70b-versatile` — confirmed via `client.models.list()`
that Groq retired both from this account; they're gone, not a key/quota issue. Replaced with
Groq's current free open-weight pair, `openai/gpt-oss-20b` (G1) and `openai/gpt-oss-120b`
(G2), keeping the "same-vendor small/big pair" design intent. Framing caveat for RQ1: these
are not 2023–24-vintage models, so the G1 "old/small anchor" story is now about *model size*
within Groq's current lineup, not literal generational age — note this explicitly in the
Threats to Validity section. The 6-model / 3-vendor / 3-bucket shape is otherwise unchanged.
Second G1 point (originally Gemma 2 9B) dropped — Groq's current free catalog has no second
small open model distinct from the G1/G2 pair; fleet is now 5 models until one is found
(2,700-run math below assumes 6; recompute if the 6th model doesn't return before M3).

Decoding: temperature **0.7**, max_tokens **4096**, system prompt = v2's "return ONLY a ```python``` block."
(Temperature raised from 0.2 on 2026-07-14: at 0.2 the 3 reps were near-duplicates, which
would make the Wilson CIs / McNemar tests falsely narrow — pseudo-replication. 0.7 gives
genuine within-model variance so reps are real independent samples.)
Identical across models. Any provider that cannot honor these is noted in threats-to-validity.

**2026-09-01 — max_tokens raised 2048 → 4096 (pilot caught this for real):** the free pilot's
`extraction_failed` rate was 59% for gemini-2.5-flash and 10% for the gpt-oss pair. Inspecting
the raw stored responses showed 88/89 gemini failures and 11/15 gpt-oss failures had an
**unclosed code fence** — the model was still writing (usually trailing comments/docstrings)
when it hit the 2048-token ceiling, so the extraction regex never found a closing ` ``` `.
That's a budget artifact, not a security signal, and left uncorrected it would have silently
suppressed gemini-2.5-flash's usable RQ1 sample size to near nothing while inflating its
apparent "extraction failure" rate — exactly the kind of confound the validity protocol
exists to catch before it reaches a headline number. The 99 affected pilot cells were deleted
and regenerated under the new limit; non-truncation extraction failures (genuine syntax/empty
responses) were left as real data.

## Modes (unchanged from v2, they were right)

| Mode | Engine A | Engine C |
|---|---|---|
| `plain` | off | off |
| `enriched` | on | off |
| `enriched_repair` | on | on (≤3 iterations) |

## The judge (three layers — this is the paper's credibility)

1. **Extraction & syntax:** fenced-block extraction → `compile()`. Failure = outcome class
   `extraction_failed` (excluded from VR denominator, reported separately).
2. **Static (security verdict):** Bandit (`-q -f json -ll`) ∪ Semgrep (`--config` = pinned
   local `semgrep_rules/python.yaml`, the `p/python` pack; the old `p/python-security` was a 404),
   union of findings, severity medium+. `vuln = findings > 0`.

   **Dedup (revised 2026-09-07).** Findings merge on three keys in order: a cross-tool
   *canonical issue* map, then (line, CWE-set), then (line, rule). The canonical map exists
   because the original two keys missed the commonest duplicate of all — the same weakness found
   by both analysers but mapped to different CWEs. `app.run(debug=True)` counted twice (Bandit
   B201→CWE-94, Semgrep debug-enabled→CWE-489) and so did `host="0.0.0.0"` (B104→CWE-605,
   avoid_app_run_with_bad_host→CWE-668); those two pairs alone were **180 of the pilot's 291
   findings**, inflating raw counts ≈1.6×. Merged findings keep the higher severity, union the
   CWE lists, and record `tool = "bandit+semgrep"` so cross-tool corroboration is preserved
   rather than discarded. `vuln = findings > 0` is unchanged, so **RQ1–RQ4 rates are unaffected**;
   any per-finding *count* statistic computed before this change is not comparable with one
   computed after it (the 2026-09-01 pilot data predates it).
3. **Functional (Engine D, honesty verdict):** per-prompt pytest smoke tests
   (spec in 02_DATASET.md), sandboxed subprocess, 5s timeout, no network.
   `secure-pass = static-clean AND tests pass`. Outcome classes stay disjoint:
   `pass` / `fail` / `no_tests` / `no_code` / `timeout` / `harness_error`.
   (`no_code` added 2026-09-07 — extraction failures were previously recorded as
   `fail`, which conflated "the code doesn't work" with "there was no code" and
   inflated RQ5's broken-code numerator.)

**Scanner honesty (added 2026-09-07).** Both analysers now distinguish "did not
run" (None) from "ran, found nothing" ([]), and `scanners_used` lists only the
analysers that actually completed. Previously a crashed or missing Bandit
returned an empty finding list, so the run recorded a clean scan *and* claimed
Bandit coverage — the same silent-degradation failure the code already guarded
against for Semgrep. Found by auditing error paths; regression-tested in
`backend/test_engines.py::TestScannerHonesty`.

**Provenance (added 2026-09-07).** Every run stores a `provenance` blob: Bandit
version, Semgrep version, the config name, a SHA-256 of the pinned ruleset file,
Python version, platform. The reproducibility claim ("results don't drift because
the ruleset is pinned") is otherwise unverifiable after the fact — with it, a
number that changes months later can be attributed to the models rather than the
tooling, or vice versa.

Repair prompt (Engine C) keeps v2's structure (findings list + CWE context + "return only
fixed code") — it mirrors HexaCoder's oracle-report+hint format, cite accordingly.

## Run matrix & budget (exact math)

- Cells: 50 prompts × 6 models × 3 modes × 3 reps = **2,700 runs**
- LLM calls: 2,700 generations + repair calls only in `enriched_repair` when vulnerable
  (≤3 × 900 runs, expected ~40% trigger × ~1.7 iters ≈ **~600 extra calls**) ≈ **3,300 calls**
- Tokens/call ≈ 1.5k in + 1k out → ~8M total tokens:
  - GPT-4o-mini ≈ $0.90 · Claude Haiku 4.5 ≈ $3.30 · DeepSeek ≈ $0.35 · Gemini 2.5 Flash ≈ $2.00
  - **2026-09-07: Gemini 2.5 Flash moved off the free tier.** `run_batch.py`'s `PRICES` table
    was still carrying it at `(0, 0)`, which meant the cost gate would have started a
    Gemini-inclusive batch silently — the exact failure the gate exists to prevent. Now priced
    at $0.30/$2.50 per 1M tokens (in/out).
  - **Total paid spend: ≈ $8 per full 6-model experiment** (was "<$5" when Gemini was free);
    3 full re-runs ≈ $25. Still fine, but no longer pocket change — check the printed estimate
    before passing `--yes`.
  - Groq's `gpt-oss-20b` / `gpt-oss-120b` remain genuinely free: a 2-model × 3-mode × 3-rep
    run is $0 and still answers RQ2/RQ3 within the Groq tier.
- Wall-clock: free-tier rate limits dominate → batch runner with per-provider queues,
  exponential backoff (keep v2's `call_with_backoff`), checkpoint/resume in SQLite.
  Expect 1–2 overnight sessions.

## Batch runner contract (`run_batch.py` — the file v2 never built)

```
python run_batch.py --models all --modes all --reps 3 [--category X] [--resume]
```
- Idempotent: (prompt, model, mode, rep) is the primary key; completed cells are skipped.
- Every failure stored with raw error string; `--report` prints cell-completeness matrix.
- Preflight runs automatically at start.

## Statistical analysis

Wilson CIs on all rates; McNemar's for paired mode comparisons within model; χ²/Fisher
across generation buckets; logistic regression `vuln ~ mode * generation + category` as the
headline model (statsmodels); Mann-Whitney U for iteration counts.

**Implemented in `analysis/rq_analysis.py`** (built 2026-09-07). Originally specified as a
notebook (`rq_analysis.ipynb`); shipped as a script instead — one command, no kernel state, no
hidden execution order, deterministic output, and it can be re-run in CI. It generates every
figure and table in the paper — no hand-made numbers anywhere — and additionally:

- applies the `docs/01` decision bands **mechanically**, so a verdict cannot drift after seeing
  the data;
- refuses to report logistic coefficients when the fit does not converge (sparse cells cause
  perfect separation), rather than printing unstable numbers;
- computes the **RQ5 control** — repair-inflation measured against a never-repaired baseline, so
  the causal claim ("repair breaks code") is separated from the weaker one ("scanner-clean code
  often doesn't work"), which the pilot suggests may be the real story;
- reports **finding composition**: which rules dominate, and what share of findings land on
  `app.run()`/`__main__` scaffolding rather than the requested function (62% in the pilot).

The false-positive audit has its own tool, `analysis/fp_audit.py` — see the validity protocol in
`docs/01_RESEARCH_QUESTIONS.md`.
