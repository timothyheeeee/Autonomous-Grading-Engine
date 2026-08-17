"""Deterministic calculator node. LLM does no math."""

from __future__ import annotations

import json
from typing import Any

from app.core.logging import log_event
from app.graph.state import AgentState
from app.graph.tools.registry import execute_tool, tool_ast


def calculate_node(state: AgentState) -> dict[str, Any]:
    result = execute_tool(
        "calculate_normalized_percentages",
        {
            "actions": (state.get("parsed_actions") or {}).get("actions") or [],
            "extracted_rules": state.get("extracted_rules") or {},
            "correlation_id": state.get("correlation_id") or "unknown",
            "max_score": (state.get("parsed_actions") or {}).get("max_score") or 10,
            "roster": state.get("dynamic_roster") or [],
            "rubric_title": (state.get("parsed_actions") or {}).get("rubric_title") or "Uploaded rubric",
        },
        state.get("actor_role") or "student",
    )
    if result.get("status") == "error":
        log_event("node_calculate", status="error", result=result)
        return {
            "calculated_percentages": result,
            "halt_reason": "unreadable_data",
            "current_errors": [result.get("message") or "unreadable_data"],
            "audit_trail": [
                {"step": 4, "title": "Calculate percentages", "detail": result.get("message") or "Calculation failed.", "ok": False}
            ],
            "traces": [{"node": "calculate", "payload": result, "ast": tool_ast("calculate_normalized_percentages")}],
        }

    students = result.get("students") or []
    summary = "; ".join(
        f"{row['student_name']} {row['contribution_percentage']}%"
        for row in students
    )
    log_event("node_calculate", status="ok", students=len(students))
    return {
        "calculated_percentages": result,
        "current_errors": [],
        "audit_trail": [
            {
                "step": 4,
                "title": "Calculate percentages",
                "detail": "Converted every raw score into a normalized percentage. Contribution shares: " + summary + ".",
                "ok": True,
            }
        ],
        "traces": [
            {
                "node": "calculate",
                "payload": result,
                "ast": tool_ast("calculate_normalized_percentages"),
                "response": json.dumps(result, default=str)[:4000],
            }
        ],
    }
