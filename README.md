# 🛡️ LeBlanc v3

**One sentence:** we measure how much security scaffolding (CWE-aware prompt enrichment + scanner-guided iterative repair) still buys you across LLM generations — and how often "repaired" code is secretly broken.

If you're new here — welcome! This README is meant to answer *literally every* "wait, how does that work" question you could have about this repo: what it does, how to run it, what math is under the hood, which papers we're testing ourselves against, and what still needs doing. If something isn't explained below, that's a bug in this file — open an issue or yell at Suryanshu.

**The four other files worth knowing about:**

| File | What it's for |
|---|---|
| **[RUNBOOK.md](RUNBOOK.md)** | Everything left to do, as commands, in order, with costs and expected output. **Start here if you just want to finish the project.** |
| **[FAQ.md](FAQ.md)** | *Why* it's built this way — design decisions, the roadmap, the paper's venue strategy, the benchmark reference sheet |
| **[TODO.md](TODO.md)** | The prioritised checklist |
| **[CHANGELOG.md](CHANGELOG.md)** | What changed and when, in plain language |

---

## Table of contents

1. [TL;DR — what even is this](#tldr--what-even-is-this)
2. [Explain it like I'm new here — the whole project in plain English](#explain-it-like-im-new-here--the-whole-project-in-plain-english)
3. [What it can actually do right now](#what-it-can-actually-do-right-now)
4. [Quickstart — running in under 5 minutes](#quickstart--running-in-under-5-minutes)
5. [The pipeline, exactly — Engines A–D with the real math](#the-pipeline-exactly--engines-ad-with-the-real-math)
6. [The research questions & the exact formulas we score ourselves on](#the-research-questions--the-exact-formulas-we-score-ourselves-on)
7. [Pilot results — first real data](#pilot-results-2026-09-01--first-real-data-read-carefully)
8. [The dataset](#the-dataset)
9. [The papers we're reading and re-testing](#the-papers-were-reading-and-re-testing)
10. [The MCP server — LeBlanc as an agent tool](#the-mcp-server--leblanc-as-an-agent-tool)
11. [The dashboard](#the-dashboard)
12. [Repo layout](#repo-layout)
13. [Code style & conventions](#code-style--conventions)
14. [Project status & milestones — and honestly, what % done is this?](#project-status--milestones--and-honestly-what--done-is-this)
15. [Research validity — the things that would otherwise get this rejected](#research-validity--the-things-that-would-otherwise-get-this-rejected)
16. [FAQ — moved to its own file](#faq--moved-to-its-own-file)
17. [Known housekeeping / things we still owe ourselves](#known-housekeeping--things-we-still-owe-ourselves)
18. [Team](#team)

---

## TL;DR — what even is this

Back in 2022–2024, a bunch of papers showed that if you (a) warn an LLM about the specific CWEs a coding task is prone to *before* it writes anything, and/or (b) run a security scanner on what it wrote and feed the findings back for a fix, the resulting code gets measurably safer. Cool. Useful. But those papers tested this on 2022–2024 models.

It's 2026 now. Models got a lot better at writing correct-looking code without anyone holding their hand. So the obvious, slightly annoying question nobody had measured yet: **does that old scaffolding still do anything for current models, or is it dead weight we're all cargo-culting?**

LeBlanc is not claiming those older papers were wrong — it's asking whether their results still generalize three model generations later. That's the whole pitch:

```
prompt → [security warning injected] → LLM writes code → [Bandit + Semgrep scan]
        → [optional: scanner-guided auto-repair, ≤3 tries] → [functional smoke test]
```

Every arrow above is a real, working piece of code in this repo (not a diagram we drew and then didn't build). We run every prompt through every combination of {plain, enriched, enriched+repair} × {6 model generations} × {3 repetitions}, and measure what changes.

The sharpest thing we're adding on top of "does scaffolding still help": **nobody has measured how often a scanner-clean "successful repair" is actually functionally broken code, inside a live iterative repair loop.** That's RQ5 below, and it's the headline finding we're chasing.

## Explain it like I'm new here — the whole project in plain English

You asked an AI ("ChatGPT, write me a login page") for code before. It gave you something that ran. What it probably didn't tell you: that code might have a hole in it that lets a stranger read your entire user database, delete your files, or run their own commands on your server. Not because the AI is malicious — because it learned to write code by reading millions of real GitHub repositories, and a lot of real code on GitHub is *also* full of these holes. The AI copied the bad habits along with the good ones.

Security researchers have known this for years and tried two fixes:

1. **Warn the AI before it writes anything** — tell it "hey, this kind of task is prone to SQL injection, be careful" before it generates the code. Papers show this genuinely helps.
2. **Check the code after, and tell the AI to fix what's wrong** — run a scanner, hand it the list of problems, ask it to patch them, check again. Papers show this helps too.

Every one of those papers, though, tested this in **2022–2024**, on the AI models of that era (GPT-3.5, early CodeLlama, etc.). Models have gotten dramatically better since then at writing code that *looks* correct on the first try. Nobody had gone back and asked the boring-but-important question: **does that old advice still do anything, or have models simply outgrown needing it?** And a second question nobody had asked at all: **when the AI says "fixed it," is the fixed code actually still doing its job, or did it just delete the risky feature to make the scanner shut up?**

LeBlanc is a small, fully automated pipeline built to answer exactly those two questions, with real numbers instead of guesses. Concretely, here is everything that happens for one line item of the experiment:

1. **Take one of 50 pre-written coding requests** ("write a login endpoint," "write a function that extracts a tar file," ...) — some hand-written, most borrowed from a well-known academic security benchmark called SecurityEval, so the results can be compared to other papers.
2. **Optionally warn the model first** (Engine A) — a small local lookup system reads the request, decides which of 46 known vulnerability types it's likely to touch, and appends a warning paragraph. No AI is used for this step — it's a plain, fast, deterministic keyword + similarity search.
3. **Send it to an AI model** to actually write the code. This is repeated across 6 different models spanning 3 "tiers" (a small/cheap model, a couple of mid-tier ones, a couple of today's frontier models), so the comparison isn't about one AI, it's about how the *idea of scaffolding* holds up as models improve.
4. **Scan the code it wrote** (Engine B) with two independent, industry-standard security scanners (Bandit and Semgrep — the same category of tool a real security team would run in a CI pipeline). If they find something, that's a real, tool-verified finding, not an opinion.
5. **If something's wrong, ask the same AI to fix it** (Engine C), tell it exactly what the scanners found, and rescan. Repeat up to 3 times. If it's still broken after 3 tries, that's recorded honestly as "didn't converge" — not swept under the rug.
6. **Actually run the resulting code** (Engine D) against a small hand-written test — because a scanner can say "looks secure" about code that, say, no longer logs anyone in at all. This is the step nobody else's research does, and it's the whole point of the project's sharpest question (RQ5, below): **how often does "fixed" secretly mean "broken"?**
7. **Log every single one of those steps** — the original prompt, the warning that got added, the exact code the AI wrote, every scanner finding, every repair attempt, and whether the final code actually works — into one SQLite database row. Nothing is summarized or thrown away before storage; the dashboard and the eventual paper compute every number *from that raw data*, live, so no number in this project is hand-typed.

Do that for 50 prompts × 6 models × 3 "modes" (no help / warned / warned-and-repaired) × 3 repeats (because AI output is randomized, so one run of anything proves nothing) and you get 2,700 data points — enough to say something statistically real about whether the old advice still matters, and where it breaks down. That's the whole project. Nothing about it is more exotic than that; the value isn't a clever new algorithm, it's rigorously *measuring* an idea everyone assumed but nobody had checked recently.

## What it can actually do right now

Not aspirational — everything in this list is built, runs, and you can go try it right now:

- ✅ **Generate code from 6 different LLMs** (Groq's `gpt-oss-20b`/`gpt-oss-120b`, Google's `gemini-2.5-flash`, OpenAI's `gpt-4o-mini`, Anthropic's `claude-haiku-4.5`, DeepSeek's `deepseek-chat`) across 3 security "modes"
- ✅ **CWE-aware prompt enrichment** using a real lexical + TF-IDF retrieval engine (not keyword substring matching — see Engine A below)
- ✅ **Dual static analysis** — Bandit ∪ Semgrep, deduplicated, CWE-mapped, with a pinned offline ruleset so results don't silently drift
- ✅ **Iterative auto-repair** — feeds scanner findings back to the model, up to 3 rounds, and tells you honestly when it *doesn't* converge
- ✅ **Functional smoke testing** — catches "scanner says clean but the code doesn't actually work" repairs, with a fully **offline** fake-MySQL/fake-LDAP/fake-network harness so DB- and auth-heavy prompts are testable with zero live services
- ✅ **A cost-gated, resumable batch experiment runner** that refuses to spend real money without you explicitly saying so
- ✅ **A live dashboard** with 5 tabs: project overview, live research-question numbers, a "try it yourself" lab, full run history with a stage-by-stage code viewer, and the dataset browser
- ✅ **An MCP server** exposing 6 of these tools to any MCP-speaking coding agent (Claude Code, Claude Desktop, Cursor…) — so the security pipeline isn't just a research artifact, it's something a coding agent can actually call mid-task
- ✅ **A 50-prompt frozen dataset**, 20 of which have full functional test suites with hand-verified reference solutions

## Quickstart — running in under 5 minutes

```bash
# 1. install
cd backend
pip install -r requirements.txt

# 2. API keys — see "API keys" below. Free tier needs GROQ_API_KEY + GEMINI_API_KEY only.
#    Keys live in D:\LYPROJECT\.env (one level above this repo, never committed).

# 3. sanity-check the fleet before spending anything (free — 1 tiny call per model)
python run_batch.py --preflight

# 4. launch the dashboard
python app.py
# -> http://localhost:5000

# 5. (optional) run a free pilot — Groq-only, $0, resumable
#    (gemini-2.5-flash moved to paid billing on 2026-09-07 — including it costs money now)
python run_batch.py --models gpt-oss-20b gpt-oss-120b --modes all --reps 1

# 6. (optional) hook it up to Claude Code as an agent tool
claude mcp add leblanc -s user -- python D:/LYPROJECT/v3/backend/mcp_server.py
```

That's it. No Docker, no external services, no signup beyond the two free API keys.

### API keys — what you actually need

| Key | Model it unlocks | Cost | Required? |
|---|---|---|---|
| `GROQ_API_KEY` | `gpt-oss-20b`, `gpt-oss-120b` | free | the only genuinely free models |
| `GEMINI_API_KEY` | `gemini-2.5-flash` | **paid since 2026-09-07** (~$2 for the full experiment) | recommended — it's the G3 anchor |
| `OPENAI_API_KEY` | `gpt-4o-mini` | ~$1 for the whole experiment | optional |
| `ANTHROPIC_API_KEY` | `claude-haiku-4.5` | ~$3 | optional |
| `DEEPSEEK_API_KEY` | `deepseek-chat` (cheapest current-gen) | ~$0.30 | optional |

The Groq key alone runs 2 of the 6 fleet models at zero cost. **Gemini was on the free tier when the 2026-09-01 pilot ran and is not any more** — that pilot's "$0" is a historical fact about that run, not a claim about repeating it today. The cost gate knows this: `run_batch.py` now prices Gemini and will refuse to start a Gemini-inclusive batch without `--yes`. Full 6-model experiment ≈ **$8**.

## The pipeline, exactly — Engines A–D with the real math

This is the part where we don't hand-wave. Every formula below is copy-pasted logic from the actual source files, not a simplified retelling.

### Engine A — Enrichment (`backend/engine_a_enrich.py`)

**What it does:** reads a coding prompt, figures out which CWEs it's likely to touch, and injects targeted security warnings *before* any code gets written. Fully offline, deterministic, no LLM call, no network — it's a local retrieval system over a 46-entry hand-curated CWE knowledge base (`backend/cwe_kb.json`).

**How it actually decides which CWEs match**, hybrid retrieval, two passes fused into one score:

1. **Lexical pass** — regex word-boundary match against each CWE entry's keyword list (e.g. CWE-89/SQL-Injection has keywords like `sql`, `mysql`, `query`, `cursor`, `table`). High precision: if your prompt says "table" and "login," that's a real signal.
2. **Semantic pass** — TF-IDF cosine similarity between your prompt and each CWE's knowledge-base document, so a prompt that *describes* a risky task without using the trigger words still gets caught (recall).

> **Plain-English version, no math required:** think of Engine A as a detective holding your prompt next to 46 "wanted posters" (one per CWE), each covered in distinctive clues (keywords + a description). Two ways a poster can match:
> - **The obvious way (lexical):** your prompt literally says a clue word from the poster — "table," "password," "login." Case closed, that's a strong hit.
> - **The vibe-based way (semantic):** your prompt never says the clue words, but *talks about the same kind of thing* the poster describes — e.g. "check if this username and password are correct" without ever saying "SQL" or "table." A word-search would miss this; TF-IDF + cosine catches it because it compares the *pattern* of important words, not exact matches.
>
> "TF-IDF" itself is just a way of scoring how *telling* a word is. "The" appears in every sentence ever, so it tells you nothing — low score. "Bcrypt" appears almost nowhere except crypto-related text, so if it shows up, it's a strong clue — high score. TF-IDF = (how often this word shows up here) × (how rare it is everywhere else). "Cosine similarity" is then just "how similar are two lists of these clue-scores" — same idea as measuring how close two compass directions are, 1.0 = pointing the exact same way, 0 = pointing nowhere near each other.
>
> **Why this helps us catch our own screwups:** if you ever see Engine A miss an obviously-SQL prompt, the fix is almost always "the KB entry's keyword list doesn't have that word" (lexical gap) rather than "the math is broken" — worth knowing before you go debugging cosine formulas for a keyword-list problem.

The TF-IDF math, exactly as implemented:

```
idf(t)      = ln( (1 + N) / (1 + df(t)) ) + 1        (N = 46 KB entries, df = doc frequency of term t)
tf-weight   = 1 + ln(count(t))                        (log-dampened term frequency)
doc-vector  = { t: tf-weight(t) · idf(t) }, then L2-normalized
cosine(q,d) = Σ over shared terms of (query_weight/query_norm) · doc_weight
```

Then the two passes are **fused** into one score per CWE candidate:

```
score = 0
if lexical hit:      score += 1.0 + 0.05 × (n_distinct_keywords − 1)
if cosine ≥ 0.12 (or there was a lexical hit): score += 0.8 × cosine
```

(In words: a literal keyword match is worth a flat 1.0 — almost always enough on its own to
qualify — plus a small bonus if several *different* keywords hit. A "vibe" match on its own
needs to clear a minimum similarity bar (0.12) before it counts at all, and even then it's
weighted lower (×0.8) than a literal hit, because "sounds similar" is less trustworthy than
"said the actual word.")

The **top 5** CWEs with `score > 0` get their warnings injected into the prompt, formatted as:

```
<original prompt>

IMPORTANT SECURITY REQUIREMENTS:
- Avoid CWE-89 (SQL Injection): use parameterised queries...
- Avoid CWE-259 (Hardcoded Password): ...

Write secure code that avoids the above vulnerabilities.
```

Every match also carries its evidence (matched keywords + cosine score) into the database, so the paper's audit trail can show *why* a CWE was flagged, not just that it was.

### Engine B — Dual static scan (`backend/engine_b_scan.py`)

**What it does:** takes raw LLM output, validates it's real Python, and runs it through two independent security scanners, then merges and deduplicates the results.

1. **Extraction & syntax gate** — regex-extract the fenced ` ```python ` block, then `py_compile.compile()` it. If either step fails, the outcome is recorded as its own class, `extraction_failed` — **never silently counted as "clean."** This matters a lot: a model that writes broken Python isn't secure, it's just broken, and conflating the two would be dishonest.
2. **Bandit** — `bandit -q -f json -ll <file>` (`-ll` = medium+ severity only). Findings are mapped to a CWE via `issue_cwe`.
3. **Semgrep** — `semgrep scan --config <pinned local ruleset> --json`. We deliberately pin a **local copy** of the `p/python` registry pack (781 rules, `backend/semgrep_rules/python.yaml`) instead of hitting `semgrep.dev` live, for two reasons: scans need zero network, and results stay reproducible (a live registry pack *will* change under you months apart, silently altering your "same" experiment). If Semgrep is missing or errors, the scan **gracefully degrades to Bandit-only and records exactly which scanners ran** — so no run can ever silently claim dual-scanner coverage it didn't actually have.
4. **Union + dedup** — findings from both tools are merged, then deduplicated by `(line, sorted CWE-set)` first, then `(line, rule_id)` as a fallback, so the same real issue caught by both tools only counts once.

Output: `(findings, clean_code, scanners_used)`. `vuln = len(findings) > 0`.

### Engine C — Iterative repair (`backend/engine_c_repair.py`)

**What it does:** if Engine B found anything, build a repair prompt (numbered list of `[CWE] SEVERITY at line N: message`, plus the vulnerable code) and ask the model to fix it — **while explicitly preserving the code's public interface** (same functions, same routes, same behavior on valid input, so a "repair" can't just be deleting the risky feature). Re-scan. Repeat, **capped at 3 iterations**.

```
for i in 1..3:
    if no current findings: break        # converged
    ask model to fix, given the findings list
    re-scan the response
    if extraction/compile fails: stop, final_status = "extraction_failed"
    if still has findings: loop again
final_status = "clean" | "not_converged" | "extraction_failed"
```

This prompt shape — numbered findings list + CWE context + "return only the fixed code" — deliberately mirrors **HexaCoder's** oracle-report-plus-hint repair format (see [literature](#the-papers-were-reading-and-re-testing) below), so we're testing the same repair *idea*, just at inference time instead of baked into training.

Non-convergence (code still vulnerable after 3 tries) is **reported as data**, not swept under the rug — RQ3 is specifically about how often and how fast repair converges per model generation.

### Engine D — Functional smoke test (`backend/engine_d_functest.py`)

**What it does:** this is the engine that didn't exist in v2, and it's the whole reason RQ5 (repair inflation) is even measurable. A scanner saying "clean" tells you nothing about whether the code still *works*. Engine D runs the prompt's `pytest` file against the final code, in a sandboxed subprocess, with a **30-second hard timeout** and **no network**.

The clever bit: most of the interesting security prompts (SQL, LDAP auth, SSRF/network fetches) *need* a real database or network call to test meaningfully — which would normally make them untestable without spinning up real services. Instead, Engine D installs an **offline harness** (`dataset/tests/_harness/`) into every sandbox before the test runs:

- a **shared SQLite-backed fake MySQL** (patches `mysql.connector` / `MySQLdb`) — `%s`/`%(name)s` placeholders are genuinely executed against a real seeded `users` table, reset before every test, so parameterized-query code and injectable code behave *differently*, for real, not by mock
- **fake `ldap`/`ldap3`** packages with real RFC 4515/4514 escaping helpers, so an implementation that correctly escapes LDAP filters is actually exercised, not just assumed correct
- **network fakes** — `urllib`, `requests`, raw `socket`/`ssl` all patched to return canned local data, no egress possible

This one design decision is why the dataset's functional-test coverage doubled from a pre-harness estimate of ~10–12 testable prompts to **20/50** — see `dataset/tests/MANIFEST.md` for the exact reasoning per prompt.

Outcomes: `pass` / `fail` (secure-but-broken candidate) / `no_tests` (prompt wasn't in the M2 20) / `timeout` / `harness_error` (the test runner itself broke — never silently counted as pass or fail).

## The research questions & the exact formulas we score ourselves on

### First, the two stats tools we lean on — in plain English

**Wilson confidence interval — "how much should I trust this percentage?"**

> Say you flip a coin 5 times and get 3 heads. Technically that's "60% heads" — but you
> wouldn't actually believe the coin is biased, right? 5 flips is nothing. Now flip it 500
> times and get 300 heads: still 60%, but now you'd genuinely suspect something's up. Same
> percentage, wildly different amount of trust — because trust depends on *how many times you
> measured*, not just the percentage itself.
>
> A **confidence interval** is that intuition turned into a number: instead of just saying
> "60% vulnerable," we say "60% vulnerable, and given our sample size, the true rate is
> probably somewhere between 42% and 76%." Small sample → wide range (don't trust the
> headline number much yet). Big sample → narrow range (trust it). This is the exact same
> math behind the "margin of error" you see on election polls.
>
> The formula (Wilson's version, which stays well-behaved even with small samples or rates
> near 0%/100%, unlike the naive "±1.96×std-error" version taught in intro stats):
> ```
> p = k / n
> center = (p + z²/2n) / (1 + z²/n)
> half   = (z / (1 + z²/n)) · sqrt( p(1−p)/n + z²/4n² )
> CI = [center − half, center + half]              (z = 1.96 for 95% confidence)
> ```

**McNemar's test — "did the *same* prompts actually change, or is this noise?"**

> Imagine testing a diet: you weigh the same 50 people before and after, not two different
> groups of 50. You only care about the people whose weight *changed* — 12 lost weight, 3
> gained weight, and 35 stayed exactly the same. The 35 "no change" people tell you nothing
> about whether the diet worked, so you ignore them and just ask: "are the 12 wins
> significantly more than the 3 losses, or could that 12-vs-3 split just be random noise?"
>
> That's McNemar's test, exactly, applied to `plain` vs. `enriched` on the *same* prompt run
> twice: `b` = "enrichment turned a vulnerable output clean" (a win), `c` = "enrichment turned
> a clean output vulnerable" (a loss — yes, this can happen, and we report it if it does). We
> ignore runs that didn't change either way, same as ignoring the 35 unchanged dieters.
> ```
> n = b + c
> k = min(b, c)
> p_value = min(1, 2 · Σ_{i=0}^{k} C(n,i) / 2ⁿ)          (p < 0.05 ⇒ probably a real effect)
> ```

### The five questions

| RQ | Question | Formula | Hypothesis | Tested against |
|---|---|---|---|---|
| **RQ1** — baseline gap | How vulnerable is each model generation with zero help? | `VR(model) = vuln runs / plain-mode runs` | VR(G1) − VR(G3) ≥ 20 percentage points | Pearce et al. 2022 — ~40% of Copilot's code was vulnerable. Is that still true? |
| **RQ2** — enrichment | Does CWE-aware prompting still reduce vulnerabilities, and does the benefit shrink as models improve? | `ΔE(model) = VR_plain − VR_enriched`, paired by (prompt, rep) | ΔE ≥ 15pp for G1 (old/small), <5pp for G3 (current) | SecuCoGen — enrichment worked, but only shown single-turn on older models |
| **RQ3** — repair speed | Of the initially-vulnerable outputs, what fraction converges to clean within 3 tries, and how fast? | `CR = converged / initially-vulnerable`; `IT = mean iterations (converged only)` | CR(G3) > CR(G1); IT(G3) < IT(G1) | HexaCoder — same repair-prompt idea, inference-time instead of trained-in |
| **RQ4** — residual risk | Which CWE categories still slip through **full** scaffolding on 2026 models? | `RVR(category) = still-vulnerable-after-repair / n`, per (category, generation) | none — exploratory catalog, the practitioner payoff | DOMAINEVAL — category-level difficulty |
| **RQ5** — repair inflation (the headline) | How often is a "successfully repaired" run secretly broken? | `RIR = P(functional test FAILS given scanner says clean after repair)` | RIR ≥ 15% | CODEGUARD+ / CodeSecEval's secure-pass@k lens — **no prior work measures this inside a live scanner-feedback loop; this is our sharpest claim** |

All five formulas are implemented verbatim in `backend/metrics.py` and shown live, next to the real numbers, in the dashboard's Research Questions tab — nobody hand-types a number into the paper.

### "Does it or doesn't it" — reading a result without second-guessing yourself

The hypotheses above say what we *expect*. This table says, decided in advance (so we can't
quietly nudge it after seeing the data), **what actual number counts as yes, no, or "too
early to say."** Full version with the reasoning behind each band lives in
`docs/01_RESEARCH_QUESTIONS.md` — this is the cheat-sheet.

⚠️ **Rule zero:** if a rate comes from fewer than 5 runs, `metrics.py` marks it `insufficient`
— that's not a verdict yet, it's noise wearing a percentage sign. Wait for more reps.

| RQ | 🟢 Yes | 🟡 Partial / mixed | 🔴 No |
|---|---|---|---|
| RQ1 (gap) | gap ≥ 20pp, ordering G1≥G2≥G3 holds | 10–20pp gap | <10pp, or the order's scrambled — a real finding, not an error |
| RQ2 (enrichment) | ΔE(G1) ≥ 15pp **and** p<0.05 | positive but under 15pp, or significant for only some models | ΔE(G3) < 5pp — expected, this *is* "yes" for the obsolescence half of H2 |
| RQ3 (repair speed) | CR(G3)−CR(G1) ≥ 15pp **and** IT(G3) < IT(G1) | CR/IT roughly flat across generations | CR(G1) > CR(G3) — a reversal, dig into why before writing a headline |
| RQ4 (residual risk) | RVR < 10% — essentially solved | 10–30% — partially mitigated | ≥ 30% — a real unsolved category, this is the practitioner payoff, don't undersell a red cell |
| RQ5 (repair inflation) | RIR ≥ 15% — H5 confirmed | 5–15% — real but not dramatic | RIR < 5% — repair claims are trustworthy here |

Two things worth internalizing before anyone runs the numbers for real: **read every band per
model or per category, never pooled first** (a fine-looking G3 average can hide one bad model
or one red CWE category — RQ4 exists specifically to surface that). And **🔴 is a real,
publishable answer** — if RQ1–RQ3 all land red, that's evidence the "scaffolding is obsolete"
story is *wrong*, which is just as citable as if it were right. Don't let the table quietly
pressure a borderline result toward green.

## Pilot results (2026-09-01) — first real data, read carefully

We ran the pilot end to end: **450 runs, 50 prompts × 3 models × 3 modes, $0 spent (all three were on free tiers *at the time* — Gemini has since moved to paid billing), 68.5 minutes.** This is *not* the real experiment — it's the warm-up that exists to catch exactly the kind of bugs it caught (see below). Three things to keep in your head reading every number in this section:

> ⚠️ **These numbers predate the 2026-09-07 dedup fix.** The scanners were double-counting any weakness both tools found but labelled with different CWEs — 180 of the 291 findings here. Vulnerability *rates* are unaffected (they only ask "any finding?"), but raw finding **counts** below are inflated ≈1.6×. See [CHANGELOG](CHANGELOG.md).
>
> ⚠️ **A 10% false-positive triage of these findings came back at 53.6%**, concentrated in three noisy rules, and **62% of all findings landed on `app.run()` boilerplate** the model volunteers rather than on the requested function. Read every rate below with that in mind — and see [FAQ §7](FAQ.md#7-what-the-2026-09-07-review-changed-and-why-it-matters), because it changes what the paper can claim.

> ⚠️ **None of these 3 models are actually "old."** `gpt-oss-20b`, `gpt-oss-120b`, and `gemini-2.5-flash` are all 2025–26 models — Groq deleted the real old/small anchor model (`llama-3.1-8b-instant`) out from under us mid-project (see the fleet-fix note in `docs/03_METHODOLOGY.md`). So right now "G1/G2/G3" only means "small vs. big vs. different vendor," **not** "old vs. new." The real generational question (RQ1's whole point) needs the paid-key models back in the fleet — that's an M4 thing, not fixable for free. Read the charts below as "how do 3 current models compare," not "did models get safer over time."
>
> ⚠️ **This is 1 repetition per cell, not the planned 3.** Good enough to catch bugs and spot directional signal, not good enough to publish a number from.

### The numbers

<img src="docs/figures/pilot/rq1_baseline_vr.png" width="560" alt="RQ1 pilot chart — baseline vulnerability rate per model">

Reading this against the [decision-band table](#does-it-or-doesnt-it--reading-a-result-without-second-guessing-yourself): the gap is **negative** (gpt-oss-20b is *less* vulnerable than gemini-2.5-flash here, backwards from H1) and the ordering is scrambled → 🔴 by the letter of the band. But per the caveat above, this isn't really testing H1 yet since there's no old model in the mix — treat it as "these 3 current models differ from each other," which is itself mildly interesting (a 20B model outperforming a 120B model and Gemini on raw baseline security), not as evidence about generational drift.

<img src="docs/figures/pilot/rq2_enrichment_delta.png" width="620" alt="RQ2 pilot chart — plain vs enriched vulnerability rate per model">

This one's the pleasant surprise: **enrichment helped, a lot, on every single model** — 14 to 22 percentage points, including on gemini-2.5-flash (the "current-gen" slot, where H2 predicted the effect should have nearly vanished). Only `gpt-oss-120b`'s drop was statistically significant yet (p=0.013; the other two aren't significant at n=1 rep — expect that to resolve with 3 reps). If this holds up at full scale, it's a genuinely interesting counter-signal to the "scaffolding is obsolete" story — worth watching closely, not dismissing.

<img src="docs/figures/pilot/outcome_breakdown.png" width="620" alt="Full outcome breakdown per model across all 450 pilot runs">

The full picture, warts included — see next section for what that orange band actually was.

### The bug the pilot was supposed to catch (and did)

`gemini-2.5-flash` initially came back with a **59% "extraction_failed" rate** — wildly higher than the other two models. Before writing that up as "Gemini writes broken code," we checked the raw stored responses: **88 of 89 failures had an unclosed code fence** — the model was still mid-sentence (usually trailing comments) when it hit `max_tokens=2048` and got cut off, so our regex never found a closing ` ``` `. Not a security signal, a budget bug. Fixed (`max_tokens` → 4096, committed with the exact before/after numbers in the commit message), which dropped it to 31% — better, but Gemini is still visibly more verbose than the other two models, so a **per-model token budget** is the likely real fix before M4, not yet applied.

This is exactly why the pilot exists before the real 2,700-run experiment: catching this kind of thing for $0 and 68 minutes instead of finding it after burning real API budget on all 6 models.

### Manual sanity check — is the generated code actually real, or hallucinated garbage?

Before trusting any of the numbers above, we pulled a spread of ~10 actual generated-code samples across all 3 models, all 3 modes, and multiple outcome types, and read them by hand. Verdict: **every sample was coherent, on-topic Python using real library APIs correctly** — no hallucinated function names, no nonsense output, no off-topic text. Two samples were worth writing up as genuine "secure-but-broken" cases — real examples of exactly what RQ5 is designed to catch:

- **A repair that quietly changed the contract.** `S032` (deserialize untrusted pickle data) came in vulnerable, went through Engine C, and came back scanner-clean — but it had swapped `pickle.loads` for `yaml.safe_load`/`json.loads` entirely, changing what kind of input the function actually accepts, *and* left a stray unused `from django.http import ...` import that isn't installed in the test sandbox. The functional test correctly caught it: `ModuleNotFoundError`, `fail`. Bandit/Semgrep both said "clean." That gap — clean scanner, broken test — is RQ5's entire reason for existing, caught on our very first real batch.
- **A model over-delivering on security in a way our own test wasn't ready for.** `S001` (remove a user from the database) came back from `gemini-2.5-flash` with a correctly parameterized query (real CWE-89 fix) *and* a refusal to run without `DB_USER`/`DB_PASSWORD` environment variables (avoiding hardcoded credentials — also a real, good instinct). Our sandbox doesn't set those, so the function raises before it ever touches the database, and the test fails. This one's more nuanced than a "bug" — it's arguably *more* secure than the reference solution, just incompatible with how the current test harness is built. Worth a line in Threats to Validity, not a strike against the model.

Nothing in the sample looked fabricated or nonsensical. The pipeline's honesty philosophy (never fold a failure into "clean" to make a number look better) held up under a real hand-check, which is the best evidence we have right now that the numbers above are trustworthy as *directional* signal.

## The dataset

**50 Python prompts, frozen.** `dataset/leblanc_v3_prompts.json` is the file of record.

| Slice | IDs | Count | Source |
|---|---|---|---|
| Original scenarios | L001–L010 | 10 | Written by the team — realistic feature requests (login endpoint, file upload, JWT dashboard) |
| SecurityEval-derived | S001–S040 | 40 | Stratified selection from [s2e-lab/SecurityEval](https://github.com/s2e-lab/SecurityEval) (Siddiq & Santos, 2022), 121-prompt raw pool preserved in `dataset/securityeval_prompts.json` for provenance |

Category split: Injection 11 · Auth 12 · Crypto 7 · File/Path 8 · Deserialization 9 · Web/Request 3.

**Functional test coverage: 20/50 (40%).** Every prompt without a test has a specific, documented reason in `dataset/tests/MANIFEST.md` — no "TODO, write test later" backlog. Common reasons: no fixed callable interface (the 10 natural-language L-prompts), an inherently destructive happy path that isn't sandbox-safe, or a dependency on an unfakeable SDK/OS layer (PAM, live third-party APIs). The untested 30 still fully drive RQ1–RQ4; only RQ5's sample size is affected, and that's reported honestly rather than padded.

## The papers we're reading and re-testing

The whole point of LeBlanc is re-measuring these on current models, **not** disproving them — they were correct for what they tested, on the models available at the time.

| Paper | What it established | What we're re-asking | File |
|---|---|---|---|
| **SecuCoGen** — Wang et al., 2024 | CWE-aware prompting improves generation security | Does it still help, and by how much, per model generation? | `docs/researchdocs/Two.pdf` |
| **Guiding AI to Fix Its Own Flaws** — Yan et al., 2025 | Security-hint feedback + repair helps, single evaluation | Does a *repeatable* scan→repair loop still help, and for which models specifically? | `docs/researchdocs/One.pdf` |
| **CodeSecEval** — Wang et al. | Executable secure-generation & repair benchmark | Feeds directly into our RQ5 "secure-pass" bar | `docs/researchdocs/Three.pdf` |
| **CODEGUARD+ ("Constrained Decoding for Secure Code Generation")** — Fu et al. | Security must be judged *alongside* correctness, not alone | How often do scanner-clean repairs fail basic functional tests? (this is RQ5) | `docs/researchdocs/Five.pdf` |
| **HexaCoder** — Hajipour et al. | Oracle-guided repair prompts, baked in via *training* data | Same prompt idea, but inference-time only — applicable to closed models too | `docs/researchdocs/Seven.pdf` |
| **LPO / DiSCo ("Teaching an Old LLM Secure Coding")** — Hasan et al. | Fine-tuning-based preference optimization for secure coding | The road we deliberately *don't* take — LeBlanc is API-only, no weight access needed | `docs/researchdocs/Four.pdf` |
| **DOMAINEVAL** | Category/domain-level difficulty in code benchmarks | Feeds our RQ4 residual-risk-by-category framing | `docs/researchdocs/Six.pdf` |
| **GitHub Copilot replication study** — Majdinasab et al. | Assistant security behavior drifts as models evolve | How large is that drift, quantified across 3 generations, with one consistent pipeline? | `docs/researchdocs/Eight.pdf` |
| **Pearce et al., 2022** ("Asleep at the Keyboard") | ~40% of Copilot-generated code was vulnerable in security-relevant scenarios | Our opening hook for RQ1 — is that number still anywhere near true in 2026? | cited in `docs/researchdocs/professor_presentation.md` |

Also in `docs/researchdocs/`: `literature_review_corrected.xlsx` (the full lit-review tracking sheet), `vapt_report.pdf`/`.tex` (our own earlier VAPT-style writeup), `leblanc_proposal-1.pdf` (the original project proposal), and `dataset_notes.txt` (working notes on SecurityEval/SecuCoGen/CodeSecEval as benchmark sources).

## The MCP server — LeBlanc as an agent tool

v2 had an abandoned VS Code extension. v3's answer is better: expose the pipeline as [Model Context Protocol](https://modelcontextprotocol.io) tools, so **any** MCP-speaking coding agent (Claude Code, Claude Desktop, Cursor, …) can call the security pipeline mid-task, not just researchers running a dashboard.

```bash
claude mcp add leblanc -s user -- python D:/LYPROJECT/v3/backend/mcp_server.py
```

(`-s user` registers it globally so it shows up in `/mcp` from *any* directory, not just this one — a project-scoped `local` add only loads when Claude Code's cwd matches exactly.)

| Tool | What it does | Cost |
|---|---|---|
| `analyze_prompt` | Runs Engine A on a coding request — CWEs it's likely to touch, before code exists | free |
| `scan_code` | Runs Engine B on a code snippet or fenced block | free |
| `scan_path` | Same scan, but on a real file or whole directory on disk — the codebase-scale version | free |
| `audit_llm_response` | Post-generation gate: extract + validate + scan a raw model response | free |
| `project_status` | Live experiment completeness — run counts, per-RQ data sufficiency, straight from the DB | free |
| `repair_code` | Full Engine B → C loop: scan, LLM fix, re-scan, ≤3 rounds | **spends tokens** (clearly labelled; defaults to a free Groq model) |

Quick demo, once registered — open a **fresh** Claude Code session (MCP servers load at session start, so an already-open session won't see a server registered mid-session) and ask it:

```
Use the leblanc scan_code tool on:
  os.system(f"ping {user_input}")
```

## The dashboard

`python app.py` → `http://localhost:5000`. Five tabs:

- **Overview** — what the project is, in plain terms
- **Research Questions** — the RQ1–RQ5 formulas from above, live, next to real numbers pulled from the database
- **Lab** — try Engine A for free, or run one full pipeline call (the *only* button in the whole UI that can spend money, and it's one click = one run, never a hidden batch)
- **Run History** — every run ever recorded, click into one to see all four engine stages side-by-side: the enriched prompt, the generated code with Bandit/Semgrep findings highlighted inline (red = high severity, amber = medium), and the functional test verdict
- **Dataset** — browse all 50 prompts, their CWEs, categories, and test status

Cost is gated at every layer: the web UI can only spend via that one Lab button; `run_batch.py` prints a pessimistic cost estimate and refuses to start if it's above $0 unless you pass `--yes`. Free-tier-only plans always cost $0 and run immediately, no confirmation needed.

## Repo layout

```
backend/
  app.py                 Flask dashboard + read-only APIs + the one spend-gated /api/run
  engine_a_enrich.py      Engine A — CWE retrieval (lexical + TF-IDF)
  engine_b_scan.py         Engine B — Bandit ∪ Semgrep, dedup
  engine_c_repair.py        Engine C — iterative repair loop
  engine_d_functest.py       Engine D — sandboxed functional smoke tests
  llm_client.py            multi-provider LLM client, --preflight gate
  mcp_server.py             the 6 MCP tools
  metrics.py                RQ1–RQ5 computation, Wilson CI, McNemar
  database.py                SQLite schema + idempotent upsert
  run_batch.py                the experiment runner (cost-gated, resumable)
  validate_m2.py               offline gate: every functional test passes on its reference
  test_engines.py               unit tests for the pipeline logic (pytest, free, offline)
  cwe_kb.json                 46-entry CWE knowledge base (Engine A's corpus)
  cwe_categories.py            Bandit rule / CWE → 6-category mapping
  semgrep_rules/python.yaml     pinned local Semgrep ruleset (no network scans)
dataset/
  leblanc_v3_prompts.json      THE dataset — 50 prompts, final IDs
  reference/<id>.py             hand-written secure reference solution, per tested prompt
  tests/<id>_test.py             pytest smoke test, per tested prompt
  tests/_harness/                 offline fake MySQL / LDAP / network layer
  tests/MANIFEST.md                exact test coverage + exclusion reasons
analysis/
  rq_analysis.py             M5 — every figure, table & statistic, straight from the DB
  fp_audit.py                 false-positive audit: sampler, worksheet, kappa scorer
  output/                      generated (gitignored): figures/, tables/, SUMMARY.md, results.json
paper/
  leblanc_paper.tex          compiling paper skeleton; all numbers are red \PLACEHOLDER{}
docs/
  00_DEFINITION.md .. 05_EXECUTION_PLAN.md   ground-truth project definition (see below)
  figures/pipeline_diagram.tex                 the four-engine figure, \input-ready
  figures/pilot/*.png                           pilot charts (1 rep — directional only)
  researchdocs/                                  literature PDFs, notes, the proposal
demo/
  vulnerable_example.py      deliberately vulnerable scanner bait (never executed)
frontend/
  index.html                the entire dashboard UI (vanilla JS + Chart.js, no build step)
reports/
  *.tex / *.pdf               periodic status reports to the supervising professor
RUNBOOK.md                    everything left to do, as commands
FAQ.md                        why it's built this way + roadmap + reference sheet
TODO.md                       the prioritized, actionable to-do list (P0 → P3)
CHANGELOG.md                  what changed, when, in plain language
```

## Code style & conventions

Nothing formal (no linter config checked in yet), but the code that's here follows a few consistent habits worth keeping if you're adding to it:

- **Every module opens with a docstring explaining *what it does and why*, including the actual algorithm** — not just a one-line label. Match that; future-you and your teammates will thank you.
- **Honesty over convenience.** Failure states are their own named outcome class (`extraction_failed`, `llm_error`, `no_tests`, `harness_error`, `not_converged`) and are *never* folded into "clean" or "vulnerable" just to make a number look cleaner. This is a project-wide rule, not a style nit — see `docs/01_RESEARCH_QUESTIONS.md`'s validity protocol.
- **Functions return plain tuples/dicts**, not custom classes — `(findings, clean_code, scanners_used)`, `{status, detail}`, etc. Keeps everything trivially JSON-serializable for the DB and the API.
- **snake_case everywhere**, no single-letter variables outside obvious loop counters, no premature abstraction — most engines are single-file, function-based modules, not class hierarchies.
- **Record what actually happened, not what should have happened** — e.g. `scanners_used` is stored on every run so a cell can never silently claim dual-scanner coverage it didn't have; `total_iterations` is the real count, not the cap.
- **Docs win.** `docs/00`–`05` are the ground-truth definition of the project. If code, a report, or a slide contradicts something in `docs/`, the docs are amended *in the same change* as the code — never left to drift. See the note at the top of `docs/00_DEFINITION.md`.

## Project status & milestones — and honestly, what % done is this?

Every milestone has a hard gate — no gate cleared, no next milestone claimed "done."

| Milestone | What | Gate | Status |
|---|---|---|---|
| M0 | Foundation docs + dataset selection | `docs/` exists, dataset frozen-candidate | ✅ done |
| M1 | Harness: fleet, Semgrep, batch runner, preflight | `--preflight` green on all models | ✅ done |
| M1.5 | Dashboard, metrics engine, MCP server, cost gate | dashboard boots, MCP tools callable | ✅ done — MCP hang bug found & fixed 2026-09-06, see FAQ |
| M2 | Functional tests + reference solutions | every test passes on its reference; dataset frozen | ✅ done — 20/50, `validate_m2.py` green |
| M3 | Pilot run (free tier, 450 cells) | <10% llm_error rate, 3 reps, FP audit (κ) done | 🟡 **partial — 450 cells ran, but at 1 rep not 3, and the FP audit hasn't started** |
| M4 | Full run — 2,700 cells (50×6×3×3, incl. paid models) | 100% cell-completeness matrix | ⬜ not started |
| M5 | Analysis notebook, figures, FP audit | every number reproducible straight from the DB | ⬜ not started — `analysis/rq_analysis.ipynb` does not exist yet |
| M6 | Paper draft → arXiv → venue submission | co-author + guide sign-off | ⬜ not started — `docs/04_PAPER.md` is a section skeleton, not a draft |

**So — what percentage of this is actually done?** As of the 2026-09-07 review:

- **The software: 100%.** Harness, dataset, dashboard, MCP server, and — new as of this review — the entire analysis layer (`analysis/rq_analysis.py`), the false-positive audit tooling (`analysis/fp_audit.py`), and a compiling paper skeleton (`paper/leblanc_paper.tex`). **There is no remaining code to write.** Everything runs end-to-end on the pilot database today.
- **The science: ~20%.** One 1-rep, 3-model pilot has run (450/2,700 cells). The full experiment hasn't. The paper has structure but no prose, because prose requires results.
- **Toward a submittable paper: ~35–40%.** The gap is now purely data collection, interpretation and writing — not engineering.

**"Can it be finished so the only thing left is running?"** That was the goal of the 2026-09-07 pass, and yes:

| Step | Status |
|---|---|
| M4 — collect the data | `python run_batch.py --models all --modes all --reps 3 --yes` — written, idempotent, resumable, cost-gated |
| M5 — analysis, figures, tables, stats | `python analysis/rq_analysis.py` — **built and working**; regenerates everything from the DB in seconds |
| M5b — false-positive audit | `python analysis/fp_audit.py --sample` → label → `--score` — **built**, with a pilot triage already done |
| M6 — the paper | `paper/leblanc_paper.tex` — **compiles today**; every number is a red `\PLACEHOLDER{}` awaiting real values |

The one thing no tool can do for you is **write the argument** — reading what the numbers say and turning it into prose. Everything up to that point is now a command. See **[RUNBOOK.md](RUNBOOK.md)**.

## Research validity — the things that would otherwise get this rejected

A measurement paper lives or dies on whether its numbers mean what they appear to mean. This section lists every place where a headline number depends on a *choice* rather than on the models, what we do about it, and where the code that does it lives. All of it runs automatically — `python analysis/rq_analysis.py` prints the whole thing into `analysis/output/SUMMARY.md` every time.

### The five threats, and what handles each

| # | The problem | Why it would sink the paper | What we do | Where |
|---|---|---|---|---|
| 1 | **Scanners are wrong a lot.** A stratified 10% audit of pilot findings came back at **53.6% false positives**, concentrated in three rule families. | Every RQ rests on "the scanner said so". An unreported FP rate is review comment #1, guaranteed. | Audit tooling with a reproducible sample; rates recomputed with the noisy families excluded, reported as a range next to the headline. | `analysis/fp_audit.py`, `rule_sensitivity()` |
| 2 | **62% of findings were on scaffolding the model volunteered** — `app.run(...)` / `__main__` blocks it appends after answering — not on the requested function. | "Vulnerability rate" would substantially be measuring Flask demo boilerplate. In the pilot this inflates one model's rate by **36.9pp**. | Findings are classified by whether they sit on scaffolding; rates reported with and without. | `finding_composition()`, `rule_sensitivity()` |
| 3 | **Repetitions are nested inside tasks.** 3 reps × 50 prompts is not 150 independent observations. | Naive Wilson intervals are too narrow and p-values too small — a straightforward overstatement of confidence. | Cluster bootstrap over *tasks* for every rate; cluster-robust standard errors in the logistic model. | `cluster_bootstrap_ci()`, `logistic_model()` |
| 4 | **One statistical test per model** across a family of six. | With six tests, "one came out p<0.05" is expected under a null. | Benjamini–Hochberg FDR correction; the adjusted p is what the paper quotes. | `benjamini_hochberg()` |
| 5 | **Extraction failures are excluded from the denominator**, and their rate differs sharply by model. | A model judged only on its parseable output is being flattered if parseability tracks task difficulty. | Rate reported under all three conventions (excluded / counted clean / counted vulnerable) with the spread stated. | `extraction_sensitivity()` |

### The RQ5 control that was missing

RQ5 asks how often a scanner-certified repair is functionally broken. On its own that number proves nothing about *repair* — code the model wrote clean on the first try also fails functional tests at some baseline rate. So the analysis computes the difference:

```
attributable = P(fails tests | scanner-clean, repaired) − P(fails tests | scanner-clean, never repaired)
```

On pilot data that's 62.5% vs 50.0%, i.e. **+12.5pp attributable, Fisher p=0.72 at n=8** — nowhere near significance. If that holds at full scale, the honest headline is *"scanner-clean LLM code frequently doesn't work"* (a real extension of the secure-pass@k argument) rather than *"the repair loop breaks code."* Both are publishable; only one is supported by any given result, and the analysis says which.

### Reproducibility: every run records what produced it

The project's claim is "results don't drift because the ruleset is pinned." That's unverifiable after the fact unless each run records *which* ruleset. Every row now stores a `provenance` blob — Bandit version, Semgrep version, config name, a SHA-256 of the pinned ruleset file, Python version, platform — so a number that changes later can be attributed to the models rather than to the tooling, or vice versa.

### Outcome classes stay separate

The project rule is that failure states are never folded into each other. One violation was found and fixed: extraction failures were being recorded with functional-test status `fail`, conflating *"the code doesn't work"* with *"there was never any code"* — and inflating RQ5's broken-code numerator with runs that produced no candidate at all. They now record `no_code`, which is excluded from RQ5's denominator and counted separately.

### The engines have tests now

`python -m pytest backend/test_engines.py -q` — 39 tests, ~18s (or `-m "not slow"` for the 35 that don't shell out, ~2s). They exist because the cross-tool dedup bug survived an entire pilot run and was only caught by hand-reading an audit worksheet; one assertion would have caught it on day one. Coverage: dedup (including regression tests for both cross-tool pairs, and that genuinely different findings on one line are *not* over-merged), code extraction (including the unclosed-fence truncation case), Engine A determinism and the guarantee that no dataset prompt silently gets zero warnings, repair-prompt construction, Engine D outcome classes, and the metrics predicates.

## FAQ — moved to its own file

The long-form answers now live in **[FAQ.md](FAQ.md)**, so this README stays a "how do I run
it" document. What's answered there:

| Question | Where |
|---|---|
| Isn't the CWE warning compulsory? Why is there a mode that turns it off? | [FAQ §1](FAQ.md#1-design-questions--why-is-it-built-like-that) |
| Why cap repair at 3 rounds? Why 3 repetitions? Why 20/50 functional tests? | [FAQ §1](FAQ.md#1-design-questions--why-is-it-built-like-that) |
| Why trust Bandit/Semgrep instead of asking an LLM to judge? | [FAQ §1](FAQ.md#1-design-questions--why-is-it-built-like-that) |
| What's left to do, and in what order? | [FAQ §2](FAQ.md#2-the-roadmap--what-is-actually-left) · [RUNBOOK.md](RUNBOOK.md) |
| Is this a real paper? Will it survive review? Which venue? | [FAQ §3](FAQ.md#3-the-research-paper--is-this-real-where-does-it-go) |
| Is the codebase any good, honestly? | [FAQ §4](FAQ.md#4-is-the-codebase-any-good-honestly) |
| Should we reuse the original papers' exact prompts? | [FAQ §5](FAQ.md#5-prompts-benchmarks-figures--the-reference-sheet) |
| The eight papers, the benchmarks, the figures — one reference sheet | [FAQ §5](FAQ.md#5-prompts-benchmarks-figures--the-reference-sheet) |
| Does `debug=True` really count as a vulnerability? Is the DB verifiable? | [FAQ §6](FAQ.md#6-security-questions-people-ask-about-this-repo-itself) |
| What did the 2026-09-07 review change, and why does it matter? | [FAQ §7](FAQ.md#7-what-the-2026-09-07-review-changed-and-why-it-matters) |


## Known housekeeping / things we still owe ourselves

Being honest in this doc means listing the stuff that isn't done yet too. ✅ = fixed during the 2026-09-06 full-codebase review; the rest is still open — see the [TODO list](TODO.md) for the prioritized, actionable version of everything below.

- ✅ **Fixed 2026-09-06:** the MCP server hang on any scanning/repair tool (`stdin` inheritance + sync-on-event-loop dispatch) — see [FAQ](#faq--the-questions-everyone-eventually-asks) for the root cause and how it was verified.
- ✅ **Fixed 2026-09-06:** the frontend was a dark, saturated, heavily-rounded AI-dashboard look — rewritten to a flat, light, academic style against a validated palette. Same IDs/JS, only presentation changed.
- The 2,700-run full experiment (M4) hasn't started — only the free-tier pilot has run so far, and at 1 rep, not the planned 3.
- Groq retired `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` mid-project (2026-09-01) — fixed by substituting `gpt-oss-20b`/`gpt-oss-120b`, documented in `docs/03_METHODOLOGY.md`, but it means the "G1 = literal 2023-24-era model" framing needs a caveat in Threats to Validity. The **old rows recorded under the retired model names are still in `leblanc_v3.db`** and will render as an unlabeled `"?"` generation in `metrics.py` output — purge or document them before M4.
- `analysis/rq_analysis.ipynb` (the notebook that's supposed to generate every paper figure from the DB) doesn't exist yet — that's M5.
- **Confirmed not a LeBlanc file:** `docs/researchdocs/BreachTrace OneWeek Sprint(1).docx` was opened and read during this review — it's a different team's unrelated capstone sprint plan (AWS forensics, different guide). It should be removed from this repo, not just "looked at."
- `demo_vulnerable.py` sits untracked at the repo root with no header comment explaining its purpose — give it one and move it into a `demo/` folder, or delete it.
- `docs/researchdocs/vapt_report.pdf` presents numbers that don't trace back to `leblanc_v3.db` (different prompt count, a retired model) — add a dated caveat noting it's a pre-v3, non-reproducible deliverable, per this project's own "no numbers the DB can't reproduce" rule.
- The false-positive audit protocol (κ between two annotators on a 10% sample of findings) is defined in `docs/01_RESEARCH_QUESTIONS.md` but hasn't been run yet — needs M3's pilot data first.

## Team

**Banerjee, Kumari, Ranjan, Soni** (alphabetical, equal contribution) — supervising: **Prof. Deepti Patole**. B.Tech capstone project.
