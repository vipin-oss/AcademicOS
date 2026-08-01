"""JSONB-compatible column type.

On PostgreSQL this emits true ``JSONB`` (the required schema for the ``objects``
table). On other engines (e.g. SQLite, used by the unit-test harness) it degrades
to ``JSON`` so the same models remain importable and testable without a Postgres
server. This keeps the models PostgreSQL-compatible while allowing offline tests.
"""
from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator


class JSONBType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())
