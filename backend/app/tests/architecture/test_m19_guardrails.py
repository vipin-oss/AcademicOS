"""V3 M19 architecture guardrails (ADR-066).

Pins the production-hardening artifacts (Docker/TLS/logging/backup):

- a backend + frontend Dockerfile and an nginx reverse-proxy config exist;
- the reverse proxy terminates TLS and rate-limits the API;
- the JSON structured-log formatter emits one JSON object per line;
- backup/restore scripts exist for the RPO/RTO drill.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def test_dockerfiles_exist() -> None:
    assert (REPO / "backend" / "Dockerfile").exists()
    assert (REPO / "frontend" / "Dockerfile").exists()


def test_reverse_proxy_terminates_tls_and_rate_limits() -> None:
    src = (REPO / "deploy" / "nginx.conf").read_text(encoding="utf-8")
    assert "ssl_certificate" in src
    assert "limit_req_zone" in src
    assert "Strict-Transport-Security" in src


def test_json_log_formatter_emits_one_object_per_line() -> None:
    from app.core.logging import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord("test", logging.INFO, "path", 1, "hello", None, None)
    line = formatter.format(record)
    parsed = json.loads(line)
    assert parsed["message"] == "hello"
    assert parsed["level"] == "INFO"


def test_backup_restore_scripts_exist() -> None:
    assert (REPO / "backend" / "scripts" / "backup.py").exists()
    assert (REPO / "backend" / "scripts" / "restore.py").exists()


def test_log_json_is_config_driven() -> None:
    src = (REPO / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")
    assert "log_json: bool = False" in src
