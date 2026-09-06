"""
Engine B v3 — dual static analysis: Bandit ∪ Semgrep.

- Extraction: fenced ```python``` block -> compile() syntax gate.
- Bandit: -ll (medium+), JSON.
- Semgrep: --config p/python-security, JSON. Gracefully degrades if unavailable;
  the scanners actually used are recorded on every scan (stored in the DB so no
  run can silently claim dual-scanner coverage it didn't have).
- Findings unioned, deduplicated by (line, cwe-set) then (line, rule).
"""
import hashlib
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

from cwe_categories import get_category_by_rule

SCAN_TMP_DIR = os.path.join(os.path.dirname(__file__), "scan_tmp")
os.makedirs(SCAN_TMP_DIR, exist_ok=True)

SEMGREP_BIN = shutil.which("semgrep")
SEMGREP_TIMEOUT = 90
_SEV_OK = {"MEDIUM", "HIGH", "CRITICAL", "WARNING", "ERROR"}  # semgrep WARNING≈medium

# Ruleset. We PIN a local copy of the `p/python` registry pack (781 rules) so that
# (a) scans need no network per run, and (b) results are reproducible — the registry
# pack can change under us months apart, which would silently alter findings.
# NOTE: the previous config `p/python-security` was a 404 (never existed) and semgrep
# was silently degrading to Bandit-only on every run. Regenerate the local file with:
#   curl -L https://semgrep.dev/c/p/python -o semgrep_rules/python.yaml
SEMGREP_LOCAL_CONFIG = os.path.join(os.path.dirname(__file__), "semgrep_rules", "python.yaml")
SEMGREP_CONFIG = SEMGREP_LOCAL_CONFIG if os.path.exists(SEMGREP_LOCAL_CONFIG) else "p/python"

# Set by run_semgrep on the last invocation so callers/tests can detect silent failure
# instead of mistaking "ran, found nothing" for "never ran".
LAST_SEMGREP_ERRORS = []


_PROVENANCE = None


