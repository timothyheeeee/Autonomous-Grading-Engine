from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.rbac import require_admin
from app.core.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


class Principal:
    def __init__(self, email: str, role: str, full_name: str):
        self.email = email
        self.role = role
        self.full_name = full_name


def get_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        payload = decode_access_token(creds.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    role = str(payload.get("role") or "")
    require_admin(role)
    return Principal(email=str(payload.get("sub") or "admin"), role=role, full_name=str(payload.get("name") or "Admin"))
