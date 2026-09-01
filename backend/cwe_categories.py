# CWE / rule -> category mapping, v3 (extends v2 for the S-prompt CWEs)

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
    if rule_id in BANDIT_MAPPINGS:
        return BANDIT_MAPPINGS[rule_id]
    for cwe in cwes:
        if cwe in CWE_CATEGORY_MAP:
            return CWE_CATEGORY_MAP[cwe]
    return "Other"
