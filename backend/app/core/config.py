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
    # Password-reset tokens are short-lived by design (30 minutes).
    password_reset_token_ttl_seconds: int = 1800

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

    # ---- AI Core (Sprint M11.1 — AI Foundation) ---------------------------
    # Master switch for the AI surface (/ai/health reports "disabled" when
    # off). No M1–M10 behavior depends on it.
    ai_enabled: bool = True
    # The catalogue provider used when no explicit provider is requested.
    # M11.1 has no wired adapters — the value selects the default row in
    # the settings surface and the target for future gateway() calls.
    ai_default_provider: str = "local"
    # Default model id; empty means "the provider's own default".
    ai_default_model: str = ""
    # Generation defaults (used by future adapters; placeholders ignore).
    ai_temperature: float = 0.0
    ai_max_tokens: int = 2048
    ai_timeout_seconds: float = 30.0
    ai_streaming_enabled: bool = True
    # Feature flags for future M11 sprints. All default OFF: the AI Core
    # surface (health/providers/models) is the only M11.1 capability.
    ai_chat_enabled: bool = False
    ai_rag_enabled: bool = False
    ai_memory_enabled: bool = False
    ai_agents_enabled: bool = False
    ai_document_understanding_enabled: bool = False
    # Provider configuration: JSON list of entries, e.g.
    #   [{"provider_id": "openai", "kind": "openai", "model": "gpt-4o-mini",
    #     "base_url": "", "timeout_seconds": 30, "max_tokens": 2048,
    #     "temperature": 0.0, "streaming_enabled": true}]
    # No credentials are stored or read anywhere in M11.1.
    ai_providers_json: str = ""

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
    # All three canonical local dev origins are allowed: browsers open the
    # dev app at `localhost` OR `127.0.0.1` (and on Windows, `localhost`
    # frequently resolves IPv6-first, yielding `[::1]`). A JSON POST (login
    # included) is preflighted, and the preflight fails for any origin not
    # in this list — a one-origin allowlist silently breaks authentication
    # on fresh setups that open the app at 127.0.0.1.
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
    ]

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
