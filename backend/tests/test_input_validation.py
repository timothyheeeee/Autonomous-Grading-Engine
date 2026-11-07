import base64
from io import BytesIO

import numpy as np
import pytest
from langgraph.checkpoint.memory import MemorySaver
from PIL import Image, ImageDraw

from app.db.models import PublishedMetric
from app.db.session import SessionLocal, init_db
from app.graph.compile import build_graph
from app.graph.schemas import RubricAssessment, RubricCriterion
from app.graph.tools.semantic import extract_scored_actions
from app.graph.tools.validation import NOT_A_PEER_CSV, NOT_A_RUBRIC, VISION_REQUEST_FAILED, VISION_UNCONFIGURED
from app.graph.tools.vision import assess_image_quality, extract_rubric_from_image
from tests.test_pipeline_tools import RULES, UNSTRUCTURED, _b64, _png_bytes, _rubric_assessment

PRODUCT_CSV = "Product,Price,Quantity\nApple,3.50,100\nOrange,2.00,250\n"
WEATHER_CSV = "City,Temperature,Humidity\nSydney,25,60\nMelbourne,21,70\n"
EMPLOYEE_CSV = "Name,Age,Department\nAlice,25,Sales\nBob,30,Finance\n"
ALT_CSV = (
    "Student Name,Contribution,Peer Feedback\n"
    "Alice Chen,Completed the backend API,Strong technical contribution\n"
    "Bob Singh,Prepared the presentation,Clear communication\n"
)
EMPTY_HEADER_CSV = "Student,Feedback Notes\n"
NO_EVIDENCE_CSV = "Student,Email\nAlice,alice@university.edu\nBob,bob@university.edu\n"
COMMENTS_ONLY_CSV = "Name,Comments\nAlice,Nice person\nBob,Good colleague\n"
GROUNDED_CSV = (
    "Reviewer,Student,Tasks Completed,Feedback Notes\n"
    "Mina,Alice Chen,Completed the backend API,Strong technical contribution\n"
)


