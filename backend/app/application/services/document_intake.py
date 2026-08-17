"""Document intake orchestrator (V3 ADR-067).

The "upload → understand → extract → validate → dedupe → route → structured
record" pipeline, built on the existing M6/M7 document-understanding + claims
knowledge plane — NOT a parallel document system.

Deterministic-first: classification and field extraction are pure rules +
regex; the AI semantic-extraction layer (ADR-069) is an OPTIONAL enrichment
that fills fields the deterministic pass missed, but storage never depends on
it (absent extractor or any provider failure -> pure deterministic).

Flow (per uploaded document's text + filename):

1. classify -> primary + secondary document types (with confidence);
2. for each type, extract its schema's fields (label / doi / email / url /
   date / amount / number), normalize + validate deterministically;
3. duplicate check against existing CONFIRMED claims (same predicate + same
   normalized value);
4. conflict check against CONFIRMED claims (same predicate, different value);
5. produce claims via ClaimService: AUTO_SUGGESTED when the whole record is
   high-confidence + conflict-free + not a duplicate; PROPOSED otherwise
   (review required). Nothing is written when the document is unknown or a
   field is unparseable (honest, never fabricated).

Provenance is intrinsic: every claim carries source_document_id + spans and
is permission-scoped by the caller's acl_scope (the same claim store the
rung-0 / dossier / grounded-QA paths already read, so structured records are
retrievable and citable).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.knowledge.document_types import target_module
from app.application.knowledge.extraction_schemas import fields_for
from app.application.ports.claim_store import ClaimStore
from app.application.services.claim_service import ClaimService
from app.application.services.document_classifier import (
    DocumentClassifier,
)
from app.application.services.extraction_health import claim_value_key
from app.application.services.suggestion_policy import SuggestionPolicy
from app.application.services.value_normalizer import (
    normalize_amount,
    normalize_date,
    normalize_doi,
    normalize_email,
    normalize_number,
    normalize_text,
    normalize_url,
)
from app.domain.value_objects.span import Span

#: Field-extractor confidence (deterministic).
_LABEL_CONFIDENCE = 0.9
_REGEX_CONFIDENCE = 0.85


@dataclass(frozen=True)
class ExtractedField:
    field_name: str
    predicate_id: str
    value: object            # normalized value (str / float / None)
    original_text: str
    confidence: float
    extractor: str
    spans: tuple = ()        # source spans (TEXT_RANGE for AI-derived fields)


@dataclass(frozen=True)
class DuplicateHit:
    predicate_id: str
    existing_claim_id: str
    value: object


@dataclass(frozen=True)
class ConflictHit:
    predicate_id: str
    existing_claim_id: str
    existing_value: object
    extracted_value: object


@dataclass(frozen=True)
class RecordOutcome:
    predicate_id: str
    value: object
    status: str            # "auto_suggested" | "proposed" | "skipped"
    claim_id: str = ""
    reason: str = ""       # skip reason when skipped


@dataclass(frozen=True)
class DocumentAnalysis:
    document_id: str
    document_type_id: str | None
    confidence: float
    secondary_types: tuple[str, ...]
    target_module: str
    fields: tuple[ExtractedField, ...] = field(default_factory=tuple)
    records: tuple[RecordOutcome, ...] = field(default_factory=tuple)
    duplicates: tuple[DuplicateHit, ...] = field(default_factory=tuple)
    conflicts: tuple[ConflictHit, ...] = field(default_factory=tuple)
    review_required: bool = True
    status: str = "unknown"   # unknown | analyzed | review_required | ingested
    extraction_mode: str = "deterministic"   # "deterministic" | "ai_assisted"
    ai_rejected: int = 0                      # AI fields rejected (low-conf / ungrounded)

    def all_types(self) -> tuple[str, ...]:
        """Primary + secondary type ids (primary first)."""
        ids = [self.document_type_id] if self.document_type_id else []
        ids += [t for t in self.secondary_types if t not in ids]
        return tuple(ids)

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "document_type_id": self.document_type_id,
            "confidence": self.confidence,
            "secondary_types": list(self.secondary_types),
            "target_module": self.target_module,
            "status": self.status,
            "review_required": self.review_required,
            "extraction_mode": self.extraction_mode,
            "ai_rejected": self.ai_rejected,
            "fields": [
                {
                    "field_name": f.field_name,
                    "predicate_id": f.predicate_id,
                    "value": f.value,
                    "original_text": f.original_text,
                    "confidence": f.confidence,
                    "extractor": f.extractor,
                }
                for f in self.fields
            ],
            "records": [
                {"predicate_id": r.predicate_id, "value": r.value,
                 "status": r.status, "claim_id": r.claim_id, "reason": r.reason}
                for r in self.records
            ],
            "duplicates": [
                {"predicate_id": d.predicate_id, "existing_claim_id": d.existing_claim_id,
                 "value": d.value}
                for d in self.duplicates
            ],
            "conflicts": [
                {"predicate_id": c.predicate_id, "existing_claim_id": c.existing_claim_id,
                 "existing_value": c.existing_value, "extracted_value": c.extracted_value}
                for c in self.conflicts
            ],
        }


class DocumentIntakeService:
    """Understand + extract + validate + dedupe + route one document."""

    def __init__(
        self,
        claim_service: ClaimService,
        claim_store: ClaimStore,
        classifier: DocumentClassifier | None = None,
        policy: SuggestionPolicy | None = None,
        ai_extractor=None,  # duck-typed: .extract(**kw) -> AiExtractionResult
    ) -> None:
        self._claims = claim_service
        self._store = claim_store
        self._classifier = classifier or DocumentClassifier()
        self._policy = policy or SuggestionPolicy()
        self._ai_extractor = ai_extractor

    def analyze(
        self,
        *,
        text: str,
        filename: str,
        document_id: str,
        version: int,
        acl_scope: str | None,
        spans: list[Span] | None = None,
    ) -> DocumentAnalysis:
        classification = self._classifier.classify(text, filename)
        type_ids = classification.all_types()

        # Phase 1: Deterministic extraction (fast, always runs)
        fields: list[ExtractedField] = []
        for type_id in type_ids:
            for spec in fields_for(type_id):
                value, original, extractor = self._extract_field(spec, text)
                if value is None:
                    continue
                confidence = (
                    _LABEL_CONFIDENCE if extractor == "label" else _REGEX_CONFIDENCE
                )
                fields.append(ExtractedField(
                    field_name=spec.field_name, predicate_id=spec.predicate_id,
                    value=value, original_text=original,
                    confidence=min(confidence, classification.confidence),
                    extractor=extractor,
                ))

        # Prose fallback (ADR-068): fill fields the label pass missed
        existing_preds = {f.predicate_id for f in fields}
        from app.application.services.prose_extractor import prose_fields

        for predicate_id, (value, original) in prose_fields(text).items():
            if predicate_id in existing_preds:
                continue
            fields.append(ExtractedField(
                field_name=predicate_id, predicate_id=predicate_id,
                value=value, original_text=original,
                confidence=min(0.85, classification.confidence),
                extractor="prose",
            ))

        # Phase 2: AI enrichment (background, optional)
        ai_rejected = 0
        ai_enrichment_result = None
        if self._ai_extractor is not None and classification.document_type_id is not None:
            existing_preds = {f.predicate_id for f in fields}
            seen_specs: dict[str, object] = {}
            for type_id in type_ids:
                for s in fields_for(type_id):
                    if s.predicate_id not in existing_preds:
                        seen_specs.setdefault(s.predicate_id, s)
            missing = tuple(seen_specs.values())
            if missing:
                try:
                    ai = self._ai_extractor.extract(
                        text=text,
                        type_id=classification.document_type_id,
                        missing_fields=missing,
                        source_id=document_id,
                    )
                    for af in ai.fields:
                        fields.append(ExtractedField(
                            field_name=af.field_name, predicate_id=af.predicate_id,
                            value=af.value, original_text=af.original_text,
                            confidence=min(af.confidence, classification.confidence),
                            extractor="ai",
                            spans=(af.span,) if af.span is not None else (),
                        ))
                    ai_rejected = (
                        len(ai.rejected_low_confidence) + len(ai.rejected_ungrounded)
                    )
                except Exception:
                    # AI failure must not break deterministic extraction
                    pass

        if classification.document_type_id is None and not fields:
            return DocumentAnalysis(
                document_id=document_id, document_type_id=None, confidence=0.0,
                secondary_types=(), target_module="general_document",
                status="unknown", review_required=True,
            )

        # Phase 3: Reconciliation (compare deterministic vs AI)
        from app.application.services.field_candidate import FieldCandidate, FieldSource
        from app.application.services.reconciliation import (
            compute_document_confidence,
            reconcile_fields,
        )

        # Convert extracted fields to candidates for reconciliation
        det_candidates: list[FieldCandidate] = []
        ai_candidates: list[FieldCandidate] = []
        for f in fields:
            candidate = FieldCandidate(
                predicate_id=f.predicate_id,
                field_name=f.field_name,
                value=str(f.value),
                source=FieldSource.AI if f.extractor == "ai" else (
                    FieldSource.PROSE if f.extractor == "prose" else (
                        FieldSource.LABEL if f.extractor == "label" else FieldSource.REGEX
                    )
                ),
                confidence=f.confidence,
                evidence=f.original_text or "",
            )
            if f.extractor == "ai":
                ai_candidates.append(candidate)
            else:
                det_candidates.append(candidate)

        # Reconcile
        reconciled = reconcile_fields(det_candidates, ai_candidates, self._policy)

        # Compute document-level confidence
        doc_confidence = compute_document_confidence(
            classification.confidence, reconciled
        )

        # Phase 4: De-duplicate and write records
        # Check BOTH confirmed claims AND existing claims from this document
        # to prevent duplicate claims on re-analysis
        seen: dict[tuple[str, object], ExtractedField] = {}
        for f in fields:
            key = (f.predicate_id, _norm(f.value))
            if key not in seen:
                seen[key] = f
        unique_fields = list(seen.values())

        # Pre-load existing claims for this document (any status) to avoid
        # creating duplicates on re-analysis
        existing_doc_claims = self._store.by_source(document_id)
        existing_doc_by_pred: dict[str, list] = {}
        for c in existing_doc_claims:
            existing_doc_by_pred.setdefault(c.predicate_id, []).append(c)

        duplicates: list[DuplicateHit] = []
        conflicts: list[ConflictHit] = []
        records: list[RecordOutcome] = []
        for f in unique_fields:
            # First check: has this exact field already been claimed for this document?
            doc_claim_match = None
            for ec in existing_doc_by_pred.get(f.predicate_id, []):
                if _norm(claim_value_key(ec)) == _norm(f.value):
                    doc_claim_match = ec
                    break
            if doc_claim_match is not None:
                # Already extracted and stored for this document — reuse, don't duplicate
                records.append(RecordOutcome(
                    f.predicate_id, f.value,
                    doc_claim_match.status.value if hasattr(doc_claim_match.status, 'value') else str(doc_claim_match.status),
                    claim_id=doc_claim_match.claim_id,
                    reason="existing",
                ))
                continue

            # Second check: duplicate against CONFIRMED claims from other documents
            existing = self._store.confirmed_by_predicate(f.predicate_id)
            dup = next(
                (c for c, _s in existing if _norm(claim_value_key(c)) == _norm(f.value)),
                None,
            )
            if dup is not None:
                duplicates.append(DuplicateHit(f.predicate_id, dup.claim_id, f.value))
                records.append(RecordOutcome(
                    f.predicate_id, f.value, "skipped", reason="duplicate",
                ))
                continue
            conflict = next(
                (c for c, _s in existing if _norm(claim_value_key(c)) != _norm(f.value)),
                None,
            )
            if conflict is not None:
                conflicts.append(ConflictHit(
                    f.predicate_id, conflict.claim_id,
                    claim_value_key(conflict), f.value,
                ))
                records.append(RecordOutcome(
                    f.predicate_id, f.value, "skipped", reason="conflict",
                ))
                continue
            records.append(self._write_record(f, document_id, version, acl_scope, spans))

        review_required = bool(duplicates or conflicts) or any(
            r.status != "auto_suggested" for r in records
        )
        if ai_rejected:
            review_required = True
        extraction_mode = (
            "ai_assisted" if any(f.extractor == "ai" for f in unique_fields)
            else "deterministic"
        )
        status = "unknown" if not records else ("review_required" if review_required else "ingested")

        return DocumentAnalysis(
            document_id=document_id,
            document_type_id=classification.document_type_id,
            confidence=doc_confidence,
            secondary_types=tuple(m.type_id for m in classification.secondary_types),
            target_module=target_module(classification.document_type_id or "general_document"),
            fields=tuple(unique_fields),
            records=tuple(records),
            duplicates=tuple(duplicates),
            conflicts=tuple(conflicts),
            review_required=review_required,
            status=status,
            extraction_mode=extraction_mode,
            ai_rejected=ai_rejected,
        )

    def _write_record(self, f: ExtractedField, document_id, version, acl_scope, spans) -> RecordOutcome:
        """Propose or AUTO_SUGGEST one claim; never fabricate, never auto-confirm."""
        can_suggest = (
            self._policy.allows_auto_suggest(f.predicate_id)
            and f.confidence >= 0.9
        )
        field_spans = list(f.spans) if f.spans else list(spans or [])
        try:
            if can_suggest:
                claim = self._claims.suggest(
                    predicate_id=f.predicate_id, raw_value=f.value,
                    source_text=f.original_text,
                    source_document_id=document_id, source_version=version,
                    spans=field_spans, acl_scope=acl_scope,
                    fact_confidence=f.confidence,
                )
                return RecordOutcome(f.predicate_id, f.value, "auto_suggested", claim.claim_id)
            claim = self._claims.propose(
                predicate_id=f.predicate_id, raw_value=f.value,
                source_text=f.original_text,
                source_document_id=document_id, source_version=version,
                spans=field_spans, acl_scope=acl_scope,
                fact_confidence=f.confidence,
            )
            return RecordOutcome(f.predicate_id, f.value, "proposed", claim.claim_id)
        except Exception:  # noqa: BLE001 - a single bad field must not fail the batch
            return RecordOutcome(f.predicate_id, f.value, "skipped", reason="write_failed")

    # ------------------------------------------------------------ extraction
    @staticmethod
    def _extract_field(spec, text: str) -> tuple[object, str, str]:
        """Return (normalized_value, original_text, extractor) or (None,...)."""
        kind = spec.extractor
        if kind == "doi":
            v = normalize_doi(text)
            return (v, v, "doi") if v else (None, "", kind)
        if kind == "email":
            v = normalize_email(text)
            return (v, v, "email") if v else (None, "", kind)
        if kind == "url":
            v = normalize_url(text)
            return (v, v, "url") if v else (None, "", kind)
        if kind == "date":
            # label-scoped when synonyms exist (e.g. "Start Date: ..."); when a
            # label is declared but absent, do NOT fall back to the whole
            # document (a prose "from X to Y" would otherwise grab the wrong
            # date and block the prose extractor) — return None instead.
            if spec.synonyms:
                lines = _label_lines(text, spec.synonyms)
                for line in lines:
                    v = normalize_date(line)
                    if v:
                        return (v, line.strip(), kind)
                return (None, "", kind)
            for line in text.splitlines():
                v = normalize_date(line)
                if v:
                    return (v, line.strip(), kind)
            return (None, "", kind)
        if kind == "amount":
            lines = _label_lines(text, spec.synonyms) or text.splitlines()
            for line in lines:
                v = normalize_amount(line)
                if v is not None:
                    return (v, line.strip(), kind)
            return (None, "", kind)
        if kind == "number":
            lines = _label_lines(text, spec.synonyms)
            # Only scan all lines if no synonyms specified (unstructured extraction)
            if not lines and not spec.synonyms:
                lines = text.splitlines()
            for line in lines:
                v = normalize_number(line)
                if v is not None:
                    return (v, line.strip(), kind)
            return (None, "", kind)
        # label extractor
        original = _extract_label_value(text, spec.synonyms)
        if original is None:
            return (None, "", kind)
        # normalize the value per the field's semantic type where known
        norm = normalize_text(original)
        return (norm, original, kind)

    @staticmethod
    def _canonical(value: object) -> object:
        """A comparable key for duplicate detection (None-safe)."""
        return _norm(value)


def _norm(value: object) -> object:
    """Case-fold strings for comparison (dates/amounts pass through)."""
    return value.casefold() if isinstance(value, str) else value


def _label_lines(text: str, synonyms: tuple[str, ...]) -> list[str]:
    """Lines whose label matches a synonym (for label-scoped date/amount/etc.)."""
    if not synonyms:
        return []
    syn = {s.casefold() for s in synonyms}
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if ":" in stripped:
            label = stripped.partition(":")[0].strip().casefold()
            if label in syn:
                out.append(stripped)
    return out


def _has_currency(line: str) -> bool:
    low = line.lower()
    return "₹" in low or "rs" in low or "inr" in low


#: Generic document headings that must NOT be treated as entity values.
_STOP_VALUES: set[str] = {
    "notice", "circular", "notification", "order", "letter", "memorandum",
    "certificate", "award", "grant", "sanction", "invoice", "bill",
    "report", "minutes", "agenda", "schedule", "timetable", "syllabus",
}

# Values starting with these words are likely heading fragments, not entity values
_HEADING_PREFIXES = {"of", "the", "and", "for", "in", "on", "at", "to", "from", "by"}

def _extract_label_value(text: str, synonyms: tuple[str, ...]) -> str | None:
    """Find "Label: value" or "Label value" where label matches a synonym."""
    syn = {s.casefold() for s in synonyms}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ":" in stripped:
            label, _, value = stripped.partition(":")
            if label.strip().casefold() in syn and value.strip():
                val = value.strip()
                # Reject generic document headings as entity values
                if val.casefold() in _STOP_VALUES:
                    continue
                return val
        # "Label value" form: leading known word then value
        first, _, rest = stripped.partition(" ")
        if first.casefold() in syn and rest.strip():
            val = rest.strip()
            # Reject generic document headings as entity values
            if val.casefold() in _STOP_VALUES:
                continue
            # Reject values starting with common prepositions (heading fragments like "OF DELHI")
            first_word = val.split()[0].lower() if val.split() else ""
            if first_word in _HEADING_PREFIXES:
                continue
            return val
    return None


__all__ = [
    "ConflictHit",
    "DocumentAnalysis",
    "DocumentIntakeService",
    "DuplicateHit",
    "ExtractedField",
    "RecordOutcome",
]
