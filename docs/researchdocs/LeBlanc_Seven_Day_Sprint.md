# LEBLANC — Seven-Day Sprint
## Architecture Repair · Categorization · Dataset · Metrics · Speed

**CHOSEN SCOPE FOR THIS SPRINT:** Python-only injection category (CWE-89, CWE-78, CWE-79) finished end-to-end — plus the full pipeline made fast enough to actually use, a real benchmark dataset loaded, proper metrics defined, and the professor's full checklist addressed.

---

### TEAM

| SURYANSHU | AYUSHI | VRAJ | SWADHA |
|---|---|---|---|
| Lead Programmer | Data Track | Web Dev Track | Designer |
| Architecture, speed, engines, anything that breaks | Dataset integration, metrics, analysis, paper data | Frontend, results display, UX | Visuals, design system, presentations |

### GUIDE
Prof. Deepti Patole · K.J. Somaiya School of Engineering · Dept. of Information Technology

---

## HONEST CODEBASE AUDIT (READ BEFORE DAY 1)

Here is what is actually wrong with the codebase right now. No sugarcoating.

**Why a single pipeline run takes 5+ minutes:**
- `engine_a.py` line 6–8: `load_mappings()` reads `cwe_mappings.json` from disk **on every single call**. Every run, every iteration. Fix: module-level singleton.
- `llm_client.py` lines 22–24: `genai.configure()` and `GenerativeModel(...)` are called **per Gemini call**, not once. Wasteful.
- `engine_b.py` lines 145–146: `run_semgrep()` and `run_bandit()` run **sequentially**. They are completely independent — they can be parallelized with `ThreadPoolExecutor`.
- `engine_b.py` line 51: `--config=auto` downloads Semgrep's entire rule registry on every run. Cold start = 5–15 seconds. Fix: `--config=p/python-security`.
- `app.py` lines 125–207: `/api/compare` runs all 6 mode combinations (2 models × 3 modes) **in a single sequential loop**. They are all independent — they can all run in parallel.
- `engine_c.py` lines 50–73: The repair loop runs up to 5 iterations, each being an LLM call + a full scan. If every iteration takes 10–20 seconds that's 50–100 seconds per repair alone.

**Logical errors and poor code:**
- `engine_b.py` line 60–61: When code extraction fails in the repair loop, it `continue`s silently. This means `total_iterations` is undercounted — the run looks like it converged faster than it did.
- `engine_b.py` lines 17–22: `_PROSE_RE` tries to detect prose by matching the first word of each line. This is a hack that strips legitimate code lines starting with common English words. Replace with `py_compile`.
- `engine_b.py` line 62–64: Deduplication uses `(line, tuple(cwes))` as the key. Two different "unmapped" findings at different lines share the same CWE tuple `("unmapped",)` and will NOT be deduplicated — they should be.
- `engine_b.py` line 155: Severity filter includes `"WARNING"` from Semgrep alongside `"MEDIUM"/"HIGH"` from Bandit. Semgrep WARNING is roughly equivalent to Bandit LOW — it is below your stated "medium+" threshold. This inflates vuln counts.
- `app.py` line 17: `CORS(app, origins="*")` is wide open. Fine for a demo but must be documented.
- `database.py` lines 40–44: Migration via `ALTER TABLE ... ADD COLUMN` inside `init_db()` is fragile and will silently fail in unexpected schema states.
- `engine_a.py`: No validation — if `cwe_mappings.json` is missing, the whole pipeline crashes with a raw `FileNotFoundError` and no hint of what went wrong.

**Features not expanded on:**
- `prompts.json` has 15 prompts. The proposal says 100–200. This needs a real benchmark dataset.
- Stats endpoint (`/api/stats`) computes `vuln_count` and `reduction_pct` only. The paper needs CWE-category-level metrics, convergence rate per category, false positive estimates — none of this exists.
- Engine A `cwe_mappings.json` has no categorization. It maps keywords → CWEs but there is no grouping into human-readable categories (injection/auth/crypto/etc.).
- Repair result object has `final_status: "clean" or "not_converged"` but no breakdown of which CWEs were fixed vs. persisted.
- History page shows raw JSON blobs. Completely unreadable.

---

## DAY 1 (MONDAY) — FIX THE SPEED PROBLEM

**Goal: Make one `/api/compare` call finish under 90 seconds. Right now it routinely hits 5+ minutes. This is blocking everything.**

---

### SURYANSHU

• Open `backend/engine_a.py`. Delete `load_mappings()` call from inside `enrich_prompt()`. Add `_MAPPINGS = load_mappings()` at module level (below the imports). Change `enrich_prompt()` to use `_MAPPINGS` directly. One file read at import time, never again.

• Open `backend/llm_client.py`. Move `genai.configure(api_key=GEMINI_KEY)` to module level. Create `_GEMINI_MODEL = genai.GenerativeModel("gemma-4-31b-it", system_instruction=SYSTEM_INSTRUCTION)` at module level. In `call_gemini()`, replace the setup code with `response = _GEMINI_MODEL.generate_content(prompt)`. Guards: only do this if `GEMINI_KEY` is set, else leave `_GEMINI_MODEL = None` and raise in the function.

• Open `backend/engine_b.py`. In `scan_code()`, replace the sequential calls on lines 145–146 with `concurrent.futures.ThreadPoolExecutor(max_workers=2)`. Use `executor.submit(run_semgrep, filepath)` and `executor.submit(run_bandit, filepath)` simultaneously. Call `.result()` on both futures to collect output. Import `concurrent.futures` at the top.

