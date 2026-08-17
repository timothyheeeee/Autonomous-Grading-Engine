"""Semantic extraction: unstructured CSV + rubric → scored JSON. No percentage math."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import log_event
from app.graph.schemas import ScoredAction, SemanticExtraction
from app.graph.tools.csv_parser import classify_columns, load_unstructured_csv
from app.graph.tools.entities import cluster_names

SEMANTIC_PROMPT = """You are the Semantic Parser for a university group-assessment pipeline.

You receive:
1) Rubric rules JSON (criterion names and descriptions)
2) A raw peer-review CSV. It is UNSTRUCTURED. Typical columns include student names,
   Tasks_Completed, and Feedback_Notes. It does NOT contain criterion or score columns.

Your job:
- Dynamically extract unique student names from the CSV.
- Read Tasks_Completed and Feedback_Notes (and any similar text).
- Map each piece of evidence onto the matching rubric criterion.
- Assign a base score of 10 (exceeds / strong), 5 (meets / mixed), or 0 (does not meet / missing)
  using the rubric text. Do not use any other numbers.
- Do NOT calculate percentages, averages, or contribution shares.

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
    items = list(rules.get("criteria") or [])
    if items:
        return items
    return [
        {"name": "Collaboration", "description": "Works reliably with peers"},
        {"name": "Communication", "description": "Clear written and verbal updates"},
        {"name": "Technical Implementation", "description": "Delivers working technical work"},
        {"name": "Contribution", "description": "Completes assigned tasks"},
        {"name": "Professionalism", "description": "Prepared, respectful, on time"},
    ]


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
        if key in lowered or any(hint in lowered for hint in hints) or (desc and desc[:18] in lowered):
            matched.append(name)
    if not matched:
        fallback = next((str(item.get("name")) for item in criteria if "contrib" in str(item.get("name")).casefold()), None)
        matched = [fallback or str(criteria[0]["name"])]
    return list(dict.fromkeys(matched))


def _heuristic_extract(loaded: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    columns = loaded.get("columns") or []
    classified = classify_columns(columns)
    name_cols = classified["names"] or columns[:1]
    text_cols = classified["tasks"] + classified["notes"] + classified["other"]
    criteria = _criteria(rules)
    raw_names: list[str] = []
    actions: list[dict[str, Any]] = []

    for row in loaded.get("rows") or []:
        cells: dict[str, str] = row["cells"]
        people = [cells[col] for col in name_cols if cells.get(col)]
        raw_names.extend(people)
        student = people[-1] if people else ""
        if not student:
            continue
        evidence = " ".join(cells[col] for col in text_cols if cells.get(col)).strip()
        score = _score_from_text(evidence)
        for criterion in _match_criteria(evidence, criteria):
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
        return {"status": "error", "reason": "unreadable_data", "message": "No student names or review text could be extracted."}

    alias_map = cluster_names(raw_names + [row["student_name"] for row in actions])
    for action in actions:
        action["student_name"] = alias_map.get(action["student_name"], action["student_name"])
    roster = sorted({row["student_name"] for row in actions})
    return {
        "status": "ok",
        "source": "heuristic",
        "roster": roster,
        "actions": actions,
        "max_score": 10.0,
        "rubric_title": rules.get("rubric_title") or "Uploaded rubric",
        "alias_map": alias_map,
    }


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
        names = [item["student_name"] for item in payload["actions"]]
        alias_map = cluster_names(names)
        for item in payload["actions"]:
            item["student_name"] = alias_map.get(item["student_name"], item["student_name"])
            item["score"] = 10.0 if item["score"] >= 8 else 5.0 if item["score"] >= 4 else 0.0
        return {
            "status": "ok",
            "source": "llm",
            "roster": sorted({item["student_name"] for item in payload["actions"]}),
            "actions": payload["actions"],
            "max_score": 10.0,
            "rubric_title": rules.get("rubric_title") or "Uploaded rubric",
            "alias_map": alias_map,
            "notes": payload.get("notes") or "",
        }, 0
    except Exception as exc:  # noqa: BLE001
        log_event("semantic_llm_failed", error=str(exc))
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
    llm_result, tokens = _llm_extract(csv_text, rules)
    if llm_result:
        llm_result["token_usage"] = tokens
        log_event("semantic_extract", source="llm", actions=len(llm_result["actions"]), roster=llm_result["roster"])
        return llm_result
    heuristic = _heuristic_extract(loaded, rules)
    heuristic["token_usage"] = tokens
    log_event(
        "semantic_extract",
        source=heuristic.get("source"),
        actions=len(heuristic.get("actions") or []),
        roster=heuristic.get("roster"),
    )
    return heuristic
