# FAQ — why LeBlanc works the way it does

The [README](README.md) is *how to run it*. [RUNBOOK.md](RUNBOOK.md) is *what commands are
left to type*. This file is **why any of it is shaped this way** — the design decisions, the
research framing, and the questions that come up every time someone new reads the repo.

**Contents**
1. [Design questions — "why is it built like that?"](#1-design-questions--why-is-it-built-like-that)
2. [The roadmap — what is actually left](#2-the-roadmap--what-is-actually-left)
3. [The research paper — is this real, where does it go](#3-the-research-paper--is-this-real-where-does-it-go)
4. [Is the codebase any good, honestly?](#4-is-the-codebase-any-good-honestly)
5. [Prompts, benchmarks, figures — the reference sheet](#5-prompts-benchmarks-figures--the-reference-sheet)
6. [Security questions people ask about this repo itself](#6-security-questions-people-ask-about-this-repo-itself)
7. [What the 2026-09-07 review changed and why it matters](#7-what-the-2026-09-07-review-changed-and-why-it-matters)

---

## 1. Design questions — "why is it built like that?"

### "Isn't the CWE warning (Engine A) compulsory? Why is there a mode that turns it off?"

Two different questions wearing the same clothes:

**As an engineering decision — yes, it should always be on.** Engine A costs nothing: no model
call, no network, a few milliseconds of local lookup. There is no deployment scenario where
you'd want it off. Nobody is proposing it be optional in a real tool.

**As an experiment — you must be able to turn it off**, for exactly one reason: to measure
whether it does anything. If every run were enriched, you'd have a pile of enriched numbers and
nothing to subtract them from. `plain` mode isn't a usage recommendation, it's the control arm —
the same reason a drug trial keeps a placebo group even though nobody suggests prescribing sugar
pills.

So RQ2's real question is not "should we enrich?" (settled: yes, it's free). It's **"does this
free thing we're doing anyway still change what current models produce, or have they already
internalised it?"** If ΔE is ~0 on the newest models, the answer isn't "stop enriching" — it's
"the free thing isn't buying you anything anymore, so don't count on it as your control." That's
a *practitioner* finding, and it's exactly what `docs/04_PAPER.md`'s conclusion section is for.

### "If repair helps, why cap it at 3 rounds instead of looping until clean?"

Every extra round is another paid model call and more wall-clock, and the evidence from the
pilot is that convergence happens fast or not at all (mean iterations ≈ 1.1). Past ~3 rounds
you're mostly watching a model fail repeatedly at the same weakness class. And crucially, **the
cap makes non-convergence measurable**: "17% of runs never converged in 3 tries" is a
reportable fact about model limits. An unbounded loop hides that number by definition.

### "Why 3 repetitions? It's the same prompt — won't it give the same answer?"

No, and deliberately so. Generation runs at temperature 0.7, not 0. Each repetition is a
genuinely different sample from the model's distribution, which is what lets us distinguish
"this model writes vulnerable code for this task" from "this model wrote vulnerable code once."
`docs/03_METHODOLOGY.md` records that the temperature was *raised* from 0.2 for this reason —
at 0.2 the repetitions were near-duplicates, which would have made the confidence intervals
falsely narrow (pseudo-replication) and quietly overstated every result's significance.

### "Why compare 'generations' when you said the old models got retired?"

Fair, and it's the study's biggest framing weakness. Groq retired `llama-3.1-8b-instant` and
`llama-3.3-70b-versatile` mid-project. The substitutes (`gpt-oss-20b` / `gpt-oss-120b`) are
current models, so **G1/G2/G3 currently separate size and vendor among concurrently-available
models, not calendar age**. The paper says this in Threats to Validity rather than letting a
reviewer discover it — reviewers punish a framing they catch far harder than one you flag first.
Restoring a genuinely old model would strengthen RQ1 considerably if one can be sourced.

### "Why do only 20 of the 50 tasks have functional tests?"

Because a functional test needs something callable to test. The 30 excluded tasks either have no
fixed interface (the authored natural-language prompts don't pin a function name), have an
inherently destructive happy path (delete a file, exec user input), or depend on something
unfakeable (PAM via ctypes, churn-prone third-party SDKs). Every exclusion has a written,
per-task reason in `dataset/tests/MANIFEST.md`. The other 30 tasks still fully drive RQ1–RQ4;
only RQ5 needs execution, so RQ5's *n* is smaller and reported at its true value rather than
padded.

### "Why trust Bandit and Semgrep? Couldn't they just be wrong?"

They frequently are, in both directions, which is why the false-positive audit exists and why
`analysis/fp_audit.py` is a first-class tool rather than a footnote. On the pilot data a
single-annotator triage put the FP rate at **53.6%** — see [§7](#7-what-the-2026-09-07-review-changed-and-why-it-matters),
because that number changes how the paper must be written.

### "Why not just ask a strong LLM to judge whether the code is vulnerable?"

Three reasons: it isn't reproducible (ask twice, get two answers — fatal for a longitudinal
experiment), it costs money per judgement at 2,700+ judgements, and it makes the measuring
instrument the same class of system as the thing being measured. Static analysers are dumber but
deterministic: the same code always yields the same verdict, and anyone can re-run the exact
scan a year later against the pinned ruleset. That reproducibility is worth more here than
judgement quality — and the FP audit is how we quantify what the dumbness costs.

### "What's a CWE? Is it the same as a CVE?"

A **CWE** (Common Weakness Enumeration) is a *category* of flaw — "SQL Injection" is CWE-89, a
pattern that can occur in any program. A **CVE** is one specific, dated vulnerability in one
specific product. This project only deals in CWEs, because we're studying the patterns models
reproduce, not incidents in shipped software.

### "Why SQLite and one giant table instead of a real schema?"

Because the analysis is read-mostly and the audit trail matters more than normalisation. One row
holds the *entire* trace of one run — prompt, enriched prompt, raw output, extracted code, every
finding, every repair round, the test verdict, the raw error. Nothing is pre-aggregated, so any
number can be recomputed from the evidence and any run can be inspected in full in the
dashboard. A normalised schema would be tidier and would make "show me exactly what happened in
run 412" harder, which is the wrong trade for a research artifact.

---

## 2. The roadmap — what is actually left

Everything below is commands, not code to write. The full version with expected output is in
[RUNBOOK.md](RUNBOOK.md); the prioritised checklist is [TODO.md](TODO.md).

| Phase | What | Who/what does it | Cost | Wall-clock |
|---|---|---|---|---|
| **1. Preflight** | confirm every model answers, confirm the test harness is green | `run_batch.py --preflight`, `validate_m2.py` | free | 5 min |
| **2. The experiment (M4)** | 50 tasks × 6 models × 3 modes × 3 reps = 2,700 cells | `run_batch.py --models all --modes all --reps 3 --yes` | ~$8 | 1–2 overnight sessions |
| **3. Analysis (M5)** | every figure, table, statistic, and decision-band verdict | `analysis/rq_analysis.py` | free | seconds |
| **4. FP audit** | label a stratified 10% sample so the scanner's error rate is known | `analysis/fp_audit.py --sample` → label → `--score` | free | 1–2 hours of reading |
| **5. Paper (M6)** | swap red placeholders for real numbers, write the argument | `paper/leblanc_paper.tex` | free | the actual writing weeks |
| **6. Submit** | arXiv first, then the venue ladder | — | free | — |

The only step that requires writing anything new is **5**, and even there the structure,
figures, tables, and bibliography are already in place — what's missing is the prose that
interprets whatever the numbers turn out to say.

**Do not skip step 4.** A paper whose entire security verdict rests on two static analysers,
with no reported false-positive rate, gets that as review comment #1 with certainty.

---

## 3. The research paper — is this real, where does it go

### Is this a legitimate paper, or a student project cosplaying as one?

Legitimate, provided it's framed as what it is: an **empirical measurement study**, not a
novel-technique paper. `docs/00_DEFINITION.md` says this in its non-goals ("no claim of
algorithmic novelty") and that's the correct call — Engine A is a lookup table, Engine C is a
loop, and dressing either up as an innovation is how you get desk-rejected. The contribution is
the *measurement*:

1. **Does inference-time security scaffolding still work?** Re-measuring an established
   2022–2024 result on current models with one consistent pipeline (RQ1–RQ3).
2. **What survives it?** A residual-risk catalogue by weakness category (RQ4) — the part a
   practitioner actually uses.
3. **Repair inflation** (RQ5) — the novel piece. Having read all eight papers in the literature
   review end to end: CODEGUARD+ and CodeSecEval argue security must be judged alongside
   correctness and measure both for *generation*; HexaCoder, SVEN, SecuCoGen and Yan et al.
   all perform repair but score it by re-scanning. **None measures functional regression inside
   an iterative scan→repair loop.** That gap is real and worth a paper on its own.

### Will it survive peer review?

Conditional on finishing the work, and the conditions are knowable in advance. In descending
order of how loudly a reviewer will object:

- **The FP audit must be done and reported.** Non-negotiable. The pilot's 53.6% triage estimate
  means this isn't a formality — it materially affects how every rate must be interpreted.
- **3 repetitions, not 1.** A rate from n=1 reads as preliminary no matter how it's phrased.
- **The scaffolding-findings problem must be addressed head-on** (see [§7](#7-what-the-2026-09-07-review-changed-and-why-it-matters)):
  62% of pilot findings landed on `app.run()` boilerplate the model volunteers, not on the
  function that was requested. Report both rates, or a reviewer will conclude you measured
  Flask demo scaffolding and call it LLM security.
- **The generation framing needs its caveat stated first**, not extracted under questioning.
- **RQ5's causal claim needs its control**, which the analysis now computes: raw "clean but
  broken" rate versus the never-repaired baseline. If the difference is small, the honest
  headline is "scanner-clean LLM code often doesn't work" — still publishable, still an
  extension of secure-pass@k, just a different sentence.

Everything else (Python only, 50 tasks, 3-iteration cap, smoke tests ≠ full correctness) are
ordinary scoped limitations that get waved through when disclosed and sink papers when hidden.

### Where should it go? Realistically.

The ladder in `docs/04_PAPER.md` is well-calibrated; keep it.

| Step | Venue | Why |
|---|---|---|
| 0 | **arXiv** (cs.SE / cs.CR) | Free, immediate, citable, stakes the claim. Do this the day the draft is solid. |
| 1 | **An ICSE-colocated workshop** (LLM4Code-style) or **MSR** | MSR is ACM/IEEE-sponsored and genuinely respected; its dataset-and-tool framing fits this project unusually well. This is the realistic first *real* target. |
| 2 | **SANER / ESEM**, short or ERA track | Respectable fallbacks with real brand value. |
| 3 | **EMSE** (Springer) or **JSS** (Elsevier) | Legitimate, well-regarded journals that publish exactly this kind of measurement study. Realistic *if* the full-scale RQ5 result is strong. |

Not recommended as a first submission: ICSE/FSE main track or TSE. Not because the work is
unserious, but because those venues expect either novelty or a much larger empirical footprint,
and a rejection there costs months. Nothing on this ladder is a predatory or joke venue.

### What would make it substantially stronger, if there's time?

- Restore one genuinely old model to the fleet so "generational" means calendar time.
- Report vulnerability rates with and without the `app.run` scaffolding findings.
- Qualitatively code *how* repairs break functionality (interface change / stub-out / dependency
  drift) on a 20-run sample — `docs/01_RESEARCH_QUESTIONS.md` already specifies this and it's
  the kind of concrete detail reviewers remember.

---

## 4. Is the codebase any good, honestly?

Better than typical, with specific caveats. What's genuinely good, and checkable rather than
asserted:

- Failure states are named outcome classes (`extraction_failed`, `llm_error`, `no_tests`,
  `harness_error`, `not_converged`) and are **never** folded into "clean" to flatter a number.
- The dataset has real provenance — every SecurityEval-derived task records its exact source
  file, and spot-checking `S040` against the upstream CWE-918 file confirms it.
- `validate_m2.py` is a real acceptance gate that actually runs, not a checkbox someone ticked.
- The decision bands in `docs/01_RESEARCH_QUESTIONS.md` were written **before** the data
  existed, specifically to make post-hoc p-hacking harder, and `analysis/rq_analysis.py` now
  applies them mechanically.
- Cost is gated structurally: the batch runner refuses to start on a non-zero estimate without
  `--yes`, and the web UI can only ever spend via one explicit button.

What was wrong and is now fixed — all four found in the 2026-09-07 review, see [§7](#7-what-the-2026-09-07-review-changed-and-why-it-matters):
the MCP server hang, the dark AI-dashboard frontend, the cross-tool double-counting of findings,
and the cost gate pricing Gemini at zero after it became paid.

What remains a judgement call rather than a defect: one giant `runs` table (deliberate, see
[§1](#1-design-questions--why-is-it-built-like-that)), no linter config checked in, and no unit
tests for the engines themselves (the M2 gate tests the *dataset*, not the pipeline — a real
gap, though the engines are exercised end-to-end constantly).

---

## 5. Prompts, benchmarks, figures — the reference sheet

### The task set

**50 Python tasks, frozen**, in `dataset/leblanc_v3_prompts.json`:

| Slice | IDs | n | Source |
|---|---|---|---|
| Authored | L001–L010 | 10 | Written by the team — natural-language feature requests |
| SecurityEval | S001–S040 | 40 | Verbatim from [s2e-lab/SecurityEval](https://github.com/s2e-lab/SecurityEval), each with its exact source file recorded |

Categories: Injection 11 · Auth 12 · Crypto 7 · File/Path 8 · Deserialization 9 · Web/Request 3.
Functional tests: 20/50, each validated against a hand-written secure reference solution.

### "Shouldn't we just reuse the original papers' exact prompts?"

Largely we already do — **80% of the set is verbatim SecurityEval**, which is the same benchmark
lineage SecuCoGen, HexaCoder and Yan et al. build on, so RQ1's comparison against prior baseline
rates is apples-to-apples.

The authored 20% is a deliberate hedge, not laziness. SecurityEval has been public since 2022,
which means it may sit in the training data of every model we test — DomainEval's entire
motivation is that public benchmarks decay this way. A set that is 100% old public benchmark
text cannot separate "the model got safer" from "the model has seen this exact prompt."

**Recommendation:** keep the mix. If there's time before the full run, add a small, clearly
labelled slice of *literally* Pearce-et-al.-style scenarios so the paper's "is 40% still true?"
opening is a same-prompt comparison rather than a same-benchmark-family one. Nice-to-have,
not a correctness requirement.

### The eight papers, one line each

| # | Paper | What it established | What we re-ask |
|---|---|---|---|
| One | **Guiding AI to Fix Its Own Flaws** (Yan et al., 2025) | Self-generated hints + explained feedback both help; imprecise hints can *hurt* | Does a repeated scan→repair loop still help, per model? |
| Two | **SecuCoGen** (Wang et al., ICSE'24) | CWE-aware prompting improves security; 180 samples, Python | Does it still, on current models, and by how much? |
| Three | **CodeSecEval** | Executable benchmark judging security *and* correctness | Direct ancestor of our RQ5 lens |
| Four | **LPO / DiSCo** | Fine-tuning-based preference optimisation for secure code | The road we deliberately don't take (API-only) |
| Five | **CODEGUARD+** | Constrained decoding; secure-pass@k — security must be judged with correctness | We apply that lens inside a repair loop |
| Six | **DomainEval** | Auto-constructed benchmark; models are unevenly good by domain; contamination motivation | Feeds RQ4's category framing and our authored-prompt hedge |
| Seven | **HexaCoder** (Hajipour et al.) | Oracle-guided repair, baked in via training data | Same repair idea at inference time, usable on closed models |
| Eight | **Copilot replication** (Majdinasab et al.) | One assistant's security behaviour drifts across versions (36.5%→27.3%) | How large is that drift across six models and one pipeline? |

Plus **Pearce et al. 2022** ("Asleep at the Keyboard", ~40% vulnerable) as RQ1's opening
comparison, and **Siddiq & Santos 2022** (SecurityEval) as the task-set source.

### Figures

| Where | What |
|---|---|
| `docs/figures/pilot/*.png` | the three pilot charts (1 rep, 3 models — directional only) |
| `docs/figures/pipeline_diagram.tex` | the four-engine pipeline figure, `\input`-ready |
| `analysis/output/figures/*.png` | **the real ones** — six figures regenerated from the DB on every analysis run |
| `analysis/output/tables/rq*.tex` | paper-ready LaTeX tables, same provenance |

---

## 6. Security questions people ask about this repo itself

### "Does Flask `debug=True` really count as a vulnerability, if it's only ever on during development?"

Yes — genuinely, not pedantically. Werkzeug's interactive debugger is an unauthenticated Python
console over HTTP: anyone who can reach the port can execute code on the host. This project's
own scanners agree, which we verified rather than asserted — feeding `app.run(debug=True)`
through `scan_code()` returns Bandit `B201` (**HIGH**, CWE-94, "allows the execution of
arbitrary code") *and* Semgrep `debug-enabled` (CWE-489), independently.

"Only in dev" isn't a defence, because dev flags are precisely the ones that ship by accident —
left on for a demo, a cloud dev box with a public IP, a laptop on conference wifi. The mitigation
is structural, not disciplinary: `backend/app.py` hardcodes `debug=False`, and if you ever need
it, gate it behind an explicitly-named env var that defaults to off, never a bare `debug=True`
in committed code.

*(Worth knowing: `debug=True` is also the single most common finding in our own pilot data —
generated by the models, in the `if __name__ == "__main__":` blocks they volunteer. See
[§7](#7-what-the-2026-09-07-review-changed-and-why-it-matters).)*

### "Is the database actually storing everything, and can I verify it?"

Yes. Verified live during the review by calling `project_status` through the running MCP server
against the real database — 450 stored runs with per-status breakdowns, not a mocked number.
Each row carries the whole trace (see [§1](#1-design-questions--why-is-it-built-like-that)),
`metrics.py` computes every rate from that raw evidence, and the dashboard's Run History tab
renders the exact stored code and findings per stage. There is no summary table that could drift
from the underlying data, because there is no summary table.

### "Is anything in this repo dangerous to run?"

`demo/vulnerable_example.py` is deliberately vulnerable code — it exists as scanner bait for
testing `scan_path`. It is never imported or executed by the pipeline; its header says so. Aside
from that: Engine D executes model-generated code, which is why it runs in a sandboxed
subprocess with a hard timeout, no network egress, and a fake DB/LDAP layer rather than real
services.

---

## 7. What the 2026-09-07 review changed and why it matters

A full read of the codebase, every research PDF, and every doc surfaced four bugs and two
findings that change how the paper must be written. Full list of file changes in
[CHANGELOG.md](CHANGELOG.md).

### Bugs fixed

1. **MCP server hung on every tool that shells out.** Two stacked causes: `subprocess.run(...)`
   never set `stdin=`, so Bandit/Semgrep inherited the MCP server's own stdin — which under
   stdio transport is the pipe the client sends requests on (Windows-specific hang); and
   FastMCP runs synchronous tools directly on the event-loop thread, so a multi-second scan
   blocked the whole server. Fixed with `stdin=subprocess.DEVNULL` everywhere and `async def` +
   `asyncio.to_thread` on all six tools. Verified by round-tripping every tool through a real
   MCP client, including a real model call.
2. **Cross-tool findings were double-counted.** Dedup keyed on `(line, cwe-set)` and
   `(line, rule)`, so the *same* weakness detected by both analysers slipped through whenever
   they mapped it to different CWEs: `app.run(debug=True)` counted twice (Bandit CWE-94 +
   Semgrep CWE-489), as did `host="0.0.0.0"` (CWE-605 + CWE-668). **Those two pairs alone were
   180 of 291 pilot findings** — raw finding counts were inflated roughly 1.6×. Fixed with a
   cross-tool equivalence map that merges them, unions the CWEs, keeps the higher severity, and
   records `bandit+semgrep` so the corroboration is preserved. *Binary vulnerability rates
   (RQ1–RQ4) are unaffected — they only ask count > 0 — but any per-finding statistic computed
   before this fix is not comparable with one computed after.*
3. **The cost gate priced Gemini at $0** after it moved off the free tier, meaning a
   Gemini-inclusive batch would have started without confirmation. Now priced; full-experiment
   estimate is **~$8**, not "<$5".
4. **The frontend** was a dark, saturated, heavy-rounded AI-dashboard look; rewritten flat and
   light against a contrast- and colourblind-validated palette. Same IDs and logic.

### Findings that change the paper

5. **False-positive rate ≈ 53.6%** (single-annotator triage of a stratified 10% sample; *not*
   the two-annotator κ protocol, and labelled as such by the tool). Well above the 20% threshold
   in `docs/01_RESEARCH_QUESTIONS.md`. It is concentrated, not diffuse — three rule families
   dominate: pyCrypto-namespace deprecation (Bandit can't distinguish maintained pycryptodome
   from abandoned pycrypto), binding to `0.0.0.0` (correct and required in containers), and
   RSA-2048 flagged as "insufficient" (policy-strict; 2048 is NIST-acceptable through 2030).
   **Implication:** report FP-adjusted rates, or a sensitivity analysis excluding those rules.
6. **62% of findings landed on scaffolding the model volunteered**, not on the requested
   function — `app.run(...)` and `if __name__ == "__main__":` lines. The most common finding in
   the entire pilot is the model demonstrating its own endpoint with `debug=True`.
   **Implication:** "vulnerability rate" as currently defined substantially measures Flask demo
   boilerplate. Report with and without scaffolding findings, or expect a reviewer to say so
   first. `analysis/rq_analysis.py` now computes and prints this split every run.
7. **RQ5 needs its control, and now has one.** Raw "scanner-clean but fails its test" was 62.5%
   after repair — but 50% for never-repaired code, so the difference attributable to repair is
   ~12.5pp (Fisher p=0.72, n=8 — nowhere near significance on pilot data). If that pattern holds
   at full scale, the honest headline is **"scanner-clean LLM code frequently doesn't work"**,
   not "the repair loop breaks code." Both are publishable; only one is supported. The analysis
   computes both and says which sentence the data licenses.

None of items 5–7 is bad news. Each is a critique the work would have received *after*
submission, caught before the expensive run instead.