• Open `backend/app.py`. In `compare_models()`, the outer loops at line 125 are `for model in [...]` and `for mode in [...]`. Flatten these into a list of 6 `(model, mode)` tuples and submit each to a `ThreadPoolExecutor(max_workers=6)`. Each worker calls the existing per-model/mode logic (extract into a helper function). Collect results and reassemble into the `results` dict. This is the single biggest speed win.

• Also in `engine_b.py` line 51: change `--config=auto` to `--config=p/python-security`. Search "semgrep registry python security" or go to https://semgrep.dev/p/python-security to confirm this is the right rule pack. This alone cuts Semgrep cold-start by ~60%.

• Time the before/after: add `import time; t0 = time.time()` at the start of `compare_models()` and `print(f"compare_models took {time.time()-t0:.1f}s")` at the end. Run P001 and paste the result in `docs/perf_day1.txt`.

---

### AYUSHI

• Search GitHub for **SecurityEval dataset**: go to https://github.com/s2e-lab/SecurityEval — this is the standard Python secure code generation benchmark. Clone it or download the ZIP. Read the README. Note: it has ~130 Python prompts each tagged with a CWE. Download whatever CSV/JSON it provides and save a copy in `docs/`.

• Search GitHub for **SecuCoGen dataset**: search "SecuCoGen secure code generation dataset github" — the paper (Two.pdf) is from ICSE 2024. Find the repo, download the 180-sample dataset. Note its columns: ID, Problem, Insecure Code, Secure Code, CWE type.

• Also look at **CodeSecEval** (Three.pdf): search "CodeSecEval dataset github". It has 180 samples covering 44 CWEs.

• Write `docs/dataset_notes.txt`. For each of the 8 papers in `docs/` AND the 3 datasets above, write one entry: paper/dataset name, sample count, CWE count, Python-only or multi-language, download URL or "not publicly available." This is reference material for Day 2 work.

---

### VRAJ

• Open all HTML/JS files in `frontend/`. Map out what exists: how many pages, what each page does, where the API calls are. Write a 10-line plain text note (in your head or on paper) of what's there.

• Right now the frontend fires `/api/compare` and the user stares at a blank/spinning page for potentially 5+ minutes with no feedback. Add a status message div that updates every 800ms while the fetch is pending. Rotating messages: `"Running Engine A (enrichment)..."` → `"Calling LLMs..."` → `"Running Engine B (scanning)..."` → `"Running Engine C (repair)..."` → `"Saving results..."`. Use `setInterval` on the div's `innerText`. Clear it when fetch resolves. No library needed.

• Add color badges to wherever vuln counts are displayed. 0 vulns = green background, 1–2 = yellow, 3+ = red. Pure inline CSS or a small `<style>` block. Do not add new libraries.

---

### SWADHA

• Read all 8 PDFs in `docs/` (One.pdf through Eight.pdf). For each one, extract every CWE ID mentioned anywhere in the paper. Create `docs/cwe_master_list.xlsx` with columns: **CWE ID | CWE Name | Category | Papers That Mention It | Noted as Hard to Fix (yes/no)**. You will need to look up CWE names — use https://cwe.mitre.org/top25/archive/2023/2023_top25_list.html for the top 25.

• Assign each CWE to one of 5 categories: **Injection** (SQL injection, command injection, XSS) · **Auth** (weak passwords, hardcoded creds, broken auth) · **Crypto** (weak hashing, insecure random) · **File/Path** (path traversal, unrestricted upload) · **Deserialization/Parsing** (pickle, YAML, XML). Write the category definitions in `docs/design_system.md` with a hex color for each: Injection = #E53935 (red), Auth = #F57C00 (orange), Crypto = #7B1FA2 (purple), File/Path = #1565C0 (blue), Deserialization = #2E7D32 (green). This color system will be used everywhere in the frontend.

---

⚠️ DAY 1 HARD STOPS — do not move to Day 2 until all are true:
- ✓ Suryanshu: `/api/compare` on P001 completes in under 90 seconds. Timing printed to console. `docs/perf_day1.txt` exists.
- ✓ Ayushi: `docs/dataset_notes.txt` exists with entries for all 8 papers + SecurityEval + SecuCoGen + CodeSecEval.
- ✓ Vraj: Frontend shows rotating status messages while `/api/compare` is pending. Color badges on vuln counts.
- ✓ Swadha: `docs/cwe_master_list.xlsx` has entries for every CWE mentioned in all 8 papers. `docs/design_system.md` has the 5-category color system.

---

## DAY 2 (TUESDAY) — DEFINE METRICS + LOAD A REAL DATASET

**Goal: Know exactly what numbers your paper is computing. Load at least 30 real benchmark prompts. No more hand-written-only dataset.**

The professor said "figure out metrics to evaluate." Right now the codebase only stores `vuln_count` and computes `reduction_pct`. A paper needs: vulnerability rate (not just count), per-CWE-category breakdown, convergence speed, false positive rate. None of these are currently computed.

---

### SURYANSHU

• Create `backend/cwe_categories.py`. Write a dict `CWE_CATEGORIES` mapping CWE IDs to the 5 category names defined by Swadha yesterday. At minimum cover every CWE in `prompts.json`. Add a function `get_category(cwe_id: str) -> str` that returns the category string or `"other"` for unmapped CWEs. Example: `get_category("CWE-89")` → `"injection"`.

