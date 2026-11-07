"""Semantic extraction: unstructured CSV + rubric → scored JSON. No percentage math."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import log_event
from app.graph.schemas import ScoredAction, SemanticExtraction
from app.graph.tools.csv_parser import load_unstructured_csv
from app.graph.tools.validation import (
    NO_GROUNDED_ACTIONS,
    pipeline_error,
    validate_peer_review_csv,
    validate_scored_actions,
)

SEMANTIC_PROMPT = """You are the Semantic Parser for a university group-assessment pipeline.

You receive:
1) Rubric rules JSON (criterion names and descriptions)
2) A raw peer-review CSV. It is UNSTRUCTURED. Typical columns include student names,
   Tasks_Completed, and Feedback_Notes. It does NOT contain criterion or score columns.

Your job:
- The person being scored is the reviewee (Student, Reviewee, or Team Member), never the reviewer.
  Use only student names that appear in that column. Do not invent people.
- Read task, contribution, and feedback text.
- Map each piece of evidence onto a rubric criterion name copied from the rules.
  If a comment does not match a rubric criterion, skip it. Do not invent a criterion
  and do not substitute a default criterion.
- Assign a base score of exactly 10 (exceeds / strong), 5 (meets / mixed), or 0
  (does not meet / missing). Do not use any other numbers.
- Set csv_row_index to the data row, starting at 1. Do not count the header line.
- Put supporting words from that same student's row in evidence.
- Do NOT calculate percentages, averages, or contribution shares.
- If the table is not a peer review, return an empty actions list.

