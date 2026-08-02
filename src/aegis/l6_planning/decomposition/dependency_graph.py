"""L6 Planning Engine — Dependency Graph.

Pure-Python Directed Acyclic Graph (DAG) for task dependencies.
No external graph library — fully self-contained.

Supports:
  - Task node registration
  - Directed dependency edges
  - Cycle detection (DFS-based)
  - Topological sort (Kahn's algorithm)
  - Critical path calculation
  - Parallel group identification

Import safety: stdlib only.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

__all__ = ["DependencyGraph", "GraphNode"]


@dataclass
class GraphNode:
    """A node in the dependency graph."""

    node_id: str
    title: str
    weight: float = 1.0          # estimated duration (arbitrary units)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"GraphNode({self.node_id!r}, {self.title!r})"


class DependencyGraph:
    """Directed Acyclic Graph for task dependency management.

    All node IDs are strings. Edges are directed: A → B means
    "B depends on A" (A must complete before B starts).

    Usage::

        g = DependencyGraph()
        g.add_node("t1", "Define requirements")
        g.add_node("t2", "Implement feature", weight=3.0)
        g.add_edge("t1", "t2")   # t2 depends on t1
        order = g.topological_sort()   # ["t1", "t2"]
        cycles = g.detect_cycles()     # [] — no cycles
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        # adjacency: predecessors[node_id] = {nodes that must run before node_id}
        self._predecessors: dict[str, set[str]] = defaultdict(set)
        # successors[node_id] = {nodes that must run after node_id}
        self._successors: dict[str, set[str]] = defaultdict(set)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, node_id: str, title: str, weight: float = 1.0, **metadata: Any) -> None:
        """Register a task node. Idempotent."""
        if node_id not in self._nodes:
            self._nodes[node_id] = GraphNode(node_id=node_id, title=title, weight=weight, metadata=metadata)
            # Ensure entries in adjacency dicts
            self._predecessors.setdefault(node_id, set())
            self._successors.setdefault(node_id, set())

    def add_edge(self, from_id: str, to_id: str) -> None:
        """Add a dependency edge: to_id depends on from_id.

        Args:
            from_id: The node that must complete first.
            to_id:   The node that depends on from_id.

        Raises:
            ValueError: If either node is not registered.
        """
        if from_id not in self._nodes:
            raise ValueError(f"Node {from_id!r} not found. Register it with add_node() first.")
        if to_id not in self._nodes:
            raise ValueError(f"Node {to_id!r} not found. Register it with add_node() first.")
        self._predecessors[to_id].add(from_id)
        self._successors[from_id].add(to_id)

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its edges."""
        if node_id not in self._nodes:
            return
        del self._nodes[node_id]
        # Clean up adjacency
        for preds in self._predecessors.values():
            preds.discard(node_id)
        for succs in self._successors.values():
            succs.discard(node_id)
        del self._predecessors[node_id]
        del self._successors[node_id]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(preds) for preds in self._predecessors.values())

    def nodes(self) -> list[GraphNode]:
        return list(self._nodes.values())

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def predecessors(self, node_id: str) -> set[str]:
        """Return IDs of nodes that must complete before node_id."""
        return set(self._predecessors.get(node_id, set()))

    def successors(self, node_id: str) -> set[str]:
        """Return IDs of nodes that depend on node_id."""
        return set(self._successors.get(node_id, set()))

    def roots(self) -> list[str]:
        """Return node IDs with no predecessors (can start immediately)."""
        return [nid for nid in self._nodes if not self._predecessors[nid]]

    def leaves(self) -> list[str]:
        """Return node IDs with no successors (final tasks)."""
        return [nid for nid in self._nodes if not self._successors[nid]]

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    def detect_cycles(self) -> list[list[str]]:
        """Detect all cycles in the graph using DFS.

        Returns:
            List of cycles (each cycle is a list of node IDs).
            Empty list means the graph is acyclic.
        """
        cycles: list[list[str]] = []
        visited: set[str] = set()
        in_stack: set[str] = set()
        stack: list[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            in_stack.add(node)
            stack.append(node)

            for successor in self._successors.get(node, set()):
                if successor not in visited:
                    dfs(successor)
                elif successor in in_stack:
                    # Found a cycle — extract it
                    cycle_start = stack.index(successor)
                    cycles.append(stack[cycle_start:] + [successor])

            stack.pop()
            in_stack.discard(node)

        for node_id in self._nodes:
            if node_id not in visited:
                dfs(node_id)

        return cycles

    def is_acyclic(self) -> bool:
        """Return True if the graph has no cycles."""
        return len(self.detect_cycles()) == 0

    # ------------------------------------------------------------------
    # Topological sort (Kahn's algorithm)
    # ------------------------------------------------------------------

    def topological_sort(self) -> list[str]:
        """Return nodes in topological order (dependencies before dependents).

        Returns:
            Ordered list of node IDs.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        in_degree = {nid: len(self._predecessors[nid]) for nid in self._nodes}
        queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
        result: list[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for successor in sorted(self._successors.get(node, set())):  # sorted for determinism
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        if len(result) != len(self._nodes):
            cycles = self.detect_cycles()
            cycle_str = " → ".join(cycles[0]) if cycles else "unknown"
            raise ValueError(f"Graph contains a cycle: {cycle_str}")

        return result

    # ------------------------------------------------------------------
    # Critical path
    # ------------------------------------------------------------------

    def critical_path(self) -> list[str]:
        """Return the critical path (longest weighted path from root to leaf).

        Uses dynamic programming on the topological order.

        Returns:
            Ordered list of node IDs on the critical path.
        """
        if not self._nodes:
            return []

        topo = self.topological_sort()
        # earliest[node] = (earliest_start_time, predecessor_on_critical_path)
        earliest: dict[str, tuple[float, str | None]] = {}

        for node_id in topo:
            preds = self._predecessors.get(node_id, set())
            if not preds:
                earliest[node_id] = (0.0, None)
            else:
                best_pred = max(
                    preds,
                    key=lambda p: earliest[p][0] + self._nodes[p].weight,
                )
                earliest[node_id] = (
                    earliest[best_pred][0] + self._nodes[best_pred].weight,
                    best_pred,
                )

        # Find the leaf with the latest finish time
        leaves = self.leaves()
        if not leaves:
            return topo

        last_node = max(leaves, key=lambda n: earliest[n][0] + self._nodes[n].weight)

        # Trace back
        path: list[str] = []
        current: str | None = last_node
        while current is not None:
            path.append(current)
            current = earliest[current][1]

        return list(reversed(path))

    # ------------------------------------------------------------------
    # Parallel groups
    # ------------------------------------------------------------------

    def parallel_groups(self) -> list[list[str]]:
        """Return groups of nodes that can execute in parallel.

        Nodes in the same group share the same topological level —
        all their predecessors are in earlier groups.

        Returns:
            List of groups (each group = list of node IDs that can run together).
        """
        if not self._nodes:
            return []

        in_degree = {nid: len(self._predecessors[nid]) for nid in self._nodes}
        groups: list[list[str]] = []
        remaining = set(self._nodes.keys())

        while remaining:
            # All nodes in `remaining` with in-degree 0 form the next parallel group
            group = sorted(nid for nid in remaining if in_degree[nid] == 0)
            if not group:
                # Cycle — shouldn't happen if is_acyclic() was checked first
                break
            groups.append(group)
            for node_id in group:
                remaining.remove(node_id)
                for successor in self._successors.get(node_id, set()):
                    if successor in remaining:
                        in_degree[successor] -= 1

        return groups

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph to a plain dict (JSON-safe)."""
        return {
            "nodes": {
                nid: {"title": n.title, "weight": n.weight, "metadata": n.metadata}
                for nid, n in self._nodes.items()
            },
            "edges": [
                {"from": pred, "to": nid}
                for nid, preds in self._predecessors.items()
                for pred in preds
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DependencyGraph":
        """Restore a DependencyGraph from a serialized dict."""
        g = cls()
        for nid, attrs in data.get("nodes", {}).items():
            g.add_node(nid, attrs["title"], attrs.get("weight", 1.0), **attrs.get("metadata", {}))
        for edge in data.get("edges", []):
            g.add_edge(edge["from"], edge["to"])
        return g

    def __repr__(self) -> str:
        return f"DependencyGraph(nodes={self.node_count}, edges={self.edge_count})"
