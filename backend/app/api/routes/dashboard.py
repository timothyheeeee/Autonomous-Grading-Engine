from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal
from app.db.models import PublishedMetric
from app.db.session import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/metrics")
def metrics(_: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    rows = db.query(PublishedMetric).all()
    by_student: dict[str, dict] = {}
    for row in rows:
        bucket = by_student.setdefault(
            row.student_name,
            {
                "student_name": row.student_name,
                "overall_percentage": row.overall_percentage,
                "contribution_percentage": row.contribution_percentage,
                "criteria": [],
            },
        )
        bucket["criteria"].append(
            {
                "criterion": row.criterion,
                "percentage": row.percentage,
                "source_row_ids": [int(x) for x in row.source_row_ids.split(",") if x],
            }
        )
    contribution = [
        {"student": s["student_name"], "percentage": s["contribution_percentage"]}
        for s in sorted(by_student.values(), key=lambda item: item["student_name"])
    ]
    criteria: dict[str, list] = defaultdict(list)
    for student in by_student.values():
        for item in student["criteria"]:
            criteria[item["criterion"]].append(
                {"student": student["student_name"], "percentage": item["percentage"], "source_row_ids": item["source_row_ids"]}
            )
    return {
        "unit": "%",
        "note": "All values are survey-normalized percentages. Raw tallies are never returned.",
        "students": list(by_student.values()),
        "charts": {"contribution": contribution, "criteria": criteria},
    }