def _photo_b64() -> str:
    array = np.random.default_rng(1).integers(0, 255, size=(360, 480, 3), dtype=np.uint8)
    image = Image.fromarray(array, mode="RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _receipt_b64() -> str:
    image = Image.new("RGB", (640, 400), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(["Order summary", "Subtotal 42.00", "Tax 4.20", "Total due 46.20"]):
        draw.text((24, 24 + index * 28), line, fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _run(csv_text: str, image: str, thread: str, monkeypatch, assessment: RubricAssessment | None):
    if assessment is None:
        monkeypatch.setattr("app.graph.tools.vision._llm_assess", lambda *_args, **_kwargs: (None, "unconfigured"))
    else:
        monkeypatch.setattr(
            "app.graph.tools.vision._llm_assess",
            lambda *_args, _assessment=assessment, **_kwargs: (_assessment, None),
        )
    init_db()
    db = SessionLocal()
    try:
        before = db.query(PublishedMetric).count()
    finally:
        db.close()
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": thread}, "recursion_limit": 8}
    result = graph.invoke(
        {
            "rubric_image_base64": image,
            "image_mime": "image/png",
            "raw_csv_text": csv_text,
            "actor_role": "admin",
            "actor_email": "admin@local",
            "correlation_id": thread,
            "thread_id": thread,
            "vision_failures": 0,
            "token_usage": 0,
            "hitl_approved": False,
            "audit_trail": [],
            "traces": [],
            "current_errors": [],
            "calculated_percentages": {},
        },
        config=config,
    )
    db = SessionLocal()
    try:
        after = db.query(PublishedMetric).count()
    finally:
        db.close()
    return result, graph.get_state(config), before, after


def _nodes(result: dict) -> list[str]:
    return [trace.get("node") for trace in result.get("traces") or []]


def test_valid_peer_review_and_rubric_reach_human_approval(monkeypatch):
    parsed = extract_scored_actions(UNSTRUCTURED, RULES)
    assert parsed["status"] == "ok"
    assert parsed["roster"]
    assert all(action["score"] in {0, 5, 10} for action in parsed["actions"])

    result, snapshot, before, after = _run(UNSTRUCTURED, _b64(_png_bytes(720, 480)), "valid-hitl", monkeypatch, _rubric_assessment())
    assert snapshot.next == ("save_to_database",)
    assert result["calculated_percentages"]["status"] == "ok"
    assert "save_to_database" not in _nodes(result)
    assert after == before


@pytest.mark.parametrize(
    ("image_factory", "assessment"),
    [
        (_photo_b64, RubricAssessment(is_valid_rubric=False, reason="A photograph of a dog.", criteria=[], scale_max=None)),
        (
            _receipt_b64,
            RubricAssessment(
                is_valid_rubric=True,
                reason="Page of totals.",
                rubric_title="Order summary",
                scale_max=10,
                criteria=[
                    RubricCriterion(name="Subtotal", description="Amount"),
                    RubricCriterion(name="Tax", description="Sales tax"),
                ],
            ),
        ),
    ],
)
def test_unrelated_images_are_rejected(image_factory, assessment, monkeypatch):
    image = image_factory()
    assert assess_image_quality(image) is None
    monkeypatch.setattr("app.graph.tools.vision._llm_assess", lambda *_args, **_kwargs: (assessment, None))
    result = extract_rubric_from_image(image)
    assert result["status"] == "error"
    assert result["reason"] == "invalid_rubric"
    assert result["message"] == NOT_A_RUBRIC
    assert "criteria" not in result


def test_empty_or_blurry_image_is_rejected_without_calling_the_model(monkeypatch):
    monkeypatch.setattr(
        "app.graph.tools.vision._llm_assess",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("vision model should not run")),
    )
    blurry = assess_image_quality(_b64(_png_bytes(200, 200, text=False, fill="gray")))
    assert blurry is not None
    assert blurry["reason"] == "unreadable_data"
    tiny = extract_rubric_from_image(_b64(_png_bytes(40, 40, text=False)))
    assert tiny["status"] == "error"
    assert tiny["reason"] == "unreadable_data"
    assert "criteria" not in tiny


@pytest.mark.parametrize("csv_text", [PRODUCT_CSV, WEATHER_CSV, EMPLOYEE_CSV, NO_EVIDENCE_CSV, COMMENTS_ONLY_CSV])
def test_unrelated_or_evidenceless_csv_is_rejected(csv_text):
    parsed = extract_scored_actions(csv_text, RULES)
    assert parsed["status"] == "error"
    assert parsed["reason"] == "invalid_csv"
    assert parsed["message"] == NOT_A_PEER_CSV
    assert "actions" not in parsed


def test_alternative_peer_review_columns_are_accepted():
    parsed = extract_scored_actions(ALT_CSV, RULES)
    assert parsed["status"] == "ok"
    assert "Alice Chen" in parsed["roster"]
    assert "Bob Singh" in parsed["roster"]
    assert all(action["score"] in {0, 5, 10} for action in parsed["actions"])
    assert {action["criterion"] for action in parsed["actions"]} <= {item["name"] for item in RULES["criteria"]}


@pytest.mark.parametrize("csv_text", ["", "   ", EMPTY_HEADER_CSV])
def test_empty_csv_is_rejected(csv_text):
    parsed = extract_scored_actions(csv_text, RULES)
    assert parsed["status"] == "error"
    assert parsed["reason"] == "unreadable_data"
    assert "actions" not in parsed


def test_missing_rubric_criteria_are_not_invented():
    parsed = extract_scored_actions(GROUNDED_CSV, {"scale_max": 10, "criteria": []})
    assert parsed["status"] == "error"
    assert parsed["reason"] == "invalid_actions"
    assert "actions" not in parsed


def _bad_action(**overrides):
    action = {
        "student_name": "Alice Chen",
        "criterion": "Technical Implementation",
        "score": 10,
        "csv_row_index": 1,
        "evidence": "Completed the backend API",
    }
    action.update(overrides)
    return action


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"criterion": "Punctuality"}, "not in the uploaded rubric"),
        ({"csv_row_index": 99}, "does not exist"),
        ({"score": 7}, "0, 5, or 10"),
        ({"evidence": "Entirely unrelated quantum biology"}, "not supported"),
        ({"student_name": "Nobody Person"}, "not in the peer-review CSV"),
    ],
)
def test_ungrounded_scoring_actions_are_rejected(monkeypatch, overrides, fragment):
    monkeypatch.setattr(
        "app.graph.tools.semantic._llm_extract",
        lambda *_args, **_kwargs: ({"actions": [_bad_action(**overrides)], "notes": ""}, 0),
    )
    parsed = extract_scored_actions(GROUNDED_CSV, RULES)
    assert parsed["status"] == "error"
    assert parsed["reason"] == "invalid_actions"
    assert fragment in parsed["message"]
    assert "actions" not in parsed