Return only the structured actions array.
"""

POSITIVE = {
    "excellent",
    "great",
    "always",
    "led",
    "lead",
    "delivered",
    "thorough",
    "reliable",
    "strong",
    "completed",
    "clean",
    "clear",
    "outstanding",
    "proactive",
    "solid",
    "unblocked",
    "documented",
}
NEUTRAL = {"some", "helped", "ok", "mostly", "attempted", "partial", "needed", "quiet"}
NEGATIVE = {"missing", "late", "none", "didn't", "did not", "poor", "absent", "incomplete", "unreliable", "no show"}

CRITERION_HINTS = {
    "collaboration": ("collaborat", "team", "peer", "stand-up", "standup", "pair", "together"),
    "communication": ("communicat", "write", "wrote", "update", "explain", "document", "present"),
    "technical implementation": ("implement", "code", "api", "pipeline", "model", "fastapi", "parser", "build"),
    "contribution": ("task", "deliver", "completed", "work", "owned", "share"),
    "professionalism": ("on time", "prepared", "respect", "professional", "showed up"),
    "data wrangling": ("clean", "join", "csv", "wrangl", "null"),
    "reproducibility": ("reproduc", "readme", "seed", "rerun", "requirements", "pin"),
}


class SemanticInput(BaseModel):
    csv_text: str
    extracted_rules: dict[str, Any] = Field(default_factory=dict)


def _criteria(rules: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in (rules.get("criteria") or []) if str(item.get("name") or "").strip()]


def _score_from_text(text: str) -> float:
    lowered = text.casefold()
    pos = sum(1 for word in POSITIVE if word in lowered)
    neg = sum(1 for word in NEGATIVE if word in lowered)
    neu = sum(1 for word in NEUTRAL if word in lowered)
    if neg > pos:
        return 0.0
    if pos >= 2 or (pos > 0 and neg == 0 and neu == 0):
        return 10.0
    if pos == 0 and neg == 0 and not text.strip():
        return 0.0
    return 5.0


def _match_criteria(text: str, criteria: list[dict[str, Any]]) -> list[str]:
    lowered = text.casefold()
    matched: list[str] = []
    for item in criteria:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        key = name.casefold()
        hints = CRITERION_HINTS.get(key, ())
        desc = str(item.get("description") or "").casefold()
        if key in lowered or any(hint in lowered for hint in hints) or (desc and len(desc) >= 8 and desc[:18] in lowered):
            matched.append(name)
    return list(dict.fromkeys(matched))


def _finish_actions(
    actions: list[dict[str, Any]],
    loaded: dict[str, Any],
    rules: dict[str, Any],
    peer: dict[str, Any],
    *,
    source: str,
    notes: str = "",
) -> dict[str, Any]:
    checked = validate_scored_actions(actions, loaded, rules, peer["student_columns"])
    if checked.get("status") != "ok":
        return checked
    return {
        "status": "ok",
        "source": source,
        "roster": checked["roster"],
        "actions": checked["actions"],
        "max_score": 10.0,
        "rubric_title": rules.get("rubric_title") or "Uploaded rubric",
        "alias_map": checked["alias_map"],
        "notes": notes,
    }


def _heuristic_extract(loaded: dict[str, Any], rules: dict[str, Any], peer: dict[str, Any]) -> dict[str, Any]:
    criteria = _criteria(rules)
    if not criteria:
        return pipeline_error("invalid_actions", "No rubric criteria are available, so the peer review cannot be scored.")

    name_cols = peer["student_columns"]
    text_cols = peer["evidence_columns"]
    actions: list[dict[str, Any]] = []
    for row in loaded.get("rows") or []:
        cells: dict[str, str] = row["cells"]
        student = next((cells[col] for col in name_cols if cells.get(col)), "")
        evidence = " ".join(cells[col] for col in text_cols if cells.get(col)).strip()
        if not student or not evidence:
            continue
        matched = _match_criteria(evidence, criteria)
        if not matched:
            continue
        score = _score_from_text(evidence)
        for criterion in matched:
            actions.append(
                ScoredAction(
                    student_name=student,
                    criterion=criterion,
                    score=score,
                    csv_row_index=int(row["csv_row_index"]),
                    evidence=evidence[:280],
                ).model_dump()
            )

    if not actions:
        return pipeline_error("invalid_actions", NO_GROUNDED_ACTIONS)
    return _finish_actions(actions, loaded, rules, peer, source="heuristic")


def _llm_extract(csv_text: str, rules: dict[str, Any]) -> tuple[dict[str, Any] | None, int]:
    settings = get_settings()
    if not settings.openai_api_key:
        return None, 0
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_model, temperature=0)
        structured = llm.with_structured_output(SemanticExtraction)
        prompt = (
            f"{SEMANTIC_PROMPT}\n\nRUBRIC RULES:\n{json.dumps(rules, default=str)[:4000]}\n\n"
            f"CSV:\n{csv_text[:12000]}"
        )
        result = structured.invoke(prompt)
        payload = result.model_dump()
        if not payload.get("actions"):
            return None, 0
        return payload, 0
    except Exception as exc:  # noqa: BLE001
        log_event("semantic_llm_failed", error=type(exc).__name__)
        return None, 0


def extract_scored_actions(csv_text: str, extracted_rules: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Bridge unstructured CSV → scored JSON.
    Pandas must never see the raw CSV.
    """
    rules = extracted_rules or {}
    loaded = load_unstructured_csv(csv_text)
    if loaded.get("status") == "error":
        return loaded

    peer = validate_peer_review_csv(loaded)
    if peer.get("status") != "ok":
        log_event("csv_rejected", reason=peer.get("reason"))
        return peer
    if not _criteria(rules):
        return pipeline_error("invalid_actions", "No rubric criteria are available, so the peer review cannot be scored.")

    llm_payload, tokens = _llm_extract(csv_text, rules)
    if llm_payload:
        finished = _finish_actions(
            llm_payload.get("actions") or [],
            loaded,
            rules,
            peer,
            source="llm",
            notes=llm_payload.get("notes") or "",
        )
        finished["token_usage"] = tokens
        if finished.get("status") == "error":
            log_event("semantic_actions_rejected", reason=finished.get("message"))
            return finished
        log_event("semantic_extract", source="llm", actions=len(finished["actions"]), roster=finished["roster"])
        return finished

    heuristic = _heuristic_extract(loaded, rules, peer)
    heuristic["token_usage"] = tokens
    log_event(
        "semantic_extract",
        source=heuristic.get("source"),
        actions=len(heuristic.get("actions") or []),
        roster=heuristic.get("roster"),
    )
    return heuristic
