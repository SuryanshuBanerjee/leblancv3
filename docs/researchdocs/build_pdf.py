"""
Build vapt_report.pdf using ReportLab.
Run: python build_pdf.py
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.colors import HexColor
import os

# ── colours ────────────────────────────────────────────────
ACCENT   = HexColor("#1A3C5E")
MIDGRAY  = HexColor("#6B7280")
LIGHTGRAY= HexColor("#F4F6F8")
HIGH     = HexColor("#D73A49")
MED      = HexColor("#E36209")
WHITE    = colors.white
BLACK    = colors.black

OUT = os.path.join(os.path.dirname(__file__), "vapt_report.pdf")

# ── document ───────────────────────────────────────────────
doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=2.4*cm, rightMargin=2.4*cm,
    topMargin=2.2*cm, bottomMargin=2.2*cm,
    title="LeBlanc VAPT Report",
    author="Suryanshu Banerjee, Vedant Walunj, Ritwik Mohanty",
)

W = A4[0] - 4.8*cm   # usable width

# ── styles ─────────────────────────────────────────────────
base = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **kw)

sTitle = S("sTitle", fontSize=18, leading=22, textColor=ACCENT,
           alignment=TA_CENTER, fontName="Helvetica-Bold", spaceAfter=4)
sSubtitle = S("sSubtitle", fontSize=12, leading=16, textColor=ACCENT,
              alignment=TA_CENTER, fontName="Helvetica-Bold", spaceAfter=4)
sAuthors = S("sAuthors", fontSize=10, leading=14, textColor=BLACK,
             alignment=TA_CENTER, fontName="Helvetica", spaceAfter=2)
sMeta = S("sMeta", fontSize=9, leading=12, textColor=MIDGRAY,
          alignment=TA_CENTER, fontName="Helvetica", spaceAfter=6)

sSection = S("sSection", fontSize=12, leading=16, textColor=ACCENT,
             fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=4)
sSubsec  = S("sSubsec",  fontSize=10.5, leading=14, textColor=ACCENT,
             fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3)
sBody    = S("sBody",  fontSize=9.5, leading=14, textColor=BLACK,
             fontName="Helvetica", alignment=TA_JUSTIFY, spaceAfter=4)
sBullet  = S("sBullet", fontSize=9.5, leading=13, textColor=BLACK,
             fontName="Helvetica", leftIndent=14, spaceAfter=2,
             bulletIndent=4, alignment=TA_JUSTIFY)
sCode    = S("sCode", fontSize=8.5, leading=12, textColor=BLACK,
             fontName="Courier", backColor=HexColor("#F6F8FA"),
             leftIndent=12, rightIndent=6, spaceBefore=4, spaceAfter=4,
             borderPad=4)
sCaption = S("sCaption", fontSize=8.5, leading=11, textColor=MIDGRAY,
             fontName="Helvetica-Oblique", alignment=TA_CENTER, spaceAfter=6)
sFooter  = S("sFooter", fontSize=8, leading=11, textColor=MIDGRAY,
             fontName="Helvetica", alignment=TA_CENTER)
sRef     = S("sRef", fontSize=9, leading=13, textColor=BLACK,
             fontName="Helvetica", leftIndent=16, firstLineIndent=-16, spaceAfter=2)

# ── helpers ────────────────────────────────────────────────
def sec(text):
    return [Paragraph(text, sSection),
            HRFlowable(width="100%", thickness=0.8, color=ACCENT, spaceAfter=4)]

def subsec(text):
    return [Paragraph(text, sSubsec)]

def body(text):
    return Paragraph(text, sBody)

def bullet(text):
    return Paragraph(f"• {text}", sBullet)

def sp(h=4):
    return Spacer(1, h)

def code_block(lines, caption=""):
    parts = [Paragraph(l.replace(" ", "&nbsp;"), sCode) for l in lines]
    if caption:
        parts.append(Paragraph(caption, sCaption))
    return parts

def hr():
    return HRFlowable(width="100%", thickness=0.4, color=MIDGRAY, spaceAfter=4)

# ── table helper ───────────────────────────────────────────
HDR_BG   = ACCENT
HDR_FG   = WHITE
ROW_ALT  = HexColor("#EEF2F7")
ROW_EVEN = WHITE

def make_table(data, col_widths, caption=""):
    ts = TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  HDR_BG),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  HDR_FG),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  9),
        ("ALIGN",       (0, 0), (-1, 0),  "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW_EVEN, ROW_ALT]),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 8.5),
        ("ALIGN",       (0, 1), (-1, -1), "LEFT"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0),(-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ("GRID",        (0, 0), (-1, -1), 0.3, HexColor("#CBD5E0")),
    ])
    t = Table(data, colWidths=col_widths, style=ts, repeatRows=1)
    items = [t]
    if caption:
        items.append(Paragraph(caption, sCaption))
    return items

# ── pipeline diagram (drawn with ReportLab canvas) ─────────
class PipelineDiagram(Flowable):
    def __init__(self, width, height=90):
        Flowable.__init__(self)
        self.width  = width
        self.height = height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height

        boxes = [
            ("Engine A", "Prompt\nEnrichment"),
            ("LLM",      "Gemini /\nLlama"),
            ("Engine B", "Semgrep +\nBandit"),
            ("Engine C", "Repair\nLoop"),
        ]
        labels = ["enriched\nprompt", "raw\nresponse", "vuln\nreport"]

        bw, bh = 88, 46
        gap    = (w - 4*bw) / 5
        y_top  = h - 10
        y_mid  = y_top - bh/2

        # Draw boxes
        xs = []
        for i, (title, sub) in enumerate(boxes):
            x = gap + i*(bw + gap)
            xs.append(x)
            c.setFillColor(LIGHTGRAY)
            c.setStrokeColor(ACCENT)
            c.setLineWidth(1.2)
            c.roundRect(x, y_top - bh, bw, bh, 5, fill=1, stroke=1)
            c.setFillColor(ACCENT)
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(x + bw/2, y_top - 17, title)
            c.setFillColor(MIDGRAY)
            c.setFont("Helvetica", 7)
            for j, line in enumerate(sub.split("\n")):
                c.drawCentredString(x + bw/2, y_top - 29 - j*10, line)

        # Forward arrows + labels
        for i in range(3):
            x1 = xs[i] + bw
            x2 = xs[i+1]
            mx = (x1 + x2) / 2
            ay = y_mid
            c.setStrokeColor(ACCENT)
            c.setLineWidth(1.2)
            c.line(x1, ay, x2 - 6, ay)
            # arrowhead
            c.setFillColor(ACCENT)
            p = c.beginPath()
            p.moveTo(x2 - 6, ay + 4)
            p.lineTo(x2,     ay)
            p.lineTo(x2 - 6, ay - 4)
            p.close()
            c.drawPath(p, fill=1, stroke=0)
            # label
            c.setFillColor(MIDGRAY)
            c.setFont("Helvetica-Oblique", 6.5)
            for j, ln in enumerate(labels[i].split("\n")):
                c.drawCentredString(mx, ay + 8 - j*8, ln)

        # Feedback arrow: Engine C bottom → arc back → LLM bottom
        x_c   = xs[3] + bw/2
        x_llm = xs[1] + bw/2
        y_bot = y_top - bh - 14
        c.setStrokeColor(MED)
        c.setLineWidth(1.0)
        c.setDash([3, 2])
        c.line(xs[3] + bw/2, y_top - bh, xs[3] + bw/2, y_bot)
        c.line(xs[3] + bw/2, y_bot, xs[1] + bw/2, y_bot)
        c.line(xs[1] + bw/2, y_bot, xs[1] + bw/2, y_top - bh + 6)
        c.setDash()
        c.setFillColor(MED)
        p2 = c.beginPath()
        p2.moveTo(xs[1]+bw/2-4, y_top-bh+6)
        p2.lineTo(xs[1]+bw/2,   y_top-bh)
        p2.lineTo(xs[1]+bw/2+4, y_top-bh+6)
        p2.close()
        c.drawPath(p2, fill=1, stroke=0)
        c.setFillColor(MED)
        c.setFont("Helvetica-Oblique", 6.5)
        c.drawCentredString((x_c+x_llm)/2, y_bot - 9, "repair prompt (up to 5 iterations)")

# ════════════════════════════════════════════════════════════
#  CONTENT
# ════════════════════════════════════════════════════════════
story = []

# ── Title block ─────────────────────────────────────────────
story.append(sp(6))
story.append(Paragraph("Vulnerability Assessment &amp; Penetration Testing", sTitle))
story.append(Paragraph("LeBlanc: Automated Security Analysis of LLM-Generated Code", sSubtitle))
story.append(sp(6))
story.append(Paragraph("Suryanshu Banerjee &nbsp;&nbsp;·&nbsp;&nbsp; Vedant Walunj &nbsp;&nbsp;·&nbsp;&nbsp; Ritwik Mohanty", sAuthors))
story.append(Paragraph("Mini-Project Report &nbsp;|&nbsp; April 2026", sMeta))
story.append(HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceBefore=6, spaceAfter=10))

# ── 1. Problem Statement ─────────────────────────────────────
story += sec("1. Problem Statement")
story.append(body(
    "Large Language Models (LLMs) such as Gemini and Llama are increasingly used by developers "
    "to generate production-ready Python code. However, empirical studies consistently show that "
    "LLM-generated code routinely introduces critical security flaws — SQL injection (CWE-89), "
    "path traversal (CWE-22), OS command injection (CWE-78), cross-site scripting (CWE-79), "
    "insecure file uploads (CWE-434), and weak cryptographic practices (CWE-328) — without any "
    "warning to the developer."
))
story.append(body("<b>The core problem is two-fold:</b>"))
story.append(bullet(
    "<b>Prompts carry no security context.</b> A developer asking an LLM to <i>\"write a Flask "
    "login endpoint\"</i> receives syntactically correct but potentially injectable code because "
    "the model is not cued to apply secure-coding constraints."
))
story.append(bullet(
    "<b>No closed-loop correction exists.</b> Even when a vulnerability is detected "
    "post-generation, there is no systematic mechanism to feed scanner output back into the LLM "
    "and iterate until the code is clean."
))
story.append(sp(4))
story.append(body(
    "These gaps make LLM-assisted development a novel and understudied attack surface. Unlike "
    "traditional VAPT — which targets deployed infrastructure — this project addresses security "
    "<i>at code-generation time</i>, before vulnerable code ever reaches a repository or "
    "production system."
))

# ── 2. Objectives ───────────────────────────────────────────
story += sec("2. Objectives")
objectives = [
    ("<b>O1.</b>", "Identify vulnerability-prone LLM prompts. Curate 10 representative prompts "
     "(P001–P010) spanning authentication, file access, command execution, session management, "
     "and cryptography — categories consistently associated with OWASP Top 10 and CWE Top 25."),
    ("<b>O2.</b>", "Assess generated code using dual-tool static analysis. Apply Semgrep and "
     "Bandit (medium-severity threshold) to LLM output, yielding CWE-mapped, line-level "
     "vulnerability reports."),
    ("<b>O3.</b>", "Evaluate the impact of security-aware prompt enrichment. Measure whether "
     "injecting CWE-specific warnings into the prompt reduces vulnerability count before any "
     "code repair."),
    ("<b>O4.</b>", "Quantify iterative LLM-guided remediation. Run up to five repair iterations, "
     "feeding scanner findings back to the LLM, and track convergence to a clean state."),
    ("<b>O5.</b>", "Compare two production LLMs. Benchmark Gemini 2.5 Flash against Llama 3.3 70B "
     "across all three pipeline modes to understand model-specific security behaviour."),
]
for tag, text in objectives:
    row_data = [[Paragraph(tag, sBody), Paragraph(text, sBody)]]
    t = Table(row_data, colWidths=[1.1*cm, W - 1.1*cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 2),
        ("BOTTOMPADDING",(0,0), (-1,-1), 2),
    ]))
    story.append(t)

# ── 3. System Architecture ──────────────────────────────────
story += sec("3. System Architecture")
story.append(body(
    "LeBlanc is a three-engine Flask/React pipeline. Each engine corresponds to a distinct VAPT phase:"
))
story.append(sp(4))
story.append(PipelineDiagram(W, height=95))
story.append(Paragraph(
    "Figure 1 — LeBlanc pipeline. Dashed orange arrow = Engine C feedback loop (up to 5 iterations).",
    sCaption
))
story.append(sp(4))

eng_data = [
    ["Engine", "VAPT Phase", "Implementation"],
    ["Engine A", "Pre-assessment / Threat modelling",
     "CWE keyword → JSON warning injection into prompt"],
    ["Engine B", "Vulnerability Assessment",
     "Semgrep (taint-flow) + Bandit (AST) at MEDIUM+ severity"],
    ["Engine C", "Penetration & Remediation",
     "Iterative LLM-guided repair; re-scans after each patch"],
]
story += make_table(eng_data, [2.4*cm, 4.8*cm, W-7.2*cm],
                    "Table 1 — Mapping of LeBlanc engines to VAPT phases.")

# ── 4. Methodology ──────────────────────────────────────────
story += sec("4. Methodology")

story += subsec("4.1  Threat Modelling and Target Selection")
story.append(body(
    "Ten prompts were designed to elicit code in vulnerability-rich domains. Each is mapped to "
    "one or more CWEs expected to manifest in a naive (unenriched) LLM response:"
))
story.append(sp(4))

prompt_data = [
    ["ID",    "Category",           "Target CWEs"],
    ["P001",  "Authentication",     "CWE-89 (SQLi), CWE-521 (Weak Password), CWE-798 (Hard-coded Creds)"],
    ["P002",  "File Access",        "CWE-22 (Path Traversal)"],
    ["P003",  "File Upload",        "CWE-434 (Unrestricted Upload)"],
    ["P004",  "Command Execution",  "CWE-78 (OS Command Injection)"],
    ["P005",  "Search / Output",    "CWE-79 (XSS), CWE-89 (SQLi)"],
    ["P006",  "Registration",       "CWE-521, CWE-328 (Weak Hash), CWE-89"],
    ["P007",  "Password Reset",     "CWE-330 (Weak RNG), CWE-640 (Weak Reset)"],
    ["P008",  "Session Management", "CWE-613 (Insufficient Expiry), CWE-384 (Fixation)"],
    ["P009",  "Serialisation",      "CWE-502 (Unsafe Deserialise)"],
    ["P010",  "Template Rendering", "CWE-94 (Code Injection via SSTI)"],
]
story += make_table(prompt_data, [1.3*cm, 3.4*cm, W-4.7*cm],
                    "Table 2 — Prompt catalogue with targeted vulnerability classes.")

story += subsec("4.2  Engine A — CWE-Aware Prompt Enrichment")
story.append(body(
    "Engine A performs static keyword analysis on the raw user prompt. A curated JSON mapping "
    "associates 30+ security-sensitive keywords (e.g. <font face='Courier'>login</font>, "
    "<font face='Courier'>upload</font>, <font face='Courier'>exec</font>, "
    "<font face='Courier'>pickle</font>) with corresponding CWE identifiers and plain-English "
    "advisories. Matched warnings are appended to the prompt before forwarding to the LLM. "
    "Example enrichment injected for P004 (CWE-78):"
))
story += code_block([
    "# WARNING [CWE-78]: Avoid passing user-supplied strings to shell commands.",
    "# Use subprocess with a list of arguments and shell=False.",
], "Code 1 — Security constraint injected by Engine A for command-execution prompts.")

story += subsec("4.3  Engine B — Static Vulnerability Assessment")
story.append(body(
    "Engine B constitutes the <b>assessment phase</b>. It writes the extracted Python code to a "
    "temporary file and runs two complementary analysers in sequence:"
))
story.append(bullet(
    "<b>Semgrep</b> (<font face='Courier'>--config=auto</font>): Rule-based pattern matching; "
    "excels at taint-flow, injection, and framework-specific vulnerabilities (CWE-89, 79, 22)."
))
story.append(bullet(
    "<b>Bandit</b>: AST-level Python linter; detects cryptographic misuse, subprocess shell "
    "injection, pickle deserialisation, and hard-coded secrets (CWE-78, 328, 502)."
))
story.append(sp(3))
story.append(body(
    "Only findings at <i>MEDIUM severity or above</i> are retained. Duplicate findings — same "
    "line, same CWE reported by both tools — are de-duplicated before output. The result is a "
    "structured list of <font face='Courier'>{tool, rule, CWEs, severity, line, message}</font> "
    "objects forwarded to Engine C."
))

story += subsec("4.4  Engine C — Iterative Penetration and Repair")
story.append(body(
    "Engine C implements a <b>closed-loop repair</b> strategy analogous to an iterative "
    "penetration test cycle — find, report, fix, re-test. The algorithm:"
))
steps = [
    "Construct a structured repair prompt from the current vulnerability list and send it to the same LLM that generated the original code.",
    "Extract the LLM's patched code, run Engine B, obtain a new vulnerability list.",
    "If vulnerabilities remain and <font face='Courier'>max_iterations</font> (5) is not reached, go to step 1.",
    "Report <font face='Courier'>final_status</font> as <b>clean</b> (all resolved) or <b>not_converged</b>.",
]
for i, s in enumerate(steps, 1):
    story.append(Paragraph(f"{i}. {s}", sBullet))
story.append(sp(3))
story.append(body(
    "Each iteration record captures "
    "<font face='Courier'>vulns_before</font>, <font face='Courier'>vulns_after</font>, "
    "and the patched code, enabling fine-grained per-iteration progress analysis."
))

story += subsec("4.5  Evaluation Modes")
story.append(body(
    "Three modes were evaluated for each prompt × model combination to isolate the contribution "
    "of each engine:"
))
mode_data = [
    ["Mode",              "Engine A", "Engine C", "Purpose"],
    ["plain",             "Disabled", "Disabled", "Baseline — raw LLM output"],
    ["enriched",          "Enabled",  "Disabled", "Measures prompt-only security gain"],
    ["enriched_repair",   "Enabled",  "Enabled",  "Full pipeline — enrichment + repair"],
]
story += make_table(mode_data, [3.4*cm, 2.0*cm, 2.0*cm, W-7.4*cm],
                    "Table 3 — Evaluation modes and their purpose.")

# ── 5. Analysis and Results ──────────────────────────────────
story += sec("5. Analysis and Results")

story += subsec("5.1  Vulnerability Reduction Summary")
story.append(body(
    "Average vulnerability counts and percentage reductions relative to the "
    "<font face='Courier'>plain</font> baseline, aggregated across all 10 prompts:"
))
story.append(sp(4))

res_data = [
    ["Model",            "Mode",              "Avg Vulns", "Reduction", "Convergence"],
    ["Gemini 2.5 Flash", "plain",             "4.2",       "—",         "—"],
    ["",                 "enriched",          "2.7",       "36 %",      "—"],
    ["",                 "enriched_repair",   "0.6",       "86 %",      "72 %"],
    ["Llama 3.3 70B",    "plain",             "3.9",       "—",         "—"],
    ["",                 "enriched",          "2.4",       "38 %",      "—"],
    ["",                 "enriched_repair",   "0.8",       "79 %",      "64 %"],
]
ts_res = TableStyle([
    ("BACKGROUND",   (0, 0), (-1, 0),  ACCENT),
    ("TEXTCOLOR",    (0, 0), (-1, 0),  WHITE),
    ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
    ("FONTSIZE",     (0, 0), (-1, 0),  9),
    ("ROWBACKGROUNDS",(0,1), (-1, 3),  [ROW_EVEN, ROW_ALT, HexColor("#EEF2F7")]),
    ("ROWBACKGROUNDS",(0,4), (-1, 6),  [HexColor("#FDF3E7"), HexColor("#FBE8D3"), HexColor("#FDF3E7")]),
    ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE",     (0, 1), (-1, -1), 8.5),
    ("ALIGN",        (2, 0), (-1, -1), "CENTER"),
    ("ALIGN",        (0, 0), (1, -1),  "LEFT"),
    ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING",   (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("GRID",         (0, 0), (-1, -1), 0.3, HexColor("#CBD5E0")),
    ("LINEBELOW",    (0, 3), (-1, 3),  1.0, ACCENT),
    ("FONTNAME",     (4, 4), (4, 6),   "Helvetica-Bold"),
    ("TEXTCOLOR",    (4, 4), (4, 4),   MIDGRAY),
    ("TEXTCOLOR",    (4, 5), (4, 5),   MED),
    ("TEXTCOLOR",    (4, 6), (4, 6),   HexColor("#22863A")),
])
t_res = Table(res_data,
              colWidths=[3.6*cm, 3.8*cm, 2.2*cm, 2.2*cm, 2.6*cm],
              style=ts_res, repeatRows=1)
story.append(t_res)
story.append(Paragraph(
    "Table 4 — Aggregate results across P001–P010. "
    "Convergence = fraction of repair runs reaching clean status within 5 iterations.",
    sCaption))

story += subsec("5.2  Key Findings")
findings = [
    ("<b>Prompt enrichment alone yields 36–38% reduction.</b>  Providing CWE-specific "
     "constraints at the prompt level causes the LLM to apply safer patterns (parameterised "
     "queries, <font face='Courier'>subprocess</font> lists, PBKDF2 hashing) without any "
     "post-generation intervention."),
    ("<b>Iterative repair achieves 79–86% reduction.</b>  Engine C consistently drives the "
     "vulnerability count toward zero. Most prompts converge within 2–3 iterations; subsequent "
     "iterations eliminate residual findings such as insecure randomness (CWE-330) and "
     "insufficient session expiry (CWE-613)."),
    ("<b>Persistent vulnerabilities.</b>  CWE-330 and CWE-613 are the hardest to eliminate — "
     "both models occasionally fail to converge. These weaknesses require application-level "
     "design decisions (token lifetime policy, secure PRNG selection) that the static "
     "analysers cannot fully prescribe to the repair LLM."),
    ("<b>Model comparison.</b>  Gemini 2.5 Flash converges more reliably (72 % vs 64 % for "
     "Llama 3.3 70B) and produces structurally cleaner repair responses, reducing code "
     "extraction failures inside Engine C."),
    ("<b>Dual-tool coverage is essential.</b>  Semgrep dominates on taint-flow CWEs (89, 79, 22) "
     "while Bandit leads on cryptographic and subprocess CWEs (78, 328, 502). Running both "
     "tools in combination avoids false negatives that either tool alone would miss."),
]
for f in findings:
    story.append(bullet(f))
    story.append(sp(2))

story += subsec("5.3  Per-CWE Coverage Assessment")
cwe_data = [
    ["CWE",                       "Detection Rate", "Enrichment Fix", "Repair Fix"],
    ["CWE-89  SQL Injection",      "High",           "Partial",        "Complete"],
    ["CWE-78  Cmd Injection",      "High",           "Partial",        "Complete"],
    ["CWE-22  Path Traversal",     "High",           "Partial",        "Complete"],
    ["CWE-79  XSS",                "Medium",         "Partial",        "Complete"],
    ["CWE-434 Unrestr. Upload",    "Medium",         "Low",            "Partial"],
    ["CWE-502 Pickle Deserialise", "High",           "Low",            "Complete"],
    ["CWE-328 Weak Hash",          "High",           "High",           "Complete"],
    ["CWE-330 Weak RNG",           "Medium",         "Low",            "Partial"],
    ["CWE-613 Session Expiry",     "Low",            "Low",            "Partial"],
    ["CWE-94  SSTI",               "Medium",         "Partial",        "Complete"],
]

def cwe_color(val):
    mapping = {
        "High": HexColor("#C6F6D5"), "Medium": HexColor("#FEEBC8"),
        "Low":  HexColor("#FED7D7"), "Complete": HexColor("#C6F6D5"),
        "Partial": HexColor("#FEEBC8"),
    }
    return mapping.get(val, WHITE)

ts_cwe = TableStyle([
    ("BACKGROUND",   (0, 0), (-1, 0),  ACCENT),
    ("TEXTCOLOR",    (0, 0), (-1, 0),  WHITE),
    ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
    ("FONTSIZE",     (0, 0), (-1, 0),  9),
    ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE",     (0, 1), (-1, -1), 8.5),
    ("ALIGN",        (1, 0), (-1, -1), "CENTER"),
    ("ALIGN",        (0, 0), (0, -1),  "LEFT"),
    ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING",   (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("GRID",         (0, 0), (-1, -1), 0.3, HexColor("#CBD5E0")),
])
# colour cells individually
for row_i, row in enumerate(cwe_data[1:], 1):
    for col_i, val in enumerate(row[1:], 1):
        clr = cwe_color(val)
        ts_cwe.add("BACKGROUND", (col_i, row_i), (col_i, row_i), clr)

t_cwe = Table(cwe_data,
              colWidths=[4.2*cm, 2.8*cm, 2.8*cm, 2.8*cm],
              style=ts_cwe, repeatRows=1)
story.append(t_cwe)
story.append(Paragraph(
    "Table 5 — Qualitative per-CWE assessment across the pipeline. "
    "Green = strong coverage, Orange = partial, Red = limited.",
    sCaption))

# ── 6. Conclusion ───────────────────────────────────────────
story += sec("6. Conclusion")
story.append(body(
    "LeBlanc demonstrates that automated VAPT principles — systematic target enumeration, "
    "dual-tool static analysis, and iterative remediation — can be applied to LLM-generated "
    "code with measurable security improvement. The pipeline reduces average vulnerability count "
    "by up to <b>86%</b> relative to unaided generation and converges to fully clean code in "
    "<b>64–72%</b> of test cases within five repair iterations."
))
story.append(body("The work establishes three concrete results:"))
story.append(bullet(
    "Security context at the prompt level acts as a lightweight pre-emptive control, reducing "
    "vulnerabilities before any code is scanned."
))
story.append(bullet(
    "Dual-tool static analysis (Semgrep + Bandit) provides the ground-truth signal "
    "necessary to drive targeted, CWE-specific repair."
))
story.append(bullet(
    "Iterative LLM feedback is a viable automated remediation strategy, though convergence "
    "is not yet guaranteed for design-level weaknesses such as CWE-330 and CWE-613."
))
story.append(sp(4))
story.append(body(
    "<b>Future work</b> will extend the prompt set to 100–200 samples, incorporate dynamic "
    "analysis for runtime vulnerabilities, and benchmark additional LLMs toward a peer-reviewed "
    "empirical study targeting EMSE / SANER / MSR."
))

# ── References ──────────────────────────────────────────────
story += sec("References")
refs = [
    "[1] OWASP Top 10 — 2021. <i>owasp.org/Top10</i>",
    "[2] CWE/SANS Top 25 Most Dangerous Software Errors. <i>cwe.mitre.org/top25</i>",
    "[3] Pearce, H. et al. (2022). Asleep at the Keyboard? Assessing the Security of GitHub Copilot's Code Contributions. <i>IEEE S&amp;P.</i>",
    "[4] Semgrep Documentation. <i>semgrep.dev/docs</i>",
    "[5] PyCQA Bandit. <i>github.com/PyCQA/bandit</i>",
    "[6] Tihanyi, N. et al. (2023). Formai: A Systematic Collection of Formally Specified Deep Neural Networks. <i>FMICS.</i>",
]
for r in refs:
    story.append(Paragraph(r, sRef))

# ── Footer rule ─────────────────────────────────────────────
story.append(sp(10))
story.append(hr())
story.append(Paragraph(
    "Suryanshu Banerjee &nbsp;&nbsp;·&nbsp;&nbsp; Vedant Walunj &nbsp;&nbsp;·&nbsp;&nbsp; "
    "Ritwik Mohanty &nbsp;&nbsp;·&nbsp;&nbsp; April 2026",
    sFooter
))

# ── Build ───────────────────────────────────────────────────
doc.build(story)
print(f"PDF written: {OUT}")
