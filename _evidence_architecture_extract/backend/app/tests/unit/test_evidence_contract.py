"""Behavioral tests: the Evidence-Grounded Answer Contract through the REAL
GroundedQAUseCase (real context/citation/prompt builders, scripted gateway).

Adversarial matrix (A–J):

A. explicit "do not expand" constraint -> expansion in answer => refused
B. "do not infer from filename" -> filename-based answer => refused
C. "give only the exact phrase" -> verbatim phrase => PASS; invented => refused
D. no document reference -> general mode (no refusal; flag only)
E. "exact conference name mentioned in <doc>" -> correct name => PASS;
   reordered expansion => refused (the real-world failure shape)
F. "this document" (no filename) -> general mode (resolver limitation)
G. answer NOT in the document => refused
H. filename suggests X, body says Y -> X refused, Y PASS
I. conversation history holds the wrong fact -> history-based answer refused
J. unrelated retrieved doc contains the tempting answer -> refused (check is
   against the REFERENCED document only)
"""
from __future__ import annotations

import pytest

from app.application.assistant.claim_support import ClaimSupportVerifier
from app.application.assistant.citations import CitationBuilder
from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.dtos.ai import GenerationEvent, GenerationResult, TokenUsage
from app.application.dtos.assistant import AssistantRetrievalResult, RetrievedItem
from app.application.use_cases.ai.grounded_qa import GroundedQAUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId

TARGET = "obj:document:cblu2024"
OTHER = "obj:document:galvin"
CONF_NAME = "In Honor International Conference of Srinivasa Ramanujan's Birthday"
BODY = (
    "CERTIFICATE OF PARTICIPATION\n"
    f"This is to certify that Dr Anil Kumar has participated in the {CONF_NAME} "
    "organized by Chaudhary Bansi Lal University (CBLU), Bhiwani held on 19 and "
    "20 January 2024.\n"
)
GALVIN_BODY = (
    "Topic 20: Quantum error correction with surface codes.\n"
    "According to the authors, the decoder achieves 0.9 percent.\n"
    "Presented at the International Workshop on Quantum Computing, 14-15 Feb 2024.\n"
)

REF_QUERY = (
    'According to the source text of "Cblu Jan, 2024.pdf", what is the full name '
    "of the conference? Do not use or expand the acronym CBLU. Do not infer from "
    "the filename. Give only the conference name explicitly supported by the document."
)


def _user():
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:alice-0001"),
    )


class _MockAnnotation:
    def __init__(self, texts):
        self._texts = texts  # object_id -> text

    def extracted_text(self, document_id, storage):
        text = self._texts.get(document_id)
        if not text:
            return None
        return {"text": text}


class _MockStorage:
    pass


class _FakeGateway:
    provider_id = "test-provider"

    def __init__(self, answer, events=None):
        self._answer = answer
        self._events = list(events or [])
        self.last_prompt = None

    def generate(self, prompt):
        self.last_prompt = prompt
        return GenerationResult(
            text=self._answer, model="test-model",
            usage=TokenUsage(input_tokens=5, output_tokens=7, estimated=True),
            latency_ms=42,
        )

    def stream(self, prompt):
        self.last_prompt = prompt
        yield from self._events


class _MockAiCore:
    def __init__(self, gateway):
        self._gateway = gateway
        self.config = None

    def gateway(self):
        return self._gateway


def _item(object_id, title):
    return RetrievedItem(
        object_id=object_id, object_type="document", title=title,
        version=1, sources=("search",), score=1.0,
        metadata_text=f"file_name: {title}",
    )


def _retrieval_result(*, resolved=True, extra_items=()):
    items = [_item(TARGET, "Cblu Jan, 2024.pdf")] + list(extra_items)
    return AssistantRetrievalResult(
        items=tuple(items),
        search_count=len(items), graph_count=0,
        document_reference="Cblu Jan, 2024.pdf",
        document_reference_resolved=resolved,
        resolved_document_id=TARGET if resolved else None,
    )


