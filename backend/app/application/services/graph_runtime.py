"""Production Object Graph runtime (Sprint-2 M2).

Multi-hop traversal over the R1 edge table with permission pre-filtering
(R4 seam, P2). Replaces the single-hop ObjectGraphUseCase — depth=1 is
byte-identical to the old behaviour.

Capabilities (the smallest production set):

- **BFS** — level-order traversal (neighbourhood / shortest-path search).
- **DFS** — iterative (explicit stack, no recursion risk) for dependency
  chains (VERSION_OF, PREREQUISITE_OF, ...).
- **Shortest path** — BFS with parent pointers, hop-limited.
- **Cycle detection** — DFS colouring over the ACL-filtered subgraph the
  traversal actually saw; cycles through invisible nodes are never
  reported (no edge-existence leak).

Loading discipline (no N+1): BFS collects every candidate of a frontier
level and loads them in ONE ``find_by_ids``; DFS and path search batch
each expanded node's candidates in one call. Total queries are
O(levels) + O(expanded nodes), never O(edges).

Safety bounds (constants): depth ≤ 5, nodes ≤ 200 (amplification
guard), path hops ≤ 5. Every visited node passes the READ check through
the R4 evaluator; deleted/dangling targets are skipped and never
expanded.
"""
from __future__ import annotations

from collections import deque

from app.application.exceptions import ObjectNotFoundError
from app.application.ports.permission import PermissionEvaluator
from app.application.use_cases.object_acl import object_acl_scope
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import PermissionAction, RelationshipKind
from app.domain.value_objects.object_id import ObjectId

MAX_DEPTH = 5
MAX_NODES = 200
MAX_HOPS = 5


