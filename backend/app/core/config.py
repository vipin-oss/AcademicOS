"""Application configuration.

Single source of environment-bound settings. Reads from environment variables
or a local `.env` file (never committed). No business logic here.
"""
from __future__ import annotations

import json
from functools import lru_cache

from pydantic import field_validator
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

    # File storage (local adapter; Drive/OneDrive adapters plug into the same port)
    storage_dir: str = "./storage"

    # Public base URL of this API, used to build absolute download links
    public_base_url: str = "http://localhost:8000"

    # Auth (JWT)
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 3600
    refresh_token_ttl_seconds: int = 604800

    # Web
    # From .env, list values must use JSON form, e.g. CORS_ORIGINS=["http://localhost:3000"]
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        """Accept both the documented comma-separated form and JSON arrays."""
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                return [str(origin).strip() for origin in json.loads(text)]
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
