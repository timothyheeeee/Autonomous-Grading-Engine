from typing import Any, Literal

from pydantic import BaseModel, Field


class Unreadable(BaseModel):
    status: Literal["error"] = "error"
    reason: Literal["unreadable_data"] = "unreadable_data"
    message: str = "unreadable_data"


class RubricCriterion(BaseModel):
    name: str
    description: str = ""
    max_score: float = Field(default=10.0, gt=0)
    weight: float = Field(default=1.0, gt=0)


class ExtractedRules(BaseModel):
    status: Literal["ok"] = "ok"
    rubric_title: str
    scale_max: float = 10.0
    criteria: list[RubricCriterion]
    source: str = "vision"


class ScoredAction(BaseModel):
    student_name: str
    criterion: str
    score: float = Field(..., description="Base score assigned from rubric text. Use 10, 5, or 0.")
    csv_row_index: int = Field(default=1, ge=1)
    evidence: str = ""


class SemanticExtraction(BaseModel):
    status: Literal["ok"] = "ok"
    actions: list[ScoredAction]
    notes: str = ""


class CriterionMetric(BaseModel):
    criterion: str
    percentage: float = Field(..., ge=0, le=100)
    source_row_ids: list[int]


class MemberPercentages(BaseModel):
    student_name: str
    criteria: list[CriterionMetric]
    contribution_percentage: float = Field(..., ge=0, le=100)
    overall_percentage: float = Field(..., ge=0, le=100)
    audit: str


class CalculatedPercentages(BaseModel):
    status: Literal["ok"] = "ok"
    correlation_id: str
    rubric_title: str
    students: list[MemberPercentages]
    lineage: dict[str, list[int]] = Field(default_factory=dict)
