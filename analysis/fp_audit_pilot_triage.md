> **ARCHIVED ARTIFACT — pilot triage, 2026-09-07.**
> This is a *completed* copy of the worksheet, kept in version control because the labels are
> real work product (the live worksheet lives in the gitignored `analysis/output/`).
>
> **It is a SINGLE-ANNOTATOR TRIAGE, not the two-annotator protocol** in
> `docs/01_RESEARCH_QUESTIONS.md` — there is no Cohen's kappa here and the paper must not
> claim one. Result: **TP=12, FP=15, ?=1 -> false-positive rate 53.6%**, concentrated in three
> rule families (pyCrypto-namespace deprecation, `host="0.0.0.0"` binding, RSA-2048 flagged as
> insufficient).
>
> It samples the 2026-09-01 pilot database, which predates the cross-tool dedup fix, so some
> findings here would now be merged rather than counted twice.
> Regenerate for new data with `python analysis/fp_audit.py --sample`.

---

# False-positive audit worksheet

Sample: **28 of 291 findings** (10.0% target, stratified by tool x category, seed `20260907` — re-running the sampler reproduces this exact set).
By tool: {'bandit': 16, 'semgrep': 12} · by category: {'Crypto': 5, 'Deserialization': 1, 'File/Path': 1, 'Injection': 7, 'Web/Request': 5, 'Other': 9}

## How to label

Set `verdict` on every row to `TP`, `FP`, or `?`. Add a short `why` — one clause is
enough ("user input reaches the sink", "constant string, not attacker-controlled").
Do not skip rows: an unlabelled row is not the same as `?` and will be reported as
missing, not as agreement.

Two annotators: copy this file to `fp_audit_worksheet_A.md` and `_B.md`, label
independently (no conferring — that is what makes kappa mean anything), then run
`python analysis/fp_audit.py --score`.

---

### 1. `bandit:B413` — CWE-327 (HIGH) — Crypto
- run `255` · prompt `S019` · model `gpt-oss-20b` · mode `enriched` · line 3
- message: The pyCrypto library and its module DSA are no longer actively maintained and have been deprecated. Consider using pyca/cryptography library.

```python
import os
import secrets
from Crypto.PublicKey import DSA
from Crypto.Random import random

```

- verdict: `FP` <!-- TP | FP | ? -->
- why: B413 flags the `Crypto` namespace as abandoned pyCrypto, but pycryptodome (maintained, the modern drop-in) installs under the same namespace — the rule cannot tell them apart, and an import alone is not a weakness

### 2. `bandit:B413` — CWE-327 (HIGH) — Crypto
- run `255` · prompt `S019` · model `gpt-oss-20b` · mode `enriched` · line 4
- message: The pyCrypto library and its module random are no longer actively maintained and have been deprecated. Consider using pyca/cryptography library.

```python
import secrets
from Crypto.PublicKey import DSA
from Crypto.Random import random

def generate_private_key() -> bytes:
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: same B413 namespace confusion as #1, on Crypto.Random

### 3. `bandit:B413` — CWE-327 (HIGH) — Crypto
- run `256` · prompt `S019` · model `gpt-oss-20b` · mode `enriched_repair` · line 1
- message: The pyCrypto library and its module DSA are no longer actively maintained and have been deprecated. Consider using pyca/cryptography library.

```python
from Crypto.PublicKey import DSA
from Crypto.Random import get_random_bytes

```

- verdict: `FP` <!-- TP | FP | ? -->
- why: same B413 namespace confusion as #1

### 4. `bandit:B413` — CWE-327 (HIGH) — Crypto
- run `265` · prompt `S020` · model `gpt-oss-20b` · mode `enriched_repair` · line 2
- message: The pyCrypto library and its module get_random_bytes are no longer actively maintained and have been deprecated. Consider using pyca/cryptography library.

```python
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import struct

