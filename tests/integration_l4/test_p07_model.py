"""P07 model types tests — EnvNode, EnvEdge, ScanResult, enumerations."""

from __future__ import annotations

import pytest

from aegis.l4_memory.p07.model.types import (
    CandidateStatus,
    EnvEdge,
    EnvEdgeKind,
    EnvNode,
    EnvNodeKind,
    ObserverState,
    ScanResult,
    ScannerState,
)
from aegis.l4_memory.p07.model.freshness import FreshnessTracker, ScannerFreshness


class TestEnvNode:
    def test_basic_creation(self):
        node = EnvNode(
            key="app:vscode",
            kind=EnvNodeKind.APPLICATION,
            label="Visual Studio Code",
        )
        assert node.key == "app:vscode"
        assert node.kind == EnvNodeKind.APPLICATION
        assert node.label == "Visual Studio Code"
        assert node.privacy_tier == "P2"
        assert node.namespace == "p07_env"

    def test_frozen(self):
        node = EnvNode(key="x", kind=EnvNodeKind.TOOL, label="x")
        with pytest.raises((TypeError, AttributeError)):
            node.label = "changed"  # type: ignore[misc]

    def test_all_node_kinds(self):
        kinds = list(EnvNodeKind)
        assert len(kinds) >= 5
        assert EnvNodeKind.APPLICATION in kinds
        assert EnvNodeKind.PROJECT in kinds
        assert EnvNodeKind.TOOL in kinds


class TestEnvEdge:
    def test_basic_creation(self):
        edge = EnvEdge(
            subject_key="app:vscode",
            object_key="project:aegis",
            kind=EnvEdgeKind.USES,
        )
        assert edge.subject_key == "app:vscode"
        assert edge.kind == EnvEdgeKind.USES
        assert edge.confidence == 0.7

    def test_all_edge_kinds(self):
        kinds = list(EnvEdgeKind)
        assert EnvEdgeKind.USES in kinds
        assert EnvEdgeKind.CONTAINS in kinds
        assert EnvEdgeKind.DEPENDS_ON in kinds


class TestScanResult:
    def test_empty_result_succeeded(self):
        result = ScanResult(scanner_name="test")
        assert result.succeeded
        assert result.nodes == []
        assert result.error is None

    def test_error_result_not_succeeded(self):
        result = ScanResult(scanner_name="test", error="disk full")
        assert not result.succeeded

    def test_with_nodes(self):
        nodes = [
            EnvNode(key="app:git", kind=EnvNodeKind.TOOL, label="git"),
            EnvNode(key="app:python", kind=EnvNodeKind.APPLICATION, label="python"),
        ]
        result = ScanResult(scanner_name="app_scanner", nodes=nodes)
        assert len(result.nodes) == 2
        assert result.succeeded


class TestFreshnessTracker:
    def test_fresh_after_mark_scanned(self):
        tracker = FreshnessTracker()
        tracker.register("app_scanner", ttl_seconds=3600)
        tracker.mark_scanned("app_scanner")
        assert not tracker.is_stale("app_scanner")
        assert tracker.age_seconds("app_scanner") < 3600

    def test_stale_when_never_scanned(self):
        tracker = FreshnessTracker()
        tracker.register("app_scanner", ttl_seconds=3600)
        assert tracker.is_stale("app_scanner")

    def test_unregistered_scanner_is_stale(self):
        tracker = FreshnessTracker()
        assert tracker.is_stale("never_seen")
        assert tracker.age_seconds("never_seen") == float("inf")

    def test_all_stale_lists_stale_scanners_only(self):
        tracker = FreshnessTracker()
        for name in ("app_scanner", "cli_scanner", "project_scanner"):
            tracker.register(name, ttl_seconds=3600)
        tracker.mark_scanned("app_scanner")
        stale = tracker.all_stale()
        assert stale == ["cli_scanner", "project_scanner"]


class TestScannerFreshness:
    def test_never_scanned_is_stale(self):
        rec = ScannerFreshness(scanner_name="test", default_ttl_seconds=60)
        assert rec.never_scanned
        assert rec.is_stale

    def test_mark_scanned_resets_staleness(self):
        rec = ScannerFreshness(scanner_name="test", default_ttl_seconds=3600)
        rec.mark_scanned()
        assert not rec.never_scanned
        assert not rec.is_stale
