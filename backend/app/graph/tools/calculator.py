from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from app.core.logging import log_event


class CalculateInput(BaseModel):
    actions: list[dict[str, Any]] = Field(..., description="LLM-scored actions only. Never the raw CSV.")
    extracted_rules: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    max_score: float = 10.0
    roster: list[str] = Field(default_factory=list)
    rubric_title: str = "Uploaded rubric"


def _round_pct(value: float) -> float:
    return round(float(value), 1)


def calculate_normalized_percentages(
    actions: list[dict[str, Any]],
    correlation_id: str,
    extracted_rules: dict[str, Any] | None = None,
    max_score: float = 10.0,
    roster: list[str] | None = None,
    rubric_title: str = "Uploaded rubric",
) -> dict[str, Any]:
    """Deterministic percentage math over LLM JSON only."""
    try:
        if not actions:
            return {"status": "error", "reason": "unreadable_data", "message": "No scored actions were handed off."}

        df = pd.DataFrame(actions)
        if "student_name" not in df.columns and "reviewee" in df.columns:
            df = df.rename(columns={"reviewee": "student_name"})
        if "score" not in df.columns and "raw_score" in df.columns:
            df = df.rename(columns={"raw_score": "score"})
        required = {"student_name", "criterion", "score"}
        if required - set(df.columns):
            return {
                "status": "error",
                "reason": "unreadable_data",
                "message": "LLM payload is missing student_name, criterion, or score.",
            }

        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        if "csv_row_index" in df.columns:
            df["csv_row_index"] = pd.to_numeric(df["csv_row_index"], errors="coerce").fillna(0)
        else:
            df["csv_row_index"] = range(1, len(df) + 1)
        df = df.dropna(subset=["score", "student_name", "criterion"])
        if df.empty:
            return {"status": "error", "reason": "unreadable_data", "message": "Scored JSON had no usable rows."}

        ceiling = float((extracted_rules or {}).get("scale_max") or max_score or 10.0)
        if ceiling <= 0:
            ceiling = 10.0
        weights = {
            str(item.get("name")): float(item.get("weight") or 1.0)
            for item in (extracted_rules or {}).get("criteria") or []
            if item.get("name")
        }
        df["weight"] = df["criterion"].map(lambda name: weights.get(str(name), 1.0))
        df["row_percentage"] = (df["score"] / ceiling) * 100.0

        grouped = df.groupby(["student_name", "criterion"], as_index=False).agg(
            percentage=("row_percentage", "mean"),
            source_row_ids=("csv_row_index", lambda series: sorted({int(v) for v in series if int(v) > 0})),
        )
        student_mass = df.groupby("student_name")["row_percentage"].sum()
        team_mass = float(student_mass.sum())
        if team_mass <= 0:
            return {"status": "error", "reason": "unreadable_data", "message": "Cannot normalize a zero team mass."}

        names = list(roster or sorted({str(name) for name in df["student_name"].tolist()}))
        students: list[dict[str, Any]] = []
        lineage: dict[str, list[int]] = {}
        for name in names:
            subset = grouped[grouped["student_name"] == name]
            criteria = [
                {
                    "criterion": row.criterion,
                    "percentage": _round_pct(min(row.percentage, 100)),
                    "source_row_ids": row.source_row_ids,
                }
                for row in subset.itertuples(index=False)
            ]
            overall = _round_pct(float(subset["percentage"].mean())) if not subset.empty else 0.0
            contribution = _round_pct((float(student_mass.get(name, 0.0)) / team_mass) * 100.0)
            for item in criteria:
                lineage[f"{name}::{item['criterion']}"] = item["source_row_ids"]
            students.append(
                {
                    "student_name": name,
                    "criteria": criteria,
                    "contribution_percentage": contribution,
                    "overall_percentage": overall,
                    "audit": (
                        f"LLM-scored evidence for {name} was converted into percentages. "
                        f"Contribution share is {contribution}% of the team."
                    ),
                }
            )

        log_event("tool_calculate_percentages", students=len(students), correlation_id=correlation_id)
        return {
            "status": "ok",
            "correlation_id": correlation_id,
            "rubric_title": rubric_title or (extracted_rules or {}).get("rubric_title") or "Uploaded rubric",
            "students": students,
            "lineage": lineage,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": "unreadable_data", "message": f"Percentage calculation failed: {exc}"}
