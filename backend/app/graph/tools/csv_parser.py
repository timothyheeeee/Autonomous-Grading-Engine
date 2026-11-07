from __future__ import annotations

import re
from io import StringIO
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

# Phrases are matched on word boundaries. "name" must not match "username".
_STUDENT_PHRASES = (
    "reviewed student",
    "student name",
    "team member",
    "member name",
    "reviewee",
    "teammate",
    "assessee",
    "student",
)
_GENERIC_NAME_PHRASES = ("full name", "person", "name")
_REVIEWER_PHRASES = ("peer reviewer", "reviewer", "assessor", "evaluator", "rater")
_TASK_PHRASES = (
    "tasks completed",
    "task completed",
    "work completed",
    "contribution",
    "deliverable",
    "responsibilities",
    "responsibility",
    "completed",
    "tasks",
    "task",
)
_FEEDBACK_PHRASES = ("peer feedback", "feedback notes", "review notes", "feedback", "observation", "remark")
_COMMENT_PHRASES = ("comments", "comment", "notes", "note")


class LoadCsvInput(BaseModel):
    csv_text: str = Field(..., description="Raw sanitized CSV text. Must not be scored by this loader.")


def load_unstructured_csv(csv_text: str) -> dict[str, Any]:
    """Load CSV rows as text. Never look for criterion or score columns."""
    try:
        df = pd.read_csv(StringIO(csv_text), dtype=str, keep_default_na=False)
        if df.empty or len(df.columns) == 0:
            return {"status": "error", "reason": "unreadable_data", "message": "CSV is empty."}
        df.columns = [str(col).strip() for col in df.columns]
        rows: list[dict[str, Any]] = []
        for offset, row in df.iterrows():
            cells = {str(col): str(row[col]).strip() for col in df.columns if str(row[col]).strip()}
            if cells:
                rows.append({"csv_row_index": int(offset) + 1, "cells": cells})
        if not rows:
            return {"status": "error", "reason": "unreadable_data", "message": "CSV contained no text rows."}
        return {
            "status": "ok",
            "columns": list(df.columns),
            "rows": rows,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": "unreadable_data", "message": f"CSV could not be read: {exc}"}


def _column_key(column: str) -> str:
    return re.sub(r"\s+", " ", column.casefold().replace("_", " ").replace("-", " ")).strip()


def _has_phrase(column_key: str, phrase: str) -> bool:
    padded = f" {column_key} "
    return f" {phrase} " in padded or f" {phrase}s " in padded


def _matches(column_key: str, phrases: tuple[str, ...]) -> bool:
    return any(_has_phrase(column_key, phrase) for phrase in phrases)


def classify_columns(columns: list[str]) -> dict[str, list[str]]:
    """Split columns by peer-review role. Never treat column position as meaning."""
    student: list[str] = []
    generic_name: list[str] = []
    reviewer: list[str] = []
    tasks: list[str] = []
    feedback: list[str] = []
    comments: list[str] = []
    other: list[str] = []
    for col in columns:
        key = _column_key(col)
        if _matches(key, _REVIEWER_PHRASES):
            reviewer.append(col)
        elif _matches(key, _STUDENT_PHRASES):
            student.append(col)
        elif _matches(key, _GENERIC_NAME_PHRASES):
            generic_name.append(col)
        elif _matches(key, _TASK_PHRASES):
            tasks.append(col)
        elif _matches(key, _FEEDBACK_PHRASES):
            feedback.append(col)
        elif _matches(key, _COMMENT_PHRASES):
            comments.append(col)
        else:
            other.append(col)
    return {
        "student": student,
        "generic_name": generic_name,
        "reviewer": reviewer,
        "tasks": tasks,
        "feedback": feedback,
        "comments": comments,
        "other": other,
        "names": student or generic_name,
        "notes": feedback + comments,
    }
