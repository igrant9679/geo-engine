"""Ask a question to search-enabled AI engines. Each function returns (answer_text, [cited_urls_or_domains]).

An engine is used only if its API key is set in engine/.env.
"""
import requests

from common import env, settings

TIMEOUT = 120


def chatgpt(prompt, model):
    r = requests.post("https://api.openai.com/v1/responses", timeout=TIMEOUT,
                      headers={"Authorization": f"Bearer {env('OPENAI_API_KEY')}"},
                      json={"model": model, "tools": [{"type": "web_search"}], "input": prompt})
    r.raise_for_status()
    text, cites = [], []
    for item in r.json().get("output", []):
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") == "output_text":
                text.append(part.get("text", ""))
                cites += [a["url"] for a in part.get("annotations", []) if a.get("url")]
    return "\n".join(text), cites


def perplexity(prompt, model):
    r = requests.post("https://api.perplexity.ai/chat/completions", timeout=TIMEOUT,
                      headers={"Authorization": f"Bearer {env('PERPLEXITY_API_KEY')}"},
                      json={"model": model, "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    j = r.json()
    cites = j.get("citations") or [s.get("url") for s in j.get("search_results", []) if s.get("url")]
    return j["choices"][0]["message"]["content"], cites


def gemini(prompt, model):
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      timeout=TIMEOUT, headers={"x-goog-api-key": env("GEMINI_API_KEY")},
                      json={"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}]})
    r.raise_for_status()
    cand = (r.json().get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    # Gemini returns redirect URIs; the chunk title holds the real domain.
    chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
    return text, [c["web"].get("title") or c["web"].get("uri") for c in chunks if c.get("web")]


def claude(prompt, model):
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=TIMEOUT,
                      headers={"x-api-key": env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
                      json={"model": model, "max_tokens": 1500, "messages": [{"role": "user", "content": prompt}],
                            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]})
    r.raise_for_status()
    text, cites = [], []
    for block in r.json().get("content", []):
        if block.get("type") == "text":
            text.append(block.get("text", ""))
            cites += [c["url"] for c in block.get("citations") or [] if c.get("url")]
    return "".join(text), cites


ENGINES = {  # name -> (function, env key, settings key for model)
    "chatgpt": (chatgpt, "OPENAI_API_KEY", "openai_model"),
    "perplexity": (perplexity, "PERPLEXITY_API_KEY", "perplexity_model"),
    "gemini": (gemini, "GEMINI_API_KEY", "gemini_model"),
    "claude": (claude, "ANTHROPIC_API_KEY", "anthropic_model"),
}


def enabled():
    cfg = settings()["mentions"]
    return {name: (fn, cfg[model_key]) for name, (fn, key, model_key) in ENGINES.items()
            if env(key) and name in cfg.get("engines", ENGINES)}
