"""Database v3 — one row per (prompt, model, mode, rep) with unique index (idempotent batch)."""
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "leblanc_v3.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id TEXT NOT NULL,
            model TEXT NOT NULL,
            mode TEXT NOT NULL,
            rep INTEGER NOT NULL,
            generation TEXT,
            category TEXT,
            prompt_text TEXT,
            enriched_prompt TEXT,
            matched_cwes TEXT,
            match_details TEXT,
            generated_code TEXT,
            clean_code TEXT,
            final_code TEXT,
            scan_results TEXT,
            scanners TEXT,
            vuln_count INTEGER,
            repair_result TEXT,
            functest_status TEXT,
            functest_detail TEXT,
            final_status TEXT,
            total_iterations INTEGER,
            llm_error TEXT,
            timestamp TEXT,
            provenance TEXT,
            UNIQUE(prompt_id, model, mode, rep)
        )
    """)
    # Additive migration for databases created before a column existed. Kept
    # explicit and idempotent rather than silent: a missing column is added, an
    # existing one is left alone, and anything else raises rather than being
    # swallowed (v2 lesson — a migration that fails quietly corrupts an
    # experiment's comparability without anyone noticing).
    existing = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    for col, decl in (("provenance", "TEXT"),):
        if col not in existing:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {col} {decl}")
    conn.commit()
    conn.close()


def has_run(prompt_id, model, mode, rep):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM runs WHERE prompt_id=? AND model=? AND mode=? AND rep=? AND final_status != 'llm_error'",
        (prompt_id, model, mode, rep)).fetchone()
    conn.close()
    return row is not None


def save_run(d):
    conn = get_db()
    conn.execute("""
        INSERT INTO runs (prompt_id, model, mode, rep, generation, category, prompt_text,
            enriched_prompt, matched_cwes, match_details, generated_code, clean_code,
            final_code, scan_results, scanners, vuln_count, repair_result,
            functest_status, functest_detail, final_status, total_iterations, llm_error,
            timestamp, provenance)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(prompt_id, model, mode, rep) DO UPDATE SET
            generation=excluded.generation, category=excluded.category,
            prompt_text=excluded.prompt_text, enriched_prompt=excluded.enriched_prompt,
            matched_cwes=excluded.matched_cwes, match_details=excluded.match_details,
            generated_code=excluded.generated_code, clean_code=excluded.clean_code,
            final_code=excluded.final_code, scan_results=excluded.scan_results,
            scanners=excluded.scanners, vuln_count=excluded.vuln_count,
            repair_result=excluded.repair_result, functest_status=excluded.functest_status,
            functest_detail=excluded.functest_detail, final_status=excluded.final_status,
            total_iterations=excluded.total_iterations, llm_error=excluded.llm_error,
            timestamp=excluded.timestamp, provenance=excluded.provenance
    """, (
        d["prompt_id"], d["model"], d["mode"], d["rep"], d.get("generation", ""),
        d.get("category", ""), d.get("prompt_text", ""), d.get("enriched_prompt", ""),
        json.dumps(d.get("matched_cwes", [])), json.dumps(d.get("match_details", [])),
        d.get("generated_code", ""), d.get("clean_code", ""), d.get("final_code", ""),
        json.dumps(d.get("scan_results", [])), json.dumps(d.get("scanners", [])),
        d.get("vuln_count", 0), json.dumps(d.get("repair_result", {})),
        d.get("functest_status", ""), d.get("functest_detail", ""),
        d.get("final_status", ""), d.get("total_iterations", 0),
        d.get("llm_error", ""), datetime.now().isoformat(),
        json.dumps(d.get("provenance", {})),
    ))
    conn.commit()
    conn.close()


def get_all_runs():
    conn = get_db()
    rows = conn.execute("SELECT * FROM runs ORDER BY id DESC").fetchall()
    conn.close()
    out = []
    for row in rows:
        r = dict(row)
        for k in ("matched_cwes", "match_details", "scan_results", "scanners", "repair_result",
                  "provenance"):
            r[k] = json.loads(r[k] or ("{}" if k in ("repair_result", "provenance") else "[]"))
        out.append(r)
    return out
