"""Prompt-injection guardrail applied to raw CSV text before the LLM router."""

from __future__ import annotations

import re
from typing import Any

INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_previous", re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I)),
    ("system_override", re.compile(r"(you\s+are\s+now|new\s+system\s+prompt|override\s+the\s+system)", re.I)),
    ("jailbreak", re.compile(r"(dan\s+mode|jailbreak|developer\s+mode\s+enabled)", re.I)),
    ("forced_grade", re.compile(r"(give|award|assign)\s+\w[\w\s\-']{0,40}\s+100\s*%", re.I)),
    ("forced_grade_alt", re.compile(r"everyone\s+(gets?|should\s+get)\s+100", re.I)),
    ("exfiltrate", re.compile(r"(print|reveal|dump)\s+(the\s+)?(system\s+prompt|hidden\s+instructions)", re.I)),
]


def sanitize_text(value: str) -> tuple[str, list[dict[str, Any]]]:
    detections: list[dict[str, Any]] = []
    cleaned = value
    for label, pattern in INJECTION_PATTERNS:
        for match in pattern.finditer(value):
            detections.append(
                {
                    "rule": label,
                    "span": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
            cleaned = pattern.sub("[REDACTED_INJECTION]", cleaned)
    return cleaned, detections


def sanitize_csv_payload(raw_csv: str) -> dict[str, Any]:
    cleaned, detections = sanitize_text(raw_csv)
    return {
        "sanitized_csv": cleaned,
        "injection_detections": detections,
        "stripped": bool(detections),
    }
