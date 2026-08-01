"""Domain-agnostic exception hierarchy.

All raised errors map to an HTTP status. Application/API layers translate
these into responses. No framework imports here (keeps core dependency-free).
"""


class AcademicosError(Exception):
    code: str = "internal_error"
    http_status: int = 500
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        if message:
            self.message = message
        super().__init__(self.message)


class NotFoundError(AcademicosError):
    code = "not_found"
    http_status = 404
    message = "The requested resource was not found."


class UnauthorizedError(AcademicosError):
    code = "unauthorized"
    http_status = 401
    message = "Authentication is required."


class ForbiddenError(AcademicosError):
    code = "forbidden"
    http_status = 403
    message = "You do not have permission to perform this action."


class ConflictError(AcademicosError):
    code = "conflict"
    http_status = 409
    message = "The request conflicts with the current state."


class ValidationError(AcademicosError):
    code = "validation_error"
    http_status = 422
    message = "The request was invalid."
