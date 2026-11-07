"""Deterministic checks. These run around the model, and they do not invent content."""

from __future__ import annotations

import math
import re
from typing import Any

from app.core.logging import log_event
from app.graph.schemas import ExtractedRules, RubricAssessment, RubricCriterion
from app.graph.tools.csv_parser import classify_columns
from app.graph.tools.entities import cluster_names

NOT_A_RUBRIC = (
    "The uploaded image does not appear to contain a grading rubric. "
    "Please upload a screenshot showing assessment criteria."
)
NOT_A_PEER_CSV = (
    "The uploaded CSV does not appear to contain student peer-review information. "
    "Please check the file and try again."
)
VISION_UNCONFIGURED = "Rubric verification is unavailable because the vision model is not configured."
VISION_REQUEST_FAILED = (
    "Rubric verification failed because the vision model could not be reached. "
    "The uploaded image has not been validated."
)
NO_GROUNDED_ACTIONS = "No scoring actions could be grounded in the peer review and rubric."

_PLACEHOLDER_CRITERIA = {
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "criterion",
    "criteria",
    "rubric",
    "score",
    "scores",
    "untitled",
    "test",
    "todo",
    "tbd",
    "item",
    "category",
    "other",
}
_NON_RUBRIC_LABELS = {
    "total",
    "subtotal",
    "tax",
    "price",
    "quantity",
    "qty",
    "invoice",
    "receipt",
    "amount",
    "sku",
    "product",
    "description",
    "date",
    "address",
    "phone",
    "temperature",
    "humidity",
    "city",
    "department",
    "age",
    "salary",
    "email",
    "quantity on hand",
}
_ALLOWED_SCORES = (0.0, 5.0, 10.0)
_STOPWORDS = {
    "with",
    "from",
    "that",
    "this",
    "have",
    "were",
    "been",
    "their",
    "about",
    "into",
    "your",
    "they",
    "them",
    "and",
    "the",
    "for",
    "was",
    "are",
    "but",
}


def pipeline_error(reason: str, message: str) -> dict[str, Any]:
    return {"status": "error", "reason": reason, "message": message}


def _meaningful_criterion(item: RubricCriterion) -> bool:
    name = " ".join(item.name.split())
    folded = name.casefold()
    if folded in _PLACEHOLDER_CRITERIA or folded in _NON_RUBRIC_LABELS:
        return False
    letters = sum(character.isalpha() for character in name)
    return letters >= 3


def validate_rubric_assessment(assessment: RubricAssessment) -> dict[str, Any]:
    """Accept a rubric only when the flag, the criteria, and the scale all agree.

    Structured JSON from the model is not treated as proof.
    """
    if not assessment.is_valid_rubric:
        return pipeline_error("invalid_rubric", NOT_A_RUBRIC)

    criteria = [item for item in assessment.criteria if _meaningful_criterion(item)]
    scale = assessment.scale_max
    scale_ok = isinstance(scale, (int, float)) and not isinstance(scale, bool) and math.isfinite(float(scale))
    if not scale_ok or not 1 <= float(scale) <= 100 or not criteria:
        return pipeline_error("invalid_rubric", NOT_A_RUBRIC)

    title = " ".join((assessment.rubric_title or "").split()) or "Uploaded rubric"
    rules = ExtractedRules(
        rubric_title=title,
        scale_max=float(scale),
        criteria=criteria,
        source="gpt_vision",
    )
    return rules.model_dump()


def _is_number(value: str) -> bool:
    text = value.strip().replace(",", "").replace("$", "").replace("%", "")
    if not text:
        return False
    try:
        float(text)
        return True
    except ValueError:
        return False


def _is_textual_evidence(value: str) -> bool:
    text = " ".join(value.split())
    if not text or _is_number(text):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    words = [word for word in words if len(word) >= 2]
    letters = sum(character.isalpha() for character in text)
    return len(words) >= 2 or letters >= 12