class GraphRuntimeService:
    def __init__(
        self,
        repository: ObjectRepository,
        evaluator: PermissionEvaluator,
    ) -> None:
        self._repository = repository
        self._evaluator = evaluator

    # ------------------------------------------------------------- traversal
    def traverse(
        self,
        object_id: ObjectId,
        *,
        direction: str,
        kind: RelationshipKind | None,
        depth: int,
        mode: str,
        principal: dict | None,
    ) -> dict:
        if direction not in ("outgoing", "incoming"):
            raise ValueError("direction must be 'outgoing' or 'incoming'.")
        if mode not in ("bfs", "dfs"):
            raise ValueError("mode must be 'bfs' or 'dfs'.")
        if not 1 <= depth <= MAX_DEPTH:
            raise ValueError(f"depth must be between 1 and {MAX_DEPTH}.")

        if self._repository.get_by_id(object_id) is None:
            raise ObjectNotFoundError(f"Object not found: {object_id}")

        neighbours = self._neighbours_fn(direction, kind)
        if mode == "bfs":
            items, adjacency, truncated = self._bfs(object_id, neighbours, depth, principal)
        else:
            items, adjacency, truncated = self._dfs(object_id, neighbours, depth, principal)

        has_cycle, cycle_nodes = _detect_cycles(adjacency)
        return {
            "items": items,
            "total_count": len(items),
            "has_cycle": has_cycle,
            "cycle_nodes": cycle_nodes,
            "truncated": truncated,
        }

    # -------------------------------------------------------- shortest path
    def find_shortest_path(
        self,
        object_id: ObjectId,
        target: ObjectId,
        *,
        direction: str,
        kind: RelationshipKind | None,
        max_hops: int,
        principal: dict | None,
    ) -> dict:
        if direction not in ("outgoing", "incoming"):
            raise ValueError("direction must be 'outgoing' or 'incoming'.")
        if not 1 <= max_hops <= MAX_HOPS:
            raise ValueError(f"max_hops must be between 1 and {MAX_HOPS}.")

        if self._repository.get_by_id(object_id) is None:
            raise ObjectNotFoundError(f"Object not found: {object_id}")
        if self._repository.get_by_id(target) is None:
            raise ObjectNotFoundError(f"Object not found: {target}")

        neighbours = self._neighbours_fn(direction, kind)
        # BFS with parent pointers; hop-limited.
        visited = {str(object_id)}
        parents: dict[str, str] = {}
        queue: deque[tuple[str, int]] = deque([(str(object_id), 0)])
        found = None
        while queue:
            current, hops = queue.popleft()
            if hops >= max_hops:
                continue
            for nid, _obj in self._allowed_neighbours(current, neighbours, principal):
                if nid in visited:
                    continue
                visited.add(nid)
                parents[nid] = current
                if nid == str(target):
                    found = nid
                    queue.clear()
                    break
                queue.append((nid, hops + 1))

        if found is None:
            return {"found": False, "path": [], "hops": 0}
        path = []
        node = found
        while node is not None:
            path.append(node)
            node = parents.get(node)
        path.reverse()
        return {"found": True, "path": path, "hops": len(path) - 1}

    # ------------------------------------------------------------- internals
    def _neighbours_fn(self, direction: str, kind: RelationshipKind | None):
        if direction == "outgoing":
            return lambda oid: self._repository.find_related(oid, kind)
        return lambda oid: self._repository.find_inbound(oid, kind)

    def _bfs(self, root, neighbours, depth, principal):
        """Level-order with one batched load per frontier level."""
        items = []
        adjacency: dict[str, list[str]] = {}
        visited = {str(root)}
        frontier = [str(root)]
        truncated = False
        for level in range(1, depth + 1):
            # 1. raw neighbour ids of the whole frontier (per-node edge queries)
            raw_by_node: dict[str, list[ObjectId]] = {
                fid: neighbours(ObjectId(fid)) for fid in frontier
            }
            # 2. one batch load of every candidate, deduplicated
            all_candidates = {str(c) for raw in raw_by_node.values() for c in raw}
            loaded = self._load_objects([ObjectId(c) for c in all_candidates])
            # 3. filter per node, build adjacency + next frontier
            next_frontier: list[str] = []
            for fid, raw in raw_by_node.items():
                allowed = [
                    str(c)
                    for c in raw
                    if str(c) in loaded and self._can_read(loaded[str(c)], principal)
                ]
                adjacency[fid] = allowed
                for nid in allowed:
                    if nid in visited:
                        continue
                    if len(visited) >= MAX_NODES:
                        truncated = True
                        break  # amplification guard: stop collecting
                    visited.add(nid)
                    next_frontier.append(nid)
                    obj = loaded[nid]
                    items.append(
                        {
                            "id": nid,
                            "title": obj.title,
                            "object_type": obj.object_type.value,
                            "level": level,
                        }
                    )
                if truncated:
                    break
            if truncated or not next_frontier:
                break
            frontier = next_frontier
        return items, adjacency, truncated

    def _dfs(self, root, neighbours, depth, principal):
        """Depth-first with an explicit stack; one batched load per node."""
        items = []
        adjacency: dict[str, list[str]] = {}
        visited = {str(root)}
        truncated = False
        stack: list[tuple[str, int]] = [(str(root), 0)]
        while stack:
            node_id, level = stack.pop()
            if level >= depth:
                continue
            allowed = self._allowed_neighbours(node_id, neighbours, principal)
            adjacency[node_id] = [nid for nid, _obj in allowed]
            for nid, obj in reversed(allowed):
                if nid in visited:
                    continue
                if len(visited) >= MAX_NODES:
                    truncated = True
                    break  # amplification guard: stop collecting
                visited.add(nid)
                items.append(
                    {
                        "id": nid,
                        "title": obj.title,
                        "object_type": obj.object_type.value,
                        "level": level + 1,
                    }
                )
                stack.append((nid, level + 1))
            if truncated:
                break
        return items, adjacency, truncated

    def _allowed_neighbours(self, node_id: str, neighbours, principal):
        """One neighbours query + one batched load for the node's candidates.

        Returns (id, object) pairs for the READ-allowed, existing targets.
        """
        raw = neighbours(ObjectId(node_id))
        loaded = self._load_objects(raw)
        return [
            (str(c), loaded[str(c)])
            for c in raw
            if str(c) in loaded and self._can_read(loaded[str(c)], principal)
        ]

    def _load_objects(self, ids: list[ObjectId]) -> dict[str, UniversalObject]:
        """Batch-load objects; deleted ones are simply absent."""
        if not ids:
            return {}
        return {str(o.id): o for o in self._repository.find_by_ids(ids)}

    def _can_read(self, obj: UniversalObject, principal: dict | None) -> bool:
        return self._evaluator.can(
            principal=principal,
            scope=object_acl_scope(obj),
            action=PermissionAction.READ,
        )


def _detect_cycles(adjacency: dict[str, list[str]]) -> tuple[bool, list[str]]:
    """DFS colouring over the ACL-filtered subgraph.

    Returns (has_cycle, one cycle's node ids). Iterative; bounded by the
    traversal's node cap.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    colour: dict[str, int] = {node: WHITE for node in adjacency}
    for start in adjacency:
        if colour[start] is not WHITE:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        colour[start] = GRAY
        while stack:
            node, idx = stack[-1]
            neighbours = adjacency.get(node, [])
            if idx < len(neighbours):
                stack[-1] = (node, idx + 1)
                nxt = neighbours[idx]
                if colour.get(nxt, WHITE) is GRAY:
                    # Back edge: reconstruct the cycle from the stack.
                    return True, [n for n, _ in stack]
                if colour.get(nxt, WHITE) is WHITE:
                    colour[nxt] = GRAY
                    stack.append((nxt, 0))
            else:
                colour[node] = BLACK
                stack.pop()
    return False, []
