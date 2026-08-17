"""Save-to-database node. Runs only after HITL resume."""

from __future__ import annotations

import json
from typing import Any

from app.core.logging import log_event
from app.db.models import PipelineRun, PublishedMetric
from app.db.session import SessionLocal
from app.graph.state import AgentState


def save_to_database_node(state: AgentState) -> dict[str, Any]:
    if not state.get("hitl_approved"):
        return {
            "current_errors": ["Approval required before saving."],
            "halt_reason": "awaiting_hitl",
        }

    metrics = state.get("calculated_percentages") or {}
    students = metrics.get("students") or []
    correlation_id = state.get("correlation_id") or "unknown"
    thread_id = state.get("thread_id") or correlation_id

    db = SessionLocal()
    try:
        db.query(PublishedMetric).delete()
        for student in students:
            for criterion in student.get("criteria") or []:
                db.add(
                    PublishedMetric(
                        student_name=student["student_name"],
                        criterion=criterion["criterion"],
                        percentage=criterion["percentage"],
                        contribution_percentage=student["contribution_percentage"],
                        overall_percentage=student["overall_percentage"],
                        source_row_ids=",".join(str(i) for i in criterion.get("source_row_ids") or []),
                        correlation_id=correlation_id,
                    )
                )
        run = db.query(PipelineRun).filter(PipelineRun.thread_id == thread_id).one_or_none()
        if run:
            run.status = "published"
            run.token_usage = int(state.get("token_usage") or 0)
            run.qualitative_feedback = json.dumps(state.get("audit_trail"), default=str)
        db.commit()
    finally:
        db.close()

    log_event("saved_to_database", approver=state.get("hitl_approver"), students=len(students))
    return {
        "current_errors": [],
        "audit_trail": [
            {
                "step": 5,
                "title": "Saved",
                "detail": f"Approved by {state.get('hitl_approver')}. Percentages stored for the dashboard.",
                "ok": True,
            }
        ],
        "traces": [
            {
                "node": "save_to_database",
                "payload": {"students": len(students), "approver": state.get("hitl_approver")},
                "ast": {"node_type": "Save", "dump": "interrupt_before=['save_to_database']"},
            }
        ],
    }