def validate_peer_review_csv(loaded: dict[str, Any]) -> dict[str, Any]:
    """Decide whether a parsed table is peer-assessment data.

    A person column by itself, or a comments column by itself, is not enough.
    Column order is never used as a substitute for a student field.
    """
    if loaded.get("status") == "error":
        return loaded
    columns = list(loaded.get("columns") or [])
    rows = list(loaded.get("rows") or [])
    if not columns or not rows:
        return pipeline_error("invalid_csv", NOT_A_PEER_CSV)

    classified = classify_columns(columns)
    student_cols = classified["student"]
    generic_cols = classified["generic_name"]
    task_cols = classified["tasks"]
    feedback_cols = classified["feedback"]
    comment_cols = classified["comments"]
    reviewer_cols = classified["reviewer"]

    has_task = bool(task_cols)
    has_feedback = bool(feedback_cols)
    has_reviewer = bool(reviewer_cols)
    has_comments = bool(comment_cols)

    if student_cols:
        identity = student_cols
    elif generic_cols and has_task and (has_feedback or has_comments or has_reviewer):
        identity = generic_cols
    else:
        return pipeline_error("invalid_csv", NOT_A_PEER_CSV)

    evidence = list(task_cols) + list(feedback_cols)
    if comment_cols and (has_task or (bool(student_cols) and has_reviewer)):
        evidence.extend(comment_cols)
    if not evidence:
        return pipeline_error("invalid_csv", NOT_A_PEER_CSV)

    identity_values = [
        row["cells"][column]
        for row in rows
        for column in identity
        if row["cells"].get(column)
    ]
    if not identity_values or not any(any(character.isalpha() for character in value) for value in identity_values):
        return pipeline_error("invalid_csv", NOT_A_PEER_CSV)

    textual_rows = 0
    numeric_cells = 0
    evidence_cells = 0
    for row in rows:
        if not any(row["cells"].get(column) for column in identity):
            continue
        chunks = [row["cells"].get(column, "") for column in evidence if row["cells"].get(column)]
        blob = " ".join(chunks).strip()
        if _is_textual_evidence(blob):
            textual_rows += 1
        for chunk in chunks:
            evidence_cells += 1
            if _is_number(chunk):
                numeric_cells += 1
    if textual_rows < 1 or (evidence_cells and numeric_cells / evidence_cells > 0.6):
        return pipeline_error("invalid_csv", NOT_A_PEER_CSV)

    return {
        "status": "ok",
        "student_columns": identity,
        "evidence_columns": evidence,
        "reviewer_columns": reviewer_cols,
    }


def _canonical(name: str, alias_map: dict[str, str]) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        return ""
    for key in (cleaned, cleaned.casefold()):
        if key in alias_map:
            return alias_map[key]
    return ""


def _row_index(value: Any) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not number.is_integer():
        return None
    index = int(number)
    return index if index >= 1 else None


def _allowed_score(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and any(abs(number - allowed) < 1e-6 for allowed in _ALLOWED_SCORES)


def _content_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9']+", text.casefold())
        if len(token) >= 4 and token not in _STOPWORDS
    }


def _row_text(row: dict[str, Any]) -> str:
    return " ".join(str(value) for value in row["cells"].values())


def _overlap(evidence: str, row: dict[str, Any]) -> int:
    return len(_content_tokens(evidence) & _content_tokens(_row_text(row)))


def _reviewee(row: dict[str, Any], student_columns: list[str], alias_map: dict[str, str]) -> str:
    for column in student_columns:
        value = str(row["cells"].get(column) or "").strip()
        if not value:
            continue
        canonical = _canonical(value, alias_map)
        if canonical:
            return canonical
    return ""


