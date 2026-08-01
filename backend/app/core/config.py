"""Application configuration.

Single source of environment-bound settings. Reads from environment variables
or a local `.env` file (never committed). No business logic here.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Identity
    app_name: str = "AcademicOS"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    version: str = "0.1.0"

    # Relational store (PostgreSQL)
    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/academicos"
    )

    # Vector store (Qdrant)
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # Auth (JWT)
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 3600
    refresh_token_ttl_seconds: int = 604800

    # Web
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