TWO_ROW_CSV = (
    "Reviewer,Student,Tasks Completed,Feedback Notes\n"
    "Alice Chen,Bob Singh,Completed the backend API,Strong technical contribution\n"
    "Bob Singh,Alice Chen,Prepared the presentation,Clear communication\n"
)


def test_mismatched_row_is_regrounded_to_that_students_review(monkeypatch):
    monkeypatch.setattr(
        "app.graph.tools.semantic._llm_extract",
        lambda *_args, **_kwargs: (
            {
                "actions": [
                    _bad_action(
                        student_name="Bob Singh",
                        csv_row_index=2,
                        evidence="Completed the backend API",
                    )
                ],
                "notes": "",
            },
            0,
        ),
    )
    parsed = extract_scored_actions(TWO_ROW_CSV, RULES)
    assert parsed["status"] == "ok"
    assert parsed["actions"][0]["student_name"] == "Bob Singh"
    assert parsed["actions"][0]["csv_row_index"] == 1


def test_reviewer_name_is_regrounded_to_the_reviewee(monkeypatch):
    monkeypatch.setattr(
        "app.graph.tools.semantic._llm_extract",
        lambda *_args, **_kwargs: (
            {
                "actions": [
                    _bad_action(
                        student_name="Alice Chen",
                        csv_row_index=1,
                        evidence="Completed the backend API and a strong technical contribution",
                    )
                ],
                "notes": "",
            },
            0,
        ),
    )
    parsed = extract_scored_actions(TWO_ROW_CSV, RULES)
    assert parsed["status"] == "ok"
    assert parsed["actions"][0]["student_name"] == "Bob Singh"
    assert parsed["actions"][0]["csv_row_index"] == 1


def test_unconfigured_vision_does_not_invent_a_rubric():
    result = extract_rubric_from_image(_b64(_png_bytes(640, 400, text=True)))
    assert result == {"status": "error", "reason": "vision_unavailable", "message": VISION_UNCONFIGURED}


def test_failed_vision_request_does_not_invent_a_rubric(monkeypatch):
    class ExplodingClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(
        "app.graph.tools.vision.get_settings",
        lambda: type("Settings", (), {"openai_api_key": "sk-test", "vision_model": "gpt-4o"})(),
    )
    import langchain_openai

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", ExplodingClient)
    result = extract_rubric_from_image(_b64(_png_bytes(640, 400, text=True)))
    assert result["status"] == "error"
    assert result["reason"] == "vision_unavailable"
    assert result["message"] == VISION_REQUEST_FAILED
    assert "criteria" not in result
    assert "connection refused" not in result["message"]


def test_rejected_inputs_never_reach_publication(monkeypatch):
    image = _b64(_png_bytes(640, 400, text=True))
    photo, photo_state, photo_before, photo_after = _run(UNSTRUCTURED, _photo_b64(), "reject-photo", monkeypatch, RubricAssessment(is_valid_rubric=False, reason="dog"))
    inventory, inventory_state, inventory_before, inventory_after = _run(PRODUCT_CSV, image, "reject-inventory", monkeypatch, _rubric_assessment())
    unconfigured, unconfigured_state, bare_before, bare_after = _run(UNSTRUCTURED, image, "reject-unconfigured", monkeypatch, None)

    for result, snapshot, before, after in (
        (photo, photo_state, photo_before, photo_after),
        (inventory, inventory_state, inventory_before, inventory_after),
        (unconfigured, unconfigured_state, bare_before, bare_after),
    ):
        assert snapshot.next != ("save_to_database",)
        assert "calculate" not in _nodes(result)
        assert "save_to_database" not in _nodes(result)
        assert result.get("halt_reason")
        assert (result.get("calculated_percentages") or {}).get("status") != "ok"
        assert after == before


def test_placeholder_criterion_is_not_accepted_as_a_rubric():
    from app.graph.tools.validation import validate_rubric_assessment

    result = validate_rubric_assessment(
        RubricAssessment(
            is_valid_rubric=True,
            reason="json only",
            rubric_title="Untitled",
            scale_max=10,
            criteria=[RubricCriterion(name="N/A", description="")],
        )
    )
    assert result["status"] == "error"
    assert result["message"] == NOT_A_RUBRIC
