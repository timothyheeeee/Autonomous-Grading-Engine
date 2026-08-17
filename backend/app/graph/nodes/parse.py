"""Semantic parser: unstructured CSV + rubric rules → scored JSON. Pandas never sees the CSV."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from app.core.logging import log_event
from app.core.sanitization import sanitize_csv_payload
from app.graph.state import AgentState
from app.graph.tools.registry import openai_tool_schemas
from app.graph.tools.semantic import extract_scored_actions


def _bind_semantic_llm(csv_text: str, rules: dict[str, Any]) -> int:
    from app.config import get_settings

    settings = get_settings()
    if not settings.openai_api_key:
        return 0
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_model, temperature=0)
        bound = llm.bind_tools(openai_tool_schemas())
        bound.invoke(
            "Read this unstructured peer-review CSV and the rubric. "
            "Do not call the Pandas calculator. Extract scored actions only.\n\n"
            f"RUBRIC:\n{json.dumps(rules, default=str)[:3000]}\n\nCSV:\n{csv_text[:8000]}"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        log_event("semantic_tool_bind_failed", error=str(exc))
        return 0


def semantic_parser_node(state: AgentState) -> dict[str, Any]:
    raw = state.get("raw_csv_text") or ""
    sanitized = sanitize_csv_payload(raw)
    csv_text = sanitized["sanitized_csv"]
    detections = sanitized["injection_detections"]
    rules = state.get("extracted_rules") or {}
    if detections:
        log_event("injection_stripped", count=len(detections))

    tokens = int(state.get("token_usage") or 0) + _bind_semantic_llm(csv_text, rules)
    extracted = extract_scored_actions(csv_text, rules)
    tokens += int(extracted.pop("token_usage", 0) or 0)

    if extracted.get("status") == "error":
        log_event("node_semantic_parser", status="error", extracted=extracted)
        return {
            "raw_csv_text": csv_text,
            "parsed_actions": extracted,
            "dynamic_roster": [],
            "injection_detections": detections,
            "token_usage": tokens,
            "halt_reason": "unreadable_data",
            "current_errors": [extracted.get("message") or "unreadable_data"],
            "audit_trail": [
                {
                    "step": 2,
                    "title": "Extract team",
                    "detail": extracted.get("message") or "Unstructured reviews could not be read.",
                    "ok": False,
                }
            ],
            "traces": [{"node": "semantic_parser", "payload": extracted, "ast": {"node_type": "SemanticExtractor"}}],
        }

    roster = extracted.get("roster") or []
    actions = extracted.get("actions") or []
    per_member = Counter(row["student_name"] for row in actions)
    member_lines = [f"{name}: mapped review text onto the rubric" for name in roster]
    log_event("node_semantic_parser", roster=roster, actions=len(actions), source=extracted.get("source"))
    return {
        "raw_csv_text": csv_text,
        "parsed_actions": extracted,
        "dynamic_roster": roster,
        "injection_detections": detections,
        "token_usage": tokens,
        "current_errors": [],
        "audit_trail": [
            {
                "step": 2,
                "title": "Extract team",
                "detail": f"Extracted {len(roster)} unique team member{'s' if len(roster) != 1 else ''} from the CSV: {', '.join(roster)}.",
                "ok": True,
            },
            {
                "step": 3,
                "title": "Map work",
                "detail": (
                    f"Read unstructured tasks and feedback, mapped them onto {len({row['criterion'] for row in actions})} "
                    f"rubric criteria, and assigned base scores of 10, 5, or 0. "
                    + "; ".join(member_lines)
                    + "."
                ),
                "ok": True,
            },
        ],
        "traces": [
            {
                "node": "semantic_parser",
                "payload": {
                    "roster": roster,
                    "action_preview": actions[:12],
                    "source": extracted.get("source"),
                    "per_member": dict(per_member),
                },
                "ast": {"node_type": "SemanticExtractor", "dump": "extract_scored_actions(csv, rubric_rules)"},
                "response": json.dumps({"roster": roster, "actions": actions[:20]}, default=str),
            }
        ],
    }
