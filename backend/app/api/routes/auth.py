from fastapi import APIRouter

from app.core.security import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/bootstrap")
def bootstrap():
    """Mock admin JWT for the local console. Upload routes still verify role=admin."""
    token = create_access_token("admin@local", "admin", "Administrator")
    return {"access_token": token, "token_type": "bearer", "role": "admin"}
