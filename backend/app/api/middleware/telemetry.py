"""Request telemetry middleware (V3 M1 — Instrumentation & Truthful Baseline).

The single place where every HTTP request acquires an identity and a measured
duration. Blueprint V3 M1: *you cannot optimize or gate on what you cannot
measure* — every later milestone's latency claim is verified against the
baseline this middleware produces.

Contract (V3 §M1):

- ``request_id`` — per-request identity; echoed as the ``X-Request-ID``
  response header and attached to the request state so downstream code and
  logs can correlate. An inbound ``X-Request-ID`` is honoured (clients and
  proxies may already carry one); otherwise one is generated.
- ``trace_id`` — correlation across a multi-request user action. Honoured
  from ``X-Trace-ID`` when supplied, else equal to ``request_id``.
- ``total_ms`` — wall-clock duration of the whole request, measured with a
  monotonic clock, emitted as the ``X-Response-Time-Ms`` header.

Stage timings (``*_ms``) are recorded by the code that owns each stage
through the ``RequestTelemetry`` accessor below; this middleware owns only
the envelope. Nothing here is business logic and nothing here may fail a
request: telemetry is best-effort by construction.

Deliberately NOT here (V3 discipline — no speculative infrastructure):
no metrics backend, no tracing exporter, no sampling, no log shipping. The
timings land in the structured log line and the response headers, which is
what M1 needs to produce a baseline report.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import logger

#: Response/request header names (stable contract — clients may rely on them).
HEADER_REQUEST_ID = "X-Request-ID"
HEADER_TRACE_ID = "X-Trace-ID"
HEADER_RESPONSE_TIME = "X-Response-Time-Ms"

#: Paths excluded from telemetry logging (noise, not signal). They still get
#: identity headers — only the log line is suppressed.
_QUIET_PATHS = frozenset({"/", "/docs", "/redoc", "/openapi.json", "/favicon.ico"})


class RequestTelemetry:
    """Per-request telemetry accumulator, reachable via ``request.state``.

    Stage owners record their own durations::

        telemetry = RequestTelemetry.of(request)
        if telemetry is not None:
            telemetry.record("vector_retrieval_ms", 42.0)

    The accessor is null-safe by design: code paths exercised in unit tests
    (no middleware, no ``request``) must never break because telemetry is
    absent. That is why ``of()`` returns ``None`` rather than raising.
    """

    __slots__ = ("request_id", "trace_id", "_started", "_stages", "_facts")

    def __init__(self, request_id: str, trace_id: str) -> None:
        self.request_id = request_id
        self.trace_id = trace_id
        self._started = time.perf_counter()
        self._stages: dict[str, float] = {}
        self._facts: dict[str, object] = {}

    # ------------------------------------------------------------ recording
    def record(self, stage: str, milliseconds: float) -> None:
        """Record (or accumulate) a stage duration in milliseconds."""
        if milliseconds < 0:
            return
        self._stages[stage] = round(self._stages.get(stage, 0.0) + milliseconds, 3)

    def fact(self, key: str, value: object) -> None:
        """Attach a non-timing fact (``rung``, ``source_class``, ``model_used``…)."""
        self._facts[key] = value

    def elapsed_ms(self) -> float:
        """Wall-clock milliseconds since the request began."""
        return round((time.perf_counter() - self._started) * 1000.0, 3)

    # ------------------------------------------------------------- rendering
    def snapshot(self) -> dict[str, object]:
        """The full telemetry record for logging / diagnostics."""
        payload: dict[str, object] = {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "total_ms": self.elapsed_ms(),
        }
        payload.update(self._stages)
        payload.update(self._facts)
        return payload

    # -------------------------------------------------------------- accessor
    @staticmethod
    def of(request: Request | None) -> RequestTelemetry | None:
        """The telemetry attached to ``request``, or ``None`` when absent."""
        if request is None:
            return None
        return getattr(request.state, "telemetry", None)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Assigns request/trace identity and measures total request duration."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = _clean_header(request.headers.get(HEADER_REQUEST_ID)) or _new_id()
        trace_id = _clean_header(request.headers.get(HEADER_TRACE_ID)) or request_id

        telemetry = RequestTelemetry(request_id=request_id, trace_id=trace_id)
        request.state.telemetry = telemetry

        status_code = 500
        error_class = ""
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:  # noqa: BLE001 — observe, then re-raise unchanged
            error_class = type(exc).__name__
            _emit(request, telemetry, status_code=500, error_class=error_class)
            raise

        response.headers[HEADER_REQUEST_ID] = request_id
        response.headers[HEADER_TRACE_ID] = trace_id
        response.headers[HEADER_RESPONSE_TIME] = f"{telemetry.elapsed_ms():.3f}"
        _emit(request, telemetry, status_code=status_code, error_class=error_class)
        return response


def _emit(
    request: Request,
    telemetry: RequestTelemetry,
    *,
    status_code: int,
    error_class: str,
) -> None:
    """Log one structured telemetry line. Never raises."""
    try:
        path = request.url.path
        if path in _QUIET_PATHS:
            return
        record = telemetry.snapshot()
        record["method"] = request.method
        record["path"] = path
        record["status"] = status_code
        if error_class:
            record["error_class"] = error_class
        logger.info("request %s", record)
    except Exception:  # noqa: BLE001 — telemetry must never break a request
        pass


def _clean_header(value: str | None) -> str:
    """Accept only a short, safe inbound id (header injection guard)."""
    if not value:
        return ""
    candidate = value.strip()[:64]
    if not candidate or not all(c.isalnum() or c in "-_" for c in candidate):
        return ""
    return candidate


def _new_id() -> str:
    return uuid.uuid4().hex


__all__ = [
    "HEADER_REQUEST_ID",
    "HEADER_RESPONSE_TIME",
    "HEADER_TRACE_ID",
    "RequestTelemetry",
    "TelemetryMiddleware",
]
