"""
LeBlanc MCP server — exposes the pipeline engines as Model Context Protocol tools.

This replaces v2's never-built VS Code extension: any MCP client (Claude Code,
Claude Desktop, Cursor, ...) can now call LeBlanc's security engines directly.

Register with Claude Code:
    claude mcp add leblanc -- python D:/LYPROJECT/v3/backend/mcp_server.py

Free tools (no API spend): analyze_prompt, scan_code, audit_llm_response, project_status
Spending tools (clearly marked): repair_code — makes LLM API calls.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "leblanc",
    instructions=(
        "LeBlanc security pipeline for LLM-generated Python code. "
        "Use analyze_prompt BEFORE generating code to get CWE warnings to include; "
        "use scan_code AFTER generating code to check it; use repair_code to have an "
        "LLM fix findings (spends API tokens)."
    ),
)


@mcp.tool()
def analyze_prompt(prompt: str) -> str:
    """Analyze a coding request for security risk BEFORE code generation.
    Returns the CWEs it likely touches (with retrieval evidence) and an enriched
    version of the prompt containing security warnings. Free — no API calls."""
    from engine_a_enrich import enrich_prompt
    enriched, cwes, keywords, details = enrich_prompt(prompt)
    return json.dumps({
        "matched_cwes": cwes,
        "evidence": details,
        "enriched_prompt": enriched,
    }, indent=1)


@mcp.tool()
def scan_code(code: str) -> str:
    """Statically scan Python code for security vulnerabilities using Bandit ∪ Semgrep
    (medium+ severity, CWE-mapped, deduplicated). Accepts raw code or a fenced
    ```python``` block. Free — no API calls."""
    from engine_b_scan import scan_code as _scan
    payload = code if "```" in code else f"```python\n{code}\n```"
    findings, clean, scanners = _scan(payload)
    if not clean:
        return json.dumps({"error": "extraction_or_syntax_failed",
                           "hint": "code must be valid Python"})
    return json.dumps({
        "scanners_used": scanners,
        "finding_count": len(findings),
        "findings": findings,
        "verdict": "clean" if not findings else "vulnerable",
    }, indent=1)


@mcp.tool()
def scan_path(path: str, max_findings: int = 100) -> str:
    """Scan a real FILE or DIRECTORY (recursively) on disk for security issues using
    Bandit ∪ Semgrep — the codebase-scale version of scan_code. Use this to audit an
    existing project or a file the model just wrote to disk. Returns per-file findings
    and a per-file count. Free — no API calls. (scan_code is for a single in-memory
    snippet; scan_path is for actual paths / whole repos.)"""
    from engine_b_scan import scan_path as _scan_path
    res = _scan_path(path)
    if not res.get("ok"):
        return json.dumps(res)
    res["findings"] = res["findings"][:max_findings]
    res["truncated"] = res["finding_count"] > max_findings
    return json.dumps(res, indent=1)


@mcp.tool()
def audit_llm_response(response_text: str) -> str:
    """Audit a raw LLM response: extract the ```python``` block, validate syntax,
    scan it, and report findings by category. Ideal as a post-generation gate in
    an agent loop. Free — no API calls."""
    from engine_b_scan import scan_code as _scan
    findings, clean, scanners = _scan(response_text)
    if not clean:
        return json.dumps({"verdict": "extraction_failed",
                           "hint": "no valid ```python``` block found"})
    by_cat = {}
    for f in findings:
        by_cat.setdefault(f["category"], []).append(f"{f['rule']} L{f['line']}: {f['message'][:100]}")
    return json.dumps({
        "verdict": "clean" if not findings else "vulnerable",
        "scanners_used": scanners,
        "finding_count": len(findings),
        "by_category": by_cat,
        "clean_code": clean,
    }, indent=1)


@mcp.tool()
def repair_code(code: str, model: str = "gpt-oss-120b") -> str:
    """Repair vulnerable Python code via LeBlanc's iterative loop: scan -> send
    findings to the LLM -> re-scan, up to 3 rounds. ⚠️ SPENDS API TOKENS (1-3 LLM
    calls on the chosen model; default is a free-tier Groq model).
    Models: gpt-oss-20b, gpt-oss-120b, gemini-2.5-flash, gpt-4o-mini,
    claude-haiku-4.5, deepseek-chat."""
    from engine_b_scan import scan_code as _scan
    from engine_c_repair import repair_loop
    payload = code if "```" in code else f"```python\n{code}\n```"
    findings, clean, scanners = _scan(payload)
    if not clean:
        return json.dumps({"error": "extraction_or_syntax_failed"})
    if not findings:
        return json.dumps({"verdict": "already_clean", "code": clean})
    rr = repair_loop(clean, findings, model)
    return json.dumps({
        "verdict": rr["final_status"],
        "iterations": [
            {"n": it["iteration"], "before": it["vulns_before"], "after": it["vulns_after"]}
            for it in rr["iterations"]
        ],
        "final_code": rr["final_code"],
    }, indent=1)


@mcp.tool()
def project_status() -> str:
    """LeBlanc experiment status: run counts, completeness, per-RQ data sufficiency.
    Free — reads the local database only."""
    from metrics import compute_all
    m = compute_all()
    return json.dumps({
        "summary": m["summary"],
        "rq_ready": {k: (not m[k]["insufficient"]) for k in ("rq1", "rq2", "rq3", "rq4", "rq5")},
    }, indent=1)


if __name__ == "__main__":
    mcp.run()  # stdio transport
