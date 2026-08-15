"""Focused tests: multi-signal retrieval plan (evidence-based fix).

Covers the representative queries from the second forensic analysis:
- type/count questions resolve to object_type-scoped search
- proper nouns (CBLU) are preserved as the retrieval entity
- year + type questions keep the type constraint
- domain nouns map to existing ObjectType values
- legacy fallback behavior is unchanged
"""
from __future__ import annotations

from app.application.services.assistant_retrieval import (
    AssistantRetrievalService,
    RetrievalPlan,
    retrieval_plan,
)


class TestRetrievalPlan:
    def test_total_number_of_publication_is_type_question(self):
        plan = retrieval_plan("my total number of publication")
        assert plan == RetrievalPlan(terms=("publication",), object_type="publication", type_question=True)

    def test_how_many_publications_is_type_question(self):
        plan = retrieval_plan("how many publications do I have")
        assert plan.object_type == "publication"
        assert plan.type_question is True

    def test_what_conferences_is_type_question(self):
        plan = retrieval_plan("what conferences have I attended")
        assert plan.object_type == "event"
        assert plan.type_question is True

    def test_cblu_proper_noun_preserved(self):
        plan = retrieval_plan("when did I attend the CBLU conference")
        assert plan.terms == ("cblu",)
        assert plan.object_type is None  # entity search, not type-scoped

    def test_research_grants_keeps_grant_type_and_term(self):
        plan = retrieval_plan("show my research grants")
        assert plan.terms == ("grants",)
        assert plan.object_type == "grant"
        assert plan.type_question is False

    def test_designation_maps_to_faculty(self):
        plan = retrieval_plan("what is my designation")
        assert plan.object_type == "faculty"
        assert plan.type_question is True

    def test_papers_published_in_2025_keeps_type_and_year(self):
        plan = retrieval_plan("which papers have I published in 2025")
        assert plan.object_type == "publication"
        assert "2025" in plan.terms
        assert plan.type_question is False  # year constraint, not count-only

    def test_hindi_question_preserves_cblu(self):
        plan = retrieval_plan(
            "maine CBLU me conference attend ki thi uski date batana document upload hai"
        )
        assert plan.terms == ("cblu",)

    # -- legacy English behavior preserved (marker + fallback) -------------
    def test_topic_marker_related_to_unchanged(self):
        plan = retrieval_plan("Find my research projects related to mathematics")
        assert plan.terms == ("mathematics",)
        assert plan.object_type is None

    def test_find_quantum_fallback_unchanged(self):
        plan = retrieval_plan("find quantum")
        assert plan.terms == ("quantum",)

    def test_quantum_entanglement_fallback_unchanged(self):
        plan = retrieval_plan("quantum entanglement")
        assert plan.terms == ("entanglement",)

    def test_empty_question(self):
        assert retrieval_plan("") == RetrievalPlan(terms=())

    # -- ZIP-1 regression: unsafe substring marker matching -----------------
    def test_marker_for_never_matches_inside_information(self):
        # Historical failure: "for" matched inside "information" and the
        # query degraded to the fragment "mation" — the CBLU document was
        # never retrieved and the LLM answered from unrelated sources.
        plan = retrieval_plan(
            "What is the exact name of the conference mentioned in the Cblu "
            "Jan, 2024.pdf? Do not infer from the filename. Quote only the "
            "information supported by the document."
        )
        assert plan.terms == ("cblu",)
        assert "mation" not in plan.terms

    def test_document_reference_keeps_entity(self):
        plan = retrieval_plan("Tell me the conference name from Cblu Jan, 2024.pdf")
        assert plan.terms == ("cblu",)

    def test_sentence_initial_document_entity_with_year(self):
        # "Cblu" is the sentence-initial entity; the year makes this a
        # document reference, so the entity must survive (previously the
        # month abbreviation "jan" won).
        plan = retrieval_plan("Cblu Jan 2024")
        assert plan.terms == ("cblu",)

    def test_month_not_treated_as_proper_noun(self):
        # "January" is a month, not an entity: the domain-noun branch must
        # scope the search to events with the year constraint.
        plan = retrieval_plan("Which conference did I attend in January 2024?")
        assert plan.terms == ("conference", "2024")
        assert plan.object_type == "event"

    def test_cblu_conference_when(self):
        plan = retrieval_plan("When did I attend the CBLU conference?")
        assert plan.terms == ("cblu",)

    def test_cblu_conference_title_and_date(self):
        plan = retrieval_plan(
            "What was the title of the CBLU conference I attended, and when was it held?"
        )
        assert plan.terms == ("cblu",)

    def test_cblu_happened_in_january(self):
        plan = retrieval_plan("What happened at CBLU in January 2024?")
        assert plan.terms == ("cblu",)

    def test_hindi_maine_not_entity_even_when_capitalized(self):
        # "Maine" (Hinglish "I") is sentence-initial and capitalized but
        # the question has no year/extension signal — it must NOT become
        # the entity; "CBLU" must.
        plan = retrieval_plan("Maine CBLU me conference attend ki thi uski date batana")
        assert plan.terms == ("cblu",)

    def test_word_boundary_markers_still_match(self):
        assert retrieval_plan("Find my research projects related to mathematics").terms == ("mathematics",)
        assert retrieval_plan("Tell me information about the CBLU conference").terms == ("cblu",)
        assert retrieval_plan("documents containing the quantum results").terms == ("quantum",)

    def test_standalone_for_marker_still_works(self):
        plan = retrieval_plan("documents for the CBLU conference")
        assert plan.terms == ("cblu",)

    def test_january_conference_uses_domain_noun(self):
        plan = retrieval_plan("January 2024 conference")
        assert plan.terms == ("conference", "2024")
        assert plan.object_type == "event"


