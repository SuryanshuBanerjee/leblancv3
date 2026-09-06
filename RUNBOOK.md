# RUNBOOK — everything that is left to do, as commands

Every piece of software this project needs is written. What remains is running it
and reading what comes out. This file is the complete sequence, in order, with what
each step costs, how long it takes, and what "it worked" looks like.

If a command here fails, that is a bug — the code is supposed to be finished. Nothing
below asks you to write new code.

---

## 0. One-time setup (5 minutes, free)

```bash
cd D:\LYPROJECT\v3\backend
pip install -r requirements.txt
```

Keys live in `D:\LYPROJECT\.env` (one directory above the repo, never committed):

```
GROQ_API_KEY=...        # free      -> gpt-oss-20b, gpt-oss-120b
GEMINI_API_KEY=...      # PAID now  -> gemini-2.5-flash
OPENAI_API_KEY=...      # paid      -> gpt-4o-mini          (optional)
ANTHROPIC_API_KEY=...   # paid      -> claude-haiku-4.5     (optional)
DEEPSEEK_API_KEY=...    # paid      -> deepseek-chat        (optional)
```

Check the fleet answers before spending anything (one 1-token call per model):

```bash
python run_batch.py --preflight
```

**Looks right:** every model you intend to use prints `[+] ... ok`. A `[!]` means that
key is missing, wrong, or the model was retired by the provider — fix it before going
further. Do not start a run with a red model in the fleet.

Confirm the offline test harness still passes (free, no network, ~1 minute):

```bash
python validate_m2.py
```

**Looks right:** `M2 gate GREEN.` — all 20 functional tests pass on their reference
solutions. If this is red, Engine D would score the real experiment wrongly.

---

## 1. The experiment (M4) — the one long step

Costs are printed before anything runs, and the runner **refuses to start** on a
non-zero estimate unless you pass `--yes`. Estimates are deliberately pessimistic.

### Option A — free only (2 models, no card required)

```bash
python run_batch.py --models gpt-oss-20b gpt-oss-120b --modes all --reps 3
```
~1,380 LLM calls · **$0** · several hours wall-clock (free-tier rate limits dominate).

### Option B — the full designed experiment (6 models, 3 vendors)

```bash
python run_batch.py --models all --modes all --reps 3 --yes
```
~4,140 LLM calls · **~$8** estimated · 1–2 overnight sessions.

This is what `docs/03_METHODOLOGY.md` specifies and what the paper's RQ1 generational
claim needs. Anything less and G1/G2/G3 is only "small vs big model", not "old vs new".

### While it runs / after a crash

The runner is **idempotent**: every completed `(prompt, model, mode, rep)` cell is
skipped on re-run. Ctrl-C is safe. Re-run the exact same command to resume.

```bash
python run_batch.py --report        # completeness matrix, anytime
```

**Looks right:** each `(model, mode)` pair shows `ok` counts climbing toward
50 prompts × 3 reps = 150, with `err` near zero. An error rate above 10% for any
model means stop and investigate — that is the gate in `docs/05_EXECUTION_PLAN.md`.

### The moment it finishes — back it up

```bash
copy backend\leblanc_v3.db backend\leblanc_v3.db.bak-%DATE%
```
The database is gitignored on purpose (it is generated state), but a *completed*
experiment is not regenerable for free. Put a copy somewhere off this machine.

---

## 2. The analysis (M5) — free, offline, instant

```bash
python analysis/rq_analysis.py
```

Writes to `analysis/output/`:

| file | what it is |
|---|---|
| `SUMMARY.md` | **read this first** — plain-English readout, every RQ, with the pre-registered decision-band verdict (yes / mixed / no) computed mechanically |
| `figures/*.png` | the six paper figures, publication-styled |
| `tables/rq*.tex` | paper-ready LaTeX tables — `\input{}` them straight into the draft |
| `tables/rq*.md` | the same tables for the README / slides |
| `results.json` | every computed number, machine-readable |

**Looks right:** it prints the run count, then `wrote 6 figures, 10 table files...`.
If it says the logistic regression did not converge, that is the script correctly
refusing to report unstable coefficients from sparse data — collect more reps, do not
report those numbers.

Re-run it as often as you like; it is read-only over the database.

---

## 3. The false-positive audit — the credibility step

Every vulnerability number rests on Bandit and Semgrep being right. They are not
always right (in the pilot, a single-annotator triage put the false-positive rate at
**53.6%**, driven by three noisy rules). Reviewers will ask. Run this:

```bash
python analysis/fp_audit.py --sample        # draws a stratified 10% worksheet
```

Open `analysis/output/fp_audit_worksheet.md`, set every `verdict:` to `TP`, `FP`, or
`?`, then:

```bash
python analysis/fp_audit.py --score
```

**For the strongest claim** (what `docs/01_RESEARCH_QUESTIONS.md` specifies): two
people label copies named `fp_audit_worksheet_A.md` and `fp_audit_worksheet_B.md`
independently, and `--score` reports Cohen's κ. With one labeller it still works and
still gives you an FP rate — it just prints, loudly, that it is a triage and not an
inter-rater measurement, and the paper must describe it that way.

A pre-filled triage of the pilot sample already exists in the worksheet as a starting
point; re-label rather than trust it if you want the number to be yours.

---

## 4. Look at it in the dashboard (optional, free)

```bash
python app.py     # -> http://localhost:5000
```

Run History → click any row → every pipeline stage side by side: the prompt, the
enriched prompt, the raw generation, each scanner finding highlighted on its code
line, every repair round, and the functional-test verdict. This is the fastest way to
sanity-check that the numbers correspond to reality before writing about them.

---

## 5. The paper

`paper/leblanc_paper.tex` is a complete, compiling skeleton with every section, the
pipeline figure, and the tables wired in — **all numbers in it are marked
`\PLACEHOLDER{}` and render in red.** Replace them with the values from
`analysis/output/` (or `\input` the generated tables directly), then:

```bash
cd paper
pdflatex leblanc_paper.tex && pdflatex leblanc_paper.tex
```

The rule from `docs/04_PAPER.md` still applies: **if a number is in the paper, it came
out of `analysis/output/`.** Nothing hand-typed. If the paper and `SUMMARY.md`
disagree, the paper is wrong.

---

## The whole thing, if you just want the shortest path

```bash
cd D:\LYPROJECT\v3\backend
pip install -r requirements.txt
python run_batch.py --preflight
python validate_m2.py
python run_batch.py --models all --modes all --reps 3 --yes    # the long one
python run_batch.py --report
cd .. && python analysis/rq_analysis.py
python analysis/fp_audit.py --sample     # then label, then --score
```

Then read `analysis/output/SUMMARY.md` and write the paper around what it says —
including if what it says is "no, the scaffolding does nothing." A null result
answered honestly is the finding; `docs/01` fixed the decision bands in advance
precisely so that conclusion stays available.
