# 02 — The Dataset (exact)

**File of record:** `dataset/leblanc_v3_prompts.json` — 50 prompts. That file IS the dataset;
this doc explains how it was constructed and what still must be added to each entry.

## Composition

| Slice | IDs | Count | Source | Nature |
|---|---|---|---|---|
| Original scenarios | L001–L010 | 10 | LeBlanc team (written for v1/v2, 2026) | Natural-language "realistic feature" requests (login endpoint, file upload, JWT dashboard…) |
| SecurityEval | S001–S040 | 40 | s2e-lab/SecurityEval (Siddiq & Santos, 2022) | Python code-completion stubs, each tagged with one target CWE |

Category distribution (6-category taxonomy):
Injection 11 · Auth 12 · Crypto 7 · File/Path 8 · Deserialization 9 · Web/Request 3.

## Selection protocol (reproducible, already executed)

1. Downloaded full SecurityEval `Testcases_Prompt/` tree (121 prompts, 69 CWEs) —
   raw pool preserved at `dataset/securityeval_prompts.json` for provenance.
2. Mapped CWEs into the 6 categories (mapping table lives in the selection script and
   in `cwe_categories.py` when ported).
3. Stratified selection: per-category targets (9/8/7/6/7/3), **max 2 prompts per CWE**,
   exact-duplicate texts rejected by prefix hash. Deterministic order (no random seed needed —
   selection is first-fit over sorted CWEs; rerunning the script reproduces it byte-for-byte).
4. Merged with L001–L010 (v2's P001–P010, the only genuinely original prompts in v2;
   v2's P011–P045 were 8 SecurityEval fragments duplicated ~4× and are **abandoned**).

## Schema (per entry)

```json
{
  "id": "S007",
  "source": "SecurityEval",
  "source_file": "CWE-089/codeql_1.py",
  "prompt": "...",
  "target_cwes": ["CWE-089"],
  "category": "Injection"
}
```

### How tests are linked (resolved 2026-09-07 — M2 shipped differently than planned)

The plan was to add `"tests"` and `"entrypoint"` fields to every entry. **That is not what was
built, and the dataset file has no such fields.** Engine D resolves tests *by convention*
instead: prompt `S001` is tested by `dataset/tests/S001_test.py` against the reference solution
`dataset/reference/S001.py`, and a prompt with no matching test file yields the outcome class
`no_tests`. The entrypoint is not recorded as data either — it is expressed directly in the
test, which imports what it needs from `solution`.

This is simpler and has one fewer thing to keep in sync (a `"tests"` path that disagrees with
the file on disk is a bug that convention makes impossible), at the cost of the mapping being
implicit rather than declared. The per-prompt entrypoint each test actually exercises is
documented in `dataset/tests/MANIFEST.md`, which is the file of record for coverage.

## Functional test spec (Engine D contract)

Purpose: catch **secure-but-broken** repairs (RQ5), not to be a full test suite.

Per prompt, 1–3 tests that assert:
1. **Existence** — the expected function/route exists and is importable/registerable.
2. **Happy path** — one benign input produces a sane result
   (e.g., L001 login: correct creds → success response shape; S-tar-extract: benign tar extracts).
3. **(Where trivial) benign edge** — e.g., empty input doesn't crash.

Execution rules: subprocess sandbox, 5s timeout, no network (socket disabled), temp working
dir wiped per run; Flask prompts tested via `app.test_client()`. A test ERROR (import crash)
counts as fail. Tests must pass on a hand-written reference solution before being accepted
into the dataset (that reference solution is also stored, `dataset/reference/<id>.py` —
it doubles as the paper's "secure solution exists" evidence).

Effort estimate: 50 prompts ≈ 15–20 person-hours. Split: Suryanshu 20, Ayushi 15, Vraj 15.

## Rules

- The dataset is **frozen** once M2 completes and the pilot passes. Any post-freeze change
  = new dataset version (`v3.1`), logged here with reason.
- Never edit prompt text to make a model behave. If a prompt is broken, drop it and record why.
- Provenance chain for every S-prompt: raw pool file → selection file → dataset file.
