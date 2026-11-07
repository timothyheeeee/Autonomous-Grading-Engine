from __future__ import annotations

import json
import threading
from typing import Any

from app.core.correlation import get_correlation_id, new_correlation_id
from app.core.logging import log_event
from app.core.rbac import require_admin
from app.db.models import PipelineRun, TraceEvent
from app.db.session import SessionLocal
from app.graph.compile import get_graph
from app.graph.tracing import persist_trace

_LOCK = threading.Lock()
_RUNNING: dict[str, str] = {}


def _snapshot_run(thread_id: str, correlation_id: str, status: str, payload: dict[str, Any], actor: str) -> None:
    db = SessionLocal()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.thread_id == thread_id).one_or_none()
        title = ((payload.get("extracted_rules") or {}).get("rubric_title")) or "Uploaded rubric"
        if run is None:
            run = PipelineRun(
                thread_id=thread_id,
                correlation_id=correlation_id,
                status=status,
                rubric_name=title,
                initiated_by=actor,
            )
            db.add(run)
            db.flush()
        else:
            run.status = status
            run.token_usage = int(payload.get("token_usage") or 0)
            run.qualitative_feedback = json.dumps(payload.get("audit_trail"), default=str)
            if payload.get("current_errors"):
                run.error_json = json.dumps(payload.get("current_errors"), default=str)
        for trace in payload.get("traces") or []:
            db.add(
                TraceEvent(
                    run_id=run.id,
                    node_name=trace.get("node", "unknown"),
                    payload_json=json.dumps(trace, default=str),
                )
            )
        db.commit()
    finally:
        db.close()


def _public_error(values: dict[str, Any]) -> dict[str, str]:
    reason = str(values.get("halt_reason") or "unreadable_data")
    raw = values.get("current_errors") or []
    message = raw[0] if raw else "The upload could not be validated."
    if not isinstance(message, str) or "Traceback" in message or message == reason:
        message = "The upload could not be validated. Check the rubric screenshot and peer-review CSV."
    return {"status": "error", "reason": reason, "message": message}


def _derive_status(thread_id: str, values: dict[str, Any], next_nodes: tuple[str, ...] | list[str]) -> str:
    nxt = list(next_nodes or [])
    if values.get("hitl_approved") and not nxt:
        return "published"
    if "save_to_database" in nxt:
        return "pending_review"
    if values.get("halt_reason") and values.get("halt_reason") != "awaiting_hitl":
        return "error"
    if _RUNNING.get(thread_id) or nxt:
        return "running"
    if values.get("calculated_percentages", {}).get("status") == "ok":
        return "pending_review"
    if values:
        return "running"
    return "empty"


def serialize_run(thread_id: str, values: dict[str, Any], status: str, next_nodes: list[str]) -> dict[str, Any]:
    metrics = values.get("calculated_percentages") or {}
    rules = values.get("extracted_rules") or {}
    current = next_nodes[0] if next_nodes else ("done" if status in {"published", "error"} else status)
    if status == "pending_review":
        current = "save_to_database"
    if status == "running" and not next_nodes:
        current = _RUNNING.get(thread_id, "vision_extractor")
    return {
        "thread_id": thread_id,
        "correlation_id": values.get("correlation_id"),
        "status": status,
        "current_node": current,
        "next_nodes": next_nodes,
        "token_usage": values.get("token_usage") or 0,
        "vision_failures": values.get("vision_failures") or 0,
        "audit_trail": values.get("audit_trail") or [],
        "dynamic_roster": values.get("dynamic_roster") or [],
        "extracted_rules": {k: v for k, v in rules.items() if k != "image"} if rules else None,
        "percentages": metrics if metrics.get("status") == "ok" else None,
        "error": _public_error(values) if status == "error" else None,
        "injection_detections": values.get("injection_detections") or [],
        "traces": values.get("traces") or [],
        "hitl_approved": bool(values.get("hitl_approved")),
    }


def get_run_state(thread_id: str) -> dict[str, Any]:
    graph = get_graph()
    snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
    values = dict(snapshot.values or {})
    next_nodes = list(snapshot.next or [])
    status = _derive_status(thread_id, values, next_nodes)
    return serialize_run(thread_id, values, status, next_nodes)


def _worker(initial: dict[str, Any], thread_id: str, actor: str) -> None:
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 8}
    try:
        with _LOCK:
            result = graph.invoke(initial, config=config)
        values = result if isinstance(result, dict) else {}
        persist_trace(initial["correlation_id"], values.get("traces") or [], extra={"thread_id": thread_id})
        snapshot = graph.get_state(config)
        status = _derive_status(thread_id, dict(snapshot.values or {}), list(snapshot.next or []))
        _snapshot_run(thread_id, initial["correlation_id"], status, dict(snapshot.values or {}), actor)
        log_event("pipeline_paused_or_done", thread_id=thread_id, status=status)
    except Exception as exc:  # noqa: BLE001
        log_event("pipeline_worker_failed", thread_id=thread_id, error=str(exc))
        _snapshot_run(thread_id, initial["correlation_id"], "error", {"current_errors": [str(exc)]}, actor)
    finally:
        _RUNNING.pop(thread_id, None)


def start_pipeline(*, csv_text: str, image_base64: str, image_mime: str, actor_email: str, actor_role: str) -> dict[str, Any]:
    require_admin(actor_role)
    correlation_id = get_correlation_id() or new_correlation_id()
    thread_id = correlation_id
    initial = {
        "rubric_image_base64": image_base64,
        "image_mime": image_mime,
        "raw_csv_text": csv_text,
        "extracted_rules": {},
        "dynamic_roster": [],
        "parsed_actions": {},
        "calculated_percentages": {},
        "audit_trail": [],
        "traces": [],
        "vision_failures": 0,
        "token_usage": 0,
        "correlation_id": correlation_id,
        "actor_email": actor_email,
        "actor_role": actor_role,
        "thread_id": thread_id,
        "hitl_approved": False,
        "current_errors": [],
    }
    _RUNNING[thread_id] = "vision_extractor"
    _snapshot_run(thread_id, correlation_id, "running", initial, actor_email)
    log_event("pipeline_start", thread_id=thread_id, actor=actor_email)
    _worker(initial, thread_id, actor_email)
    return get_run_state(thread_id)


def resume_pipeline(thread_id: str, *, approved: bool, approver: str, actor_role: str) -> dict[str, Any]:
    require_admin(actor_role)
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 8}
    snapshot = graph.get_state(config)
    if not snapshot.values and not snapshot.next:
        raise ValueError("Unknown thread — nothing to resume.")
    graph.update_state(config, {"hitl_approved": approved, "hitl_approver": approver})
    if not approved:
        values = dict(snapshot.values)
        persist_trace(values.get("correlation_id") or thread_id, values.get("traces") or [], extra={"status": "rejected"})
        _snapshot_run(thread_id, values.get("correlation_id") or thread_id, "rejected", values, approver)
        return serialize_run(thread_id, values, "rejected", [])
    with _LOCK:
        result = graph.invoke(None, config=config)
    values = result if isinstance(result, dict) else dict(graph.get_state(config).values or {})
    persist_trace(values.get("correlation_id") or thread_id, values.get("traces") or [], extra={"status": "published"})
    _snapshot_run(thread_id, values.get("correlation_id") or thread_id, "published", values, approver)
    return serialize_run(thread_id, values, "published", [])
