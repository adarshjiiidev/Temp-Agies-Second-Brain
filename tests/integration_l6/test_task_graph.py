"""Integration tests — L6 Dependency Graph (DAG)."""

from __future__ import annotations

import pytest

from aegis.l6_planning.decomposition.dependency_graph import DependencyGraph


@pytest.fixture
def empty_graph():
    return DependencyGraph()


@pytest.fixture
def linear_graph():
    g = DependencyGraph()
    for i in range(5):
        g.add_node(f"n{i}", f"Node {i}")
    for i in range(4):
        g.add_edge(f"n{i}", f"n{i+1}")
    return g


@pytest.fixture
def parallel_graph():
    g = DependencyGraph()
    g.add_node("root", "Root")
    g.add_node("a", "Branch A")
    g.add_node("b", "Branch B")
    g.add_node("merge", "Merge")
    g.add_edge("root", "a")
    g.add_edge("root", "b")
    g.add_edge("a", "merge")
    g.add_edge("b", "merge")
    return g


class TestDependencyGraphBasics:
    def test_add_nodes(self, empty_graph):
        empty_graph.add_node("t1", "Task 1")
        assert empty_graph.node_count == 1

    def test_add_node_idempotent(self, empty_graph):
        empty_graph.add_node("t1", "Task 1")
        empty_graph.add_node("t1", "Task 1 duplicate")  # idempotent
        assert empty_graph.node_count == 1

    def test_add_edge_registers_dependency(self, empty_graph):
        empty_graph.add_node("a", "A")
        empty_graph.add_node("b", "B")
        empty_graph.add_edge("a", "b")
        assert "a" in empty_graph.predecessors("b")
        assert "b" in empty_graph.successors("a")

    def test_add_edge_unknown_node_raises(self, empty_graph):
        empty_graph.add_node("a", "A")
        with pytest.raises(ValueError, match="not found"):
            empty_graph.add_edge("a", "unknown")

    def test_roots_identified(self, linear_graph):
        roots = linear_graph.roots()
        assert roots == ["n0"]

    def test_leaves_identified(self, linear_graph):
        leaves = linear_graph.leaves()
        assert leaves == ["n4"]

    def test_empty_graph_has_no_roots(self, empty_graph):
        assert empty_graph.roots() == []


class TestCycleDetection:
    def test_acyclic_graph_no_cycles(self, linear_graph):
        assert linear_graph.is_acyclic()
        assert linear_graph.detect_cycles() == []

    def test_self_loop_detected(self, empty_graph):
        empty_graph.add_node("a", "A")
        empty_graph.add_edge("a", "a")
        cycles = empty_graph.detect_cycles()
        assert len(cycles) > 0

    def test_two_node_cycle_detected(self, empty_graph):
        empty_graph.add_node("a", "A")
        empty_graph.add_node("b", "B")
        empty_graph.add_edge("a", "b")
        empty_graph.add_edge("b", "a")
        assert not empty_graph.is_acyclic()


class TestTopologicalSort:
    def test_linear_order(self, linear_graph):
        order = linear_graph.topological_sort()
        assert order == ["n0", "n1", "n2", "n3", "n4"]

    def test_cyclic_graph_raises(self, empty_graph):
        empty_graph.add_node("a", "A")
        empty_graph.add_node("b", "B")
        empty_graph.add_edge("a", "b")
        empty_graph.add_edge("b", "a")
        with pytest.raises(ValueError, match="cycle"):
            empty_graph.topological_sort()

    def test_parallel_graph_order_correct(self, parallel_graph):
        order = parallel_graph.topological_sort()
        assert order.index("root") < order.index("a")
        assert order.index("root") < order.index("b")
        assert order.index("a") < order.index("merge")
        assert order.index("b") < order.index("merge")


class TestCriticalPath:
    def test_linear_critical_path(self, linear_graph):
        path = linear_graph.critical_path()
        assert path[0] == "n0"
        assert path[-1] == "n4"

    def test_critical_path_single_node(self, empty_graph):
        empty_graph.add_node("solo", "Solo")
        path = empty_graph.critical_path()
        assert path == ["solo"]


class TestParallelGroups:
    def test_parallel_graph_groups(self, parallel_graph):
        groups = parallel_graph.parallel_groups()
        assert len(groups) >= 3
        # First group is root
        assert groups[0] == ["root"]
        # Second group has a and b (parallel)
        second = sorted(groups[1])
        assert second == ["a", "b"]

    def test_linear_graph_no_parallelism(self, linear_graph):
        groups = linear_graph.parallel_groups()
        # Each group has exactly 1 task
        assert all(len(g) == 1 for g in groups)


class TestSerialization:
    def test_round_trip(self, parallel_graph):
        data = parallel_graph.to_dict()
        restored = DependencyGraph.from_dict(data)
        assert restored.node_count == parallel_graph.node_count
        assert restored.edge_count == parallel_graph.edge_count
