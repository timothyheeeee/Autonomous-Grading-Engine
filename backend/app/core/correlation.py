from contextvars import ContextVar
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def get_correlation_id() -> str:
    return correlation_id_var.get() or new_correlation_id()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-correlation-id") or new_correlation_id()
        token = correlation_id_var.set(incoming)
        try:
            response = await call_next(request)
            response.headers["x-correlation-id"] = incoming
            return response
        finally:
            correlation_id_var.reset(token)
