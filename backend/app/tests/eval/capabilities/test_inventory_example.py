"""The brief's Hinglish inventory formulation is catalog DATA, not a route."""

from __future__ import annotations

from pathlib import Path

from app.application.services.capability_eval import load_suite

HINGLISH = "mere system mein kaunsa data available hai?"
INTENTS = Path(__file__).resolve().parents[3] / "application" / "assistant" / "intents.py"
ROUTING_TEST = Path(__file__).resolve().parents[2] / "unit" / "test_assistant_intents.py"


def test_inventory_hinglish_is_registered_as_inventory_data():
    matches = [
        case
        for case in load_suite()
        if case.question == HINGLISH
    ]
    assert len(matches) == 1
    case = matches[0]
    assert case.capability_id == "inventory"
    assert case.language == "hi-en"
    assert case.gate_level == "l5"


def test_inventory_hinglish_is_not_a_routing_rule():
    assert HINGLISH not in INTENTS.read_text(encoding="utf-8")
    assert HINGLISH not in ROUTING_TEST.read_text(encoding="utf-8")
