"""Graph integrity validation (Sprint-2 M3).

Centralizes the graph invariants that were enforced ad hoc (or not at
all) across the relationship-producing use cases:

- **Target existence** — an edge must never point at a missing Object
  (dangling edges are the primary graph-consistency risk; they were only
  skipped at read time).
- **Target type** — some relationship kinds are typed (``RELATED_TO``
  from a committee must point at the committee's target types); the
  type expectation is expressed per call site.
- **Self-loop** — an Object must not point at itself (no legitimate
  use case creates one; the aggregate does not guard it).

Duplicate edges are already prevented by the aggregate's
``Relationship.identity`` key (physical UNIQUE in R1) — not duplicated
here.

Callers: relationship-producing use cases invoke ``assert_edges`` with
the targets they are about to link; the check is deliberately pure
(repository reads only, no writes).
"""
from __future__ import annotations

from app.application.exceptions import ValidationError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId


def assert_edge_targets(
    repository: ObjectRepository,
    edges: list[tuple[ObjectId, ObjectType | None]],
    *,
    source_id: ObjectId,
    label: str = "target",
) -> None:
    """Validate a batch of (target, expected_type) edges.

    Raises ValidationError (422 at the API) when a target is missing,
    carries the wrong type, or equals the source (self-loop). ``edges``
    may be empty; ``expected_type`` None skips the type check.
    """
    if not edges:
        return

    # One batch lookup for existence; type-check per object.
    ids = [target for target, _ in edges]
    by_id = {str(o.id): o for o in repository.find_by_ids(ids)}
    for target, expected_type in edges:
        if str(target) == str(source_id):
            raise ValidationError(f"{label} {target} must not be the source object itself.")
        obj = by_id.get(str(target))
        if obj is None:
            raise ValidationError(f"{label} {target} not found.")
        if expected_type is not None and obj.object_type is not expected_type:
            raise ValidationError(
                f"{label} {target} must be a {expected_type.value}; got {obj.object_type.value}."
            )


def assert_no_inbound_edges(
    repository: ObjectRepository,
    object_id: ObjectId,
) -> None:
    """Reject deletion of an Object that others still reference.

    Hard delete would orphan every inbound edge (dangling references are
    the graph's primary consistency risk — readers only skip them). The
    caller decides the policy: this validator surfaces the conflict and
    the caller may reject the delete or cascade.
    """
    inbound = repository.find_inbound(object_id)
    if inbound:
        raise ValidationError(
            f"Object {object_id} is referenced by {len(inbound)} other object(s); "
            "remove the relationships before deleting it."
        )
