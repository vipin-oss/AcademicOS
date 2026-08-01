"""Application-layer exceptions.

Distinct from ``app.domain.exceptions.DomainError``. These represent
use-case / boundary failures (invalid input, not-found, conflicts) and are the
types the presentation layer catches and maps to responses.

Framework-independent by design: no HTTP status codes, no transport details.
The API layer translates these to responses much later.
"""
from __future__ import annotations


class ApplicationError(Exception):
    code: str = "application_error"


class ValidationError(ApplicationError):
    code = "validation_error"

    def __init__(self, message: str, *, field: str | None = None) -> None:
        self.field = field
        self.message = message
        super().__init__(message)


class ObjectAlreadyExistsError(ApplicationError):
    code = "object_already_exists"


class ObjectNotFoundError(ApplicationError):
    code = "object_not_found"