• Add a new endpoint `GET /api/metrics` to `app.py`. It should return: (1) per-model per-mode vulnerability rate (fraction of runs with vuln_count > 0), (2) per-CWE-category average vuln reduction from plain to repair, (3) convergence rate per model (fraction of repair runs that reached `final_status = "clean"`), (4) average iterations to converge per model. Pull all data from the DB using existing `get_all_runs()`. Return clean JSON. This is what the charts will consume.

• Fix the `"WARNING"` severity issue in `engine_b.py` line 155: remove `"WARNING"` from the allowed severities. Semgrep WARNING is below medium. Only keep `"MEDIUM", "HIGH", "CRITICAL"`. Rerun P001 and confirm the vuln count changes (it should drop slightly). Note the before/after counts.

---

### AYUSHI

• Take the SecurityEval dataset from yesterday. Filter to Python-only prompts (exclude any labeled C or other languages). Convert to LeBlanc's `prompts.json` format: each entry needs `id` (P016, P017...), `prompt` (the problem statement), `target_cwes` (list of CWE IDs from SecurityEval's labels), `category` (use your category list from Swadha's file). Add the first 30 Python prompts as P016–P045. Keep P001–P015 intact. Test that `python app.py` still starts with the new file.

• Write `docs/metrics_spec.md`. Four sections, one per RQ from the proposal. For each RQ write: the metric name, formula (plain English pseudocode), what data it needs from the DB, expected range based on literature. Example:

> **RQ1 — Enrichment Effect**
> Metric: Vulnerability Rate = (number of runs where vuln_count > 0) / (total runs), computed per model per mode.
> Formula: `vuln_rate = len([r for r in runs if r.vuln_count > 0]) / len(runs)`
> Data needed: all runs grouped by (model, mode).
> Expected range based on papers: plain=0.6–0.9, enriched=0.4–0.7, repair=0.1–0.4.

Write this for all 4 RQs. This document is the contract between data collection and paper writing.

---

### VRAJ

• Read the existing stats page in the frontend. Find where `plain_avg`, `enriched_avg`, `repair_avg` are rendered. Convert this flat list of numbers into a proper HTML table: rows = each prompt ID (P001–P015 initially), columns = plain/enriched/repair vuln count for Gemini and Groq. Cell color = green (0 vulns) / yellow (1–2) / red (3+) matching yesterday's badge colors. No chart library yet — plain `<table>` with inline CSS.

• Add a dropdown above the table to filter by CWE category. Options: All | Injection | Auth | Crypto | File/Path | Deserialization. Filtering by category shows only prompts that have that category in their `target_cwes`. The category mapping will come from a small hardcoded JS object (you can copy it from `cwe_categories.py` manually for now).

---

### SWADHA

• Read Ayushi's `docs/metrics_spec.md` (she'll have a draft by midday — coordinate). For each of the 4 RQs she defines, sketch a chart that visualizes the metric. Appropriate chart types: RQ1 = grouped bar (mode on X, vuln rate on Y, grouped by model). RQ2 = grouped bar (model on X, avg vuln count on Y, grouped by mode). RQ3 = line or bar chart (iterations to converge on Y, CWE category or model on X). RQ4 = heatmap or small grouped bars (CWE category vs. model, showing convergence rate as color intensity or bar height). Save as `docs/metrics_wireframe.png` — a photo of a sketch is fine.

• Update `docs/design_system.md`: add chart-specific colors. Gemini = #1A73E8 (Google blue). Groq = #FF6B35 (orange). Plain mode = #9E9E9E (grey). Enriched mode = #42A5F5 (light blue). Repair mode = #66BB6A (green). These go on every chart. Also define status badge styles: clean = green, not_converged = orange, has_vulns = red, llm_error = grey.

---

⚠️ DAY 2 HARD STOPS:
- ✓ Suryanshu: `GET /api/metrics` returns valid JSON with vuln rates, convergence rates, per-category breakdown. Severity filter no longer includes "WARNING".
- ✓ Ayushi: `prompts.json` has P001–P045 (45 entries). `docs/metrics_spec.md` has all 4 RQs with formulas.
- ✓ Vraj: Stats page shows a color-coded table of vuln counts per prompt. Category dropdown filters rows.
- ✓ Swadha: `docs/metrics_wireframe.png` shows chart sketches for all 4 RQs. Design system has chart colors.

---

## DAY 3 (WEDNESDAY) — CATEGORIZATION + ISOLATION

**Goal: Every vulnerability finding has a category tag. Scanning runs in an isolated directory. Two professor requirements cleared.**

**On isolation:** Prof said "isolation." The practical meaning: right now `scan_code()` writes LLM output to `tempfile.gettempdir()` (the system temp folder) and scans from there. If the LLM generates something weird (not necessarily malicious, but just messy), it sits in your system temp alongside other processes. Minimal isolation = a dedicated `backend/scan_tmp/` directory owned by the process, cleaned up after every scan, not accessible to other users. Full isolation = Docker container with `--network=none`. Do minimal now, document full for next sprint.

**On categorization:** Every scan finding currently has a list of CWE IDs. Now that `cwe_categories.py` exists, every finding should also carry a `category` field. This makes the history page readable and the metrics charts possible.

---

### SURYANSHU

• Open `backend/engine_b.py`. Import `cwe_categories` at the top. In `run_semgrep()` and `run_bandit()`, after building each finding dict, add: `"category": cwe_categories.get_category(cwe_ids[0] if cwe_ids else "unmapped")`. Every finding now has a category.