class _FakeSearch:
    def __init__(self, hits_by_text):
        self.hits_by_text = hits_by_text
        self.calls: list[tuple] = []

    def execute(self, *, user, text, object_type=None, limit=8):
        self.calls.append((text, object_type))
        key = text or "<none>"
        return self.hits_by_text.get((key, object_type), self.hits_by_text.get(key, []))


class _FakeGraph:
    def traverse(self, *a, **k):
        return {"items": []}


class _User:
    id = "obj:user:test-0001"

    class _Meta:
        def get_value(self, key):
            return None

    metadata = _Meta()


class _Hit:
    def __init__(self, oid, otype):
        self.object_id = oid
        self.object_type = otype
        self.title = otype
        self.version = 1
        self.score = 0.5
        self.metadata_text = ""


_USER = _User()


class TestRetrieveUsesPlan:
    def test_type_question_falls_back_to_type_only_search(self):
        # "how many publications" -> term "publications" misses, singular
        # misses, then type-only returns the publications.
        pubs = [_Hit("obj:publication:1", "publication")]
        search = _FakeSearch({
            ("publications", "publication"): [],
            ("publication", "publication"): [],
            ("<none>", "publication"): pubs,
        })
        svc = AssistantRetrievalService(search, _FakeGraph())
        res = svc.retrieve("how many publications do I have", _USER)
        assert [i.object_id for i in res.items] == ["obj:publication:1"]
        assert (None, "publication") in search.calls  # type-only fallback

    def test_proper_noun_term_used_directly(self):
        ev = [_Hit("obj:event:1", "event")]
        search = _FakeSearch({("cblu", None): ev})
        svc = AssistantRetrievalService(search, _FakeGraph())
        res = svc.retrieve("when did I attend the CBLU conference", _USER)
        assert ("cblu", None) in search.calls
        assert [i.object_id for i in res.items] == ["obj:event:1"]

    def test_year_type_question_searches_terms_in_order(self):
        paper = [_Hit("obj:publication:2", "publication")]
        search = _FakeSearch({
            ("papers", "publication"): [],
            ("2025", "publication"): paper,
        })
        svc = AssistantRetrievalService(search, _FakeGraph())
        res = svc.retrieve("which papers have I published in 2025", _USER)
        assert ("papers", "publication") in search.calls
        assert ("2025", "publication") in search.calls
        assert [i.object_id for i in res.items] == ["obj:publication:2"]

    def test_singular_fallback_still_works_inside_plan(self):
        grant = [_Hit("obj:grant:1", "grant")]
        search = _FakeSearch({
            ("grants", "grant"): [],
            ("grant", "grant"): grant,
        })
        svc = AssistantRetrievalService(search, _FakeGraph())
        res = svc.retrieve("show my research grants", _USER)
        assert ("grants", "grant") in search.calls
        assert ("grant", "grant") in search.calls
        assert [i.object_id for i in res.items] == ["obj:grant:1"]

    def test_caller_object_type_wins_over_plan(self):
        # Memory recall passes object_type=ai_conversation explicitly.
        conv = [_Hit("obj:ai_conversation:1", "ai_conversation")]
        search = _FakeSearch({("quantum", "ai_conversation"): conv})
        svc = AssistantRetrievalService(search, _FakeGraph())
        res = svc.retrieve("find quantum", _USER, object_type="ai_conversation")
        assert ("quantum", "ai_conversation") in search.calls
        assert [i.object_id for i in res.items] == ["obj:ai_conversation:1"]

    def test_internal_types_excluded_in_every_step(self):
        conv = _Hit("obj:ai_conversation:9", "ai_conversation")
        doc = _Hit("obj:document:1", "document")
        search = _FakeSearch({("hello", None): [conv, doc]})
        svc = AssistantRetrievalService(search, _FakeGraph())
        res = svc.retrieve("hello", _USER)
        assert [i.object_id for i in res.items] == ["obj:document:1"]
