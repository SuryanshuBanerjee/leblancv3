# Changelog

Newest first. Plain language, no jargon — this file exists so anyone can see what changed
without reading diffs.

---

## 2026-09-07 — full-codebase review, M5 built, four bugs fixed

A complete read of the codebase, all ten research PDFs, and every project doc — then everything
that could be finished without running the experiment was finished. **The project is now at the
point where only running remains.** See [RUNBOOK.md](RUNBOOK.md) for exactly what to type.

### Bugs found and fixed

- **The MCP server hung on any tool that ran a scanner.** `scan_code`, `scan_path`,
  `audit_llm_response` and `repair_code` would hang forever through the real MCP protocol,
  though the same functions returned instantly when called directly in Python. Two causes:
  the Bandit/Semgrep subprocesses inherited the server's own stdin (which is the pipe the MCP
  client talks on), and FastMCP runs synchronous tools on the event-loop thread so a slow scan
  froze the whole server. Fixed both; verified by driving every tool through a real MCP client.
  → `backend/mcp_server.py`, `backend/engine_b_scan.py`, `backend/engine_d_functest.py`
- **The same weakness was counted twice when both scanners found it.** Deduplication compared
  CWE numbers, so when Bandit and Semgrep labelled one issue with different CWEs it slipped
  through as two findings. `app.run(debug=True)` and `host="0.0.0.0"` were the big offenders —
  together **180 of the pilot's 291 findings**, inflating raw finding counts about 1.6×.
  Vulnerability *rates* (RQ1–RQ4) are unaffected because they only ask "any finding?", but
  per-finding counts collected before today aren't comparable with ones collected after.
  → `backend/engine_b_scan.py` (new `dedupe_findings`, cross-tool equivalence map)
- **The cost gate thought Gemini was free.** It moved to paid billing; the runner would have
  started a Gemini batch without asking for confirmation. Now priced correctly — the full
  6-model experiment estimates at **~$8**, not "<$5". → `backend/run_batch.py`
- **The dashboard looked like a generic AI dashboard** (dark, saturated, heavily rounded).
  Rewritten flat and light using a palette checked for contrast and colourblind separation.
  Identical markup IDs and JavaScript — only presentation changed. → `frontend/index.html`

### Two findings that change how the paper must be written

- **The scanners' false-positive rate is about 53.6%** on a stratified 10% sample of pilot
  findings (single-annotator triage — deliberately *not* claimed as the two-annotator κ
  protocol). It is concentrated in three rule families: pyCrypto-namespace deprecation, binding
  to `0.0.0.0`, and RSA-2048 flagged as too short. All three are noise for our purposes.
- **62% of all findings landed on boilerplate the model volunteered** — the
  `if __name__ == "__main__": app.run(...)` block it adds after answering — not on the function
  that was actually requested. The single most common finding in the whole pilot is a model
  demoing its own endpoint with `debug=True`.

Together these mean the vulnerability rate, as currently defined, substantially measures Flask
demo scaffolding. The paper must report rates with and without those findings. This is now
computed automatically on every analysis run. Full reasoning in [FAQ.md §7](FAQ.md#7-what-the-2026-09-07-review-changed-and-why-it-matters).

### New — the entire analysis layer (milestone M5)

- **`analysis/rq_analysis.py`** — turns the run database into every figure, table and statistic
  the paper needs: six publication-styled figures, LaTeX + Markdown tables per research
  question, `results.json`, and `SUMMARY.md` (a plain-English readout that applies the
  pre-registered decision bands mechanically, so a verdict can't drift to suit the data).
  Includes the Wilson intervals, McNemar, χ²/Fisher, Mann-Whitney and logistic regression the
  methodology specifies — and refuses to report regression coefficients when the model doesn't
  converge, rather than printing unstable numbers.
- **`analysis/fp_audit.py`** — draws a reproducible stratified sample of findings, writes a
  labelling worksheet with each finding shown against its actual line of code, and scores it
  (Cohen's κ with two annotators; loudly labelled as "triage, no κ" with one).
- **`paper/leblanc_paper.tex`** — a complete, compiling paper skeleton: every section, the
  pipeline figure, tables wired in, bibliography populated. **Every number is a red
  `\PLACEHOLDER{}` and the title page carries a DRAFT banner**, so it cannot be mistaken for
  results. Compiles to PDF as-is.
- **`docs/figures/pipeline_diagram.tex`** — the four-engine pipeline figure as a standalone,
  `\input`-ready TikZ file (rescued and corrected from the removed VAPT report, which showed
  only three engines and a 5-iteration cap).

### New documentation

- **[RUNBOOK.md](RUNBOOK.md)** — every remaining command in order, with costs, durations, and
  what "it worked" looks like at each step.
- **[FAQ.md](FAQ.md)** — why the system is built this way: the design decisions, the roadmap,
  the paper's venue strategy and review risks, the benchmark/prompt reference sheet.
- **[CHANGELOG.md](CHANGELOG.md)** — this file.
- README gained a plain-English "explain it like I'm new here" walkthrough and an honest
  completion assessment; TODO.md was rewritten around what actually remains.

### Removed / cleaned

- `docs/researchdocs/BreachTrace OneWeek Sprint(1).docx` — read and confirmed to be an unrelated
  team's capstone sprint plan (AWS forensics, different supervisor). Not our material.
- `docs/researchdocs/vapt_report.pdf` / `.tex` — an April 2026 mini-project report whose numbers
  (10 prompts, a since-retired model) can't be reproduced from the current database, which
  conflicts with this project's own "no numbers the DB can't reproduce" rule. Its pipeline
  diagram was preserved and corrected first.
- `demo_vulnerable.py` → `demo/vulnerable_example.py`, with a header explaining that it's
  deliberately vulnerable scanner bait and listing the weaknesses it's supposed to trigger.
- One leftover run row from a retired model (`llama-3.1-8b`) removed from the database, so it
  stops appearing as an unlabelled `?` generation in every chart. Database backed up first.

---

## 2026-09-01 — pilot run

450 cells (50 prompts × 3 free models × 3 modes × 1 rep), $0, 68 minutes. Caught a truncation
bug: `max_tokens` was 2048, and 88 of Gemini's 89 "extraction failures" were really unclosed
code fences from hitting that ceiling mid-sentence. Raised to 4096, regenerated the affected
cells. Fleet substitution the same day: Groq retired `llama-3.1-8b-instant` and
`llama-3.3-70b-versatile`, replaced with `gpt-oss-20b` / `gpt-oss-120b`.

## 2026-07-14 — M0–M2 complete

Foundation docs, dataset frozen at 50 prompts with provenance, harness rewritten (Semgrep
restored, batch runner, preflight gate), dashboard + metrics engine + MCP server, and 20 of 50
prompts given functional tests validated against hand-written reference solutions
(`validate_m2.py` green). The offline fake MySQL/LDAP/network harness roughly doubled how many
prompts were testable at all.
