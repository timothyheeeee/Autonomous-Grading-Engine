import pytest

from app.graph.tools.calculator import INTERNAL_SCORE_MAX, calculate_normalized_percentages
from app.graph.tools.semantic import extract_scored_actions
from tests.test_input_validation import GROUNDED_CSV, _bad_action
from tests.test_pipeline_tools import RULES


def _score(scale_max: float, score: float):
    rules = {
        "rubric_title": "Uploaded rubric",
        "scale_max": scale_max,
        "criteria": [{"name": "Collaboration", "description": "Works with peers", "max_score": scale_max, "weight": 2}],
    }
    return calculate_normalized_percentages(
        [
            {
                "student_name": "Ada Lovelace",
                "criterion": "Collaboration",
                "score": score,
                "csv_row_index": 1,
                "evidence": "Completed the agreed work",
            }
        ],
        "scale-check",
        rules,
        scale_max,
        ["Ada Lovelace"],
        "Uploaded rubric",
    )


@pytest.mark.parametrize(
    ("scale_max", "score", "expected"),
    [
        (10, 10, 100.0),
        (100, 10, 100.0),
        (5, 10, 100.0),
        (100, 5, 50.0),
        (5, 5, 50.0),
        (20, 0, 0.0),
        (100, 0, 0.0),
    ],
)
def test_internal_percentage_ignores_original_rubric_scale(scale_max, score, expected):
    result = _score(scale_max, score)
    assert result["status"] == "ok"
    student = result["students"][0]
    assert student["criteria"][0]["percentage"] == expected
    assert student["overall_percentage"] == expected
    assert student["criteria"][0]["source_row_ids"] == [1]
    assert INTERNAL_SCORE_MAX == 10.0


def test_contribution_shares_still_sum_to_the_team():
    rules = {"scale_max": 100, "criteria": [{"name": "Collaboration", "weight": 3}]}
    result = calculate_normalized_percentages(
        [
            {"student_name": "Ada", "criterion": "Collaboration", "score": 10, "csv_row_index": 1},
            {"student_name": "Grace", "criterion": "Collaboration", "score": 0, "csv_row_index": 2},
        ],
        "shares",
        rules,
        100,
        ["Ada", "Grace"],
        "Out of 100",
    )
    assert result["status"] == "ok"
    by_name = {row["student_name"]: row for row in result["students"]}
    assert by_name["Ada"]["criteria"][0]["percentage"] == 100.0
    assert by_name["Grace"]["criteria"][0]["percentage"] == 0.0
    assert by_name["Ada"]["contribution_percentage"] == 100.0
    assert by_name["Grace"]["contribution_percentage"] == 0.0
    assert by_name["Grace"]["criteria"][0]["source_row_ids"] == [2]
    total = sum(row["contribution_percentage"] for row in result["students"])
    assert abs(total - 100) < 1.5


@pytest.mark.parametrize("score", [7, 9])
def test_invalid_internal_scores_are_rejected_before_calculation(monkeypatch, score):
    monkeypatch.setattr(
        "app.graph.tools.semantic._llm_extract",
        lambda *_args, **_kwargs: ({"actions": [_bad_action(score=score)], "notes": ""}, 0),
    )
    parsed = extract_scored_actions(GROUNDED_CSV, RULES)
    assert parsed["status"] == "error"
    assert parsed["reason"] == "invalid_actions"
    assert "0, 5, or 10" in parsed["message"]
    assert "actions" not in parsed
