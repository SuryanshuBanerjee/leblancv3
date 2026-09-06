"""
test_engines.py — unit tests for the pipeline logic itself.

    python -m pytest backend/test_engines.py -q        (free, offline, ~seconds)

WHY THIS FILE EXISTS. `validate_m2.py` tests the *dataset* (every functional test
passes on its reference solution). Nothing tested the *engines*, and that gap had
a cost: the cross-tool dedup bug — the same weakness counted twice whenever Bandit
and Semgrep labelled it with different CWEs, 180 of the pilot's 291 findings —
survived a full pilot run and was only caught by hand-reading an audit worksheet.
A single assertion would have caught it on the day it was written.

These tests are deliberately about LOGIC, not about the analysers' verdicts:
anything that shells out to Bandit/Semgrep is slow and version-dependent, so the
scan-integration tests are marked and can be deselected with `-m "not slow"`.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cwe_categories import get_category_by_rule
from engine_a_enrich import enrich_prompt
from engine_b_scan import (CROSS_TOOL_EQUIVALENT, dedupe_findings,
                           extract_code_from_response, scan_code, scanner_provenance)
from engine_c_repair import build_repair_prompt
from engine_d_functest import run_functional_tests
from metrics import _is_vuln_final, mcnemar_exact, wilson_ci


def F(tool="bandit", rule="B101", cwes=("CWE-1",), line=1, sev="MEDIUM", **kw):
    """Minimal finding fixture."""
    d = {"tool": tool, "rule": rule, "cwes": list(cwes), "line": line,
         "severity": sev, "category": "Other", "message": "m"}
    d.update(kw)
    return d


# --------------------------------------------------------------- Engine B: dedup
class TestDedup:
    def test_the_bug_that_shipped_cross_tool_same_issue_different_cwe(self):
        """THE regression test. Bandit and Semgrep both flag Flask debug=True on
        the same line but map it to different CWEs; it is ONE weakness."""
        merged = dedupe_findings([
            F(tool="bandit", rule="B201", cwes=["CWE-94"], line=9, sev="HIGH"),
            F(tool="semgrep", rule="debug-enabled", cwes=["CWE-489"], line=9, sev="WARNING"),
        ])
        assert len(merged) == 1, "same weakness from two tools must collapse to one finding"
        assert merged[0]["tool"] == "bandit+semgrep", "cross-tool agreement must be preserved"
        assert set(merged[0]["cwes"]) == {"CWE-94", "CWE-489"}, "CWE evidence must be unioned"
        assert merged[0]["severity"] == "HIGH", "the higher severity must win"

    def test_bind_all_interfaces_pair_also_merges(self):
        merged = dedupe_findings([
            F(tool="bandit", rule="B104", cwes=["CWE-605"], line=9),
            F(tool="semgrep", rule="avoid_app_run_with_bad_host", cwes=["CWE-668"], line=9),
        ])
        assert len(merged) == 1

    def test_genuinely_different_issues_on_one_line_are_kept(self):
        """The dedup must not over-merge: two unrelated rules with unrelated CWEs
        on the same line are two findings."""
        merged = dedupe_findings([
            F(tool="bandit", rule="B608", cwes=["CWE-89"], line=5),
            F(tool="semgrep", rule="tainted-sql-string", cwes=["CWE-943"], line=5),
        ])
        assert len(merged) == 2

    def test_same_issue_on_different_lines_is_two_findings(self):
        merged = dedupe_findings([
            F(rule="B201", cwes=["CWE-94"], line=9),
            F(rule="B201", cwes=["CWE-94"], line=40),
        ])
        assert len(merged) == 2

    def test_identical_finding_repeated_collapses(self):
        merged = dedupe_findings([F(), F()])
        assert len(merged) == 1

    def test_per_file_keying_keeps_same_line_in_different_files(self):
        merged = dedupe_findings([
            F(rule="B201", cwes=["CWE-94"], line=9, file="a.py"),
            F(rule="B201", cwes=["CWE-94"], line=9, file="b.py"),
        ], file_key=True)
        assert len(merged) == 2

    def test_equivalence_map_is_symmetric(self):
        """Every canonical issue must be reachable from at least two rules,
        otherwise the entry does nothing and is a typo waiting to happen."""
        canon_counts = {}
        for rule, canon in CROSS_TOOL_EQUIVALENT.items():
            canon_counts.setdefault(canon, []).append(rule)
        singles = {c: rs for c, rs in canon_counts.items() if len(rs) < 2}
        assert not singles, f"canonical issues with only one rule mapped: {singles}"

    def test_empty_input(self):
        assert dedupe_findings([]) == []


# ---------------------------------------------------------- Engine B: extraction
class TestExtraction:
    def test_fenced_python_block(self):
        assert extract_code_from_response("pre\n```python\nx = 1\n```\npost") == "x = 1"

    def test_bare_fence_without_language(self):
        assert extract_code_from_response("```\nx = 1\n```") == "x = 1"

    def test_unclosed_fence_yields_nothing(self):
        """The truncation case that caused the 2026-09-01 max_tokens bug: a model
        cut off mid-block has no closing fence, and that must read as
        extraction-failed rather than as empty-but-fine code."""
        assert extract_code_from_response("```python\nx = 1\n# still writing") == ""

    def test_no_code_at_all(self):
        assert extract_code_from_response("I cannot help with that.") == ""

    def test_empty_and_none(self):
        assert extract_code_from_response("") == ""
        assert extract_code_from_response(None) == ""

    def test_first_block_wins_when_several(self):
        assert extract_code_from_response("```python\na = 1\n```\n```python\nb = 2\n```") == "a = 1"


# ------------------------------------------------------------------- Engine A
class TestEnrichment:
    def test_sql_prompt_matches_injection_cwe(self):
        enriched, cwes, kws, details = enrich_prompt(
            "Write a Flask endpoint that looks up a user in a MySQL table by username")
        assert cwes, "an obviously SQL-shaped prompt must match at least one CWE"
        assert enriched != "" and "SECURITY REQUIREMENTS" in enriched
        assert all("cwe" in d and "score" in d for d in details), "evidence must be recorded"

    def test_enrichment_is_deterministic(self):
        """Engine A must be reproducible — it is the one component the paper
        describes as deterministic and offline."""
        a = enrich_prompt("upload a file and store it on disk")
        b = enrich_prompt("upload a file and store it on disk")
        assert a == b

    def test_enriched_prompt_contains_the_original(self):
        p = "Write a function that runs a shell command supplied by the user"
        enriched, _, _, _ = enrich_prompt(p)
        assert p in enriched, "enrichment must augment the prompt, never replace it"

    def test_every_dataset_prompt_gets_at_least_one_warning(self):
        """If Engine A fires on nothing for some prompt, then plain and enriched
        are the SAME prompt for it, and that pair contributes nothing but noise
        to RQ2. We want to know immediately if that ever becomes true."""
        path = os.path.join(os.path.dirname(__file__), "..", "dataset",
                            "leblanc_v3_prompts.json")
        with open(path, encoding="utf-8") as f:
            prompts = json.load(f)
        silent = [p["id"] for p in prompts if not enrich_prompt(p["prompt"])[1]]
        assert not silent, f"Engine A matched no CWE for: {silent} (RQ2 no-ops)"


# ------------------------------------------------------------------- Engine C
class TestRepairPrompt:
    def test_lists_every_finding_and_demands_interface_preservation(self):
        prompt = build_repair_prompt(
            "x = 1", [F(cwes=["CWE-89"], line=3, sev="HIGH"),
                      F(cwes=["CWE-78"], line=7, sev="MEDIUM")])
        assert "CWE-89" in prompt and "CWE-78" in prompt
        assert "line 3" in prompt and "line 7" in prompt
        assert "PRESERVING" in prompt, "repair must not be allowed to delete the feature"
        assert "x = 1" in prompt, "the code under repair must be included"

    def test_security_context_is_included_when_supplied(self):
        assert "CWE-502" in build_repair_prompt("x=1", [F()], security_context=["CWE-502"])


# ------------------------------------------------------------------- Engine D
class TestFunctionalTests:
    def test_missing_test_file_is_no_tests_not_a_failure(self):
        assert run_functional_tests("ZZZ999", "x = 1")["status"] == "no_tests"

    def test_absent_code_is_no_code_not_fail(self):
        """`no_code` and `fail` are different facts. Folding the first into the
        second inflates RQ5's broken-code numerator with runs that never
        produced a candidate. (Regression test for the 2026-09-07 fix.)"""
        assert run_functional_tests("S001", "")["status"] == "no_code"


# -------------------------------------------------------------- metrics logic
class TestMetrics:
    def test_wilson_ci_brackets_the_point_estimate(self):
        rate, lo, hi = wilson_ci(3, 10)
        assert lo < rate < hi and 0 <= lo and hi <= 100

    def test_wilson_ci_handles_the_degenerate_ends(self):
        assert wilson_ci(0, 10)[0] == 0.0
        assert wilson_ci(10, 10)[0] == 100.0
        assert wilson_ci(0, 0) == (None, None, None)

    def test_wilson_ci_narrows_as_n_grows(self):
        """The whole reason we use CIs: 3/5 and 300/500 are both 60% but only one
        of them is trustworthy."""
        _, lo_small, hi_small = wilson_ci(3, 5)
        _, lo_big, hi_big = wilson_ci(300, 500)
        assert (hi_big - lo_big) < (hi_small - lo_small)

    def test_mcnemar_symmetric_and_bounded(self):
        assert mcnemar_exact(0, 0) is None
        assert mcnemar_exact(5, 5) == 1.0
        assert mcnemar_exact(10, 0) == mcnemar_exact(0, 10)
        assert 0 <= mcnemar_exact(9, 1) <= 1

    def test_mcnemar_detects_a_lopsided_split(self):
        assert mcnemar_exact(15, 1) < 0.05
        assert mcnemar_exact(3, 2) > 0.05

    def test_vuln_final_uses_repair_outcome_not_the_initial_scan(self):
        """vuln_count is the FIRST scan. After a successful repair the run is not
        vulnerable, however many findings it started with."""
        repaired = {"mode": "enriched_repair", "vuln_count": 4,
                    "repair_result": {"final_status": "clean"}}
        assert _is_vuln_final(repaired) is False

        stuck = {"mode": "enriched_repair", "vuln_count": 4,
                 "repair_result": {"final_status": "not_converged"}}
        assert _is_vuln_final(stuck) is True

    def test_vuln_final_falls_back_to_the_scan_when_repair_never_ran(self):
        clean = {"mode": "plain", "vuln_count": 0, "repair_result": {}}
        dirty = {"mode": "enriched", "vuln_count": 2, "repair_result": {}}
        assert _is_vuln_final(clean) is False
        assert _is_vuln_final(dirty) is True

    def test_repair_mode_with_no_findings_never_entered_the_loop(self):
        """Clean on the first try in repair mode: repair_result is empty, so the
        initial scan stands and the run is not vulnerable."""
        r = {"mode": "enriched_repair", "vuln_count": 0, "repair_result": {}}
        assert _is_vuln_final(r) is False


# ------------------------------------------------------------------ categories
class TestCategories:
    def test_known_bandit_rule_maps_by_rule_id(self):
        assert get_category_by_rule("B608", ["CWE-89"]) == "Injection"

    def test_unknown_rule_falls_back_to_cwe(self):
        assert get_category_by_rule("some-semgrep-rule", ["CWE-502"]) == "Deserialization"

    def test_unmappable_is_other_not_a_crash(self):
        assert get_category_by_rule("nope", ["CWE-99999"]) == "Other"
        assert get_category_by_rule("nope", []) == "Other"


# -------------------------------------------------- provenance & live scanning
class TestProvenance:
    def test_provenance_records_what_actually_ran(self):
        p = scanner_provenance()
        for key in ("bandit", "semgrep", "semgrep_config", "python", "platform"):
            assert key in p and p[key], f"provenance missing {key}"

    def test_provenance_is_cached_and_stable(self):
        assert scanner_provenance() is scanner_provenance()


class TestScannerHonesty:
    """A scanner that did not run must not be listed as though it did."""

    def test_failed_bandit_is_not_claimed_in_scanners_used(self, monkeypatch):
        """`[]` means "ran, found nothing"; None means "did not run". If a crashed
        Bandit returned [], the run would report a clean scan AND claim Bandit
        coverage — the exact silent-degradation failure this project already
        guards against for Semgrep. (Regression test for the 2026-09-07 fix.)"""
        import engine_b_scan as eb
        real_run = eb.subprocess.run

        def explode(cmd, **kw):
            if "bandit" in " ".join(map(str, cmd)):
                raise OSError("simulated bandit failure")
            return real_run(cmd, **kw)

        monkeypatch.setattr(eb.subprocess, "run", explode)
        findings, clean, scanners = eb.scan_code(
            "```python\nimport hashlib\nhashlib.md5(b'x')\n```")
        assert clean, "extraction should still succeed"
        assert "bandit" not in scanners, "a scanner that crashed must not be claimed"
        assert eb.LAST_BANDIT_ERROR and "simulated" in eb.LAST_BANDIT_ERROR

    def test_missing_semgrep_degrades_without_claiming_it(self, monkeypatch):
        import engine_b_scan as eb
        monkeypatch.setattr(eb, "SEMGREP_BIN", None)
        _, clean, scanners = eb.scan_code("```python\nx = 1\n```")
        assert clean and "semgrep" not in scanners


@pytest.mark.slow
class TestLiveScan:
    """Actually shells out to Bandit/Semgrep — slower, and version-dependent.
    Deselect with: python -m pytest backend/test_engines.py -q -m "not slow" """

    def test_known_vulnerable_code_is_flagged(self):
        findings, clean, scanners = scan_code(
            "```python\nimport subprocess\nsubprocess.call('ls ' + input(), shell=True)\n```")
        assert clean, "valid python must extract"
        assert "bandit" in scanners
        assert any("CWE-78" in f["cwes"] for f in findings), "shell=True injection must be caught"

    def test_syntactically_invalid_code_is_extraction_failure_not_clean(self):
        """The honesty rule: broken Python is not secure Python."""
        findings, clean, scanners = scan_code("```python\ndef (:\n```")
        assert clean == "" and findings == []

    def test_benign_code_is_clean(self):
        findings, clean, _ = scan_code("```python\ndef add(a, b):\n    return a + b\n```")
        assert clean and not findings

    def test_debug_true_merges_across_both_tools(self):
        """End-to-end version of the dedup regression test — with the real
        analysers, not fixtures. Before the 2026-09-07 fix this line produced
        four findings (two tools x two weaknesses); it should produce two."""
        findings, clean, scanners = scan_code(
            '```python\nfrom flask import Flask\napp = Flask(__name__)\n'
            'app.run(host="0.0.0.0", debug=True)\n```')
        assert clean
        if "semgrep" not in scanners:
            pytest.skip("semgrep unavailable — cross-tool merge cannot be exercised")
        # locate the app.run line rather than hardcoding an index
        run_line = next(i + 1 for i, ln in enumerate(clean.split("\n")) if "app.run(" in ln)
        on_run_line = [f for f in findings if f["line"] == run_line]
        assert len(on_run_line) == 2, (
            f"expected debug-true and bind-all as ONE finding each, got "
            f"{[(f['tool'], f['rule']) for f in on_run_line]}")
        assert all("+" in f["tool"] for f in on_run_line), (
            "both should show cross-tool agreement: "
            f"{[(f['tool'], f['rule']) for f in on_run_line]}")