def validate_scored_actions(
    actions: list[dict[str, Any]],
    loaded: dict[str, Any],
    rules: dict[str, Any],
    student_columns: list[str],
) -> dict[str, Any]:
    """Reject actions that are not supported by the uploaded CSV and rubric."""
    if not actions:
        return pipeline_error("invalid_actions", NO_GROUNDED_ACTIONS)

    criterion_names = {
        " ".join(str(item.get("name") or "").split()).casefold(): " ".join(str(item.get("name") or "").split())
        for item in (rules.get("criteria") or [])
        if str(item.get("name") or "").strip()
    }
    if not criterion_names:
        return pipeline_error("invalid_actions", "No rubric criteria are available, so the peer review cannot be scored.")

    rows = list(loaded.get("rows") or [])
    row_by_index = {int(row["csv_row_index"]): row for row in rows}
    raw_students = [
        row["cells"][column].strip()
        for row in rows
        for column in student_columns
        if str(row["cells"].get(column) or "").strip()
    ]
    action_names = [" ".join(str(action.get("student_name") or "").split()) for action in actions]
    alias_map = cluster_names([*raw_students, *action_names])
    known_students = {_canonical(name, alias_map) for name in raw_students}
    known_students.discard("")

    normalized: list[dict[str, Any]] = []
    failures: list[str] = []
    for action in actions:
        student = " ".join(str(action.get("student_name") or "").split())
        canonical = _canonical(student, alias_map)
        if not student or not canonical or canonical not in known_students:
            failures.append("A scoring action names a student who is not in the peer-review CSV.")
            continue

        criterion_key = " ".join(str(action.get("criterion") or "").split()).casefold()
        if criterion_key not in criterion_names:
            failures.append("A scoring action uses a criterion that is not in the uploaded rubric.")
            continue

        if not _allowed_score(action.get("score")):
            failures.append("A scoring action uses a score outside the allowed values of 0, 5, or 10.")
            continue

        evidence = " ".join(str(action.get("evidence") or "").split())
        if len(evidence) < 8:
            failures.append("A scoring action is not supported by the referenced peer-review row.")
            continue

        index = _row_index(action.get("csv_row_index"))
        cited = row_by_index.get(index or -1)
        if index is None or cited is None:
            failures.append("A scoring action references a CSV row that does not exist.")
            continue

        cited_student = _reviewee(cited, student_columns, alias_map)
        cited_overlap = _overlap(evidence, cited)
        owned = [
            (candidate, _overlap(evidence, candidate))
            for candidate in rows
            if _reviewee(candidate, student_columns, alias_map) == canonical
        ]
        owned_row, owned_overlap = max(owned, key=lambda item: (item[1], -int(item[0]["csv_row_index"]))) if owned else (None, 0)

        grounded_student = canonical
        grounded_row = cited
        if cited_student == canonical and cited_overlap > 0:
            grounded_row = cited
        elif owned_row is not None and owned_overlap > cited_overlap:
            grounded_row = owned_row
            log_event("scoring_row_regrounded", student=canonical, cited_row=index, used_row=grounded_row["csv_row_index"])
        elif cited_overlap > 0 and cited_student:
            grounded_student = cited_student
            grounded_row = cited
            log_event("scoring_student_regrounded", cited_name=canonical, student=cited_student, csv_row_index=index)
        else:
            failures.append(
                "A scoring action points at a CSV row for a different student."
                if cited_student != canonical
                else "A scoring action is not supported by the referenced peer-review row."
            )
            continue

        if _overlap(evidence, grounded_row) <= 0:
            failures.append("A scoring action is not supported by the referenced peer-review row.")
            continue

        normalized.append(
            {
                "student_name": grounded_student,
                "criterion": criterion_names[criterion_key],
                "score": float(action["score"]),
                "csv_row_index": int(grounded_row["csv_row_index"]),
                "evidence": evidence[:280],
            }
        )

    if not normalized:
        return pipeline_error("invalid_actions", failures[0] if failures else NO_GROUNDED_ACTIONS)

    roster = sorted({row["student_name"] for row in normalized})
    return {"status": "ok", "actions": normalized, "roster": roster, "alias_map": alias_map}
