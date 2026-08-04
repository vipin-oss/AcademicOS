"""Intake Foundations (v2) — application services for the intake pipeline.

Contains the deterministic pipeline machinery (stage vocabulary, hygiene
rules, MIME sniffer) plus the two execution services:

- ``runner.IntakeRunner`` — walks one session through the stage machine,
  cooperatively, with idempotent steps and per-item isolation;
- ``jobs.IntakeJobManager`` — the single-dispatcher in-process job framework
  (FIFO queue, progress, pause/resume/cancel) whose durable state lives on the
  session object itself, so nothing is lost across restarts.

No extraction, OCR, classification, matching, proposal or commit logic exists
here yet — those stages execute through the structurally-real *deferred*
handler until their milestones land.
"""