def scanner_provenance():
    """What actually produced the findings — captured once, stored on every run.

    The project's reproducibility claim is "we pin the ruleset so results don't
    drift". That claim is unverifiable after the fact unless each run records
    *which* pinned ruleset and *which* analyser versions were actually in play:
    a reader (or we, six months later) otherwise cannot tell whether a changed
    number means the models changed or the tooling did. Cheap to record, and it
    is the difference between "reproducible" as an aspiration and as a fact.
    """
    global _PROVENANCE
    if _PROVENANCE is not None:
        return _PROVENANCE

    def _ver(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                               stdin=subprocess.DEVNULL)
            return (r.stdout or r.stderr).strip().splitlines()[0][:80]
        except Exception as e:
            return f"unavailable: {type(e).__name__}"

    ruleset_hash = None
    if os.path.exists(SEMGREP_LOCAL_CONFIG):
        h = hashlib.sha256()
        with open(SEMGREP_LOCAL_CONFIG, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        ruleset_hash = h.hexdigest()[:16]

    _PROVENANCE = {
        "bandit": _ver(["python", "-m", "bandit", "--version"]),
        "semgrep": _ver([SEMGREP_BIN, "--version"]) if SEMGREP_BIN else "not installed",
        "semgrep_config": os.path.basename(SEMGREP_CONFIG),
        "semgrep_ruleset_sha256_16": ruleset_hash,
        "python": sys.version.split()[0],
        "platform": sys.platform,
    }
    return _PROVENANCE


def extract_code_from_response(response_text):
    if not response_text:
        return ""
    matches = re.findall(r"```(?:python)?\s*\n(.*?)```", response_text, re.DOTALL)
    return matches[0].strip() if matches else ""


def run_bandit(filepath):
    findings = []
    try:
        result = subprocess.run(
            ["python", "-m", "bandit", "-q", "-f", "json", "-ll", filepath],
            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
        )
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        for r in data.get("results", []):
            cwe_info = r.get("issue_cwe") or {}
            cwe_id = f"CWE-{cwe_info.get('id')}" if cwe_info.get("id") else "unmapped"
            rule_id = r.get("test_id", "unknown")
            findings.append({
                "tool": "bandit",
                "rule": rule_id,
                "category": get_category_by_rule(rule_id, [cwe_id]),
                "cwes": [cwe_id],
                "severity": r.get("issue_severity", "UNKNOWN"),
                "line": r.get("line_number", 0),
                "message": r.get("issue_text", ""),
            })
    except Exception:
        pass
    return findings


def run_semgrep(filepath):
    global LAST_SEMGREP_ERRORS
    LAST_SEMGREP_ERRORS = []
    if not SEMGREP_BIN:
        return None  # unavailable (distinct from "ran and found nothing")
    try:
        result = subprocess.run(
            [SEMGREP_BIN, "scan", "--config", SEMGREP_CONFIG, "--json",
             "--quiet", "--disable-version-check", "--metrics", "off", filepath],
            capture_output=True, text=True, timeout=SEMGREP_TIMEOUT, stdin=subprocess.DEVNULL,
        )
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        # Surface config/rule errors instead of pretending the scan was clean.
        errs = data.get("errors", [])
        if errs:
            LAST_SEMGREP_ERRORS = [str(e.get("message", e))[:200] for e in errs]
        findings = []
        for r in data.get("results", []):
            extra = r.get("extra", {})
            sev = extra.get("severity", "UNKNOWN").upper()
            if sev not in _SEV_OK:
                continue
            meta = extra.get("metadata", {})
            cwes_raw = meta.get("cwe", [])
            if isinstance(cwes_raw, str):
                cwes_raw = [cwes_raw]
            cwes = []
            for c in cwes_raw:
                m = re.search(r"CWE-\d+", str(c))
                if m:
                    cwes.append(m.group(0))
            cwes = cwes or ["unmapped"]
            rule_id = r.get("check_id", "unknown").split(".")[-1]
            findings.append({
                "tool": "semgrep",
                "rule": rule_id,
                "category": get_category_by_rule(rule_id, cwes),
                "cwes": cwes,
                "severity": sev,
                "line": r.get("start", {}).get("line", 0),
                "message": extra.get("message", "")[:300],
            })
        return findings
    except Exception:
        return None


# Cross-tool rule equivalences: the SAME underlying weakness that Bandit and
# Semgrep both detect but map to different CWEs, which made the old
# (line, cwe-set) / (line, rule) dedup miss them entirely — a Flask
# `app.run(debug=True)` was counted twice (Bandit B201 -> CWE-94, Semgrep
# debug-enabled -> CWE-489), and so was `host="0.0.0.0"` (B104 -> CWE-605,
# avoid_app_run_with_bad_host -> CWE-668). Found 2026-09-07 during the
# false-positive audit: those two pairs alone accounted for 180 of 291 findings
# in the pilot database, i.e. the raw finding COUNT was inflated roughly 1.6x.
# (The binary vuln = count > 0 verdict, and therefore RQ1-RQ4, are unaffected —
# but any per-finding statistic computed before this fix is not comparable with
# one computed after it. Pilot data pre-dates the fix; see docs/03_METHODOLOGY.md.)
CROSS_TOOL_EQUIVALENT = {
    "B201": "flask-debug-true", "debug-enabled": "flask-debug-true",
    "B104": "bind-all-interfaces", "avoid_app_run_with_bad_host": "bind-all-interfaces",
    "B105": "hardcoded-secret", "generic-api-key": "hardcoded-secret",
    "B303": "weak-hash", "insecure-hash-algorithm-md5": "weak-hash",
    "B324": "weak-hash", "insecure-hash-function": "weak-hash",
}

_SEV_RANK = {"CRITICAL": 4, "ERROR": 3, "HIGH": 3, "MEDIUM": 2, "WARNING": 2, "LOW": 1,
             "UNKNOWN": 0}


def dedupe_findings(findings, file_key=None):
    """Merge duplicate findings, including the SAME issue reported by both tools.

    Three keys, in order of confidence:
      1. (file, line, canonical-issue)  — known cross-tool equivalences, the fix for
                                          the double-counting described above
      2. (file, line, cwe-set)          — both tools agreed on the CWE
      3. (file, line, rule)             — the same rule firing twice

    When two findings merge, we keep the higher severity, union the CWE lists, and
    record both tool names (e.g. "bandit+semgrep") so the audit trail still shows
    that two independent analysers agreed — that agreement is evidence, and
    throwing it away would be a different kind of dishonesty than double-counting.
    """
    merged = {}
    order = []
    for fd in findings:
        fkey = os.path.normpath(fd.get("file", "")) if file_key else ""
        canon = CROSS_TOOL_EQUIVALENT.get(fd.get("rule", ""))
        keys = [(fkey, fd["line"], f"canon:{canon}")] if canon else []
        keys.append((fkey, fd["line"], "cwes:" + ",".join(sorted(fd.get("cwes") or []))))
        keys.append((fkey, fd["line"], "rule:" + str(fd.get("rule"))))

        hit = next((k for k in keys if k in merged), None)
        if hit is None:
            slot = dict(fd)
            for k in keys:
                merged[k] = slot
            order.append(slot)
            continue

        slot = merged[hit]
        # union the evidence rather than discarding the second detection
        tools = sorted(set(str(slot.get("tool", "")).split("+")) |
                       {str(fd.get("tool", ""))} - {""})
        slot["tool"] = "+".join(t for t in tools if t)
        slot["cwes"] = sorted(set(slot.get("cwes") or []) | set(fd.get("cwes") or []))
        if _SEV_RANK.get(str(fd.get("severity", "")).upper(), 0) > \
           _SEV_RANK.get(str(slot.get("severity", "")).upper(), 0):
            slot["severity"] = fd["severity"]
        for k in keys:
            merged.setdefault(k, slot)
    return order


def scan_code(code_string):
    """
    Returns (findings, clean_code, scanners_used).
    findings = [] with clean_code == "" means extraction/compile failure.
    """
    clean_code = extract_code_from_response(code_string)
    if not clean_code:
        return [], "", []

    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False, dir=SCAN_TMP_DIR
    ) as f:
        f.write(clean_code)
        filepath = f.name

    try:
        try:
            py_compile.compile(filepath, doraise=True)
        except py_compile.PyCompileError:
            return [], "", []

        scanners = ["bandit"]
        findings = run_bandit(filepath)
        sg = run_semgrep(filepath)
        if sg is not None:
            scanners.append("semgrep")
            findings.extend(sg)

        return dedupe_findings(findings), clean_code, scanners
    finally:
        if os.path.exists(filepath):
            os.unlink(filepath)


