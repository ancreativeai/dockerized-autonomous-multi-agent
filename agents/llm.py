"""Hybrid LLM routing — locked at bootstrap:
   * Claude (official Anthropic SDK)  -> orchestrator/planner ONLY
   * Hermes (local llama.cpp, OpenAI-compatible) -> all worker agents
"""
import json
import os
import time

import requests
from prometheus_client import Counter, Histogram

TOKENS = Counter("llm_tokens_total", "LLM tokens consumed", ["model", "direction"])
REQUESTS = Counter("llm_requests_total", "LLM requests", ["model", "status"])
LATENCY = Histogram("llm_request_seconds", "LLM request latency", ["model"],
                    buckets=(1, 5, 15, 30, 60, 120, 300, 600))

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")
HERMES_BASE = os.getenv("HERMES_BASE_URL", "http://hermes-llm:8080/v1")

_anthropic_client = None


def claude_available():
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def claude_plan(guard, system, user, schema=None):
    """Planner call: adaptive thinking, streaming, optional constrained JSON output."""
    guard.check_forbidden(user)
    kwargs = dict(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": guard.compress(user)}],
    )
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    start = time.time()
    try:
        with _client().messages.stream(**kwargs) as stream:
            msg = stream.get_final_message()
        REQUESTS.labels(CLAUDE_MODEL, "ok").inc()
    except Exception:
        REQUESTS.labels(CLAUDE_MODEL, "error").inc()
        raise
    finally:
        LATENCY.labels(CLAUDE_MODEL).observe(time.time() - start)

    TOKENS.labels(CLAUDE_MODEL, "input").inc(msg.usage.input_tokens)
    TOKENS.labels(CLAUDE_MODEL, "output").inc(msg.usage.output_tokens)
    guard.add_tokens(msg.usage.input_tokens + msg.usage.output_tokens, model=CLAUDE_MODEL)

    if msg.stop_reason == "refusal":
        guard.audit("claude_refusal", details=str(getattr(msg, "stop_details", None)))
        return ""
    return "".join(b.text for b in msg.content if b.type == "text")


def hermes_work(guard, system, user, schema=None, timeout=600):
    """Worker call against local Hermes via llama.cpp OpenAI-compatible API."""
    guard.check_forbidden(user)
    payload = {
        "model": "hermes",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": guard.compress(user, max_chars=6000 * 4)},
        ],
        "temperature": 0.4,
        "max_tokens": 1024,
    }
    if schema is not None:
        payload["response_format"] = {"type": "json_object", "schema": schema}
    start = time.time()
    try:
        r = requests.post(f"{HERMES_BASE}/chat/completions", json=payload, timeout=timeout)
        r.raise_for_status()
        REQUESTS.labels("hermes", "ok").inc()
    except Exception:
        REQUESTS.labels("hermes", "error").inc()
        raise
    finally:
        LATENCY.labels("hermes").observe(time.time() - start)

    data = r.json()
    usage = data.get("usage", {})
    TOKENS.labels("hermes", "input").inc(usage.get("prompt_tokens", 0))
    TOKENS.labels("hermes", "output").inc(usage.get("completion_tokens", 0))
    # Local tokens are free — tracked in metrics but not charged to the paid budget.
    return data["choices"][0]["message"]["content"]


def parse_json(text, fallback=None):
    """Best-effort JSON extraction for constrained outputs."""
    if not text:
        return fallback
    try:
        return json.loads(text)
    except ValueError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except ValueError:
                pass
    return fallback
