"""Shared Anthropic LLM client + JSON extraction utilities.

Used by B4, B5, Ours. Real API calls (not mocks), per CLAUDE.md's
reality-first engineering principles. Uses Sonnet 4.6 by default.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None  # type: ignore


MODEL = "claude-sonnet-4-6"


_client: Optional["Anthropic"] = None


def _get_client() -> "Anthropic":
    global _client
    if _client is None:
        if Anthropic is None:
            raise RuntimeError(
                "anthropic SDK not installed. `pip install anthropic`."
            )
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set in environment."
            )
        _client = Anthropic()
    return _client


def call_anthropic(prompt: str, max_tokens: int = 1500) -> tuple[str, int, int]:
    """Single LLM call. Returns (text_output, tokens_in, tokens_out).
    Raises on API failure — by design, we don't mask errors with fallbacks.
    """
    client = _get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if hasattr(b, "text"))
    return text, resp.usage.input_tokens, resp.usage.output_tokens


def parse_json_blob(text: str) -> Optional[dict]:
    """Extract the first JSON object from an LLM response.

    Handles: bare JSON, JSON wrapped in ```json ... ``` fences, JSON with
    leading/trailing prose. Returns None if no valid JSON can be parsed.
    """
    # Try fenced first.
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Try the largest brace-balanced substring.
    starts = [i for i, c in enumerate(text) if c == "{"]
    for s in starts:
        depth = 0
        for e in range(s, len(text)):
            if text[e] == "{":
                depth += 1
            elif text[e] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[s:e + 1])
                    except json.JSONDecodeError:
                        break
    return None
