import base64

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import Principal, get_principal
from app.graph.service import get_run_state, resume_pipeline, start_pipeline
from pydantic import BaseModel

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

ALLOWED_IMAGE = {"image/png", "image/jpeg", "image/webp", "image/gif"}


class ResumeRequest(BaseModel):
    approved: bool = True


@router.post("/run")
async def run(
    principal: Principal = Depends(get_principal),
    csv_file: UploadFile = File(...),
    rubric_image: UploadFile = File(...),
):
    csv_name = (csv_file.filename or "").lower()
    if not csv_name.endswith(".csv"):
        raise HTTPException(status_code=400, detail={"status": "error", "reason": "unreadable_data", "message": "Upload a .csv file."})
    mime = rubric_image.content_type or "image/png"
    if mime not in ALLOWED_IMAGE:
        raise HTTPException(status_code=400, detail={"status": "error", "reason": "unreadable_data", "message": "Upload a rubric screenshot image."})
    csv_text = (await csv_file.read()).decode("utf-8", errors="replace")
    image_bytes = await rubric_image.read()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    return start_pipeline(
        csv_text=csv_text,
        image_base64=image_b64,
        image_mime=mime,
        actor_email=principal.email,
        actor_role=principal.role,
    )


@router.get("/{thread_id}")
def status(thread_id: str, _: Principal = Depends(get_principal)):
    return get_run_state(thread_id)


@router.post("/{thread_id}/approve")
def approve(thread_id: str, body: ResumeRequest, principal: Principal = Depends(get_principal)):
    try:
        return resume_pipeline(thread_id, approved=body.approved, approver=principal.email, actor_role=principal.role)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