• Modify `scan_code()` to use a dedicated temp directory. Replace `tempfile.gettempdir()` with `os.path.join(os.path.dirname(__file__), "scan_tmp")`. Create that directory at module level with `os.makedirs(..., exist_ok=True)`. The `finally` block already calls `os.unlink(filepath)` — keep that.

• Fix the silent skip in `engine_c.py` line 60–61: when `clean_code` is empty after an LLM call, instead of `continue` (which loses the attempt), append a record to `iterations` with `"extraction_failed": True, "code": "", "vulns_before": len(current_vulns), "vulns_after": len(current_vulns)`. This keeps `total_iterations` honest.

• Run a quick test: call `scan_code()` with a short known-vulnerable Python snippet (`import subprocess; subprocess.call(input(), shell=True)`) and confirm: (a) the temp file appears in `backend/scan_tmp/`, (b) findings include a `category` field, (c) the temp file is deleted after.

---

### AYUSHI

• Cross-reference `cwe_mappings.json` (Engine A's keyword→CWE map) against the 45 prompts in `prompts.json`. For each `target_cwes` in P001–P045, check that the CWE exists in `cwe_mappings.json`. If a CWE is in `target_cwes` but Engine A has no keyword that triggers it for that prompt — that's a gap. List all gaps. For each gap, either (a) add a new keyword entry to `cwe_mappings.json` or (b) document it as a known limitation in `docs/engine_a_gaps.md`. Goal: at least 80% of prompts should get at least one Engine A warning.

• Do the first pass of false positive analysis. Run the pipeline on 10 prompts (use P001–P010 from existing DB runs if they exist, otherwise run fresh). Open `backend/leblanc.db` with `sqlite3 backend/leblanc.db "SELECT id, prompt_id, scan_results FROM runs WHERE mode='plain' LIMIT 10"`. For each run, read the `scan_results` JSON. For each finding, decide: is this a real vulnerability in the code, or a false positive? Write your reasoning in `docs/false_positive_analysis.md` — one row per finding: run ID, CWE, line, finding message, your verdict (TP/FP), reason.

---

### VRAJ

• Add CWE category tags to the history page (`frontend/history.html`). Right now it shows raw scan results JSON. Parse `scan_results` in JavaScript, extract the `category` field from each finding, collect unique categories, render one colored tag per unique category using the color system from `docs/design_system.md`. If `category` is missing from old DB records (pre-today runs), fall back to mapping CWE IDs yourself in JS using a small hardcoded dict.

• Create `frontend/metrics.html` — a new page accessible from the main nav. It calls `GET /api/metrics` on load. Use Chart.js from CDN: `https://cdn.jsdelivr.net/npm/chart.js`. Render two charts today: (1) RQ1 bar chart — X axis = mode (plain/enriched/repair), Y axis = vuln rate (0–1), two bars per group (Gemini, Groq) using design system colors. (2) RQ2 grouped bar — X axis = model, Y axis = avg vuln count, grouped by mode. Wire them to real data from `/api/metrics`. Placeholder charts with hardcoded data are not acceptable.

---

### SWADHA

• Design the full layout for `frontend/metrics.html`. Vraj is building it simultaneously — share the spec with him before noon. Write `docs/metrics_page_spec.md`: exact layout (4 charts in a 2×2 grid, or stacked, your call), CSS variables to use, chart titles, axis labels, legend placement. Include the exact Chart.js config options for each chart (colors, borderRadius, etc.) so Vraj can copy-paste.

• Create two report template files. These are for the professor review meeting. (1) `docs/report_template_single.docx` — one-page template for a single prompt run: prompt text, enriched prompt, scan findings table (CWE | severity | category | line | message), repair timeline (iteration 1 → N vulns, iteration 2 → N-1 vulns, ...), final status. (2) `docs/report_template_summary.docx` — summary template for the full dataset: per-model summary table, per-category breakdown, convergence stats. Use Word or Google Docs — just get the structure right.

---

⚠️ DAY 3 HARD STOPS:
- ✓ Suryanshu: `scan_code()` writes temp files to `backend/scan_tmp/`, cleans up after, and every finding has a `category` field.
- ✓ Suryanshu: Repair loop no longer silently drops failed extraction attempts from `total_iterations`.
- ✓ Ayushi: `docs/engine_a_gaps.md` documents any Engine A CWE coverage gaps. `docs/false_positive_analysis.md` has 10 manually verified findings.
- ✓ Vraj: History page shows category color tags. `frontend/metrics.html` loads and shows 2 real charts.
- ✓ Swadha: `docs/metrics_page_spec.md` written and shared with Vraj. Two report templates exist.

---

## DAY 4 (THURSDAY) — FINISH ONE CATEGORY END TO END

**Goal: Run every injection-category prompt through the full pipeline and have actual numbers. This is the professor's "finish one category of vulnerability" requirement.**

Injection prompts in the current dataset: **P001** (CWE-89 — login/MySQL), **P004** (CWE-78 — command execution), **P005** (CWE-89/CWE-79 — search/HTML), **P011** (CWE-78 — shell command). Plus any injection-tagged prompts in P016–P045 from SecurityEval (check `target_cwes` for CWE-89, CWE-78, CWE-79).

---

### SURYANSHU

• Write `backend/run_batch.py` — a command-line script that runs multiple prompts programmatically without the frontend. Usage: `python run_batch.py --category injection --models gemini groq --reps 3`. It reads `prompts.json`, filters by category, and for each prompt calls the pipeline logic (same code as `compare_models()`) 3 times to account for LLM non-determinism. Saves all results to the DB. Prints progress: `"P001 [1/3] gemini plain... done (3 vulns)"`. This is critical infrastructure — you will use it for the full 200-prompt data collection run later.

• After the batch runs, check the DB for anomalies: any runs where `generated_code` is empty (LLM returned nothing), `clean_code` is empty (extraction failed even though LLM returned something), or `vuln_count = 0` for all 3 modes (might indicate a scan failure, not a clean result). Log any such cases to `docs/batch_anomalies.txt`.

• Review your own code changes from Days 1–3. Any edge case you skipped? In particular: what happens if Semgrep is not installed? `engine_b.py` catches `FileNotFoundError` but returns it as a finding with `severity=ERROR` — and ERROR is filtered out in line 155. This means if Semgrep is missing, you silently get 0 findings. Add a startup check: in `app.py`'s `__main__` block, run `subprocess.run(["python", "-m", "semgrep", "--version"], ...)` and print a warning if it fails.

---

### AYUSHI

• After the batch script runs (coordinate with Suryanshu — he may have it ready by midday), export the injection-category results from the DB: `sqlite3 backend/leblanc.db "SELECT prompt_id, model, mode, vuln_count, final_status, total_iterations FROM runs WHERE prompt_id IN ('P001','P004','P005','P011') ORDER BY prompt_id, model, mode"`. Fill in `docs/injection_category_results.md` — a table with rows = prompt IDs and columns = Gemini×plain, Gemini×enriched, Gemini×repair, Groq×plain, Groq×enriched, Groq×repair. Show vuln counts and final status. Add a summary row with column means.

• Apply your RQ1–RQ4 formulas from `docs/metrics_spec.md` to the injection data. For injection category specifically: what is the vulnerability rate (plain vs. enriched vs. repair) for each model? What is the convergence rate? How many iterations on average? Write the results as `docs/injection_metrics_summary.md`. These are your first real paper numbers.

---

### VRAJ

• Add a category filter to the main dashboard prompt selector. Add 5 filter buttons above the prompt dropdown: **All | Injection | Auth | Crypto | File/Path | Deserialization**. When a category is selected, the dropdown only shows prompts from that category. Store the category-to-prompt-IDs mapping as a small JS object derived from `prompts.json` (fetch it from `GET /api/prompts` which already exists, then filter client-side).

• Fix the repair iteration display. Right now `repair_result.iterations` is almost certainly rendered as raw JSON or not at all. Render it as a readable timeline list: each iteration shows `Iteration N: X vulns → Y vulns` with a green arrow if vulns dropped and a red arrow if they stayed the same or increased. If `final_status = "clean"`, show a green "✓ Clean" banner at the end. If `final_status = "not_converged"`, show an orange "⚠ Not converged after N iterations" banner.

---

### SWADHA

• Take `docs/injection_metrics_summary.md` from Ayushi (she'll have a draft by end of day) and design `docs/injection_results_visual.pptx`. Two slides: (1) A before/after comparison table styled cleanly — which model did better on injection prompts, plain vs. repair. (2) A simple bar chart showing vuln reduction for each model. This is the artifact you show the professor as evidence that the system works. It needs to look professional. Use PowerPoint, Google Slides, or Canva.

• Write `docs/ux_audit.md`. Go through every frontend page (main compare page, history page, metrics page). List exactly 3–5 UX issues per page: missing labels, confusing button names, poor contrast, things that require a PhD to understand. Be brutal. Example issues: "Scan results show 'CWE-89' with no explanation of what that means." "The enriched prompt is visible but there's no label explaining what enrichment did." "The repair loop iterations are shown as raw JSON." Maximum 3 sentences per issue.

---

⚠️ DAY 4 HARD STOPS:
- ✓ Suryanshu: `backend/run_batch.py` runs successfully for `--category injection`. DB contains fresh injection runs. `docs/batch_anomalies.txt` exists (even if empty).
- ✓ Ayushi: `docs/injection_category_results.md` has the filled-in numbers table. `docs/injection_metrics_summary.md` has RQ1–RQ4 numbers for injection.
- ✓ Vraj: Category filter buttons exist on the main dashboard. Repair iterations render as a readable timeline with final status banner.
- ✓ Swadha: `docs/injection_results_visual.pptx` exists and is presentable. `docs/ux_audit.md` lists specific issues per page.

---

## DAY 5 (FRIDAY) — SPEED PHASE 2 + METRICS DASHBOARD COMPLETE

**Goal: Full `/api/compare` under 60 seconds. Metrics dashboard fully functional. Data collection started for all 45 prompts.**

After Day 1 fixes, you are probably around 90 seconds. The remaining bottleneck is Semgrep itself — even with parallelism, it spawns a Python/JVM process per call. Three options, try in order:

1. **Change `--config=auto` to `--config=p/python-security`** (should already be done from Day 1 — confirm it's in). This is the cheapest fix.
2. **Reduce scan timeout**: add `timeout=30` to the Semgrep subprocess call (already 60 in code — try 30). If Semgrep can't finish in 30 seconds, the code sample is probably too large.
3. **Use Semgrep as a Python library** (no subprocess): search "semgrep python API programmatic" — look at the semgrep GitHub repo at https://github.com/semgrep/semgrep. There is a `semgrep.semgrep_main` module. If you can call it directly without subprocess, you remove the process-spawn overhead entirely. This is the biggest potential win but also most likely to break — test in isolation first.

---

### SURYANSHU

• Profile the pipeline with the Day 1 fixes applied. Add `time.time()` checkpoints at every step in `compare_models()`: after Engine A, after each LLM call, after each scan, after each repair iteration. Run P001 and save the timestamps to `docs/perf_profile.txt`. This tells you where the remaining time is going.

• Try the Semgrep library API: in a throwaway file, try `from semgrep.semgrep_main import main as semgrep_main`. If it imports without error, try running it on a test file. If it works, integrate it into `run_semgrep()` as a replacement for subprocess. If it doesn't work (import error, API mismatch), document why in `docs/perf_profile.txt` and move on — do not spend more than 2 hours on this.

• Verify the ThreadPoolExecutor in `compare_models()` handles exceptions correctly: if one (model, mode) combo raises an exception (e.g., Groq API rate limit), the other 5 combos should still complete. Wrap each worker function body in `try/except` and return an error dict if it fails, not a raised exception.

---

### AYUSHI

• Run the batch script (`run_batch.py`) for ALL categories — not just injection. All 45 prompts, both models, 1 rep each (3 reps is ideal but 1 is fine for the first full pass). This will take time. Start it running and work on other tasks while it runs. Check back every 30 minutes. Note any prompts that consistently fail.

• Once the run completes, export the full results to `docs/full_dataset_results.md`. Same table format as `injection_category_results.md` but for all 45 prompts. Group by category (injection prompts together, auth prompts together, etc.). Compute the column means per category. These are your preliminary RQ1–RQ4 answers.

• Add 10 more entries to `docs/false_positive_analysis.md` from the new P016–P045 runs. Update the running false positive rate. If it's above 25%, flag it prominently — this needs to be addressed before paper submission.

---

### VRAJ

• Finish `frontend/metrics.html`. All 4 charts must work with real data from `/api/metrics`. Chart specs:
  - **RQ1** — Grouped bar: X = mode (plain/enriched/repair), Y = vulnerability rate (0.0–1.0), two bars per group (Gemini in Google blue, Groq in orange).
  - **RQ2** — Grouped bar: X = model, Y = average vuln count, three bars per group (plain/enriched/repair in grey/light blue/green).
  - **RQ3** — Bar chart: X = CWE category, Y = average iterations to converge. Only show categories with at least one repair run.
  - **RQ4** — Grouped bar or heatmap: X = CWE category, Y = convergence rate (0.0–1.0), grouped by model.
  Use Chart.js. Data comes from `GET /api/metrics`.

• Add a "Run Batch" button to the main dashboard: clicking it calls `/api/run` sequentially for all visible prompts (filtered by current category selection), showing a progress bar (`Prompt N of M`). This lets Ayushi trigger data collection from the UI. Implement as a simple `for` loop with `await fetch(...)` in an `async` function.

---

### SWADHA

• Fix every issue from `docs/ux_audit.md`. Specifically: add a tooltip or small info text next to CWE tags explaining what they are (e.g., "CWE-89: SQL Injection — attacker-controlled input executed as SQL"). Add labels to every section of the results panel (not just raw keys from JSON). Make sure all buttons have visible hover states. Check text contrast — anything below 4.5:1 contrast ratio fails accessibility. Use https://webaim.org/resources/contrastchecker/ to check.

• Write `docs/demo_script.md`. Step-by-step instructions for a 10-minute professor demo: (1) Open app at localhost:5000. (2) Select P001 from dropdown. (3) Click Compare. (4) While loading, explain Engine A enrichment. (5) Results load — point to scan results and categories. (6) Show repair iterations timeline. (7) Navigate to metrics.html. (8) Walk through RQ1 chart. (9) Show injection category results. (10) End with next sprint goals. Write it as "say this, then click that, then say this" — no vagueness.

---

⚠️ DAY 5 HARD STOPS:
- ✓ Suryanshu: `/api/compare` on P001 finishes under 60 seconds. `docs/perf_profile.txt` has timestamped profile.
- ✓ Ayushi: `docs/full_dataset_results.md` exists with all 45 prompts and preliminary numbers.
- ✓ Vraj: `frontend/metrics.html` has all 4 charts rendering with real data.
- ✓ Swadha: All UX audit issues fixed. `docs/demo_script.md` written.

---

## DAY 6 (SATURDAY) — PYTHON ONLY + PAPER PREP + PROFESSOR CHECKLIST

**Goal: Address the "Python only deep dive" requirement. Have a complete preliminary findings document. Knock off the rest of the professor's checklist.**

Professor's checklist recap:
- ✓ Categorize vulnerabilities (Day 3)
- ✓ Figure out metrics (Day 2)
- ✓ Search for a repo for vulnerabilities (Day 1–2)
- ✓ Fix architecture (Day 1)
- ✓ Finish one category of vulnerability (Day 4)
- → Python only, deep dive (today)
- ✓ Isolation (Day 3 minimal)
- ✓ Speed optimized (Day 5)

**What "Python only deep dive" means:** Stop being general-purpose. Right now `_looks_like_python()` in `engine_b.py` is a naive heuristic. The LLM system prompt already says "return only Python code" — enforce this rigorously. If the extracted code is not valid Python, log it loudly, don't silently return 0 vulns. The scanner should fail fast on non-Python, not pretend it scanned successfully.

---

### SURYANSHU

• Replace `_looks_like_python()` in `engine_b.py` entirely. Delete both the function and `_PROSE_RE`. Instead, after `extract_code_from_response()`, add: `import py_compile, tempfile, io; compile(clean_code, '<string>', 'exec')` — Python's built-in `compile()` raises `SyntaxError` if the code is not valid Python. Catch `SyntaxError` and return `([], "")` from `scan_code()`. This is a zero-cost syntax check (no subprocess, no disk write) using the same Python runtime you're already running in.

• Verify isolation end-to-end: write `backend/test_isolation.py`. The test: write a "suspicious" Python file to `backend/scan_tmp/` that does `import os; os.system("echo ISOLATION_TEST_PASSED")`. Call `scan_code()` on that string. Assert that the file is cleaned up after (check `scan_tmp/` is empty). Assert that the `os.system` never actually executed (the file should be scanned, not run — Semgrep/Bandit are static analyzers, not executors). If the file actually executes, that's a real problem — document it. Run: `python backend/test_isolation.py`.

• Code review the whole codebase for your own changes. Look specifically at: does any LLM output get passed to `eval()`, `exec()`, or `subprocess` outside of the controlled scan path? If yes, that is a critical security issue. Flag it.

---

### AYUSHI

• Take the full dataset results from `docs/full_dataset_results.md` and write `docs/preliminary_findings.md`. Structure it as a mini results section for the paper: four sections (one per RQ), each with the actual computed numbers, a 2-sentence interpretation, and an honest caveat (sample size, reps=1 not 3, false positive rate not validated yet). Example:

> **RQ1 — Enrichment Effect**
> Across 45 prompts, vulnerability rate for Gemini dropped from 72% (plain) to 58% (enriched) and 31% (repair). For Groq: 68% → 55% → 39%. Caveat: based on 1 run per prompt; with 3 reps, variance may reduce these rates by ±10pp.

• Cross-check your false positive rate across all entries in `docs/false_positive_analysis.md`. If FP rate > 20%, add a section to `preliminary_findings.md` explaining how this affects RQ1–RQ4 interpretation.

---

### VRAJ

• Add a "Python validation" indicator to the frontend. When a run is displayed: if `clean_code` is empty (extraction failed), show a red badge "⚠ Code extraction failed — LLM may have returned non-Python." Don't show scan results or vuln count 0 for these runs — that 0 is not real, it's a failure. This is currently misleading in the UI.

• Connect the metrics page category charts to the history page: clicking on a bar in the RQ4 chart (e.g., the "Injection" bar for Gemini) should navigate to `history.html?category=injection&model=gemini`. On the history page, read URL params and pre-filter the results table accordingly.

• Add the metrics page to the main navigation. It should not require knowing the URL.

---

### SWADHA

• Create `docs/professor_presentation.pptx`. 10 slides, no placeholder text, everything real. Slides:
  1. LeBlanc — one sentence description ("Automated prompt enrichment + iterative repair pipeline for secure LLM code generation")
  2. The Problem — one statistic (e.g., "Copilot generates insecure code 40% of the time — Pearce et al. 2022")
  3. The 3 Engines — one diagram showing A → LLM → B → C loop
  4. What We Fixed This Sprint — before/after speed (5 min → <60 sec), architecture, categorization
  5. Injection Category Results — Ayushi's table from `docs/injection_category_results.md` as a visual
  6. Metrics Defined — list the 4 RQs and their metric formulas (from `docs/metrics_spec.md`)
  7. Dataset Used — SecurityEval N prompts, CWE coverage breakdown
  8. Isolation — one slide explaining what isolation means and what was done
  9. Remaining Work — honest list of what's not done yet
  10. Next Sprint Goals — 3 bullet points

• Export as PDF: `docs/professor_presentation.pdf`. This is the email attachment.

---

⚠️ DAY 6 HARD STOPS:
- ✓ Suryanshu: `_looks_like_python()` and `_PROSE_RE` deleted. `py_compile`/`compile()` used instead. `test_isolation.py` passes.
- ✓ Ayushi: `docs/preliminary_findings.md` has real numbers for all 4 RQs with interpretations and caveats.
- ✓ Vraj: Extraction failure shows a visible error badge, not silent 0 vulns. Metrics page is in the main nav.
- ✓ Swadha: `docs/professor_presentation.pptx` and `.pdf` exist. No placeholder text on any slide.

---

## DAY 7 (SUNDAY) — INTEGRATION TEST + SPRINT CLOSE

**Goal: Run the full demo from a clean state. Fix whatever breaks. Leave the repo cleaner than you found it.**

Everyone participates in the integration test first. Start fresh: rename `backend/leblanc.db` to `backend/leblanc_backup.db`, start the server, follow `docs/demo_script.md` step by step. Note every broken step.

---

### SURYANSHU

• Fix any critical bugs surfaced by the integration test.

• Clean up dead code: `_PROSE_RE` and `_looks_like_python()` should already be gone (Day 6). Check for any leftover debug `print()` statements in `engine_b.py`, `engine_c.py`, `app.py`. Remove them.

• Ensure `cwe_categories.py` is actually used in the API responses. Check: does `GET /api/metrics` include category breakdown? Do scan results in `/api/run` and `/api/compare` responses include the `category` field on each finding? If not, wire it in now.

• Time the full integration test demo run on P001. Record the actual seconds to `docs/perf_profile.txt` final entry.

---

### AYUSHI

• Final data check. Run this SQL against `backend/leblanc.db` and fix anything weird:
  ```
  sqlite3 backend/leblanc.db
  SELECT COUNT(*) FROM runs;
  SELECT prompt_id, COUNT(*) FROM runs GROUP BY prompt_id;
  SELECT final_status, COUNT(*) FROM runs GROUP BY final_status;
  SELECT * FROM runs WHERE generated_code = '' OR generated_code IS NULL;
  ```
  Any run with empty `generated_code` should be investigated — is it a real LLM failure or a bug?

• Update `docs/preliminary_findings.md` with Day 7 run data if the numbers improved.

• Write `docs/next_sprint_goals.md`. Be specific: "Run all 45 prompts × 3 reps × 2 models = 270 runs." "Add one more model (GPT-4o-mini or DeepSeek)." "Validate false positive rate below 15% by manual review of 27 runs (10%)." "Extend to auth category — run P006, P007, P010, P014 through the same analysis." "Write the paper methodology section."

---

### VRAJ

• Full frontend pass: open every page in Chrome and Firefox. Fix any console errors, broken API calls, or render failures. Check that all 3 pages load without errors on a fresh DB (no existing runs).

• Ensure the main page, history page, and metrics page are all linked to each other in the navigation. No page should be reachable only by typing the URL.

• Check that the "Run Batch" button (Day 5) works end to end — clicking it on the injection filter runs all injection prompts and updates the results table when done.

---

### SWADHA

• Final visual pass: open every page and check specifically (1) contrast ratios on all text — use the browser devtools accessibility check, (2) every icon/color-coded element has a text label, (3) loading states are visible and labeled, (4) error states are visible and say what went wrong (not just a red color).

• Update `docs/design_system.md` with any ad-hoc color or style decisions made during the sprint that weren't documented.

• Confirm `docs/professor_presentation.pdf` is ready to send and all slide content is accurate given the final numbers from Ayushi.

---

⚠️ DAY 7 HARD STOPS (SPRINT COMPLETE):
- ✓ Suryanshu: Fresh DB demo runs without errors. Dead code removed. API responses include `category` on findings.
- ✓ Ayushi: DB is clean. `docs/next_sprint_goals.md` written. `docs/preliminary_findings.md` final version done.
- ✓ Vraj: All 3 pages load clean on Chrome and Firefox with no console errors. Navigation links all pages.
- ✓ Swadha: Final visual pass done. `docs/professor_presentation.pdf` ready to send.

---

📋 SPRINT VERIFICATION TEST — Run This On Day 7

```
Step 1:  Rename backend/leblanc.db → backend/leblanc_backup.db
Step 2:  cd backend && python app.py
Step 3:  Open http://localhost:5000 in browser
Step 4:  Select P001. Click Compare.
Step 5:  Status messages appear and rotate while running.
Step 6:  Results load in under 60 seconds.
Step 7:  Scan results show category tags (Injection) in the correct color.
Step 8:  Repair iterations render as a timeline (not raw JSON).
Step 9:  Open http://localhost:5000/metrics.html — all 4 charts render.
Step 10: Open http://localhost:5000/history.html — P001 appears with category tag.
Step 11: Click Injection filter on main page — only injection prompts shown.
Step 12: python backend/run_batch.py --category injection --models gemini groq --reps 1
Step 13: Confirm new runs appear in history page after batch completes.

If all 13 steps pass: sprint is complete.
```

---

## ISSUES NOT IN THIS SPRINT — LOG FOR NEXT SPRINT

These are real problems. They are not being fixed this sprint because they are lower priority than what is above. Do not forget them.

- **CORS wildcard** (`origins="*"` in `app.py` line 17): fine for local demo, must be restricted before any deployment to a shared server.
- **No rate limiting**: anyone who knows the API can spam it and burn your Gemini/Groq API credits. Add `flask-limiter` before any public demo.
- **API keys in `.env`**: confirm `.env` is in `.gitignore`. Run `git status` and confirm it shows as untracked/ignored.
- **`get_all_runs()` returns all rows**: at 200+ prompts × 3 modes × 2 models × 3 reps = 3,600 rows, this will be a large response. Add `LIMIT` and pagination before full data collection.
- **Engine A keyword matching is dumb substring**: the prompt "write a password manager" triggers auth warnings — that's correct. But "discuss the history of SQL" would trigger CWE-89 warnings — that's a false trigger. A proper fix requires a small NLP filter or part-of-speech check. Document as a known limitation.
- **Semgrep `--config=p/python-security` may miss rules**: validate that the rule pack covers all CWEs in `target_cwes` across `prompts.json`. Some less common CWEs (CWE-338, CWE-611) may not be in the Python security pack. Check with `semgrep --config=p/python-security --show-supported-languages`.
- **Database migration code is fragile**: `ALTER TABLE ... ADD COLUMN` in `init_db()` is a hack. Next sprint, introduce Alembic for proper schema versioning.
- **No 3× repetitions yet**: for publication, each prompt needs 3 runs to show LLM non-determinism. This sprint establishes infrastructure; next sprint does the full 3-rep run.
- **Full isolation (Docker)**: Day 3 adds a dedicated temp directory. Full isolation = `docker run --rm --network=none -v scan_tmp:/tmp python:3.11-slim python -m semgrep ...`. Defer to next sprint after Docker is confirmed available.
