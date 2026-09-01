# LeBlanc v3

**One sentence:** We measure how much security scaffolding (CWE-aware prompt enrichment + scanner-guided iterative repair) still buys you across LLM generations — and how often "repaired" code is secretly broken.

This folder is the ground-truth definition of the project. If code, slides, or the paper
contradict anything in `docs/`, the docs win — or the docs get amended first, deliberately.

## Layout

| Path | What it is |
|---|---|
| `docs/00_DEFINITION.md` | What EXACTLY is being done, and what is explicitly NOT |
| `docs/01_RESEARCH_QUESTIONS.md` | The 5 RQs — hypotheses, exact metrics, exact statistical tests |
| `docs/02_DATASET.md` | The exact 50-prompt dataset: selection protocol, provenance, test-case spec |
| `docs/03_METHODOLOGY.md` | Model fleet, modes, judge design, run matrix, budget math |
| `docs/04_PAPER.md` | Paper type, working titles, venue targets, authorship, section skeleton |
| `docs/05_EXECUTION_PLAN.md` | Build order, what's reused from v2, milestones |
| `dataset/leblanc_v3_prompts.json` | **THE dataset.** 50 prompts, final IDs (L001–L010, S001–S040) |
| `dataset/securityeval_prompts.json` | Raw SecurityEval pool (121 prompts, 69 CWEs) for provenance |
| `dataset/leblanc_v3_securityeval_selection.json` | The stratified 40-prompt selection, pre-merge |

## Status
- 2026-07-14: Foundation defined. Angle = generational gap. Budget = ~$10–30. Judge = dual static + functional tests.
- 2026-07-14: M2 complete — 20/50 functional tests GREEN on references (`validate_m2.py`), dataset FROZEN. Offline harness (`dataset/tests/_harness/`) fakes MySQL/LDAP/network so those prompts are testable with no services and no egress; the 30 untested prompts are excluded by design (see `dataset/tests/MANIFEST.md`).
- 2026-09-01: Frontend Run History got a side-by-side stage viewer (Engine A→B→C→D per run,
  Bandit/Semgrep findings highlighted inline on the code, functional-test verdict) and MCP
  server registered with Claude Code. Fleet fix: Groq retired `llama-3.1-8b-instant` and
  `llama-3.3-70b-versatile`; substituted `gpt-oss-20b`/`gpt-oss-120b` (see `docs/03_METHODOLOGY.md`).
  M3 pilot and M4 full run (2,700 cells) still not started — DB has 1 leftover dev-test row.

## Prior work in this repo
`../v2/` is the April 2026 proof-of-concept (working pipeline, demo-scale data, known flaws
documented in the sprint retrospective). v3 reuses its engine code, not its dataset or claims.
