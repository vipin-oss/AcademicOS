"""object_relationships edge table

Revision ID: 0002_object_relationships
Revises: 0001_initial
Create Date: 2026-08-05

R1 — Object Graph physical model. Promotes the graph's edges from the embedded
``relationships_json`` JSON column on ``objects`` to a first-class
``object_relationships`` table.

Backward compatibility: existing rows are backfilled in array order (so row
``id`` order reproduces the original relationship list order), then the
redundant column is dropped. The downgrade reverses both steps and re-embeds
the edges as JSON, restoring the pre-R1 schema exactly.

Design notes:

- ``UNIQUE (source_id, target_id, kind, provenance)`` mirrors the domain's
  ``Relationship.identity`` de-duplication key.
- No FK on ``target_id``: the domain permits edges to not-yet-existing
  Objects (deferred edges), so a strict foreign key would reject legitimate
  writes.
- ``ON DELETE CASCADE`` from the source Object (PostgreSQL). SQLite parity is
  guaranteed by the repository's explicit edge deletion.
- ``created_at`` is stored as the ISO-8601 string produced by the snapshot
  layer, keeping the Domain <-> Snapshot round-trip lossless.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_object_relationships"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    is_pg = _is_postgresql()
    json_type = postgresql.JSONB() if is_pg else sa.JSON()

    op.create_table(
        "object_relationships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("provenance", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", json_type, nullable=False, server_default=sa.text("'[]'::jsonb" if is_pg else "'[]'")),
        sa.Column("acl_scope", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["objects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "source_id", "target_id", "kind", "provenance",
            name="uq_object_relationships_identity",
        ),
    )
    op.create_index(
        "ix_object_relationships_target_id",
        "object_relationships",
        ["target_id"],
    )

    # Backfill: one edge row per embedded relationship, in array order.
    # (The old column is NULL or a JSON object on never-written rows; guard
    # on json type 'array' so only genuine lists produce edges.)
    if is_pg:
        op.execute(
            """
            INSERT INTO object_relationships
                (source_id, target_id, kind, provenance, confidence,
                 evidence, acl_scope, created_at)
            SELECT o.id,
                   r.value ->> 'target',
                   r.value ->> 'kind',
                   r.value ->> 'provenance',
                   (r.value ->> 'confidence')::float8,
                   r.value -> 'evidence',
                   r.value ->> 'acl_scope',
                   r.value ->> 'created_at'
            FROM objects o,
                 jsonb_array_elements(o.relationships_json) WITH ORDINALITY
                     AS r(value, ord)
            WHERE jsonb_typeof(o.relationships_json) = 'array'
            ORDER BY o.id, r.ord
            """
        )
    else:
        op.execute(
            """
            INSERT INTO object_relationships
                (source_id, target_id, kind, provenance, confidence,
                 evidence, acl_scope, created_at)
            SELECT o.id,
                   json_extract(r.value, '$.target'),
                   json_extract(r.value, '$.kind'),
                   json_extract(r.value, '$.provenance'),
                   json_extract(r.value, '$.confidence'),
                   json_extract(r.value, '$.evidence'),
                   json_extract(r.value, '$.acl_scope'),
                   json_extract(r.value, '$.created_at')
            FROM objects o, json_each(o.relationships_json) AS r
            WHERE json_type(o.relationships_json) = 'array'
            """
        )

    op.drop_column("objects", "relationships_json")


def downgrade() -> None:
    is_pg = _is_postgresql()
    bind = op.get_bind()

    op.add_column(
        "objects",
        sa.Column(
            "relationships_json",
            postgresql.JSONB() if is_pg else sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb" if is_pg else "'{}'"),
        ),
    )

    # Re-embed edges as the legacy RelationshipSnapshot.to_dict() list,
    # dialect-portably, in Python. (Raw-SQL JSON aggregation is dialect-
    # specific and — on SQLite — the UPDATE..SET=(SELECT json_group_array(
    # json_object(...))) form fails at parse time, so introspection + typed
    # columns keeps this path identical and verifiable on both engines.)
    meta = sa.MetaData()
    objects_t = sa.Table("objects", meta, autoload_with=bind)
    edges_t = sa.Table("object_relationships", meta, autoload_with=bind)

    rows = bind.execute(
        sa.select(
            edges_t.c.source_id,
            edges_t.c.target_id,
            edges_t.c.kind,
            edges_t.c.provenance,
            edges_t.c.confidence,
            edges_t.c.evidence,
            edges_t.c.acl_scope,
            edges_t.c.created_at,
        ).order_by(edges_t.c.source_id, edges_t.c.id)
    ).fetchall()

    relationships_by_source: dict[str, list[dict]] = {}
    for row in rows:
        relationships_by_source.setdefault(row.source_id, []).append(
            {
                "target": row.target_id,
                "kind": row.kind,
                "provenance": row.provenance,
                "confidence": row.confidence,
                "evidence": list(row.evidence or ()),
                "acl_scope": row.acl_scope,
                "created_at": row.created_at,
            }
        )

    for source_id, relationships in relationships_by_source.items():
        bind.execute(
            objects_t.update()
            .where(objects_t.c.id == source_id)
            .values(relationships_json=relationships)
        )

    op.drop_index("ix_object_relationships_target_id", table_name="object_relationships")
    op.drop_table("object_relationships")
