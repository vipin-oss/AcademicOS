"""L1 source registration service (format-agnostic SOURCE contract).

Persists the source contract (media kind, blob key, container provenance,
engine stamp, extraction state) onto a ``document`` object's metadata. The
original blob key is the evidence binding: every span/claim/CDM derived from
this source resolves back to the stored original artifact.

L1 only *registers* the contract; it does not parse/OCR/vision the source.
"""

from __future__ import annotations

from app.application.use_cases.object_acl import object_acl_scope
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer, Provenance
from app.domain.value_objects.source import (
    KEY_SOURCE_BLOB_KEY,
    KEY_SOURCE_CONTAINER_ID,
    KEY_SOURCE_CONTAINER_PATH,
    KEY_SOURCE_ENGINE,
    KEY_SOURCE_ENGINE_VERSION,
    KEY_SOURCE_EXTRACTION_STATE,
    KEY_SOURCE_MEDIA_KIND,
    MediaKind,
    SourceContract,
)


def _entry(key: str, value: str) -> MetadataEntry:
    return MetadataEntry(key, value, MetadataLayer.L2_FILESYSTEM, Provenance.SYSTEM)


def register_source(obj: UniversalObject, contract: SourceContract) -> None:
    """Stamp the source contract onto the document object (system layer)."""
    obj.set_metadata(_entry(KEY_SOURCE_MEDIA_KIND, contract.media_kind.value))
    obj.set_metadata(_entry(KEY_SOURCE_BLOB_KEY, contract.blob_key))
    if contract.container_source_id:
        obj.set_metadata(
            _entry(KEY_SOURCE_CONTAINER_ID, contract.container_source_id)
        )
    if contract.container_path:
        obj.set_metadata(_entry(KEY_SOURCE_CONTAINER_PATH, contract.container_path))
    if contract.engine:
        obj.set_metadata(_entry(KEY_SOURCE_ENGINE, contract.engine))
    if contract.engine_version is not None:
        obj.set_metadata(
            _entry(KEY_SOURCE_ENGINE_VERSION, str(contract.engine_version))
        )
    obj.set_metadata(_entry(KEY_SOURCE_EXTRACTION_STATE, contract.extraction_state))


def read_source_contract(obj: UniversalObject) -> SourceContract:
    """Reconstruct the SourceContract from a document object's metadata."""
    media = obj.metadata.get_value(KEY_SOURCE_MEDIA_KIND)
    blob = obj.metadata.get_value(KEY_SOURCE_BLOB_KEY) or ""
    container_id = obj.metadata.get_value(KEY_SOURCE_CONTAINER_ID)
    container_path = obj.metadata.get_value(KEY_SOURCE_CONTAINER_PATH)
    engine = obj.metadata.get_value(KEY_SOURCE_ENGINE)
    engine_version = obj.metadata.get_value(KEY_SOURCE_ENGINE_VERSION)
    state = obj.metadata.get_value(KEY_SOURCE_EXTRACTION_STATE) or "unprocessed"
    return SourceContract(
        source_id=str(obj.id),
        media_kind=MediaKind(media) if media and media in MediaKind._value2member_map_ else MediaKind.UNKNOWN,
        blob_key=blob,
        version=obj.version,
        container_source_id=container_id,
        container_path=container_path,
        engine=engine,
        engine_version=int(engine_version) if engine_version and engine_version.isdigit() else None,
        extraction_state=state,
        provenance=Provenance.SYSTEM,
    )


def acl_scope_of(obj: UniversalObject) -> str | None:
    """The ACL scope string for derived rows of this source object."""
    return object_acl_scope(obj)
