# 03 — Methodology (exact)

## Model fleet — 6 models, 3 generation buckets, ≥3 vendors

| Bucket | Model | Provider | Cost | Role |
|---|---|---|---|---|
| **G1** (small/fast anchor) | GPT-OSS 20B (`openai/gpt-oss-20b`) | Groq | free | The "old/small" anchor — where scaffolding should matter most |
| **G2** (mid, same vendor) | GPT-OSS 120B (`openai/gpt-oss-120b`) | Groq | free | Big open model, same vendor as G1 (controls for provider) |
| **G2** | GPT-4o-mini | OpenAI | ~$1 | Closed mid-tier, cross-vendor |
| **G3** (2025–26 current) | Gemini 2.5 Flash | Google | free tier | Current-gen, replaces v2's dead 1.5 line |
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
   union of findings, dedup by (line, CWE), severity medium+. `vuln = findings > 0`.
3. **Functional (Engine D, honesty verdict):** per-prompt pytest smoke tests
   (spec in 02_DATASET.md), sandboxed subprocess, 5s timeout, no network.
   `secure-pass = static-clean AND tests pass`.

Repair prompt (Engine C) keeps v2's structure (findings list + CWE context + "return only
fixed code") — it mirrors HexaCoder's oracle-report+hint format, cite accordingly.

## Run matrix & budget (exact math)

- Cells: 50 prompts × 6 models × 3 modes × 3 reps = **2,700 runs**
- LLM calls: 2,700 generations + repair calls only in `enriched_repair` when vulnerable
  (≤3 × 900 runs, expected ~40% trigger × ~1.7 iters ≈ **~600 extra calls**) ≈ **3,300 calls**
- Tokens/call ≈ 1.5k in + 1k out → ~8M total tokens, ~2.2M on paid models:
  - GPT-4o-mini ≈ $0.90 · Claude Haiku 4.5 ≈ $3.30 (or DeepSeek ≈ $0.35)
  - **Total paid spend: < $5 per full experiment; 3 full re-runs still < $15. Budget OK.**
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
headline model (statsmodels); Mann-Whitney U for iteration counts. Analysis notebook
(`analysis/rq_analysis.ipynb`) generates every figure and table in the paper — no hand-made
numbers anywhere.
