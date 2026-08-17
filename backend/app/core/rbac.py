from enum import Enum

from fastapi import HTTPException, status


class Role(str, Enum):
    ADMIN = "admin"
    STUDENT = "student"


def is_admin(role: str | Role) -> bool:
    return str(role) == Role.ADMIN.value


def can_execute_tools(role: str | Role) -> bool:
    return is_admin(role)


def require_admin(role: str | Role) -> None:
    if not is_admin(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "reason": "rbac_denied", "message": "Only an admin can run this workflow."},
        )
