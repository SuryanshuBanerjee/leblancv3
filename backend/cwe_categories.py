"""
CWE / scanner-rule -> six-category mapping.

WHY CATEGORIES EXIST. RQ4 asks which *kinds* of weakness survive full scaffolding.
Answering that per-CWE would give ~40 cells of 1-2 runs each — noise. Grouping into
six families (Injection, Auth, Crypto, File/Path, Deserialization, Web/Request)
gives cells big enough to say something about, and matches how a practitioner
actually thinks about risk.

TWO LOOKUPS, IN ORDER. A finding is categorised by its scanner rule ID first and
by its CWE only as a fallback, because the rule is more specific: Bandit's B301
(pickle) and B303 (md5) both map to "crypto-ish" CWEs, but B301 is a
deserialization problem and B303 is a crypto one. Rule-first gets that right.

NOTE ON PROMPT CATEGORIES. This maps *findings*. The category used for RQ4's rows
is the one attached to the prompt in the dataset, never inferred from generated
text — see metrics._rq4. The two are deliberately separate: what a task is about
and what a scanner found in the answer are different questions.
"""

BANDIT_MAPPINGS = {
    # Injection - command & subprocess
    "B602": "Injection", "B603": "Injection", "B604": "Injection", "B605": "Injection",
    "B606": "Injection", "B607": "Injection", "B404": "Injection",
    # Injection - SQL / code
    "B608": "Injection", "B610": "Injection", "B611": "Injection", "B307": "Injection",
    # Auth & secrets
    "B105": "Auth", "B106": "Auth", "B107": "Auth", "B501": "Auth",
    # Crypto
    "B301": "Deserialization", "B302": "Deserialization", "B303": "Crypto", "B304": "Crypto",
    "B305": "Crypto", "B311": "Crypto", "B324": "Crypto", "B505": "Crypto",
    # File/Path
    "B108": "File/Path", "B103": "File/Path", "B104": "Web/Request", "B202": "File/Path",
    # Deserialization & XML
    "B313": "Deserialization", "B314": "Deserialization", "B315": "Deserialization",
    "B316": "Deserialization", "B317": "Deserialization", "B318": "Deserialization",
    "B319": "Deserialization", "B320": "Deserialization", "B506": "Deserialization",
    # Web/Request
    "B310": "Web/Request", "B113": "Web/Request", "B201": "Injection",
}

CWE_CATEGORY_MAP = {
    # Injection
    "CWE-89": "Injection", "CWE-943": "Injection", "CWE-78": "Injection", "CWE-94": "Injection",
    "CWE-95": "Injection", "CWE-79": "Injection", "CWE-80": "Injection", "CWE-90": "Injection",
    "CWE-113": "Injection", "CWE-117": "Injection", "CWE-643": "Injection", "CWE-77": "Injection",
    # Auth
    "CWE-521": "Auth", "CWE-798": "Auth", "CWE-287": "Auth", "CWE-384": "Auth",
    "CWE-285": "Auth", "CWE-614": "Auth", "CWE-259": "Auth", "CWE-306": "Auth",
    "CWE-321": "Auth", "CWE-522": "Auth", "CWE-295": "Auth", "CWE-347": "Auth",
    # Crypto
    "CWE-328": "Crypto", "CWE-338": "Crypto", "CWE-326": "Crypto", "CWE-327": "Crypto",
    "CWE-329": "Crypto", "CWE-330": "Crypto", "CWE-331": "Crypto", "CWE-339": "Crypto",
    "CWE-759": "Crypto", "CWE-760": "Crypto", "CWE-1204": "Crypto", "CWE-916": "Crypto",
    # File/Path
    "CWE-434": "File/Path", "CWE-22": "File/Path", "CWE-377": "File/Path",
    "CWE-379": "File/Path", "CWE-732": "File/Path",
    # Deserialization / parsing
    "CWE-502": "Deserialization", "CWE-611": "Deserialization", "CWE-776": "Deserialization",
    "CWE-20": "Deserialization",
    # Web/Request
    "CWE-601": "Web/Request", "CWE-918": "Web/Request", "CWE-400": "Web/Request",
}


def get_category_by_rule(rule_id, cwes):
    """Categorise one finding. Rule ID wins; CWE is the fallback; "Other" is honest.

    Returns one of the six category names, or "Other" when neither the rule nor any
    of its CWEs is mapped. "Other" is a real answer, not a failure — it means the
    analysers found something outside our taxonomy, and lumping it into the nearest
    category would quietly corrupt RQ4's per-category rates.
    """
    if rule_id in BANDIT_MAPPINGS:
        return BANDIT_MAPPINGS[rule_id]
    for cwe in cwes:
        if cwe in CWE_CATEGORY_MAP:
            return CWE_CATEGORY_MAP[cwe]
    return "Other"
