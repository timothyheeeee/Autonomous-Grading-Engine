"""Vision extractor: multimodal rubric screenshot → structured rules. Drops base64 after this node."""

from __future__ import annotations

from typing import Any

from app.core.logging import log_event
from app.graph.state import AgentState
from app.graph.tools.vision import extract_rubric_from_image


def vision_extractor_node(state: AgentState) -> dict[str, Any]:
    failures = int(state.get("vision_failures") or 0)
    image = state.get("rubric_image_base64") or ""
    mime = state.get("image_mime") or "image/png"
    result = extract_rubric_from_image(image, mime)
    tokens = int(state.get("token_usage") or 0) + int(result.pop("token_usage", 0) or 0)

    if result.get("status") == "error":
        failures += 1
        reason = result.get("reason") or "unreadable_data"
        message = result.get("message") or "The screenshot could not be read."
        log_event("node_vision", status="error", failures=failures, reason=reason)
        return {
            "extracted_rules": {"status": "error", "reason": reason, "message": message},
            "vision_failures": failures,
            "token_usage": tokens,
            "rubric_image_base64": "",
            "halt_reason": reason,
            "current_errors": [message],
            "audit_trail": [{"step": 1, "title": "Read rubric", "detail": message, "ok": False}],
            "traces": [
                {
                    "node": "vision_extractor",
                    "payload": {"status": "error", "reason": reason, "message": message},
                    "ast": {"node_type": "VisionExtractor", "dump": "extract_rubric_from_image(image)"},
                }
            ],
        }

    criteria = result.get("criteria") or []
    detail = (
        f"Checked the screenshot and extracted {len(criteria)} grading "
        f"{'criterion' if len(criteria) == 1 else 'criteria'}."
    )
    log_event("node_vision", status="ok", criteria=len(criteria), source=result.get("source"))
    return {
        "extracted_rules": result,
        "vision_failures": 0,
        "token_usage": tokens,
        "rubric_image_base64": "",
        "current_errors": [],
        "audit_trail": [{"step": 1, "title": "Read rubric", "detail": detail, "ok": True}],
        "traces": [
            {
                "node": "vision_extractor",
                "payload": {k: v for k, v in result.items() if k != "image"},
                "ast": {"node_type": "VisionExtractor", "dump": "extract_rubric_from_image(image)"},
            }
        ],
    }
