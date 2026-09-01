"""
LLM client v3 — multi-provider, preflight-gated.

Fleet (see docs/03_METHODOLOGY.md). Providers: groq, gemini (google-genai),
openai (also serves deepseek via base_url), anthropic.

v2 post-mortem rules enforced here:
  - Unknown model name = hard ValueError (v2's silent fallback was itself a KeyError bug).
  - preflight() must be green before any batch run.
"""
import os
import time

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

SYSTEM_INSTRUCTION = (
    "You are a Python code generator. Return ONLY Python code inside a single "
    "```python``` code block. No explanations, no comments outside the code, "
    "no markdown outside the code block."
)

# Generation temperature. Raised from 0.2 -> 0.7 (2026-07-14) so the 3 reps per
# cell are genuinely independent samples: at 0.2 the reps were near-duplicates,
# which would make Wilson CIs / McNemar tests falsely narrow (pseudo-replication).
# 0.7 gives real within-model variance without going incoherent. See docs/03.
TEMPERATURE = 0.7
MAX_TOKENS = 2048

# generation buckets per docs/03_METHODOLOGY.md
# 2026-09-01: llama-3.1-8b-instant and llama-3.3-70b-versatile confirmed retired from
# Groq (404 on this account's key; absent from client.models.list()). Substituted with
# the currently-active Groq free models below — see docs/03_METHODOLOGY.md substitution note.
MODEL_CONFIGS = {
    # G1 — small/fast anchor (was Llama 3.1 8B; Groq retired it 2026)
    "gpt-oss-20b":     {"provider": "groq",      "api_model": "openai/gpt-oss-20b",       "gen": "G1"},
    # G2 — big open, same vendor as G1 (was Llama 3.3 70B; Groq retired it 2026)
    "gpt-oss-120b":    {"provider": "groq",      "api_model": "openai/gpt-oss-120b",      "gen": "G2"},
    "gpt-4o-mini":     {"provider": "openai",    "api_model": "gpt-4o-mini",              "gen": "G2"},
    # G3 — 2025-26 current
    "gemini-2.5-flash": {"provider": "gemini",   "api_model": "gemini-2.5-flash",         "gen": "G3"},
    "claude-haiku-4.5": {"provider": "anthropic", "api_model": "claude-haiku-4-5-20251001", "gen": "G3"},
    "deepseek-chat":   {"provider": "deepseek",  "api_model": "deepseek-chat",            "gen": "G3"},
}

_clients = {}


def _client(provider):
    if provider in _clients:
        return _clients[provider]
    if provider == "groq":
        from groq import Groq
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if not key:
            raise ValueError("GROQ_API_KEY not set")
        _clients[provider] = Groq(api_key=key)
    elif provider == "gemini":
        from google import genai
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise ValueError("GEMINI_API_KEY not set")
        _clients[provider] = genai.Client(api_key=key)
    elif provider == "openai":
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise ValueError("OPENAI_API_KEY not set")
        _clients[provider] = OpenAI(api_key=key)
    elif provider == "deepseek":
        from openai import OpenAI
        key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not key:
            raise ValueError("DEEPSEEK_API_KEY not set")
        _clients[provider] = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    elif provider == "anthropic":
        from anthropic import Anthropic
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        _clients[provider] = Anthropic(api_key=key)
    else:
        raise ValueError(f"Unknown provider: {provider}")
    return _clients[provider]


def call_with_backoff(func, max_retries=5, base_delay=10):
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            s = str(e).lower()
            if any(t in s for t in ("429", "too many requests", "rate limit", "quota")):
                if i == max_retries - 1:
                    raise
                wait = base_delay * (2 ** i)
                print(f"    [rate-limited] sleeping {wait}s ({i+1}/{max_retries})")
                time.sleep(wait)
            elif any(t in s for t in ("503", "overloaded", "500", "502")):
                if i == max_retries - 1:
                    raise
                time.sleep(8)
            else:
                raise


def _generate(provider, api_model, prompt, max_tokens=MAX_TOKENS):
    if provider in ("groq", "openai", "deepseek"):
        resp = _client(provider).chat.completions.create(
            model=api_model,
            messages=[{"role": "system", "content": SYSTEM_INSTRUCTION},
                      {"role": "user", "content": prompt}],
            temperature=TEMPERATURE, max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content
    elif provider == "gemini":
        from google.genai import types
        resp = _client(provider).models.generate_content(
            model=api_model, contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=TEMPERATURE, max_output_tokens=max_tokens,
            ),
        )
        text = resp.text
    elif provider == "anthropic":
        resp = _client(provider).messages.create(
            model=api_model, system=SYSTEM_INSTRUCTION,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE, max_tokens=max_tokens,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    else:
        raise ValueError(f"Unknown provider: {provider}")

    if not text or not text.strip():
        raise ValueError(f"{provider} returned an empty response")
    return text


def call_llm(prompt, model_name):
    if model_name not in MODEL_CONFIGS:
        raise ValueError(f"Unknown model '{model_name}'. Known: {list(MODEL_CONFIGS)}")
    cfg = MODEL_CONFIGS[model_name]
    return call_with_backoff(lambda: _generate(cfg["provider"], cfg["api_model"], prompt))


def preflight(models=None):
    """Call every model with a tiny prompt. Returns dict name -> 'ok' | error string."""
    results = {}
    for name in (models or MODEL_CONFIGS):
        cfg = MODEL_CONFIGS[name]
        try:
            _generate(cfg["provider"], cfg["api_model"],
                      "Return a python code block containing exactly: x = 1", max_tokens=512)
            results[name] = "ok"
        except Exception as e:
            results[name] = f"ERROR: {str(e)[:200]}"
    return results


if __name__ == "__main__":
    for name, status in preflight().items():
        mark = "+" if status == "ok" else "!"
        print(f" [{mark}] {name:18s} {status}")
