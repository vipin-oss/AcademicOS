"""Unit tests: ClaimSupportVerifier — the evidence-support boundary (P0).

Tests the deterministic mechanisms of the Evidence-Grounded Answer Contract:

- evidence_mode(): extraction (document named / quote demanded) vs general,
  with count questions never entering extraction mode;
- normalize_text(): verbatim containment normalization (citation markers,
  punctuation, case);
- acronym_expansion_violation(): the generic guard — a user forbidding an
  acronym expansion + an answer that expands any acronym => violation;
- extraction-mode verdicts: verbatim-quote containment against the
  REFERENCED document only; missing text; empty answer;
- general-mode verdicts: content-token coverage flag (advisory, no refusal).
"""
from __future__ import annotations

from app.application.assistant.claim_support import (
    ClaimSupportVerifier,
    acronym_expansion_violation,
    content_tokens,
    evidence_mode,
    normalize_text,
)

BODY = (
    "CERTIFICATE OF PARTICIPATION\n"
    "This is to certify that Dr Anil Kumar has participated in the In Honor "
    "International Conference of Srinivasa Ramanujan's Birthday organized by "
    "Chaudhary Bansi Lal University (CBLU), Bhiwani held on 19 and 20 January 2024.\n"
)

TARGET = "obj:document:cblu2024"


class _Result:
    document_reference = "Cblu Jan, 2024.pdf"
    document_reference_resolved = True
    resolved_document_id = TARGET


class TestEvidenceMode:
    def test_document_reference_is_extraction(self):
        assert evidence_mode("According to the source text of \"Cblu Jan, 2024.pdf\", what is the full name of the conference?", _Result()) == "extraction"

    def test_quote_word_is_extraction(self):
        assert evidence_mode("Quote the exact words from the document.") == "extraction"

    def test_verbatim_is_extraction(self):
        assert evidence_mode("Give the verbatim phrase.") == "extraction"

    def test_entity_query_is_general(self):
        assert evidence_mode("When did I attend the CBLU conference?") == "general"

    def test_exact_number_question_is_general(self):
        assert evidence_mode("What is the exact number of my publications?") == "general"

    def test_count_question_never_extraction(self):
        result = _Result()
        assert evidence_mode("According to Cblu Jan, 2024.pdf, how many sessions were there?", result) == "general"

    def test_plain_exact_is_general(self):
        assert evidence_mode("What is the exact title of my project?") == "general"


class TestNormalize:
    def test_strips_citation_markers(self):
        assert normalize_text("The name is X. [1]") == "the name is x"

    def test_punctuation_to_space(self):
        assert normalize_text("Cblu Jan, 2024.pdf") == "cblu jan 2024 pdf"

    def test_case_and_whitespace(self):
        assert normalize_text("  In Honor   Conference ") == "in honor conference"


class TestAcronymExpansionGuard:
    def test_forbidden_expansion_detected(self):
        q = "Do not use or expand the acronym CBLU."
        assert acronym_expansion_violation(q, "CBLU (Chaudhary Bansi Lal University)") is True

    def test_no_forbidden_expansion(self):
        q = "Do not use or expand the acronym CBLU."
        assert acronym_expansion_violation(q, "The conference name only") is False

    def test_expansion_without_prohibition_ok(self):
        q = "What is the conference name?"
        assert acronym_expansion_violation(q, "CBLU (Chaudhary Bansi Lal University)") is False

    def test_any_acronym_generic(self):
        q = "Never expand the acronym SERB."
        assert acronym_expansion_violation(q, "SERB (Science and Engineering Research Board)") is True


class TestExtractionVerdicts:
    def _verify(self, answer, *, question='According to the source text of "Cblu Jan, 2024.pdf", what is the full name of the conference?', texts=None):
        verifier = ClaimSupportVerifier()
        return verifier.verify(
            question=question, answer=answer,
            referenced_id=TARGET, source_texts=texts if texts is not None else {TARGET: BODY},
            mode="extraction",
        )

    def test_verbatim_quote_passes(self):
        verdict = self._verify("In Honor International Conference of Srinivasa Ramanujan's Birthday")
        assert verdict.supported is True
        assert verdict.mode == "extraction"

    def test_quote_with_trailing_citation_marker_passes(self):
        verdict = self._verify("In Honor International Conference of Srinivasa Ramanujan's Birthday [1]")
        assert verdict.supported is True

    def test_reordered_expansion_refused(self):
        # The real-world failure: the answer reorders the source's
        # "Chaudhary Bansi Lal University (CBLU)" into an expansion — not a
        # verbatim quote from the referenced document.
        verdict = self._verify("CBLU (Chaudhary Bansi Lal University)")
        assert verdict.supported is False
        assert "verbatim" in verdict.reason

    def test_filename_inference_refused(self):
        verdict = self._verify("Cblu Jan")
        assert verdict.supported is False

    def test_world_knowledge_refused(self):
        verdict = self._verify("A conference held at a university in Haryana")
        assert verdict.supported is False

    def test_forbidden_acronym_expansion_refused(self):
        verdict = self._verify(
            "CBLU (Chaudhary Bansi Lal University)",
            question="Do not expand CBLU. What is the conference name in Cblu Jan, 2024.pdf?",
        )
        assert verdict.supported is False
        assert "acronym" in verdict.reason

    def test_missing_source_text_refused(self):
        verdict = self._verify("anything", texts={})
        assert verdict.supported is False
        assert "unavailable" in verdict.reason

    def test_missing_referenced_id_refused(self):
        verifier = ClaimSupportVerifier()
        verdict = verifier.verify(
            question="Quote the phrase.", answer="In Honor International Conference",
            referenced_id=None, source_texts={TARGET: BODY},
        )
        assert verdict.supported is False

    def test_empty_answer_refused(self):
        verdict = self._verify("   ")
        assert verdict.supported is False


class TestGeneralVerdicts:
    def test_coverage_flag_advisory(self):
        verifier = ClaimSupportVerifier()
        verdict = verifier.verify(
            question="What is the conference name?",
            answer="In Honor International Conference of Srinivasa Ramanujan's Birthday",
            source_texts={TARGET: BODY},
        )
        assert verdict.mode == "general"
        assert verdict.supported is True
        assert verdict.coverage is not None and verdict.coverage > 0.5

    def test_low_coverage_flagged(self):
        verifier = ClaimSupportVerifier()
        verdict = verifier.verify(
            question="What is the conference name?",
            answer="The quantum entanglement decoherence rate was measured in the lab",
            source_texts={TARGET: BODY},
        )
        assert verdict.mode == "general"
        assert verdict.supported is False


class TestContentTokens:
    def test_filters_stopwords(self):
        tokens = content_tokens("The conference name is CBLU University")
        assert "conference" in tokens and "name" in tokens
        assert "the" not in tokens and "is" not in tokens
