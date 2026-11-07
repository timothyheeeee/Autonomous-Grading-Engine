from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image

from app.config import get_settings
from app.core.logging import log_event
from app.graph.schemas import RubricAssessment, Unreadable
from app.graph.tools.validation import (
    VISION_REQUEST_FAILED,
    VISION_UNCONFIGURED,
    pipeline_error,
    validate_rubric_assessment,
)

VISION_PROMPT = """You are checking a university grading-rubric screenshot.

Set is_valid_rubric to true only when the image itself shows an assessment rubric:
named grading criteria and a scoring scale. Accept different criterion names and layouts.

Set is_valid_rubric to false for photographs, landscapes, food, receipts, invoices,
website screenshots, blank pages, and text that is not a grading rubric.

When it is a rubric, copy the visible title, the scale maximum, and each criterion
name with its description. When it is not, leave criteria empty and explain why in reason.
Never invent criteria, titles, or a scale that are not visible. Do not score students.
"""


def _decode_image(image_base64: str) -> Image.Image:
    payload = image_base64.split(",", 1)[-1]
    raw = base64.b64decode(payload)
    return Image.open(BytesIO(raw))


def assess_image_quality(image_base64: str) -> dict[str, Any] | None:
    try:
        image = _decode_image(image_base64).convert("L")
    except Exception as exc:  # noqa: BLE001
        return Unreadable(message=f"Screenshot could not be opened: {exc}").model_dump()
    width, height = image.size
    if width < 80 or height < 80:
        return Unreadable(message="Screenshot is too small to read.").model_dump()
    pixels = np.asarray(image, dtype=np.float32)
    gy, gx = np.gradient(pixels)
    sharpness = float(gx.var() + gy.var())
    if sharpness < 18:
        return Unreadable(message="Screenshot looks blurry or blank.").model_dump()
    return None


def _llm_assess(image_base64: str, mime: str) -> tuple[RubricAssessment | None, str | None]:
    """Return (assessment, failure). failure is 'unconfigured', 'request_failed', or None."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None, "unconfigured"
    try:
        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(api_key=settings.openai_api_key, model=settings.vision_model, temperature=0)
        structured = llm.with_structured_output(RubricAssessment)
        payload = image_base64.split(",", 1)[-1]
        message = HumanMessage(
            content=[
                {"type": "text", "text": VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{payload}"}},
            ]
        )
        result = structured.invoke([message])
        if isinstance(result, RubricAssessment):
            return result, None
        return RubricAssessment.model_validate(result), None
    except Exception as exc:  # noqa: BLE001
        log_event("vision_llm_failed", error=type(exc).__name__)
        return None, "request_failed"


def extract_rubric_from_image(image_base64: str, mime: str = "image/png") -> dict[str, Any]:
    quality = assess_image_quality(image_base64)
    if quality:
        return quality

    assessment, failure = _llm_assess(image_base64, mime)
    if failure == "unconfigured":
        log_event("vision_rejected", reason="vision_unavailable")
        return pipeline_error("vision_unavailable", VISION_UNCONFIGURED)
    if failure or assessment is None:
        log_event("vision_rejected", reason="vision_request_failed")
        return pipeline_error("vision_unavailable", VISION_REQUEST_FAILED)

    validated = validate_rubric_assessment(assessment)
    if validated.get("status") == "error":
        log_event("vision_rejected", reason="invalid_rubric", model_reason=assessment.reason)
        return validated
    validated["token_usage"] = 0
    return validated
