"""FastAPI application entrypoint.

Wires the Clean-Architecture layers: infrastructure adapters (db, vector_db,
auth) are composed here; API routers expose them. No business logic lives here.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import AcademicosError
from app.core.logging import logger
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.objects import router as objects_router
from app.api.routes.publications import router as publications_router


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="AcademicOS — Object-Centric Knowledge Graph API",
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

    @app.get("/")
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
        }

    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(objects_router, prefix=settings.api_v1_prefix)
    app.include_router(documents_router, prefix=settings.api_v1_prefix)
    app.include_router(publications_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()

logger.info("AcademicOS API initialised (environment=%s)", settings.environment)
