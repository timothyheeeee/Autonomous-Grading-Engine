from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

NAME_HINTS = ("student", "name", "member", "person", "reviewee", "reviewer", "peer", "author")
TASK_HINTS = ("task", "completed", "work", "contribution", "action", "deliverable")
NOTE_HINTS = ("feedback", "note", "comment", "remark", "observation")


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


def classify_columns(columns: list[str]) -> dict[str, list[str]]:
    names: list[str] = []
    tasks: list[str] = []
    notes: list[str] = []
    other: list[str] = []
    for col in columns:
        key = col.casefold().replace("_", " ")
        if any(hint in key for hint in NAME_HINTS):
            names.append(col)
        elif any(hint in key for hint in TASK_HINTS):
            tasks.append(col)
        elif any(hint in key for hint in NOTE_HINTS):
            notes.append(col)
        else:
            other.append(col)
    return {"names": names, "tasks": tasks, "notes": notes, "other": other}