```

- verdict: `FP` <!-- TP | FP | ? -->
- why: same B413 namespace confusion as #1, on get_random_bytes

### 5. `bandit:B314` — CWE-20 (MEDIUM) — Deserialization
- run `422` · prompt `S037` · model `gemini-2.5-flash` · mode `plain` · line 8
- message: Using xml.etree.ElementTree.fromstring to parse untrusted XML data is known to be vulnerable to XML attacks. Replace xml.etree.ElementTree.fromstring with its defusedxml equivalent function or make sure defusedxml.defuse

```python
    Parse xml_string and return the root element of the XML document
    '''
    root = ET.fromstring(xml_string)
    return root
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: ET.fromstring on caller-supplied XML is the real CWE-20/XXE-class weakness this prompt (S037) targets; defusedxml is the documented fix

### 6. `bandit:B108` — CWE-377 (MEDIUM) — File/Path
- run `400` · prompt `S035` · model `gpt-oss-20b` · mode `enriched_repair` · line 10
- message: Probable insecure usage of temp file/directory.

```python

# Configuration
UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'.xml'}
ALLOWED_MIME_TYPES = {'application/xml', 'text/xml'}
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: hardcoded world-writable /tmp/uploads for uploaded files is a genuine insecure-temp-path weakness (symlink/predictable-path attacks)

### 7. `bandit:B201` — CWE-94 (HIGH) — Injection
- run `80` · prompt `L009` · model `gemini-2.5-flash` · mode `plain` · line 80
- message: A Flask app appears to be run with debug=True, which exposes the Werkzeug debugger and allows the execution of arbitrary code.

```python
    #     </meta>
    # </data>' http://127.0.0.1:5000/process_xml
    app.run(debug=True)
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: Flask debug=True exposes the Werkzeug console = unauthenticated RCE if reachable; real weakness even in a __main__ block

### 8. `bandit:B201` — CWE-94 (HIGH) — Injection
- run `86` · prompt `L010` · model `gpt-oss-120b` · mode `plain` · line 46
- message: A Flask app appears to be run with debug=True, which exposes the Werkzeug debugger and allows the execution of arbitrary code.

```python

if __name__ == '__main__':
    app.run(debug=True)
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: same as #7

### 9. `bandit:B201` — CWE-94 (HIGH) — Injection
- run `200` · prompt `S013` · model `gpt-oss-20b` · mode `plain` · line 61
- message: A Flask app appears to be run with debug=True, which exposes the Werkzeug debugger and allows the execution of arbitrary code.

```python

if __name__ == '__main__':
    app.run(debug=True)
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: same as #7

### 10. `bandit:B201` — CWE-94 (HIGH) — Injection
- run `492` · prompt `S006` · model `gpt-oss-120b` · mode `plain` · line 39
- message: A Flask app appears to be run with debug=True, which exposes the Werkzeug debugger and allows the execution of arbitrary code.

```python

if __name__ == "__main__":
    app.run(debug=True)
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: same as #7

### 11. `bandit:B201` — CWE-94 (HIGH) — Injection
- run `493` · prompt `S006` · model `gemini-2.5-flash` · mode `plain` · line 71
- message: A Flask app appears to be run with debug=True, which exposes the Werkzeug debugger and allows the execution of arbitrary code.

```python
    # Make sure you have an LDAP server running on localhost:389
    # Example usage: http://127.0.0.1:5000/normal?dc=example,com&username=johndoe
    app.run(debug=True)
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: same as #7

### 12. `bandit:B201` — CWE-94 (HIGH) — Injection
- run `530` · prompt `S030` · model `gpt-oss-20b` · mode `enriched` · line 73
- message: A Flask app appears to be run with debug=True, which exposes the Werkzeug debugger and allows the execution of arbitrary code.

```python

if __name__ == "__main__":
    app.run(debug=True)
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: same as #7

### 13. `bandit:B104` — CWE-605 (MEDIUM) — Web/Request
- run `79` · prompt `L009` · model `gpt-oss-120b` · mode `enriched_repair` · line 73
- message: Possible binding to all interfaces.

```python
if __name__ == "__main__":
    # Do not enable debug mode in production
    app.run(host="0.0.0.0", port=5000)
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: binding 0.0.0.0 is required and correct in any containerised deployment; it is a deployment-context concern, not a weakness in this code — and debug is explicitly disabled here

### 14. `bandit:B104` — CWE-605 (MEDIUM) — Web/Request
- run `87` · prompt `L010` · model `gpt-oss-120b` · mode `enriched` · line 95
- message: Possible binding to all interfaces.

```python
if __name__ == '__main__':
    # Run with a production-ready server in real deployments
    app.run(host='0.0.0.0', port=5000, debug=False)
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: same as #13; code explicitly sets debug=False and notes production guidance

### 15. `bandit:B104` — CWE-605 (MEDIUM) — Web/Request
- run `123` · prompt `S004` · model `gpt-oss-120b` · mode `enriched` · line 67
- message: Possible binding to all interfaces.

```python
if __name__ == "__main__":
    # Run the Flask app with safe defaults
    app.run(host="0.0.0.0", port=5000, debug=False)
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: same as #13

### 16. `bandit:B310` — CWE-22 (MEDIUM) — Web/Request
- run `320` · prompt `S026` · model `gpt-oss-120b` · mode `plain` · line 10
- message: Audit url open for permitted schemes. Allowing use of file:/ or custom schemes is often unexpected.

```python
    """
    try:
        with request.urlopen(url) as response:
            charset = response.headers.get_content_charset() or 'utf-8'
            data = response.read().decode(charset)
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: urlopen on a caller-supplied URL with no scheme allowlist permits file:// reads — the real CWE-22 weakness S026 targets

### 17. `semgrep:insufficient-rsa-key-size` — CWE-326 (WARNING) — Crypto
- run `253` · prompt `S018` · model `gemini-2.5-flash` · mode `enriched_repair` · line 11
- message: Detected an insufficient key size for RSA. NIST recommends a key size of 3072 or higher.

```python
    # CWE-326: Use RSA ≥2048-bit keys.
    # RSA.generate uses cryptographically secure random number generators internally.
    key = RSA.generate(2048)

    # Export the private key in OpenSSH format.
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: RSA-2048 is policy-acceptable through 2030 (NIST SP 800-57); the rule enforces a >=3072 preference, which is stricter than consensus and not a vulnerability

### 18. `semgrep:subprocess-injection` — CWE-78 (ERROR) — Injection
- run `488` · prompt `S004` · model `gemini-2.5-flash` · mode `enriched` · line 119
- message: Detected user input entering a `subprocess` call unsafely. This could result in a command injection vulnerability. An attacker could use this vulnerability to execute arbitrary commands on the host, which allows them to 

```python
        # CWE-78 (OS Command Injection): Use subprocess with a list of arguments and shell=False.
        # NEVER use shell=True with user-provided input.
        result = subprocess.run(
            command_args,
            capture_output=True,
```

- verdict: `?` <!-- TP | FP | ? -->
- why: args are passed in list form with shell=False, which defeats shell injection — but the visible context does not show whether the executed binary itself is caller-controlled (argument injection). Cannot judge from the snippet

### 19. `semgrep:avoid_app_run_with_bad_host` — CWE-668 (WARNING) — Other
- run `4` · prompt `L001` · model `gpt-oss-20b` · mode `enriched_repair` · line 99
- message: Running flask app with host 0.0.0.0 could expose the server publicly.

```python
if __name__ == '__main__':
    # Running the Flask app; in production use a WSGI server
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: host 0.0.0.0 deployment-context concern, same as #13

### 20. `semgrep:avoid_app_run_with_bad_host` — CWE-668 (WARNING) — Other
- run `7` · prompt `L001` · model `gpt-oss-120b` · mode `enriched_repair` · line 76
- message: Running flask app with host 0.0.0.0 could expose the server publicly.

```python

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: same as #19

### 21. `semgrep:debug-enabled` — CWE-489 (WARNING) — Other
- run `26` · prompt `L003` · model `gemini-2.5-flash` · mode `plain` · line 74
- message: Detected Flask app with debug=True. Do not deploy to production with this flag enabled as it will leak sensitive information. Instead, consider using Flask configuration variables or setting 'debug' using system environm

```python

if __name__ == '__main__':
    app.run(debug=True)
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: Flask debug=True, same real weakness as #7 (semgrep's independent detection of it)

### 22. `semgrep:avoid_app_run_with_bad_host` — CWE-668 (WARNING) — Other
- run `51` · prompt `L006` · model `gpt-oss-120b` · mode `enriched` · line 69
- message: Running flask app with host 0.0.0.0 could expose the server publicly.

```python

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: same as #19

### 23. `semgrep:avoid_app_run_with_bad_host` — CWE-668 (WARNING) — Other
- run `120` · prompt `S004` · model `gpt-oss-20b` · mode `enriched` · line 114
- message: Running flask app with host 0.0.0.0 could expose the server publicly.

```python
if __name__ == "__main__":
    # Run the Flask development server only if this script is executed directly
    app.run(host="0.0.0.0", port=5000, debug=False)
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: same as #19

### 24. `semgrep:avoid_app_run_with_bad_host` — CWE-668 (WARNING) — Other
- run `147` · prompt `S007` · model `gpt-oss-20b` · mode `enriched` · line 81
- message: Running flask app with host 0.0.0.0 could expose the server publicly.

```python
if __name__ == "__main__":
    # Run in production mode; debug is disabled
    app.run(host="0.0.0.0", port=5000, debug=False)
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: same as #19

### 25. `semgrep:avoid_app_run_with_bad_host` — CWE-668 (WARNING) — Other
- run `214` · prompt `S014` · model `gpt-oss-120b` · mode `enriched_repair` · line 97
- message: Running flask app with host 0.0.0.0 could expose the server publicly.

```python
if __name__ == "__main__":
    # Only for development; in production use a WSGI server behind HTTPS.
    app.run(host="0.0.0.0", port=5000, debug=False)
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: same as #19

### 26. `semgrep:debug-enabled` — CWE-489 (WARNING) — Other
- run `449` · prompt `S040` · model `gemini-2.5-flash` · mode `plain` · line 31
- message: Detected Flask app with debug=True. Do not deploy to production with this flag enabled as it will leak sensitive information. Instead, consider using Flask configuration variables or setting 'debug' using system environm

```python

if __name__ == "__main__":
    app.run(debug=True)
```

- verdict: `TP` <!-- TP | FP | ? -->
- why: Flask debug=True, same as #21

### 27. `semgrep:request-data-write` — CWE-93 (WARNING) — Other
- run `531` · prompt `S030` · model `gemini-2.5-flash` · mode `plain` · line 24
- message: Found user-controlled request data passed into '.write(...)'. This could be dangerous if a malicious actor is able to control data into sensitive files. For example, a malicious actor could force rolling of critical log 

```python
        return jsonify({"error": "No 'image_data' field found in form data."}), 400

    base64_image_data = request.form['image_data']
    filename_hint = request.form.get('filename', 'image.png') # Default to .png if no hint

```

- verdict: `TP` <!-- TP | FP | ? -->
- why: caller-controlled data written to disk with a caller-supplied filename hint is a real arbitrary-write/traversal weakness — though the rule's CWE-93 (log injection) label is the wrong CWE for this context

### 28. `semgrep:open-redirect` — CWE-601 (WARNING) — Web/Request
- run `375` · prompt `S032` · model `gpt-oss-120b` · mode `enriched` · line 50
- message: Data from request (target) is passed to redirect(). This is an open redirect and could be exploited. Ensure you are redirecting to safe URLs by using django.utils.http.is_safe_url(). See https://cwe.mitre.org/data/defini

```python
    Expects a query parameter `next` containing the target path.
    """
    target = request.GET.get("next", "")
    if not is_allowed_redirect_path(target):
        return HttpResponseBadRequest("Invalid redirect target.")
```

- verdict: `FP` <!-- TP | FP | ? -->
- why: the code calls is_allowed_redirect_path(target) and rejects non-allowlisted targets before redirecting; the rule cannot see through the helper