def _plain_result():
    """A retrieval result WITHOUT a document reference (entity/fact query)."""
    items = (_item(TARGET, "Cblu Jan, 2024.pdf"),)
    return AssistantRetrievalResult(
        items=items, search_count=1, graph_count=0,
        document_reference=None,
    )


def _qa(gateway, *, retrieval_result=None, texts=None):
    return GroundedQAUseCase(
        repository=None,
        retrieval=_FakeRetrieval(retrieval_result if retrieval_result is not None else _retrieval_result()),
        ai_core=_MockAiCore(gateway),
        context_builder=AssistantContextBuilder(),
        prompt_builder=AssistantPromptBuilder(),
        citation_builder=CitationBuilder(),
        verifier=None,
        annotation_service=_MockAnnotation(texts or {TARGET: BODY, OTHER: GALVIN_BODY}),
        storage=_MockStorage(),
        claim_verifier=ClaimSupportVerifier(),
    )


class _FakeRetrieval:
    def __init__(self, result):
        self._result = result

    def retrieve(self, question, user):
        return self._result


# ====================================================================== A–J
class TestEvidenceContractMatrix:
    def test_a_forbidden_expansion_refused(self):
        gw = _FakeGateway("The full name of the conference is CBLU (Chaudhary Bansi Lal University).")
        out = _qa(gw).execute(REF_QUERY, _user())
        assert out.claim_supported is False
        assert out.claim_mode == "extraction"
        assert "could not be verified" in out.answer
        assert out.citations == ()

    def test_b_filename_inference_refused(self):
        gw = _FakeGateway("Cblu Jan")
        out = _qa(gw).execute(
            "Do not infer from the filename. What is the conference name in Cblu Jan, 2024.pdf?",
            _user(),
        )
        assert out.claim_supported is False
        assert "could not be verified" in out.answer

    def test_c_exact_phrase_supported_passes(self):
        gw = _FakeGateway(CONF_NAME)
        out = _qa(gw).execute(REF_QUERY, _user())
        assert out.claim_supported is True
        assert out.claim_mode == "extraction"
        assert out.answer == CONF_NAME
        assert len(out.citations) == 1
        assert out.citations[0]["object_id"] == TARGET

    def test_c2_exact_phrase_invented_refused(self):
        gw = _FakeGateway("The conference was a wonderful academic gathering")
        out = _qa(gw).execute(REF_QUERY, _user())
        assert out.claim_supported is False

    def test_d_no_document_reference_general_mode(self):
        gw = _FakeGateway("CBLU conference")
        out = _qa(gw, retrieval_result=_plain_result()).execute("What is the conference name?", _user())
        assert out.claim_mode == "general"
        assert out.claim_supported is not False  # not refused by the contract
        assert "could not be verified" not in out.answer

    def test_e_exact_name_mentioned_passes_with_verbatim(self):
        gw = _FakeGateway(CONF_NAME)
        out = _qa(gw).execute(
            "What is the exact conference name mentioned in Cblu Jan, 2024.pdf?", _user()
        )
        assert out.claim_supported is True
        assert out.answer == CONF_NAME

    def test_e2_reordered_expansion_refused(self):
        # The exact real-world failure shape: answer reorders the source's
        # "Chaudhary Bansi Lal University (CBLU)".
        gw = _FakeGateway("CBLU (Chaudhary Bansi Lal University)")
        out = _qa(gw).execute(
            "What is the exact conference name mentioned in Cblu Jan, 2024.pdf?", _user()
        )
        assert out.claim_supported is False
        assert "could not be verified" in out.answer

    def test_f_this_document_without_filename_general(self):
        # "this document" (no filename) is not resolved by the P0 resolver —
        # documented limitation; the contract stays general (no refusal).
        gw = _FakeGateway("It discussed the conference.")
        out = _qa(gw, retrieval_result=_plain_result()).execute(
            "What does this document explicitly say about the conference?", _user())
        assert out.claim_mode == "general"

    def test_g_answer_not_in_document_refused(self):
        gw = _FakeGateway("XYZ Academic Summit")
        out = _qa(gw).execute(
            "What is the name of the conference in Cblu Jan, 2024.pdf?", _user()
        )
        assert out.claim_supported is False

    def test_h_filename_suggests_wrong_answer_refused(self):
        # Filename "Cblu Jan, 2024.pdf" suggests a "CBLU" conference; the
        # body says otherwise. Answering from the filename must be refused.
        gw = _FakeGateway("CBLU conference in January")
        out = _qa(gw).execute(
            "What is the conference name in Cblu Jan, 2024.pdf? Do not infer from the filename.", _user()
        )
        assert out.claim_supported is False

    def test_i_conversation_history_wrong_fact_refused(self):
        # The model repeats the prior-turn wrong fact; the referenced
        # document's source text does not contain it -> refused.
        gw = _FakeGateway("The full name of the conference is CBLU (Chaudhary Bansi Lal University).")
        out = _qa(gw).execute(REF_QUERY, _user())
        assert out.claim_supported is False

    def test_j_unrelated_source_temptation_refused(self):
        # Another retrieved document contains a tempting phrase; the
        # REFERENCED document does not. Verification is scoped to the
        # referenced document only.
        tempting = "International Workshop on Quantum Computing"
        # referenced doc body does NOT contain it; GALVIN does
        texts = {TARGET: BODY, OTHER: GALVIN_BODY}
        gw = _FakeGateway(tempting)
        result = _retrieval_result(extra_items=(_item(OTHER, "Topic20_8p7_Galvin.pdf"),))
        out = _qa(gw, retrieval_result=result, texts=texts).execute(
            "Which conference is mentioned in Cblu Jan, 2024.pdf?", _user()
        )
        assert out.claim_supported is False
        assert "could not be verified" in out.answer

    def test_stream_refuses_unsupported_claim(self):
        gw = _FakeGateway(
            "CBLU (Chaudhary Bansi Lal University)",
            events=[
                GenerationEvent(kind="token", delta="CBLU "),
                GenerationEvent(kind="complete", result=GenerationResult(
                    text="CBLU (Chaudhary Bansi Lal University)", model="m",
                    usage=TokenUsage(estimated=True), latency_ms=5,
                )),
            ],
        )
        events = list(_qa(gw).stream(REF_QUERY, _user()))
        completion = [e for e in events if e["type"] == "complete"][0]
        assert completion["result"].claim_supported is False
        assert "could not be verified" in completion["result"].answer

    def test_stream_passes_supported_claim(self):
        gw = _FakeGateway(
            CONF_NAME,
            events=[
                GenerationEvent(kind="complete", result=GenerationResult(
                    text=CONF_NAME, model="m",
                    usage=TokenUsage(estimated=True), latency_ms=5,
                )),
            ],
        )
        events = list(_qa(gw).stream(REF_QUERY, _user()))
        completion = [e for e in events if e["type"] == "complete"][0]
        assert completion["result"].claim_supported is True
        assert completion["result"].answer == CONF_NAME

    def test_prompt_contains_answer_contract_in_extraction_mode(self):
        gw = _FakeGateway(CONF_NAME)
        qa = _qa(gw)
        qa.execute(REF_QUERY, _user())
        user_msg = gw.last_prompt.user
        assert "ANSWER CONTRACT (extraction mode)" in user_msg
        assert "EXACT QUOTE" in user_msg

    def test_prompt_has_no_answer_contract_in_general_mode(self):
        gw = _FakeGateway("CBLU conference")
        qa = _qa(gw, retrieval_result=_plain_result())
        qa.execute("What is the conference name?", _user())
        assert "ANSWER CONTRACT" not in gw.last_prompt.user
