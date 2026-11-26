"""Groq chat + structured JSON helpers."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import get_settings


class LLMError(RuntimeError):
    pass


def _default_model() -> str:
    return get_settings().groq_model or "qwen/qwen3.8-27b"


def _fast_model() -> str:
    return get_settings().groq_fast_model or "qwen/qwen3.8-27b"


def _headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.groq_configured:
        raise LLMError("GROQ_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }


def _parse_json_content(content: str) -> dict[str, Any]:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise LLMError(f"Could not parse JSON from model: {content[:300]}") from None
        return json.loads(match.group(0))


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 2048,
) -> str:
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=_headers(),
        json={
            "model": model or _default_model(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=90.0,
    )
    if resp.status_code >= 400:
        raise LLMError(f"Groq error {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    return str(data["choices"][0]["message"]["content"] or "")


def chat_json(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Ask for a JSON object in the assistant content (no native tool calls)."""
    msgs = list(messages)
    guard = (
        "Respond with ONE JSON object as plain text in the assistant message content. "
        "Do NOT call tools/functions. Do NOT wrap in markdown."
    )
    if msgs and msgs[0].get("role") == "system":
        msgs[0] = {**msgs[0], "content": msgs[0]["content"] + "\n" + guard}
    else:
        msgs.insert(0, {"role": "system", "content": guard})

    payload = {
        "model": model or _fast_model(),
        "messages": msgs,
        "temperature": temperature,
        "max_tokens": 2048,
    }
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=_headers(),
        json=payload,
        timeout=90.0,
    )
    if resp.status_code >= 400:
        # gpt-oss sometimes returns tool_use_failed with usable JSON in failed_generation
        try:
            err = resp.json().get("error") or {}
            failed = err.get("failed_generation")
            if failed:
                # May be a bare tool call — wrap into our schema if needed
                parsed = _parse_json_content(failed)
                if "name" in parsed and "tools" not in parsed:
                    return {
                        "tools": [{"name": parsed["name"], "args": parsed.get("arguments") or {}}],
                        "reply": "Done.",
                    }
                return parsed
        except Exception:
            pass
        raise LLMError(f"Groq error {resp.status_code}: {resp.text[:500]}")

    message = resp.json()["choices"][0]["message"]
    content = message.get("content") or ""
    if not content and message.get("tool_calls"):
        # Convert native tool calls into our schema
        tools = []
        for tc in message["tool_calls"]:
            fn = tc.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                args = {}
            tools.append({"name": fn.get("name"), "args": args})
        return {"tools": tools, "reply": "Done."}
    return _parse_json_content(content)
