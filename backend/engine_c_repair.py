"""
Engine C v3 — iterative scanner-guided repair loop.
Ported from v2 (extraction-failure honesty preserved); scan_code now returns scanners too.
"""
from engine_b_scan import scan_code
from llm_client import call_llm

MAX_ITERATIONS = 3


def build_repair_prompt(code, vulnerabilities, security_context=None):
    vuln_lines = []
    for i, v in enumerate(vulnerabilities, 1):
        cwes = ", ".join(v["cwes"]) if v["cwes"] else "unknown"
        vuln_lines.append(f"{i}. [{cwes}] {v['severity']} at line {v['line']}: {v['message']}")

    context_block = ""
    if security_context:
        context_block = f"SECURITY REQUIREMENTS (CWEs relevant to this code): {', '.join(security_context)}\n\n"

    return (
        "The following Python code has security vulnerabilities. "
        "Fix ALL of them while PRESERVING the code's functionality and public interface "
        "(same functions, same routes, same behaviour for valid inputs). "
        "Return ONLY the corrected code in a ```python``` block.\n\n"
        f"{context_block}"
        f"VULNERABILITIES FOUND:\n" + "\n".join(vuln_lines) + "\n\n"
        f"CODE TO FIX:\n```python\n{code}\n```\n\n"
        "Return ONLY the fixed Python code. No explanations."
    )


def repair_loop(code, initial_vulns, model_name, max_iterations=MAX_ITERATIONS, security_context=None):
    if not code:
        return {"final_code": "", "final_status": "extraction_failed",
                "iterations": [], "total_iterations": 0}

    iterations = []
    current_code, current_vulns = code, initial_vulns

    for i in range(max_iterations):
        if not current_vulns:
            break

        repair_prompt = build_repair_prompt(current_code, current_vulns, security_context)
        try:
            raw_response = call_llm(repair_prompt, model_name)
        except Exception as e:
            iterations.append({
                "iteration": i + 1, "vulns_before": len(current_vulns),
                "vulns_after": len(current_vulns), "extraction_failed": True,
                "llm_error": str(e)[:300], "code": current_code,
            })
            break

        new_vulns, clean_code, scanners = scan_code(raw_response)
        failed = not clean_code
        iterations.append({
            "iteration": i + 1,
            "vulns_before": len(current_vulns),
            "vulns_after": len(current_vulns) if failed else len(new_vulns),
            "vulnerabilities": new_vulns,
            "scanners": scanners,
            "extraction_failed": failed,
            "code": clean_code or current_code,
        })
        if failed:
            break
        current_code, current_vulns = clean_code, new_vulns

    if iterations and iterations[-1].get("extraction_failed"):
        final_status = "extraction_failed"
    else:
        final_status = "clean" if not current_vulns else "not_converged"

    return {"final_code": current_code, "final_status": final_status,
            "iterations": iterations, "total_iterations": len(iterations)}