def _bandit_path(path):
    findings = []
    try:
        result = subprocess.run(
            ["python", "-m", "bandit", "-q", "-f", "json", "-ll", "-r", path],
            capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL,
        )
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        for r in data.get("results", []):
            cwe_info = r.get("issue_cwe") or {}
            cwe_id = f"CWE-{cwe_info.get('id')}" if cwe_info.get("id") else "unmapped"
            rule_id = r.get("test_id", "unknown")
            findings.append({
                "tool": "bandit", "rule": rule_id,
                "category": get_category_by_rule(rule_id, [cwe_id]),
                "cwes": [cwe_id], "severity": r.get("issue_severity", "UNKNOWN"),
                "file": r.get("filename", path), "line": r.get("line_number", 0),
                "message": r.get("issue_text", ""),
            })
    except Exception:
        pass
    return findings


def _semgrep_path(path):
    global LAST_SEMGREP_ERRORS
    LAST_SEMGREP_ERRORS = []
    if not SEMGREP_BIN:
        return None
    try:
        result = subprocess.run(
            [SEMGREP_BIN, "scan", "--config", SEMGREP_CONFIG, "--json",
             "--quiet", "--disable-version-check", "--metrics", "off", path],
            capture_output=True, text=True, timeout=max(SEMGREP_TIMEOUT, 300), stdin=subprocess.DEVNULL,
        )
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        if data.get("errors"):
            LAST_SEMGREP_ERRORS = [str(e.get("message", e))[:200] for e in data["errors"]]
        findings = []
        for r in data.get("results", []):
            extra = r.get("extra", {})
            sev = extra.get("severity", "UNKNOWN").upper()
            if sev not in _SEV_OK:
                continue
            meta = extra.get("metadata", {})
            cwes_raw = meta.get("cwe", [])
            if isinstance(cwes_raw, str):
                cwes_raw = [cwes_raw]
            cwes = [m.group(0) for c in cwes_raw if (m := re.search(r"CWE-\d+", str(c)))] or ["unmapped"]
            findings.append({
                "tool": "semgrep", "rule": r.get("check_id", "unknown").split(".")[-1],
                "category": get_category_by_rule(r.get("check_id", ""), cwes),
                "cwes": cwes, "severity": sev,
                "file": r.get("path", path), "line": r.get("start", {}).get("line", 0),
                "message": extra.get("message", "")[:300],
            })
        return findings
    except Exception as e:
        LAST_SEMGREP_ERRORS = [str(e)[:200]]
        return None


def scan_path(path, max_files=500):
    """
    Scan a real file OR directory (recursively) with Bandit ∪ Semgrep — the
    codebase-scale counterpart to scan_code(). Returns:
      {ok, path, scanners_used, semgrep_errors, finding_count, findings, by_file}
    findings carry a `file` key. Skips nothing silently: if semgrep errors, they
    are reported in semgrep_errors rather than vanishing.
    """
    if not os.path.exists(path):
        return {"ok": False, "error": f"path not found: {path}"}

    scanners = ["bandit"]
    findings = _bandit_path(path)
    sg = _semgrep_path(path)
    if sg is not None:
        scanners.append("semgrep")
        findings.extend(sg)

    # same three-key merge as scan_code(), but keyed per file as well
    deduped = dedupe_findings(findings, file_key=True)

    by_file = {}
    for fd in deduped:
        by_file.setdefault(os.path.normpath(fd.get("file", "")), 0)
        by_file[os.path.normpath(fd.get("file", ""))] += 1

    return {
        "ok": True, "path": path, "scanners_used": scanners,
        "semgrep_errors": LAST_SEMGREP_ERRORS,
        "finding_count": len(deduped), "findings": deduped, "by_file": by_file,
    }


if __name__ == "__main__":
    vuln_snippet = '''```python
import subprocess, hashlib, yaml

def run(cmd, doc):
    subprocess.call(cmd, shell=True)
    h = hashlib.md5(b"pw").hexdigest()
    data = yaml.load(doc)
    return h, data
```'''
    findings, code, scanners = scan_code(vuln_snippet)
    print("scanners:", scanners)
    for fd in findings:
        print(f"  [{fd['tool']}] {fd['rule']} {fd['cwes']} sev={fd['severity']} line={fd['line']}")
