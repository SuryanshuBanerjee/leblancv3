# LeBlanc UX Audit

An analysis of the user experience gaps present in the LeBlanc dashboard, directly answering the Professor's requirement to perform a critical audit of the frontend interface before paper submission.

## Main Dashboard (`index.html`)

| Severity | Issue Description | Proposed Fix |
|:---:|---|---|
| HIGH | Empty state provides no feedback | User is presented with a blank table block if they haven't run a prompt. Need a clear empty-state prompting selection. |
| HIGH | Invisible Extraction Failures | The previous iteration would return a `vuln_count: 0` if `py_compile` crashed on invalid Python, falsely reporting success. Must display a prominent "Extraction Failed" warning badge to not skew metrics. |
| MED | Hardcoded LLM Columns | Currently the frontend exclusively expects `gemini` and `groq` data structures. Requires dynamic iteration so any list of models returned from the backend is rendered properly. |
| MED | Lack of CWE Tooltips | "CWE-89" has no context for non-security users. Hover states should include a 1-line description of the vulnerability. |

## Metrics View (`metrics.html`)

| Severity | Issue Description | Proposed Fix |
|:---:|---|---|
| HIGH | Static model coloring | Colors in `metrics.html` are strictly bound to 'Gemini' and 'Groq'. Needs dynamic color assignment to support our RQ5 generational gap comparison (e.g. comparing Llama-3-8b, GPT-3.5, and GPT-4o). |
| MED | Disconnected history | Clicking on a specific bar in the charts does not navigate the user to the underlying data. Click events on the charts should route to the history table pre-filtered. |

## History List (`history.html`)

| Severity | Issue Description | Proposed Fix |
|:---:|---|---|
| MED | Missing Visual Timelines | Repair iterations are dumped heavily. Turn the iterations into structural timelines showing `Iteration N: X vulns -> Y vulns` with red/green arrows. |
| LOW | Category Tags missing visual weight | Tags like "Injection" are plain text. Use SWADHA's color category map (Injection = #E53935) to colorize the tags. |
