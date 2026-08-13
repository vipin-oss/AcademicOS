"""Unit tests for the assistant's deterministic intent parser (no DB).

LEGACY / TRANSITIONAL (L0 freeze). Do not grow ``ROUTING_CASES`` or
``PRECEDENCE_CASES``. New language belongs in
``tests/eval/capabilities/golden/``.

The parser is the module's routing layer: an ordered rule table over the
normalized question. These batteries pin (a) every intent's positive cases,
(b) shadow-precedence pairs (the ordering IS the semantics), and (c) the
extractors (thresholds, keywords, report modules). No repository involved.
"""
from __future__ import annotations

import pytest

from app.application.assistant.intents import (
    clean_keyword,
    normalize,
    parse_question,
)
from app.application.dtos import assistant as dto

# ---------------------------------------------------------------------------
# Positive battery — every intent, at least the brief's canonical phrasings
# ---------------------------------------------------------------------------
ROUTING_CASES = [
    # dashboard
    ("What should I do today?", dto.INTENT_TODAY_PLAN),
    ("plan for today", dto.INTENT_TODAY_PLAN),
    ("today agenda", dto.INTENT_TODAY_PLAN),
    ("What is pending?", dto.INTENT_PENDING_ITEMS),
    ("what's pending", dto.INTENT_PENDING_ITEMS),
    ("my pendings", dto.INTENT_PENDING_ITEMS),
    ("Upcoming deadlines", dto.INTENT_UPCOMING_DEADLINES),
    ("deadlines this week", dto.INTENT_UPCOMING_DEADLINES),
    ("any deadlines?", dto.INTENT_UPCOMING_DEADLINES),
    ("Upcoming meetings", dto.INTENT_UPCOMING_MEETINGS),
    ("Show today's meetings", dto.INTENT_UPCOMING_MEETINGS),
    ("meetings today", dto.INTENT_UPCOMING_MEETINGS),
    ("Pending reports", dto.INTENT_PENDING_REPORTS),
    ("reports due", dto.INTENT_PENDING_REPORTS),
    ("Budget remaining", dto.INTENT_BUDGET_REMAINING),
    ("how much budget is left", dto.INTENT_BUDGET_REMAINING),
    # research
    ("Show my publications", dto.INTENT_MY_PUBLICATIONS),
    ("list publications", dto.INTENT_MY_PUBLICATIONS),
    ("My latest publication", dto.INTENT_LATEST_PUBLICATION),
    ("recent publications", dto.INTENT_LATEST_PUBLICATION),
    ("Publications this year", dto.INTENT_PUBLICATIONS_THIS_YEAR),
    ("papers this year", dto.INTENT_PUBLICATIONS_THIS_YEAR),
    ("Conference papers", dto.INTENT_CONFERENCE_PAPERS),
    ("papers in conferences", dto.INTENT_CONFERENCE_PAPERS),
    ("Show active research projects", dto.INTENT_ACTIVE_PROJECTS),
    ("my research projects", dto.INTENT_ACTIVE_PROJECTS),
    ("Completed projects", dto.INTENT_COMPLETED_PROJECTS),
    ("projects funded by HSRF", dto.INTENT_PROJECTS_BY_FUNDER),
    ("HSRF funded projects", dto.INTENT_PROJECTS_BY_FUNDER),
    ("Research grants", dto.INTENT_RESEARCH_GRANTS),
    ("grants sanctioned", dto.INTENT_RESEARCH_GRANTS),
    ("Show HSRF documents", dto.INTENT_DOCUMENTS_BY_KEYWORD),
    ("documents about metadata framework", dto.INTENT_DOCUMENTS_BY_KEYWORD),
    ("documents", dto.INTENT_DOCUMENTS_BY_KEYWORD),
    # teaching
    ("Show students below 75% attendance", dto.INTENT_ATTENDANCE_BELOW),
    ("students with attendance below 70%", dto.INTENT_ATTENDANCE_BELOW),
    ("attendance below 60", dto.INTENT_ATTENDANCE_BELOW),
    ("shortage of attendance", dto.INTENT_ATTENDANCE_BELOW),
    ("Pending grading", dto.INTENT_PENDING_GRADING),
    ("ungraded submissions", dto.INTENT_PENDING_GRADING),
    ("Upcoming classes", dto.INTENT_UPCOMING_CLASSES),
    ("classes today", dto.INTENT_UPCOMING_CLASSES),
    ("Assignments pending", dto.INTENT_PENDING_ASSIGNMENTS),
    ("pending assignments", dto.INTENT_PENDING_ASSIGNMENTS),
    # finance
    ("Budget summary", dto.INTENT_BUDGET_SUMMARY),
    ("summarize the budget", dto.INTENT_BUDGET_SUMMARY),
    ("Show pending purchases", dto.INTENT_PENDING_PURCHASES),
    ("Recent procurements", dto.INTENT_RECENT_PROCUREMENTS),
    # events
    ("Show upcoming events", dto.INTENT_UPCOMING_EVENTS),
    ("Upcoming workshops", dto.INTENT_UPCOMING_EVENTS),
    ("events this week", dto.INTENT_UPCOMING_EVENTS),
    ("Events attended", dto.INTENT_EVENTS_ATTENDED),
    ("events I attended", dto.INTENT_EVENTS_ATTENDED),
    ("Events organized", dto.INTENT_EVENTS_ORGANIZED),
    ("events I organized", dto.INTENT_EVENTS_ORGANIZED),
    ("Certificates", dto.INTENT_CERTIFICATES),
    ("my certificates", dto.INTENT_CERTIFICATES),
    # committees
    ("Show upcoming committee meetings", dto.INTENT_COMMITTEE_MEETINGS),
    ("iqac meetings", dto.INTENT_COMMITTEE_MEETINGS),
    ("Show pending committee actions", dto.INTENT_PENDING_ACTIONS),
    ("action items", dto.INTENT_PENDING_ACTIONS),
    ("Recent decisions", dto.INTENT_RECENT_DECISIONS),
    ("committee decisions", dto.INTENT_RECENT_DECISIONS),
    # reports
    ("What reports can I see?", dto.INTENT_REPORT_CATALOGUE),
    ("list reports", dto.INTENT_REPORT_CATALOGUE),
    ("Summarize the publications report", dto.INTENT_MODULE_REPORT_SUMMARY),
    ("finance report summary", dto.INTENT_MODULE_REPORT_SUMMARY),
    # search & meta
    ("search for quantum dots", dto.INTENT_KNOWLEDGE_SEARCH),
    ("find Rakesh Sharma", dto.INTENT_KNOWLEDGE_SEARCH),
    ("what is the meaning of life", dto.INTENT_KNOWLEDGE_SEARCH),
    ("hi", dto.INTENT_GREETING),
    ("namaste", dto.INTENT_GREETING),
    ("Hello!", dto.INTENT_GREETING),
    ("help", dto.INTENT_HELP),
    ("what can you do", dto.INTENT_HELP),
]


