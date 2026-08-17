"""Sliding token window for conversation history."""

from typing import Any

from app.config import get_settings


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def trim_messages(messages: list[Any], max_tokens: int | None = None) -> list[Any]:
    budget = max_tokens or get_settings().max_context_tokens
    kept: list[Any] = []
    used = 0
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content", "")
        tokens = _estimate_tokens(str(content or ""))
        if used + tokens > budget and kept:
            break
        kept.append(message)
        used += tokens
    return list(reversed(kept))
