"""FastAPI application entrypoint.

Wires the Clean-Architecture layers: infrastructure adapters (db, vector_db,
auth) are composed here; API routers expose them. No business logic lives here.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.ai import router as ai_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.auth import router as auth_router
from app.api.routes.cdm import router as cdm_router
from app.api.routes.claims import router as claims_router
from app.api.routes.committees import router as committees_router
from app.api.routes.confirmations import router as confirmations_router
from app.api.routes.document_viewer import router as document_viewer_router
from app.api.routes.documents import router as documents_router
from app.api.routes.eval_history import router as eval_history_router
from app.api.routes.events import router as events_router
from app.api.routes.faculty import router as faculty_router
from app.api.routes.finance import router as finance_router
from app.api.routes.health import router as health_router
from app.api.routes.intake import router as intake_router
from app.api.routes.objects import router as objects_router
from app.api.routes.plans import router as plans_router
from app.api.routes.productivity import router as productivity_router
from app.api.routes.publications import router as publications_router
from app.api.routes.reports import router as reports_router
from app.api.routes.research import router as research_router
from app.api.routes.search import router as search_router
from app.api.routes.settings import router as settings_router
from app.api.routes.students import router as students_router
from app.api.routes.teaching import router as teaching_router
from app.api.routes.tools import router as tools_router
from app.application.use_cases.auth.helpers import bootstrap_admin
from app.core.config import settings
from app.core.exceptions import AcademicosError
from app.core.logging import logger
from app.domain.exceptions import OptimisticConcurrencyError
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: on shutdown, release AI Core gateway resources
    exactly once (M11.3.3). The AI Core owns the gateway lifecycle; this wires
    that ownership into the FastAPI shutdown so httpx clients are closed
    gracefully. Best-effort - cleanup never blocks shutdown."""
    yield
    try:
        from app.api.dependencies.ai import reset_ai_core_cache

        reset_ai_core_cache()
    except Exception:  # noqa: BLE001 - cleanup must never break shutdown
        logger.exception("AI Core shutdown cleanup failed")


def create_app() -> FastAPI:
    _bootstrap_admin()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="AcademicOS — Object-Centric Knowledge Graph API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AcademicosError)
    async def handle_academicos_error(
        _: Request, exc: AcademicosError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(OptimisticConcurrencyError)
    async def handle_optimistic_concurrency_error(
        _: Request, exc: OptimisticConcurrencyError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.get("/")
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
        }

    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(ai_router, prefix=settings.api_v1_prefix)
    app.include_router(objects_router, prefix=settings.api_v1_prefix)
    app.include_router(documents_router, prefix=settings.api_v1_prefix)
    app.include_router(document_viewer_router, prefix=settings.api_v1_prefix)
    app.include_router(faculty_router, prefix=settings.api_v1_prefix)
    app.include_router(publications_router, prefix=settings.api_v1_prefix)
    app.include_router(students_router, prefix=settings.api_v1_prefix)
    app.include_router(teaching_router, prefix=settings.api_v1_prefix)
    app.include_router(research_router, prefix=settings.api_v1_prefix)
    app.include_router(committees_router, prefix=settings.api_v1_prefix)
    app.include_router(finance_router, prefix=settings.api_v1_prefix)
    app.include_router(events_router, prefix=settings.api_v1_prefix)
    app.include_router(reports_router, prefix=settings.api_v1_prefix)
    app.include_router(productivity_router, prefix=settings.api_v1_prefix)
    app.include_router(settings_router, prefix=settings.api_v1_prefix)
    app.include_router(assistant_router, prefix=settings.api_v1_prefix)
    app.include_router(eval_history_router, prefix=settings.api_v1_prefix)
    app.include_router(intake_router, prefix=settings.api_v1_prefix)
    app.include_router(search_router, prefix=settings.api_v1_prefix)
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    # L1 knowledge-plane surfaces (ADR-022 OpenAPI contracts).
    app.include_router(claims_router, prefix=settings.api_v1_prefix)
    app.include_router(cdm_router, prefix=settings.api_v1_prefix)
    app.include_router(confirmations_router, prefix=settings.api_v1_prefix)
    app.include_router(plans_router, prefix=settings.api_v1_prefix)
    app.include_router(tools_router, prefix=settings.api_v1_prefix)
    return app


def _bootstrap_admin() -> None:
    """Sprint-1 M3: promote the configured username to ADMIN on first boot."""
    if not settings.bootstrap_admin_username:
        return
    try:
        db = SessionLocal()
        try:
            if bootstrap_admin(SQLAlchemyObjectRepository(db), settings.bootstrap_admin_username):
                logger.info("Bootstrap admin promoted: %s", settings.bootstrap_admin_username)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — bootstrap must never block startup
        logger.exception("Bootstrap admin promotion failed")


app = create_app()

logger.info("AcademicOS API initialised (environment=%s)", settings.environment)
