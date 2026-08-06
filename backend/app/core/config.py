"""Application configuration.

Single source of environment-bound settings. Reads from environment variables
or a local `.env` file (never committed). No business logic here.
"""
from __future__ import annotations

import json
from functools import lru_cache

from pydantic import field_validator, model_validator
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

    # RBAC (Sprint-1 M3): username promoted to ADMIN at startup if it has
    # no roles yet (first-admin bootstrap; idempotent).
    bootstrap_admin_username: str | None = None

    # LLM assistant provider (Sprint-6 M2): OpenAI-compatible chat
    # completions. The provider is ENABLED only when a base URL is set;
    # without one the assistant stays on the deterministic rules provider.
    # An empty API key is allowed (self-hosted endpoints often need none);
    # the key is sent as "Bearer <key>" when present.
    assistant_llm_base_url: str | None = None
    assistant_llm_model: str = "academicos-default"
    assistant_llm_api_key: str = ""
    assistant_llm_timeout_seconds: float = 30.0

    # Assistant human-review gate (Sprint-6 M5): when enabled, fresh
    # assistant answers are stored as PENDING and only become visible after
    # a human approves them via /assistant/review/*.
    assistant_review_enabled: bool = False

    # Model registry (Sprint-7 M1): the single source of truth for
    # assistant models. JSON list of specs, e.g.
    #   [{"id": "main", "base_url": "http://llm:8000/v1", "model": "m1"},
    #    {"id": "rules", "provider_kind": "rules", "model": "rules-v1"}]
    # Empty (default): the legacy single-model settings below synthesize
    # one "default" spec — zero-config backward compatibility.
    assistant_models_json: str = ""
    assistant_default_model: str = "default"

    @model_validator(mode="after")
    def _reject_insecure_default_secret(self) -> Settings:
        # Sprint-1 auth foundation: the default JWT secret must never run in
        # a non-development environment. Failing fast at startup beats
        # shipping forged tokens.
        if (
            self.environment not in ("development", "test")
            and self.jwt_secret == "change-me-in-production"
        ):
            raise ValueError(
                "JWT_SECRET must be set to a non-default value outside development."
            )
        return self

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
