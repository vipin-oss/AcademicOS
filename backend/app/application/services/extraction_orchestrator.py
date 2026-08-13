"""L2 ingestion orchestrator (application layer, ADR-028).

Drives the full ingestion path for one source blob, staying format-agnostic:

1. detect format (family/media kind) and record MIME/content mismatch honestly;
2. if a container -> expand into members (each member an independent Source);
3. for each supported source -> engine parse -> ``NirDocument`` (transient);
4. NIR mapper -> L1 CDM blocks (via ``CdmService``); optional proposed claims
   (via ``ClaimService``);
5. register the SourceContract on the document object;
6. write the content projection (via ``DocumentContentStore``) for search;
7. record a provenance/nir descriptor.

This orchestrator depends only on application ports/services (no engine
libraries, no SQLAlchemy). Infrastructure injects the parser registry,
container expander, and store implementations.
"""

from __future__ import annotations

import dataclasses
import hashlib

from app.application.dtos.extraction import ExtractionStatus
from app.application.dtos.nir import NirDocument
from app.application.ports.container_expander import ContainerExpander, ContainerMember
from app.application.ports.document_content_store import DocumentContentStore
from app.application.ports.nir_parser import NirParser
from app.application.services.nir_mapper import NirMapper
from app.application.services.claim_service import ClaimService
from app.application.services.source_service import register_source
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.source import MediaKind, SourceContract


@dataclasses.dataclass
class MemberIngestResult:
    path: str
    ok: bool
    error: str | None = None
    document_id: str | None = None
    media_kind: str | None = None
    elements: int = 0
    needs_ocr: bool = False


