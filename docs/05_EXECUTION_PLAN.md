# 05 — Execution Plan

## Reused from v2 (port, don't rewrite)

| v2 file | Verdict |
|---|---|
| `engine_a_enrich.py` | Port as-is (singleton mapping load is fine) |
| `engine_b_scan.py` | Port + **add Semgrep runner** + union/dedup logic |
| `engine_c_repair.py` | Port as-is (extraction-failure honesty is already right); cap stays 3 |
| `llm_client.py` | Rewrite config table (dead models), fix the KeyError fallback (`llama3-70b` isn't a key), add OpenAI/Anthropic/DeepSeek providers + `--preflight` |
| `database.py` | Port; add `rep` column + unique index on (prompt_id, model, mode, rep); new file `leblanc_v3.db` |
| `cwe_mappings.json`, `cwe_categories.py` | Port + extend for the 40 new CWEs in the S-set |
| `frontend/*` | Untouched until M5; it's demo-ware |
| `prompts.json` (P011–P045) | **Abandoned** (duplicated data — see 02_DATASET.md) |

## New builds

- `engine_d_functest.py` — sandboxed pytest runner (30s hard timeout, no network;
  injects the `dataset/tests/_harness/` offline fakes into every sandbox)
- `run_batch.py` — idempotent batch runner per contract in 03_METHODOLOGY.md
- `dataset/tests/<id>_test.py` + `dataset/reference/<id>.py` for every testable
  prompt (final: 20 of 50; the rest excluded by design — see the M2 manifest)
- `analysis/rq_analysis.ipynb` — all stats, figures, tables

## Milestones (each has a hard gate; no gate, no next milestone)

| M | What | Gate | Est. |
|---|---|---|---|
| **M0** | Foundation docs + dataset selection | this folder exists, dataset frozen-candidate | ✅ done 2026-07-14 |
| **M1** | Harness: fleet rewrite, Semgrep restored, batch runner, preflight | `run_batch.py --preflight` green on all 6 models; 1 prompt × 6 × 3 runs clean end-to-end | ✅ done 2026-07-14 (free models green; paid pending keys) |
| **M1.5** | Frontend (teaching UI), metrics engine (RQ1–RQ5), MCP server, cost gate | dashboard boots, all APIs respond, MCP tools callable, batch refuses paid runs w/o `--yes` | ✅ done 2026-07-14 |
| **M2** | Functional tests + reference solutions | every test passes on its reference solution (`validate_m2.py` green); dataset FROZEN | ✅ done 2026-07-14: 20/50 tested, gate GREEN, dataset FROZEN (see `dataset/tests/MANIFEST.md`). Offline harness (fake MySQL/LDAP/network in `dataset/tests/_harness/`) doubled the pre-harness ceiling of ~10–12. The 30 untested prompts are excluded by design with per-prompt reasons; they drive RQ1–RQ4 only. |
| **M3** | Pilot: 5 prompts × 6 models × 3 modes × 1 rep (90 runs) + FP audit dry-run | <10% llm_error; both annotators complete pilot FP labels; κ computed | 2–3 days |
| **M4** | Full run: 2,700 runs (overnight sessions, resumable) | cell-completeness matrix 100%; DB backed up | ~1 week wall-clock |
| **M5** | Analysis + figures + 10% FP audit | notebook reproduces every figure from DB alone | ~1 week |
| **M6** | Paper draft → arXiv → venue submission | co-authors + guide sign off | ~2–3 weeks |

## Risk register (carried over from v2's corpses)

1. **Dead models mid-experiment** → preflight + provider substitution rules in 03.
2. **Rate limits stretch M4** → per-provider queues, resume, run categories in tranches.
3. **FP rate >20%** → already has a protocol (report prominently, hedge RQs) — not a surprise, a plan.
4. **Test-writing stalls (the real schedule risk)** → M2 is parallelized 3-ways and capped:
   if a prompt can't get a sane smoke test in 30 min, drop it and record why (dataset may
   land at 45–48; that's fine and documented).
5. **Team bandwidth** → M1 is one person (Suryanshu). M2 is the all-hands week. Everything
   else is 1–2 people. If solo: add ~2 weeks to M2.
