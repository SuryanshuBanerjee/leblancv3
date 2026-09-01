# LeBlanc v3 — Setup & Run Guide

Nothing here spends money unless you explicitly opt in. Read the **Cost** section.

## 1. Install

```bash
cd D:\LYPROJECT\v3\backend
pip install -r requirements.txt
```

Semgrep runs against a **pinned local ruleset** (`backend/semgrep_rules/python.yaml`,
the `p/python` pack) so scans need no network and stay reproducible. If Semgrep is
missing entirely the code degrades to Bandit-only and records which scanners actually
ran, per run (so a run can't silently claim dual-scanner coverage it didn't have).
Regenerate the ruleset with: `curl -L https://semgrep.dev/c/p/python -o backend/semgrep_rules/python.yaml`.

## 2. API keys

Keys live in `D:\LYPROJECT\.env` (already has `GROQ_API_KEY`, `GEMINI_API_KEY`).
Add any of these for the paid models — all optional:

```
OPENAI_API_KEY=...      # gpt-4o-mini
ANTHROPIC_API_KEY=...   # claude-haiku-4.5
DEEPSEEK_API_KEY=...    # deepseek-chat  (cheapest current-gen option)
```

The 3 free models (gpt-oss-20b, gpt-oss-120b, gemini-2.5-flash — Groq's `openai/gpt-oss-*`
open-weight models, substituted 2026-09-01 after Groq retired llama-3.1-8b-instant and
llama-3.3-70b-versatile) need no new keys.

## 3. Launch the dashboard

```bash
python app.py        # -> http://localhost:5000
```

Tabs: **Overview** (what the project is) · **Research Questions** (live numbers next to
each formula) · **Lab** (try Engine A for free; run one pipeline) · **History** · **Dataset**.

## 4. Check the fleet before spending anything

```bash
python run_batch.py --preflight        # 1 tiny call per model; shows which keys work
```

## Cost — how spending is gated

- The **web UI** can only spend via the Lab's "Run pipeline" button = 1–4 calls, one click.
- **Batch runs** print a pessimistic cost estimate and **refuse to start** if it's > $0
  unless you pass `--yes`. Free-tier-only plans always cost $0 and run immediately.

```bash
# free pilot (costs $0, ~450 runs, resumable):
python run_batch.py --models gpt-oss-20b gpt-oss-120b gemini-2.5-flash --modes all --reps 1

# full experiment incl. paid models (~$6 estimated, must confirm):
python run_batch.py --models all --modes all --reps 3 --yes

python run_batch.py --report            # completeness matrix anytime
```

Batch is **idempotent**: completed cells are skipped, so you can stop (Ctrl-C) and resume
by rerunning the same command.

## 5. MCP server (LeBlanc engines as agent tools)

```bash
claude mcp add leblanc -- python D:/LYPROJECT/v3/backend/mcp_server.py
```

Tools: `analyze_prompt`, `scan_code`, `audit_llm_response`, `project_status` (all free),
and `repair_code` (spends tokens, clearly labelled). Lets Claude Code / Cursor / Claude
Desktop call the pipeline directly — this is v3's replacement for v2's abandoned VS Code extension.

## Milestone M2 — complete, dataset frozen

`dataset/tests/<id>_test.py` + `dataset/reference/<id>.py`: **20/50 done and verified**
(run `python backend/validate_m2.py` — free, offline; every test passes on its reference).
An offline harness (`dataset/tests/_harness/`: sqlite-backed fake MySQL, fake ldap/ldap3
with real escaping helpers, patched urllib/requests/socket/ssl) makes DB/LDAP/network
prompts testable with zero services and zero egress — double the pre-harness ceiling of
~10–12. The remaining 30 prompts are untestable **by design** (no fixed interface,
destructive happy paths, OS/SDK dependencies) and drive RQ1–RQ4 only; every exclusion
is recorded per-prompt in `dataset/tests/MANIFEST.md`. Nothing here is pending.