@dataclasses.dataclass
class IngestionResult:
    source_id: str
    family: str | None
    media_kind: str
    status: str
    elements: int = 0
    pages: int = 0
    slides: int = 0
    sheets: int = 0
    images: int = 0
    needs_ocr: bool = False
    warning: str | None = None
    members: tuple[MemberIngestResult, ...] = ()
    engine: str | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ExtractionOrchestrator:
    def __init__(
        self,
        *,
        parsers: dict[str, NirParser],
        expander: ContainerExpander,
        mapper: NirMapper,
        content_store: DocumentContentStore | None = None,
        claim_service: "ClaimService | None" = None,
    ) -> None:
        self._parsers = parsers
        self._expander = expander
        self._mapper = mapper
        self._content_store = content_store
        self._claim_service = claim_service

    def ingest_blob(
        self,
        *,
        document: UniversalObject,
        blob: bytes,
        file_name: str,
        extension: str,
        family: str | None,
        media_kind: MediaKind,
        version: int,
        acl_scope: str | None = None,
        blob_key: str | None = None,
        container_source_id: str | None = None,
        container_path: str | None = None,
        ocr_enabled: bool = False,
    ) -> IngestionResult:
        """Ingest one blob (a direct upload or a single container member)."""
        source_contract = SourceContract(
            source_id=str(document.id),
            media_kind=media_kind,
            blob_key=blob_key or f"documents/{document.id}",
            file_sha256=_sha256(blob),
            version=version,
            container_source_id=container_source_id,
            container_path=container_path,
            extraction_state="processed",
            needs_ocr=False,
        )
        register_source(document, source_contract)

        if media_kind is MediaKind.PACKAGE:
            return self._ingest_package(
                document=document, blob=blob, file_name=file_name,
                acl_scope=acl_scope, version=version,
                container_source_id=container_source_id,
            )

        if family is None or family not in self._parsers:
            return IngestionResult(
                source_id=str(document.id), family=family,
                media_kind=media_kind.value, status=ExtractionStatus.UNSUPPORTED.value,
                warning=f"Unsupported format: {extension or '(none)'}.",
            )

        try:
            nir = self._parsers[family].parse(
                blob, source_id=str(document.id), version=version
            )
        except Exception as exc:  # noqa: BLE001 - engine boundary
            return IngestionResult(
                source_id=str(document.id), family=family,
                media_kind=media_kind.value, status="error",
                warning=f"Extraction failed ({type(exc).__name__}: {exc}).",
            )

        return self._persist_nir(
            document=document, nir=nir, family=family, acl_scope=acl_scope,
            version=version,
        )

    def _persist_nir(
        self,
        *,
        document: UniversalObject,
        nir: NirDocument,
        family: str,
        acl_scope: str | None,
        version: int,
    ) -> IngestionResult:
        # CDM blocks via L1
        block_count = self._mapper.write_cdm(
            nir, document_id=str(document.id), acl_scope=acl_scope
        )
        # extraction→claim bridge (ADR-034): propose PROPOSED claims
        if self._claim_service is not None:
            self._mapper.write_claims(
                nir,
                document_id=str(document.id),
                acl_scope=acl_scope,
                claim_service=self._claim_service,
                ocr_derived=nir.needs_ocr,
            )
        # content projection for search
        if self._content_store is not None and nir.text:
            self._content_store.upsert(
                object_id=str(document.id),
                version=version,
                content_text=nir.text,
                source_item_id=str(document.id),
                content_hash=_sha256(nir.text.encode("utf-8")),
            )
        # mark source extraction state + needs_ocr honesty
        contract = SourceContract(
            source_id=str(document.id),
            media_kind=MediaKind(nir.media_kind),
            blob_key=f"documents/{document.id}",
            version=version,
            extraction_state="extracted",
            needs_ocr=nir.needs_ocr,
            engine=nir.engine,
            engine_version=nir.engine_version,
        )
        register_source(document, contract)

        return IngestionResult(
            source_id=str(document.id), family=family,
            media_kind=nir.media_kind, status=ExtractionStatus.EXTRACTED.value,
            elements=block_count, pages=nir.pages, slides=nir.slides,
            sheets=len(nir.sheets), images=len(nir.images),
            needs_ocr=nir.needs_ocr,
            engine=nir.engine,
            warning="; ".join(nir.warnings) if nir.warnings else None,
        )

    def _ingest_package(
        self,
        *,
        document: UniversalObject,
        blob: bytes,
        file_name: str,
        acl_scope: str | None,
        version: int,
        container_source_id: str | None,
    ) -> IngestionResult:
        try:
            members = self._expander.expand(blob)
        except Exception as exc:  # noqa: BLE001 - unsafe whole package
            return IngestionResult(
                source_id=str(document.id), family="zip",
                media_kind=MediaKind.PACKAGE.value, status="error",
                warning=f"Container unsafe/corrupt: {exc}.",
            )
        results: list[MemberIngestResult] = []
        total_elements = 0
        for member in members:
            results.append(self._ingest_member(member, document, acl_scope, version))
            if results[-1].ok:
                total_elements += results[-1].elements
        ok = [m for m in results if m.ok]
        return IngestionResult(
            source_id=str(document.id), family="zip",
            media_kind=MediaKind.PACKAGE.value, status=ExtractionStatus.EXTRACTED.value,
            elements=total_elements, members=tuple(results),
            warning=None if len(ok) == len(results) else "Some members could not be ingested.",
        )

    def _ingest_member(
        self,
        member: ContainerMember,
        package_document: UniversalObject,
        acl_scope: str | None,
        version: int,
    ) -> MemberIngestResult:
        if not member.ok:
            return MemberIngestResult(path=member.path, ok=False, error=member.error)
        ext = member.path.rsplit(".", 1)[-1].lower() if "." in member.path else ""
        from app.application.dtos.extraction import format_of

        family = format_of(ext)
        media_kind = MediaKind.from_extension(ext)
        if media_kind is MediaKind.PACKAGE:
            return MemberIngestResult(
                path=member.path, ok=False,
                error="Nested container not auto-expanded (depth limit); member recorded.",
            )
        if family is None or family not in self._parsers:
            return MemberIngestResult(
                path=member.path, ok=False,
                error=f"Unsupported member format (.{ext}).",
            )
        try:
            nir = self._parsers[family].parse(
                member.data, source_id=f"{package_document.id}:{member.path}",
                version=version,
            )
        except Exception as exc:  # noqa: BLE001
            return MemberIngestResult(
                path=member.path, ok=False,
                error=f"Member extraction failed: {exc}.",
            )
        # members write CDM/content scoped under a pseudo-document id
        member_doc_id = f"{package_document.id}:{member.path}"
        block_count = self._mapper.write_cdm(
            nir, document_id=member_doc_id, acl_scope=acl_scope
        )
        # propose claims for the member too (ADR-034)
        if self._claim_service is not None:
            self._mapper.write_claims(
                nir,
                document_id=member_doc_id,
                acl_scope=acl_scope,
                claim_service=self._claim_service,
                ocr_derived=nir.needs_ocr,
            )
        if self._content_store is not None and nir.text:
            self._content_store.upsert(
                object_id=member_doc_id, version=version,
                content_text=nir.text, source_item_id=str(package_document.id),
                content_hash=_sha256(nir.text.encode("utf-8")),
            )
        return MemberIngestResult(
            path=member.path, ok=True, document_id=member_doc_id,
            media_kind=nir.media_kind, elements=block_count,
            needs_ocr=nir.needs_ocr,
        )
