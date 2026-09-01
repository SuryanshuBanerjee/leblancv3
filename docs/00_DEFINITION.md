# 00 — What EXACTLY Is Being Done

## The claim we are testing

> Inference-time security scaffolding — warning the model before it writes code (enrichment)
> and feeding scanner findings back until clean (iterative repair) — was very valuable for
> 2023-era models. We measure precisely how much of that value survives in 2025/26-era
> models, which vulnerability classes remain immune to scaffolding, and how often
> "successful repair" is an illusion created by not checking that the code still works.

## The system (LeBlanc pipeline, v3)

```
user prompt ──► Engine A (CWE-aware enrichment) ──► LLM ──► Engine B (Bandit ∪ Semgrep)
                                                     ▲                    │
                                                     └── Engine C ◄───────┘  (repair loop, ≤3 iters)
                                                                           │
                                              Engine D (functional test runner) ◄── final code
```

- **Engine A** — keyword→CWE→warning injection (rule-based, no LLM). Unchanged concept from v2.
- **Engine B** — dual static analysis: Bandit (`-ll`, medium+) ∪ Semgrep (pinned local copy
  of the `p/python` pack, 781 rules), findings unioned and deduplicated by (line, CWE).
  v2 shipped Bandit only; v3 restores Semgrep. (The initially-configured `p/python-security`
  pack was a 404 that silently degraded to Bandit-only — fixed 2026-07-14 by pinning `p/python`.)
- **Engine C** — scanner findings → structured repair prompt → same LLM → re-scan. Max 3 iterations.
- **Engine D (NEW)** — per-prompt functional smoke tests executed against the final code in a
  sandboxed subprocess. This is what makes "clean" mean something. See 03_METHODOLOGY.

## The experiment

50 prompts × 6 models (3 generation buckets) × 3 modes (plain / enriched / enriched+repair)
× 3 repetitions = **2,700 pipeline runs**, all auto-logged to SQLite, analyzed per the exact
formulas in 01_RESEARCH_QUESTIONS.

## Deliverables (exactly three)

1. **The dataset+harness** — reproducible: anyone with API keys reruns the whole experiment
   with one command (`run_batch.py`).
2. **The paper** — empirical study per 04_PAPER.md.
3. **The tool demo** — the v2 dashboard, updated to v3 backend (kept minimal; it is a demo,
   not a deliverable we sink weeks into).

## Explicit NON-goals (write these on the wall)

- ❌ **No fine-tuning, no model weights, no logits.** API-only by design — that IS the positioning.
- ❌ **No languages other than Python.** Stated scope, stated limitation.
- ❌ **No claim of algorithmic novelty.** Engine A is a lookup table; Engine C is a loop.
  The contribution is the *measurement*, especially RQ4/RQ5. Never claim otherwise.
- ❌ **No VS Code extension / MCP server until the paper data is collected.** Demo-ware after
  science, not instead of it. (An MCP server wrapping scan/repair is the designated
  "if time remains" stretch goal — it replaces v2's abandoned VS Code extension plan.)
- ❌ **No dataset inflation.** Every prompt ID maps to a unique prompt with recorded provenance.
  50 means 50.
- ❌ **No results in slides/reports that the DB cannot reproduce.** (v2 lesson.)

## Institutional context

B.Tech capstone, Dept. of IT, K.J. Somaiya School of Engineering.
Guide: Prof. Deepti Patole.
Team: Suryanshu Banerjee (lead programmer), Ayushi Ranjan (data/analysis),
Vraj Soni (frontend/harness), Swadha Kumari (design/paper production).
