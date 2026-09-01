"""
Engine A v3 — CWE-aware prompt enrichment via hybrid retrieval.

Replaces v2's naive substring lookup with a real retrieval algorithm:
  1. LEXICAL pass  — word-boundary keyword matching against the KB (high precision).
  2. SEMANTIC pass — TF-IDF vector-space cosine similarity between the prompt and
                     each CWE's knowledge-base document (recall for prompts that
                     describe a risky task without using trigger words).
Scores are fused (lexical hits dominate), top-K CWEs above threshold produce warnings.

Deterministic, offline, no LLM, no external services. Cite as
"lexical + TF-IDF vector-space retrieval over a curated CWE corpus".
"""
import json
import math
import os
import re
from collections import Counter

KB_PATH = os.path.join(os.path.dirname(__file__), "cwe_kb.json")

TOP_K = 5              # max CWE warnings injected
SEM_THRESHOLD = 0.12   # min cosine similarity for a semantic-only match
LEX_WEIGHT = 1.0       # a lexical hit guarantees inclusion
SEM_WEIGHT = 0.8

_TOKEN_RE = re.compile(r"[a-z][a-z0-9_.]{1,}")
_STOP = frozenset(
    "the a an and or of to in for with that this from is are be as on by it its "
    "into your you we they their which will can may use using used user write "
    "function return def import class if else not none".split()
)


def _tokenize(text):
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]


class _KnowledgeBase:
    """TF-IDF index over the CWE corpus, built once at import."""

    def __init__(self, path):
        with open(path, "r", encoding="utf-8") as f:
            self.entries = json.load(f)

        # document term frequencies
        self._doc_tfs = []
        df = Counter()
        for e in self.entries:
            tokens = _tokenize(e["doc"] + " " + e["name"] + " " + " ".join(e["keywords"]))
            tf = Counter(tokens)
            self._doc_tfs.append(tf)
            df.update(set(tokens))

        n_docs = len(self.entries)
        self._idf = {t: math.log((1 + n_docs) / (1 + c)) + 1.0 for t, c in df.items()}

        # pre-normalised doc vectors
        self._doc_vecs = []
        for tf in self._doc_tfs:
            vec = {t: (1 + math.log(c)) * self._idf[t] for t, c in tf.items()}
            norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
            self._doc_vecs.append({t: w / norm for t, w in vec.items()})

        # word-boundary regex per entry (multi-word keywords supported)
        self._kw_res = [
            re.compile(r"\b(?:" + "|".join(re.escape(k) for k in e["keywords"]) + r")\b")
            for e in self.entries
        ]

    def query(self, prompt):
        """Return list of (entry, score, matched_keywords) sorted by score desc."""
        p_lower = prompt.lower()
        q_tf = Counter(_tokenize(prompt))
        q_vec = {t: (1 + math.log(c)) * self._idf.get(t, 0.0) for t, c in q_tf.items()}
        q_norm = math.sqrt(sum(w * w for w in q_vec.values())) or 1.0

        results = []
        for entry, doc_vec, kw_re in zip(self.entries, self._doc_vecs, self._kw_res):
            matched_kws = sorted(set(kw_re.findall(p_lower)))
            cosine = sum((w / q_norm) * doc_vec.get(t, 0.0) for t, w in q_vec.items())

            score = 0.0
            if matched_kws:
                # lexical hit: base weight + small bonus per distinct keyword
                score += LEX_WEIGHT + 0.05 * (len(matched_kws) - 1)
            if cosine >= SEM_THRESHOLD or matched_kws:
                score += SEM_WEIGHT * cosine
            if score > 0.0:
                results.append((entry, score, matched_kws, round(cosine, 4)))

        results.sort(key=lambda r: r[1], reverse=True)
        return results


_KB = _KnowledgeBase(KB_PATH)


def enrich_prompt(prompt):
    """
    Returns (enriched_prompt, matched_cwes, matched_keywords, match_details).
    Signature kept compatible with v2 callers; 4th element now carries
    per-CWE retrieval evidence (keyword hits + cosine) for the paper's audit trail.
    """
    hits = _KB.query(prompt)[:TOP_K]
    if not hits:
        return prompt, [], [], []

    warnings, seen = [], set()
    all_cwes, all_keywords, details = [], [], []
    for entry, score, kws, cosine in hits:
        if entry["warning"] not in seen:
            seen.add(entry["warning"])
            warnings.append(f"- {entry['warning']}")
        all_cwes.append(entry["cwe"])
        all_keywords.extend(k for k in kws if k not in all_keywords)
        details.append({
            "cwe": entry["cwe"], "name": entry["name"], "category": entry["category"],
            "score": round(score, 4), "cosine": cosine, "keywords": kws,
        })

    enriched = (
        f"{prompt}\n\n"
        f"IMPORTANT SECURITY REQUIREMENTS:\n" + "\n".join(warnings) + "\n\n"
        f"Write secure code that avoids the above vulnerabilities."
    )
    return enriched, all_cwes, all_keywords, details


if __name__ == "__main__":
    # smoke check
    tests = [
        "Write a Flask endpoint for user login that checks username and password against a MySQL database",
        "Write a function that fetches a URL provided by the user and returns the response body",
        "Explain the history of SQL as a language",  # should score low / lexical-only
        "Create an endpoint that extracts an uploaded tar archive into a workspace folder",
    ]
    for t in tests:
        _, cwes, kws, det = enrich_prompt(t)
        print(f"\nPROMPT: {t[:70]}")
        for d in det:
            print(f"  {d['cwe']:9s} score={d['score']:.3f} cos={d['cosine']:.3f} kw={d['keywords']}")
