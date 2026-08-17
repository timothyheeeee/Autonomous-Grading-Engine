from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import BACKEND_ROOT, get_settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.logging import log_event
from app.db.seed import seed_if_empty
from app.db.session import SessionLocal, init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(BACKEND_ROOT / "data").mkdir(parents=True, exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    log_event("app_startup", environment=settings.environment)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Autonomous Group Assignment & Capability Tracking System",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
