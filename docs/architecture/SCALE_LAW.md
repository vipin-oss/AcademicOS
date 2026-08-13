# Scale law (M-5 / Freeze Contract Part 8 + §13.2.2)

Doctrine for 1M documents. **Mechanisms** land at L10–L12. L0 records
the law so scale cannot justify a new architecture.

## Working architecture (do not replace without measured evidence)

PostgreSQL + Qdrant + one worker pool + existing Next.js + existing LLM
gateway.

**Forbidden without measured evidence:** Kafka, Elasticsearch, Temporal,
a new database, a new queue, an event bus, or a microservice — merely
because “scale” was mentioned.

## Planned mechanisms at 1M (additive, triggered by measurement)

| Concern | 1M mechanism |
|---|---|
| Storage | object storage + tiering + cold archive (behind the existing storage port) |
| FTS | PostgreSQL partition + optional read replicas; no new search engine without evidence |
| Chunks | PostgreSQL partitioned keyed rows |
| Vectors | Qdrant multi-node / sharding; alias swap retained |
| Workers | horizontal worker pool + batch reprocessing |
| Outbox | same single relay; scale via batch sizes |
| Rebuild | windowed / parallel rebuild |
| ACL | `acl_scope` + partitions + cached scopes where justified |
| Query latency | <300ms p95 (cache frequent queries) |

One writer per projection. All projections rebuildable. Dedupe before
embed. Memory budgets stay in indexes, never in unbounded context.
