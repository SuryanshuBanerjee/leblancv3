# TODO — LeBlanc v3

Last full review: **2026-09-07** (whole codebase, all ten research PDFs, all project docs).

**State of the project: every piece of software is written.** What remains is running the
experiment, reading the output, and writing the paper around it. [RUNBOOK.md](RUNBOOK.md) has
the exact commands; this file is the checklist and the reasoning.

**Docs win rule:** if a task below changes code or data, update the relevant `docs/0X_*.md` in
the *same* change (`docs/00_DEFINITION.md`).

---

## P0 — the only thing blocking everything else

- [ ] **Run the experiment (M4).**
      `python run_batch.py --models all --modes all --reps 3 --yes`
      ~4,140 calls · ~$8 · 1–2 overnight sessions · idempotent and resumable.
      Requires the paid keys below. A free Groq-only variant exists if the budget isn't there —
      it answers RQ2/RQ3 within one vendor but not RQ1's cross-tier question.
- [ ] **Add the paid keys** to `D:\LYPROJECT\.env`: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
      `DEEPSEEK_API_KEY`. Note `GEMINI_API_KEY` is now **paid** (~$2/run) — the cost gate prices
      it correctly as of 2026-09-07.
- [ ] **Back up the database the moment the run finishes.** It's gitignored as regenerable
      state, but a *completed* experiment costs $8 and a night to regenerate.
- [ ] **Decide the 6th-model question.** `docs/03_METHODOLOGY.md` still says "5 models until one
      is found" — either source a second small open model for the G1 bucket, or formally accept
      5 and update the 2,700-cell arithmetic everywhere it's quoted.

## P1 — after the data lands (all tooling already exists)

- [ ] **Run the analysis:** `python analysis/rq_analysis.py` → read
      `analysis/output/SUMMARY.md`. It applies the pre-registered decision bands itself, so the
      verdicts are computed, not argued.
- [ ] **Run the false-positive audit properly.** Tooling is built and a single-annotator triage
      already exists (53.6% on the pilot). For the two-annotator κ the protocol requires:
      `python analysis/fp_audit.py --sample`, copy to `_A.md` and `_B.md`, two people label
      independently, `--score`.
      *If nobody will do the two-person version, that's a legitimate choice — but the paper must
      then describe it as single-annotator triage with no κ, which the tool enforces in its
      output.*
- [ ] **Report the two composition caveats the pilot exposed**, in the paper, not just here:
      the FP rate with a sensitivity analysis excluding the three noisy rule families, and the
      share of findings landing on `app.run()` scaffolding (62% in the pilot). Both are computed
      automatically on every analysis run.
- [ ] **Check RQ5's control before writing its headline.** `repair_attribution` reports repair
      inflation against a never-repaired baseline. If the attributable difference is small, the
      finding is "scanner-clean LLM code often doesn't work", not "repair breaks code."
- [ ] **Qualitatively code 20 broken repairs** (interface change / stub-out / dependency drift).
      Specified in `docs/01_RESEARCH_QUESTIONS.md`; it's the concrete detail reviewers remember.

## P2 — the paper (M6)

- [ ] **Fill in `paper/leblanc_paper.tex`.** It compiles today; every number is a red
      `\PLACEHOLDER{}`. Replace them from `analysis/output/`, or `\input` the generated tables.
      Grep for `\PLACEHOLDER` before sending it anywhere.
- [ ] **Write Threats to Validity first** (the project's own rule) — FP rate, scaffolding
      findings, tiers-are-not-generations, smoke-tests-aren't-correctness.
- [ ] **Reframe "generation" language.** G1/G2/G3 currently separate size/vendor among current
      models, because the genuinely old models were retired mid-project. Say it upfront.
- [ ] **arXiv first**, then the ladder in `docs/04_PAPER.md` (workshop / MSR → SANER/ESEM →
      EMSE/JSS). See [FAQ §3](FAQ.md#3-the-research-paper--is-this-real-where-does-it-go).
- [ ] *(Optional, strengthens RQ1)* add a small slice of literal Pearce-et-al.-style scenarios
      so the "is 40% still true?" comparison is same-prompt, not same-benchmark-family.
- [ ] *(Optional, strengthens RQ1 more)* source one genuinely old model so "generational" means
      calendar time.

## P3 — nice to have, nothing depends on them

- [ ] Unit tests for the engines themselves. `validate_m2.py` tests the *dataset*; the pipeline
      code is only exercised end-to-end. A handful of tests around `dedupe_findings`,
      extraction, and the repair-loop status machine would have caught the double-counting bug
      earlier.
- [ ] A linter config (ruff/flake8) — the code is consistent by habit, not by enforcement.
- [ ] Re-run the pilot under the new dedup logic if per-finding pilot counts are ever quoted
      anywhere (rates are unaffected; only counts changed).

---

## Done in the 2026-09-07 review

- [x] **MCP server hang fixed** — subprocesses inherited the server's stdin (Windows pipe
      deadlock) *and* FastMCP ran sync tools on the event loop. Both fixed; all six tools
      verified through a real MCP client.
- [x] **Cross-tool double-counting fixed** — `dedupe_findings` now merges the same weakness
      when Bandit and Semgrep label it with different CWEs (was 180 of 291 pilot findings).
- [x] **Cost gate corrected** — Gemini priced as paid; full run now estimates ~$8, not $0.
- [x] **Frontend rewritten** — flat, light, professional; validated palette; same IDs and JS.
- [x] **Analysis layer built (M5)** — `analysis/rq_analysis.py`: six figures, LaTeX + Markdown
      tables, `results.json`, `SUMMARY.md` with mechanical decision-band verdicts, the RQ5
      control, and finding-composition reporting.
- [x] **FP audit tooling built** — `analysis/fp_audit.py`, plus a completed single-annotator
      triage of the pilot sample (53.6%).
- [x] **Paper skeleton written and compiling** — `paper/leblanc_paper.tex` → PDF, all numbers
      as unmistakable red placeholders.
- [x] **Docs**: `RUNBOOK.md`, `FAQ.md`, `CHANGELOG.md` written; README, SETUP, and
      `docs/01`–`05` updated for the Gemini pricing change, the dedup fix, the FP finding, and
      the RQ5 control.
- [x] **Repo cleaned** — unrelated BreachTrace docx and the non-reproducible VAPT report
      removed (its pipeline diagram rescued and corrected into
      `docs/figures/pipeline_diagram.tex` first); demo fixture documented and moved to `demo/`;
      one retired-model row removed from the database.

---

## Explicitly not on this list (by design, per `docs/00_DEFINITION.md`)

Don't add these unless the docs change first: fine-tuning / model weights / logits, non-Python
languages, a VS Code extension, or dataset inflation beyond the frozen 50.
