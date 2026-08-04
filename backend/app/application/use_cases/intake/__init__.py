"""Intake Foundations (v2) — session/item lifecycle use cases.

Vertical slice mirroring the v1 module doctrine: one use case per file,
framework-free, depending only on ports (``ObjectRepository``,
``FileStorage``) and the intake job framework. Persistence is exclusively via
universal objects — no new tables, no frozen-module edits.
"""