@pytest.mark.parametrize(("question", "expected"), ROUTING_CASES)
def test_routing(question: str, expected: str):
    parsed = parse_question(question)
    assert parsed.intent == expected, f"{question!r} routed to {parsed.intent!r}"


# ---------------------------------------------------------------------------
# Shadow-precedence — the pairs that specifically must not be swallowed
# ---------------------------------------------------------------------------
PRECEDENCE_CASES = [
    ("pending reports", dto.INTENT_PENDING_REPORTS),  # not pending_items
    ("what is pending?", dto.INTENT_PENDING_ITEMS),
    ("show students below 75% attendance", dto.INTENT_ATTENDANCE_BELOW),
    ("summarize the publications report", dto.INTENT_MODULE_REPORT_SUMMARY),  # not my_publications
    ("show my publications", dto.INTENT_MY_PUBLICATIONS),
    ("publications this year", dto.INTENT_PUBLICATIONS_THIS_YEAR),  # not my_publications
    ("events attended", dto.INTENT_EVENTS_ATTENDED),  # not upcoming_events
    ("show upcoming committee meetings", dto.INTENT_COMMITTEE_MEETINGS),  # not upcoming_meetings
    ("show today's meetings", dto.INTENT_UPCOMING_MEETINGS),
    ("budget summary", dto.INTENT_BUDGET_SUMMARY),  # not module_report_summary
]


@pytest.mark.parametrize(("question", "expected"), PRECEDENCE_CASES)
def test_shadow_precedence(question: str, expected: str):
    assert parse_question(question).intent == expected


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------
def test_threshold_extraction():
    assert parse_question("students below 75% attendance").params["threshold"] == 75
    assert parse_question("attendance below 60").params["threshold"] == 60
    assert parse_question("low attendance").params["threshold"] == 75  # default


def test_threshold_is_clamped():
    assert parse_question("students below 250% attendance").params["threshold"] == 100
    assert parse_question("students below 0% attendance").params["threshold"] == 1


def test_funder_keyword_capture():
    assert parse_question("projects funded by HSRF").params["keyword"] == "hsrf"
    assert parse_question("DST-SERB funded projects").params["keyword"] == "dst-serb"


def test_document_keyword_capture():
    assert parse_question("show HSRF documents").params["keyword"] == "hsrf"
    assert parse_question("documents").params["keyword"] == ""


def test_report_module_capture():
    assert parse_question("summarize the publications report").params["module"] == "publications"
    assert parse_question("students report summary").params["module"] == "students"
    assert parse_question("report summary for events").params["module"] == "events"


def test_knowledge_search_query_capture():
    assert parse_question("search for quantum dots").params["query"] == "quantum dots"
    # unmatched phrasing keeps the whole normalized question as the query
    assert parse_question("plumbus manual page seven").query == "plumbus manual page seven"


def test_parser_never_raises_and_labels_cover_every_intent():
    for question, expected in ROUTING_CASES:
        parse_question(question)  # must not raise
        assert dto.INTENT_LABELS[expected]
    assert set(dto.INTENT_LABELS.keys()) == set(dto.INTENT_CODES)


# ---------------------------------------------------------------------------
# normalize / clean_keyword primitives
# ---------------------------------------------------------------------------
def test_normalize_collapses_and_strips():
    assert normalize("  Hello,   World?! ") == "hello, world"
    assert normalize("What’s on?") == "what's on"
    assert normalize("") == ""


def test_clean_keyword_strips_fillers():
    assert clean_keyword("show my hsrf") == "hsrf"
    assert clean_keyword("hsrf") == "hsrf"
    assert clean_keyword("show all the proposals") == "proposals"


def test_suggested_questions_all_route_to_their_declared_intent():
    """AI Home promises: every suggested question must parse to the intent it
    is badged with (the catalogue is served verbatim by GET /assistant/home)."""
    mismatches = [
        (question, intent, parse_question(question).intent)
        for _group, question, intent in dto.SUGGESTED_QUESTIONS
        if parse_question(question).intent != intent
    ]
    assert mismatches == []
