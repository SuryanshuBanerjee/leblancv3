"""
LeBlanc v3 — demo & analysis server.

Serves the frontend and read-only analysis APIs. The ONLY endpoint that spends
API tokens is POST /api/run (single prompt, single model, user-clicked) — batch
experiments deliberately live in run_batch.py on the CLI, never behind a web button.
"""
import json
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from database import init_db, get_all_runs, save_run
from engine_a_enrich import enrich_prompt
from llm_client import MODEL_CONFIGS, preflight
from metrics import compute_all
from run_batch import load_dataset, run_cell

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__)
CORS(app, origins=["http://localhost:5000", "http://127.0.0.1:5000"])  # v2 had origins="*"


# ---------- frontend ----------

@app.route("/")
def index():
    """Serve the dashboard shell."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    """Serve frontend assets (the UI is a single file plus whatever it references)."""
    return send_from_directory(FRONTEND_DIR, path)


# ---------- read-only APIs ----------

@app.route("/api/meta")
def meta():
    """Project metadata + per-model key availability, for the Overview tab.

    `key_set` reports whether the env var for each provider is present — it does
    NOT verify the key works. Use /api/preflight (or run_batch --preflight) for
    that; a set-but-invalid key is exactly the failure the preflight gate exists
    to catch before an overnight run.
    """
    prompts = load_dataset()
    key_status = {}
    for name, cfg in MODEL_CONFIGS.items():
        env = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY",
               "anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}[cfg["provider"]]
        key_status[name] = {"gen": cfg["gen"], "provider": cfg["provider"],
                            "key_set": bool(os.environ.get(env, "").strip())}
    return jsonify({
        "project": "LeBlanc v3",
        "thesis": "How much does security scaffolding (CWE-aware enrichment + scanner-guided "
                  "repair) still buy across LLM generations — and how often is 'repaired' code "
                  "secretly broken?",
        "dataset_size": len(prompts),
        "models": key_status,
        "modes": ["plain", "enriched", "enriched_repair"],
    })


@app.route("/api/prompts")
def prompts():
    """The frozen 50-prompt dataset, as stored."""
    return jsonify(load_dataset())


@app.route("/api/enrich", methods=["POST"])
def enrich_preview():
    """Free & offline: show Engine A's retrieval on any prompt (no LLM call)."""
    prompt = (request.json or {}).get("prompt", "")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    enriched, cwes, kws, details = enrich_prompt(prompt)
    return jsonify({"enriched_prompt": enriched, "matched_cwes": cwes,
                    "matched_keywords": kws, "match_details": details})


@app.route("/api/metrics")
def metrics():
    """Live RQ1-RQ5 metrics computed from the database on every request."""
    return jsonify(compute_all())


@app.route("/api/history")
def history():
    """Every run, trimmed to the columns the history table shows.

    Deliberately slim: the full record (all code, all findings, all repair
    iterations) is fetched per-row via /api/run_detail when a user clicks in,
    rather than shipping megabytes of code to render a table.
    """
    runs = get_all_runs()
    slim = []
    for r in runs:
        slim.append({k: r[k] for k in (
            "id", "prompt_id", "model", "mode", "rep", "generation", "category",
            "vuln_count", "final_status", "functest_status", "total_iterations",
            "scanners", "timestamp")})
    return jsonify(slim)


@app.route("/api/run_detail/<int:run_id>")
def run_detail(run_id):
    """One complete run record, including every pipeline stage's code and findings."""
    for r in get_all_runs():
        if r["id"] == run_id:
            return jsonify(r)
    return jsonify({"error": "not found"}), 404


@app.route("/api/preflight")
def preflight_route():
    """Tiny 1-call-per-model check; user-triggered from the UI."""
    return jsonify(preflight())


# ---------- the one spending endpoint (single run, explicit) ----------

@app.route("/api/run", methods=["POST"])
def run_single():
    """The ONLY endpoint that spends API tokens: one prompt, one model, one run.

    Accepts either a dataset `prompt_id` or an ad-hoc `prompt`. Batch experiments
    deliberately live in run_batch.py behind a cost gate — a web button that could
    kick off 2,700 paid calls is exactly the mistake this split prevents.
    """
    data = request.json or {}
    prompt_id = data.get("prompt_id")
    model = data.get("model")
    mode = data.get("mode", "enriched_repair")
    if model not in MODEL_CONFIGS:
        return jsonify({"error": f"unknown model {model}"}), 400
    matches = load_dataset(ids=[prompt_id]) if prompt_id else []
    if matches:
        p = matches[0]
    elif data.get("prompt"):
        p = {"id": "custom", "prompt": data["prompt"], "category": "Custom", "target_cwes": []}
    else:
        return jsonify({"error": "provide prompt_id or prompt"}), 400
    rep = int(data.get("rep", 1))
    rec = run_cell(p, model, mode, rep)
    return jsonify(rec)


if __name__ == "__main__":
    init_db()
    print("\n  LeBlanc v3 — http://localhost:5000\n")
    app.run(debug=False, port=5000)
