from typing import Annotated, Any, TypedDict


def merge_list(left: list | None, right: list | None) -> list:
    return (left or []) + (right or [])


class AgentState(TypedDict, total=False):
    rubric_image_base64: str
    image_mime: str
    raw_csv_text: str
    extracted_rules: dict[str, Any]
    dynamic_roster: list[str]
    parsed_actions: dict[str, Any]
    calculated_percentages: dict[str, Any]
    audit_trail: Annotated[list[dict[str, Any]], merge_list]
    traces: Annotated[list[dict[str, Any]], merge_list]
    vision_failures: int
    token_usage: int
    correlation_id: str
    actor_email: str
    actor_role: str
    thread_id: str
    hitl_approved: bool
    hitl_approver: str
    injection_detections: list[dict[str, Any]]
    halt_reason: str
    current_errors: list[str]
