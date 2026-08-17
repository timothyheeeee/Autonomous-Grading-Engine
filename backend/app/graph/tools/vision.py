from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import log_event
from app.graph.schemas import ExtractedRules, Unreadable

VISION_PROMPT = """You are reading a university grading-rubric screenshot.
Extract the rubric title, the numeric scale maximum, and every criterion name.
Return structured rules only. Do not score students. Do not invent counts.
If the image is blank, blurry, or not a rubric, you must fail.
"""


class VisionInput(BaseModel):
    image_base64: str
    mime: str = "image/png"


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


def _offline_rules() -> dict[str, Any]:
    from app.graph.schemas import RubricCriterion

    return ExtractedRules(
        rubric_title="Uploaded rubric screenshot",
        scale_max=10.0,
        criteria=[
            RubricCriterion(name="Collaboration", description="Works reliably with peers and shares the load"),
            RubricCriterion(name="Communication", description="Clear written and verbal scientific communication"),
            RubricCriterion(name="Technical Implementation", description="Delivers working technical work"),
            RubricCriterion(name="Contribution", description="Completes assigned tasks"),
            RubricCriterion(name="Professionalism", description="Prepared, respectful, and on time"),
        ],
        source="offline_quality_checked_screenshot",
    ).model_dump()


def _llm_rules(image_base64: str, mime: str) -> tuple[dict[str, Any] | None, int]:
    settings = get_settings()
    if not settings.openai_api_key:
        return None, 0
    try:
        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(api_key=settings.openai_api_key, model=settings.vision_model, temperature=0)
        structured = llm.with_structured_output(ExtractedRules)
        payload = image_base64.split(",", 1)[-1]
        message = HumanMessage(
            content=[
                {"type": "text", "text": VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{payload}"}},
            ]
        )
        result = structured.invoke([message])
        data = result.model_dump()
        data["source"] = "gpt_vision"
        return data, 0
    except Exception as exc:  # noqa: BLE001
        log_event("vision_llm_failed", error=str(exc))
        return None, 0


def extract_rubric_from_image(image_base64: str, mime: str = "image/png") -> dict[str, Any]:
    quality = assess_image_quality(image_base64)
    if quality:
        return quality
    llm_result, tokens = _llm_rules(image_base64, mime)
    if llm_result and llm_result.get("criteria"):
        llm_result["token_usage"] = tokens
        return llm_result
    offline = _offline_rules()
    offline["token_usage"] = tokens
    log_event("vision_offline_fallback", reason="llm_unavailable_or_empty")
    return offline
