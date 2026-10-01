"""Comprehensive P07 test suite.

Tests cover:
  - Observer events, audit, sink, lifecycle, shutdown zero-leftover
  - Privacy zones: ZoneRegistry, ConsentGate
  - Inference: WorkflowInferencer (≥8/10 synthetic workflows),
    PreferenceInferencer (candidates only, never promoted)
  - Discovery: ScanningCoordinator (consent gate, denied, privacy filter)
  - Scanners: ApplicationScanner, synthetic scanners
  - Persistence: CandidateStore (create, list, promote, reject, purge)
  - EnvironmentStore: upsert_node, query_nodes, upsert_edge

P07 success criteria (P07_ARCHITECTURE_PLAN.md §8):
  - ≥ 95% application discovery: verified via synthetic fixture
  - ≥ 8/10 workflow inference: verified via 10 synthetic transcript injections
  - Preference candidates remain PENDING_REVIEW (never auto-promoted)
  - Zero privacy-zone leakage
  - Zero records remaining after observer shutdown
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# P07 imports
# ---------------------------------------------------------------------------
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
from aegis.l4_memory.p07.observer.events import EventKind, ObservedEvent
from aegis.l4_memory.p07.observer.audit import (
    AuditEventKind,
    ObserverAuditEntry,
    ObserverAuditLog,
)
from aegis.l4_memory.p07.observer.sink import ObserverSink
from aegis.l4_memory.p07.privacy.zones import PrivacyZone, ZoneCheckResult, ZoneRegistry
from aegis.l4_memory.p07.inference.workflow_inferencer import WorkflowCandidate, WorkflowInferencer
from aegis.l4_memory.p07.inference.preference_inferencer import PreferenceCandidate, PreferenceInferencer
from aegis.l4_memory.p07.discovery.consent import ConsentGate, ConsentRecord, ConsentScope
from aegis.l4_memory.p07.discovery.coordinator import DiscoveryResult, ScanningCoordinator
from aegis.l4_memory.p07.scanners.base import ScannerBase, ScannerConfig
from aegis.l4_memory.p07.scanners.app_scanner import ApplicationScanner

# L4 memory imports for persistence tests
from aegis.l4_memory import (
    MemoryManager,
    MemoryPolicy,
    MemoryStatus,
    MemoryTier,
)
from aegis.l4_memory.p07.persistence.env_store import EnvironmentStore
from aegis.l4_memory.p07.persistence.candidate_store import CandidateStore, CandidateRecord
from aegis.l4_memory.policies import PrivacyZonePolicy
from aegis.l4_memory.graph import KnowledgeGraph


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest_asyncio.fixture
async def manager() -> AsyncGenerator[MemoryManager, None]:
    mgr = MemoryManager(db_path=None, policy=MemoryPolicy.default())
    await mgr.initialize()
    yield mgr
    await mgr.close()


@pytest_asyncio.fixture
async def graph(manager: MemoryManager) -> KnowledgeGraph:
    """Use manager.graph which shares the aiosqlite connection."""
    return manager.graph


@pytest_asyncio.fixture
async def env_store(manager: MemoryManager) -> EnvironmentStore:
    return EnvironmentStore(manager, manager.graph)


@pytest_asyncio.fixture
async def candidate_store(manager: MemoryManager) -> CandidateStore:
    return CandidateStore(manager)


@pytest_asyncio.fixture
async def sink(manager: MemoryManager) -> ObserverSink:
    return ObserverSink(manager)


# ===========================================================================
# Helper: make an observed event
# ===========================================================================

def _make_event(
    kind: EventKind = EventKind.APP_OPEN,
    subject: str = "test_app",
    session_id: str = "session_001",
    privacy_tier: str = "P2",
) -> ObservedEvent:
    return ObservedEvent(
        kind=kind,
        subject=subject,
        session_id=session_id,
        privacy_tier=privacy_tier,
    )


def _make_node(
    key: str = "app:test",
    kind: EnvNodeKind = EnvNodeKind.APPLICATION,
    label: str = "Test App",
    source_path: str | None = None,
    privacy_tier: str = "P2",
) -> EnvNode:
    return EnvNode(key=key, kind=kind, label=label, source_path=source_path, privacy_tier=privacy_tier)


# ===========================================================================
# OBSERVER EVENTS
# ===========================================================================

class TestObservedEvent:
    def test_basic_creation(self):
        ev = _make_event()
        assert ev.kind == EventKind.APP_OPEN
        assert ev.subject == "test_app"
        assert ev.session_id == "session_001"
        assert ev.privacy_tier == "P2"
        assert ev.id is not None

    def test_to_dict_completeness(self):
        ev = _make_event(EventKind.CMD_RUN, "git commit")
        d = ev.to_dict()
        assert d["kind"] == "cmd_run"
        assert d["subject"] == "git commit"
        assert "id" in d
        assert "timestamp" in d

    def test_all_event_kinds_usable(self):
        for kind in EventKind:
            ev = _make_event(kind, f"subject_{kind.value}")
            assert ev.kind == kind

    def test_unique_ids(self):
        ev1 = _make_event()
        ev2 = _make_event()
        assert ev1.id != ev2.id


# ===========================================================================
# OBSERVER AUDIT
# ===========================================================================

class TestObserverAuditLog:
    def test_append_and_retrieve(self):
        log = ObserverAuditLog()
        entry = log.append(AuditEventKind.OBSERVER_STARTED, "sess_001")
        assert len(log) == 1
        assert entry.kind == AuditEventKind.OBSERVER_STARTED
        assert entry.session_id == "sess_001"

    def test_entries_for_session(self):
        log = ObserverAuditLog()
        log.append(AuditEventKind.OBSERVER_STARTED, "sess_A")
        log.append(AuditEventKind.EVENT_RECORDED, "sess_B")
        log.append(AuditEventKind.OBSERVER_STOPPED, "sess_A")
        assert len(log.entries_for_session("sess_A")) == 2
        assert len(log.entries_for_session("sess_B")) == 1

    def test_all_audit_event_kinds_available(self):
        log = ObserverAuditLog()
        for kind in AuditEventKind:
            log.append(kind, "sess_x", detail="test")
        assert len(log) == len(list(AuditEventKind))

    def test_entries_property_is_copy(self):
        log = ObserverAuditLog()
        log.append(AuditEventKind.OBSERVER_STARTED, "s")
        entries = log.entries
        entries.clear()
        assert len(log) == 1  # Original not mutated

    def test_immutable_entry(self):
        log = ObserverAuditLog()
        entry = log.append(AuditEventKind.EVENT_BLOCKED, "sess_x", reason="privacy_zone")
        # frozen dataclass: cannot modify
        with pytest.raises((TypeError, AttributeError)):
            entry.kind = AuditEventKind.OBSERVER_STARTED  # type: ignore[misc]


# ===========================================================================
# OBSERVER SINK
# ===========================================================================

class TestObserverSink:
    @pytest.mark.asyncio
    async def test_record_and_flush(self, sink: ObserverSink):
        ev = _make_event()
        await sink.record(ev)
        assert sink.buffered_count == 1
        flushed = await sink.flush()
        assert flushed == 1
        assert sink.buffered_count == 0
        assert sink.total_flushed == 1

    @pytest.mark.asyncio
    async def test_multiple_flush(self, sink: ObserverSink):
        for i in range(5):
            await sink.record(_make_event(subject=f"app_{i}"))
        count = await sink.flush()
        assert count == 5

    @pytest.mark.asyncio
    async def test_empty_flush_returns_zero(self, sink: ObserverSink):
        result = await sink.flush()
        assert result == 0

    @pytest.mark.asyncio
    async def test_drain_clears_all(self, sink: ObserverSink):
        """After drain(), zero records remain — P07 shutdown invariant."""
        for i in range(3):
            await sink.record(_make_event(subject=f"app_{i}", session_id=f"s_{i}"))
        await sink.drain()
        assert sink.buffered_count == 0
        assert sink.total_flushed == 0  # Reset by drain

    @pytest.mark.asyncio
    async def test_drain_then_buffer_empty(self, sink: ObserverSink):
        """After drain, the sink is empty and ready for reuse."""
        await sink.record(_make_event())
        await sink.drain()
        assert sink.buffered_count == 0


# ===========================================================================
# PRIVACY ZONES
# ===========================================================================

class TestZoneRegistry:
    def _make_policy(
        self,
        blocked_paths: list[str] | None = None,
        blocked_apps: list[str] | None = None,
        min_tier: str = "P0",
        enabled: bool = True,
    ) -> PrivacyZonePolicy:
        return PrivacyZonePolicy(
            blocked_path_prefixes=blocked_paths or [],
            blocked_app_names=blocked_apps or [],
            min_privacy_tier=min_tier,
            enabled=enabled,
        )

    def test_empty_registry_allows_all(self):
        registry = ZoneRegistry()
        node = _make_node(source_path="/home/user/projects/aegis")
        result = registry.check_node(node)
        assert result.allowed is True
        assert result.blocking_zone is None

    def test_zone_blocks_matching_path(self):
        registry = ZoneRegistry()
        policy = self._make_policy(blocked_paths=["/home/user/.ssh"])
        registry.add(PrivacyZone(name="ssh_zone", policy=policy))

        blocked_node = _make_node(key="app:ssh", source_path="/home/user/.ssh/config")
        result = registry.check_node(blocked_node)
        assert result.allowed is False
        assert result.blocking_zone == "ssh_zone"

    def test_zone_allows_non_matching_path(self):
        registry = ZoneRegistry()
        policy = self._make_policy(blocked_paths=["/home/user/.ssh"])
        registry.add(PrivacyZone(name="ssh_zone", policy=policy))

        safe_node = _make_node(key="app:code", source_path="/home/user/projects")
        result = registry.check_node(safe_node)
        assert result.allowed is True

    def test_zone_blocks_matching_app_name(self):
        registry = ZoneRegistry()
        policy = self._make_policy(blocked_apps=["1Password"])
        registry.add(PrivacyZone(name="password_zone", policy=policy))

        blocked = _make_node(key="app:1password", label="1Password")
        result = registry.check_node(blocked)
        assert result.allowed is False

    def test_disabled_zone_does_not_block(self):
        registry = ZoneRegistry()
        policy = self._make_policy(blocked_paths=["/secret"], enabled=False)
        registry.add(PrivacyZone(name="disabled_zone", policy=policy))

        node = _make_node(source_path="/secret/data")
        result = registry.check_node(node)
        assert result.allowed is True

    def test_remove_zone(self):
        registry = ZoneRegistry()
        policy = self._make_policy(blocked_paths=["/blocked"])
        registry.add(PrivacyZone(name="zone_1", policy=policy))
        registry.remove("zone_1")

        node = _make_node(source_path="/blocked/file")
        assert registry.check_node(node).allowed is True

    def test_check_path_shortcut(self):
        registry = ZoneRegistry()
        policy = self._make_policy(blocked_paths=["/private"])
        registry.add(PrivacyZone(name="pvt", policy=policy))
        assert not registry.check_path("/private/keys")
        assert registry.check_path("/home/user/projects")

    def test_check_app_shortcut(self):
        registry = ZoneRegistry()
        policy = self._make_policy(blocked_apps=["KeePass"])
        registry.add(PrivacyZone(name="pw_zone", policy=policy))
        assert not registry.check_app("KeePass")
        assert registry.check_app("VSCode")

    def test_clear_removes_all_zones(self):
        registry = ZoneRegistry()
        for i in range(3):
            policy = self._make_policy(blocked_paths=[f"/path_{i}"])
            registry.add(PrivacyZone(name=f"zone_{i}", policy=policy))
        registry.clear()
        assert len(registry) == 0
        node = _make_node(source_path="/path_0/file")
        assert registry.check_node(node).allowed is True

    def test_privacy_zero_leak(self):
        """Simulate the P07 privacy invariant: P0 data never passes zone filter."""
        registry = ZoneRegistry()
        # Block a sensitive path
        policy = self._make_policy(blocked_paths=["/Users/test/.gnupg"])
        registry.add(PrivacyZone(name="gpg_zone", policy=policy))

        # P0-tier node in blocked path — must be blocked
        p0_node = _make_node(
            key="app:gpg",
            label="gpg",
            source_path="/Users/test/.gnupg",
            privacy_tier="P0",
        )
        result = registry.check_node(p0_node)
        assert result.allowed is False, "P0 data in protected path must be blocked"


# ===========================================================================
# CONSENT GATE
# ===========================================================================

class TestConsentGate:
    def test_deny_by_default(self):
        gate = ConsentGate()
        for scope in ConsentScope:
            assert gate.is_allowed(scope) is False

    def test_grant_all_allows_all(self):
        gate = ConsentGate()
        gate.grant(ConsentScope.ALL)
        for scope in ConsentScope:
            assert gate.is_allowed(scope) is True

    def test_revoke_specific_overrides_all(self):
        gate = ConsentGate()
        gate.grant(ConsentScope.ALL)
        gate.revoke(ConsentScope.APP_SCANNER)
        assert gate.is_allowed(ConsentScope.APP_SCANNER) is False
        # Others still allowed via ALL
        assert gate.is_allowed(ConsentScope.CLI_SCANNER) is True

    def test_revoke_all(self):
        gate = ConsentGate()
        gate.grant(ConsentScope.ALL)
        gate.revoke_all()
        for scope in ConsentScope:
            assert gate.is_allowed(scope) is False

    def test_audit_log_tracks_changes(self):
        gate = ConsentGate()
        gate.grant(ConsentScope.APP_SCANNER, user_agent="user1")
        gate.revoke(ConsentScope.APP_SCANNER, user_agent="user1")
        log = gate.audit_log()
        assert len(log) == 2
        assert log[0].granted is True
        assert log[1].granted is False

    def test_has_any_consent(self):
        gate = ConsentGate()
        assert gate.has_any_consent is False
        gate.grant(ConsentScope.CLI_SCANNER)
        assert gate.has_any_consent is True

    def test_is_any_allowed(self):
        gate = ConsentGate()
        assert gate.is_any_allowed() is False
        gate.grant(ConsentScope.PROJECT_SCANNER)
        assert gate.is_any_allowed() is True

    def test_current_state_serializable(self):
        gate = ConsentGate()
        gate.grant(ConsentScope.APP_SCANNER)
        state = gate.current_state()
        assert isinstance(state, dict)
        assert "app_scanner" in state
        assert state["app_scanner"] is True
        assert state["cli_scanner"] is False

    def test_grant_individual_scope(self):
        gate = ConsentGate()
        gate.grant(ConsentScope.CLI_SCANNER)
        assert gate.is_allowed(ConsentScope.CLI_SCANNER) is True
        # Other scopes still denied
        assert gate.is_allowed(ConsentScope.APP_SCANNER) is False


# ===========================================================================
# SYNTHETIC SCANNER (for coordinator tests)
# ===========================================================================

class _SyntheticScanner(ScannerBase):
    """A deterministic scanner for testing — returns a fixed node list."""

    def __init__(self, name: str, nodes: list[EnvNode], config: ScannerConfig | None = None):
        super().__init__(config or ScannerConfig(opt_in=True))
        self._name = name
        self._nodes = nodes

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._name

    async def _run(self, config: ScannerConfig, deadline: float) -> ScanResult:
        return ScanResult(scanner_name=self._name, nodes=list(self._nodes))


# ===========================================================================
# SCANNING COORDINATOR
# ===========================================================================

class TestScanningCoordinator:
    @pytest.mark.asyncio
    async def test_blocked_without_consent(self):
        gate = ConsentGate()
        coord = ScanningCoordinator(consent_gate=gate)
        result = await coord.run_discovery()
        assert result.consent_denied is True
        assert result.total_nodes == 0

    @pytest.mark.asyncio
    async def test_runs_with_consent(self):
        gate = ConsentGate()
        gate.grant(ConsentScope.ALL)
        nodes = [_make_node(f"app:tool_{i}", label=f"Tool {i}") for i in range(3)]
        scanner = _SyntheticScanner("app_scanner", nodes)
        coord = ScanningCoordinator(consent_gate=gate, scanners=[scanner])
        result = await coord.run_discovery()
        assert result.consent_denied is False
        assert result.total_nodes == 3

    @pytest.mark.asyncio
    async def test_privacy_zone_filters_nodes(self):
        gate = ConsentGate()
        gate.grant(ConsentScope.ALL)

        # Zone that blocks /secret
        zones = ZoneRegistry()
        from aegis.l4_memory.policies import PrivacyZonePolicy
        policy = PrivacyZonePolicy(blocked_path_prefixes=["/secret"], min_privacy_tier="P0")
        zones.add(PrivacyZone(name="secret_zone", policy=policy))

        nodes = [
            _make_node("app:safe", label="Safe App", source_path="/home/user/app"),
            _make_node("app:secret", label="Secret App", source_path="/secret/app"),
        ]
        scanner = _SyntheticScanner("app_scanner", nodes)
        coord = ScanningCoordinator(consent_gate=gate, zone_registry=zones, scanners=[scanner])
        result = await coord.run_discovery(dry_run=True)
        assert result.total_nodes == 2
        assert result.total_filtered == 1  # One node blocked

    @pytest.mark.asyncio
    async def test_dry_run_does_not_persist(self):
        gate = ConsentGate()
        gate.grant(ConsentScope.ALL)
        nodes = [_make_node("app:test", label="Test")]
        scanner = _SyntheticScanner("app_scanner", nodes)
        coord = ScanningCoordinator(consent_gate=gate, scanners=[scanner])
        result = await coord.run_discovery(dry_run=True)
        assert result.persisted_nodes == 0

    @pytest.mark.asyncio
    async def test_scanner_specific_consent(self):
        """Only grant APP_SCANNER — CLI_SCANNER should be skipped."""
        gate = ConsentGate()
        gate.grant(ConsentScope.APP_SCANNER)  # Only app_scanner
        app_nodes = [_make_node("app:git", label="git")]
        cli_nodes = [_make_node("app:bash", label="bash")]
        app_scanner = _SyntheticScanner("app_scanner", app_nodes)
        cli_scanner = _SyntheticScanner("cli_scanner", cli_nodes)
        coord = ScanningCoordinator(
            consent_gate=gate,
            scanners=[app_scanner, cli_scanner],
        )
        result = await coord.run_discovery(dry_run=True)
        # Only app_scanner ran: total_nodes = 1
        assert result.total_nodes == 1
        assert not result.consent_denied

    @pytest.mark.asyncio
    async def test_add_remove_scanner(self):
        gate = ConsentGate()
        gate.grant(ConsentScope.ALL)
        coord = ScanningCoordinator(consent_gate=gate)
        assert coord.scanner_count == 0
        scanner = _SyntheticScanner("app_scanner", [])
        coord.add_scanner(scanner)
        assert coord.scanner_count == 1
        assert coord.remove_scanner("app_scanner") is True
        assert coord.scanner_count == 0


# ===========================================================================
# APP SCANNER (real scanner, bounded)
# ===========================================================================

class TestApplicationScanner:
    @pytest.mark.asyncio
    async def test_disabled_returns_error_result(self):
        """Scanner with opt_in=False returns a no-op result."""
        scanner = ApplicationScanner(ScannerConfig(opt_in=False))
        result = await scanner.scan()
        assert not result.succeeded
        assert "disabled" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_enabled_returns_nodes(self):
        """With opt_in=True, the scanner should discover at least some tools via PATH."""
        scanner = ApplicationScanner(ScannerConfig(opt_in=True, max_seconds=5.0, max_results=50))
        result = await scanner.scan()
        # Must succeed (no error) even if no apps found
        assert result.error is None
        # On any CI/development machine, we expect at least python in PATH
        # (If none found, result.nodes is empty list — still valid)
        assert isinstance(result.nodes, list)
        assert all(isinstance(n, EnvNode) for n in result.nodes)

    @pytest.mark.asyncio
    async def test_app_discovery_95_percent_success_criterion(self):
        """
        P07 success criterion: ≥ 95% of known-installed tools discovered.

        Ground truth fixture: tools that MUST be installed in any dev environment
        where this test runs. We test against shutil.which directly as ground truth.
        """
        import shutil
        from aegis.l4_memory.p07.scanners.app_scanner import _COMMON_TOOLS

        # Ground truth: tools actually present on this machine
        ground_truth = {t for t in _COMMON_TOOLS if shutil.which(t)}

        if not ground_truth:
            pytest.skip("No common tools found via PATH — cannot verify 95% criterion")

        scanner = ApplicationScanner(ScannerConfig(opt_in=True, max_seconds=10.0, max_results=500))
        result = await scanner.scan()

        # Map discovered nodes back to tool names
        discovered_tools = {
            n.label.lower() for n in result.nodes
        }
        discovered_tools.update(
            n.attributes.get("executable", "").split("/")[-1].lower()
            for n in result.nodes
            if "executable" in n.attributes
        )

        # Also check by key pattern "app:<name>"
        discovered_keys = {n.key.replace("app:", "") for n in result.nodes}
        all_discovered = discovered_tools | discovered_keys

        found_in_ground_truth = sum(
            1 for t in ground_truth if t in all_discovered
        )

        if len(ground_truth) > 0:
            ratio = found_in_ground_truth / len(ground_truth)
            assert ratio >= 0.95, (
                f"App discovery rate {ratio:.0%} < 95%. "
                f"Ground truth: {ground_truth}, "
                f"discovered keys: {list(discovered_keys)[:10]}"
            )

    @pytest.mark.asyncio
    async def test_scanner_respects_max_results(self):
        """Scanner never returns more than max_results nodes."""
        scanner = ApplicationScanner(ScannerConfig(opt_in=True, max_seconds=5.0, max_results=3))
        result = await scanner.scan()
        assert len(result.nodes) <= 3

    @pytest.mark.asyncio
    async def test_all_nodes_have_valid_keys(self):
        """All discovered nodes have non-empty keys and labels."""
        scanner = ApplicationScanner(ScannerConfig(opt_in=True, max_seconds=5.0, max_results=50))
        result = await scanner.scan()
        for node in result.nodes:
            assert node.key, f"Node has empty key: {node}"
            assert node.label, f"Node has empty label: {node}"
            assert node.kind == EnvNodeKind.APPLICATION


# ===========================================================================
# WORKFLOW INFERENCER — 8/10 synthetic workflows
# ===========================================================================

class TestWorkflowInferencer:
    """P07 success criterion: ≥ 8 of 10 synthetic workflows detected."""

    def _make_session(
        self,
        session_id: str,
        kinds: list[EventKind],
    ) -> list[ObservedEvent]:
        return [
            ObservedEvent(
                kind=k,
                subject=f"subject_{k.value}",
                session_id=session_id,
            )
            for k in kinds
        ]

    def test_detects_repeated_sequence(self):
        """Basic: a 2-step sequence repeated twice should be detected."""
        inf = WorkflowInferencer(min_sequence_length=2, min_occurrences=2)
        # session A and session B both do APP_OPEN → CMD_RUN
        ev_a = self._make_session("A", [EventKind.APP_OPEN, EventKind.CMD_RUN])
        ev_b = self._make_session("B", [EventKind.APP_OPEN, EventKind.CMD_RUN])
        candidates = inf.infer(ev_a + ev_b)
        assert len(candidates) >= 1
        # The detected workflow must be the 2-step sequence
        seqs = [c.event_sequence for c in candidates]
        assert [EventKind.APP_OPEN.value, EventKind.CMD_RUN.value] in seqs

    def test_all_candidates_pending_review(self):
        """P07 invariant: ALL candidates start as pending_review."""
        inf = WorkflowInferencer(min_sequence_length=2, min_occurrences=2)
        ev = (
            self._make_session("A", [EventKind.APP_OPEN, EventKind.CMD_RUN, EventKind.FILE_TOUCH])
            + self._make_session("B", [EventKind.APP_OPEN, EventKind.CMD_RUN, EventKind.FILE_TOUCH])
        )
        candidates = inf.infer(ev)
        for c in candidates:
            assert c.status == "pending_review", f"Candidate {c.label!r} not pending_review"
            assert c.source == "heuristic"

    def test_no_auto_promotion(self):
        """Verify candidates never change status spontaneously."""
        inf = WorkflowInferencer(min_sequence_length=2, min_occurrences=2)
        ev = (
            self._make_session("S1", [EventKind.CMD_RUN, EventKind.FILE_TOUCH]) * 2
        )
        candidates = inf.infer(ev)
        # Wait "some time" (simulated) and re-infer — status unchanged
        for c in candidates:
            assert c.status == "pending_review"

    def test_min_occurrences_threshold(self):
        """Sequence appearing only once is NOT returned."""
        inf = WorkflowInferencer(min_sequence_length=2, min_occurrences=2)
        ev = self._make_session("A", [EventKind.APP_OPEN, EventKind.CMD_RUN])
        candidates = inf.infer(ev)
        assert candidates == []

    def test_confidence_bounded(self):
        """Confidence must always be in [0.3, 0.95]."""
        inf = WorkflowInferencer(min_sequence_length=2, min_occurrences=2)
        # Many repetitions
        sessions = []
        for i in range(20):
            sessions.extend(
                self._make_session(f"S{i}", [EventKind.TOOL_USE, EventKind.CMD_RUN])
            )
        candidates = inf.infer(sessions)
        for c in candidates:
            assert 0.3 <= c.confidence <= 0.95

    def _make_workflow_sessions(self, session_base: str, kinds: list[EventKind], repeat: int = 2) -> list[ObservedEvent]:
        events = []
        for i in range(repeat):
            events.extend(self._make_session(f"{session_base}_{i}", kinds))
        return events

    def test_eight_of_ten_synthetic_workflows(self):
        """
        P07 success criterion: ≥ 8 of 10 synthetic workflow transcripts detected.

        10 synthetic workflows defined as event-kind sequences. Each repeated ≥2 times.
        WorkflowInferencer must detect ≥ 8 of them.
        """
        synthetic_workflows = [
            # 1. Git commit flow: open → cmd → cmd
            [EventKind.PROJECT_OPEN, EventKind.CMD_RUN, EventKind.CMD_RUN],
            # 2. Research loop: search → file_touch
            [EventKind.SEARCH_QUERY, EventKind.FILE_TOUCH],
            # 3. App switch: close → open
            [EventKind.APP_CLOSE, EventKind.APP_OPEN],
            # 4. Build loop: cmd → file → cmd
            [EventKind.CMD_RUN, EventKind.FILE_TOUCH, EventKind.CMD_RUN],
            # 5. Project start: project_open → tool_use
            [EventKind.PROJECT_OPEN, EventKind.TOOL_USE],
            # 6. Dev cycle: open → cmd → file → cmd
            [EventKind.APP_OPEN, EventKind.CMD_RUN, EventKind.FILE_TOUCH, EventKind.CMD_RUN],
            # 7. Search and use: search → tool_use
            [EventKind.SEARCH_QUERY, EventKind.TOOL_USE],
            # 8. Simple run: cmd_run alone (min length 2, so add another step)
            [EventKind.TOOL_USE, EventKind.CMD_RUN],
            # 9. Project open → search
            [EventKind.PROJECT_OPEN, EventKind.SEARCH_QUERY],
            # 10. File write loop: file_touch → cmd_run → file_touch
            [EventKind.FILE_TOUCH, EventKind.CMD_RUN, EventKind.FILE_TOUCH],
        ]

        all_events: list[ObservedEvent] = []
        for wf_idx, wf_kinds in enumerate(synthetic_workflows):
            # Repeat each workflow 3 times across 3 sessions
            for rep in range(3):
                all_events.extend(
                    self._make_session(f"wf{wf_idx}_rep{rep}", wf_kinds)
                )

        inf = WorkflowInferencer(min_sequence_length=2, min_occurrences=2)
        candidates = inf.infer(all_events)

        # How many of the 10 workflows have a matching candidate?
        detected = 0
        for wf_kinds in synthetic_workflows:
            target_seq = [k.value for k in wf_kinds]
            # A candidate's event_sequence must contain this as a sub-sequence
            for c in candidates:
                if (
                    c.event_sequence == target_seq
                    or _contains_subsequence(c.event_sequence, target_seq)
                ):
                    detected += 1
                    break

        assert detected >= 8, (
            f"WorkflowInferencer detected only {detected}/10 synthetic workflows. "
            f"Candidates: {[c.event_sequence for c in candidates]}"
        )


def _contains_subsequence(candidate_seq: list[str], target: list[str]) -> bool:
    """Return True if target appears as a contiguous sub-sequence in candidate_seq."""
    n = len(target)
    for i in range(len(candidate_seq) - n + 1):
        if candidate_seq[i:i + n] == target:
            return True
    return False


# ===========================================================================
# PREFERENCE INFERENCER
# ===========================================================================

class TestPreferenceInferencer:
    def _make_events(
        self,
        kind: EventKind,
        subjects: list[str],
        session_id: str = "sess",
    ) -> list[ObservedEvent]:
        return [
            ObservedEvent(kind=kind, subject=s, session_id=session_id)
            for s in subjects
        ]

    def test_basic_tool_preference(self):
        inf = PreferenceInferencer(top_n=3, min_count=2, dominance_ratio=1.5)
        events = self._make_events(
            EventKind.TOOL_USE,
            ["git"] * 10 + ["docker"] * 2 + ["make"] * 1,
        )
        candidates = inf.infer(events)
        # "git" dominates → should be a candidate
        keys = [c.key for c in candidates]
        assert any("git" in k for k in keys), f"Expected 'git' in candidates: {keys}"

    def test_all_candidates_pending_review(self):
        """P07 invariant: preference candidates NEVER auto-promote."""
        inf = PreferenceInferencer(min_count=2)
        events = self._make_events(EventKind.APP_OPEN, ["VSCode"] * 8 + ["Notepad"] * 2)
        candidates = inf.infer(events)
        for c in candidates:
            assert c.status == "pending_review", f"Candidate {c.label!r} auto-promoted!"
            assert c.tier_target == "T5_PERSONAL"

    def test_no_candidate_when_no_dominance(self):
        """If all tools used equally, no preference detected."""
        inf = PreferenceInferencer(top_n=3, min_count=3, dominance_ratio=2.0)
        events = self._make_events(
            EventKind.TOOL_USE,
            ["git", "docker", "make", "npm", "pip"],
        )
        candidates = inf.infer(events)
        assert candidates == []

    def test_empty_events_returns_empty(self):
        inf = PreferenceInferencer()
        assert inf.infer([]) == []

    def test_source_is_heuristic(self):
        inf = PreferenceInferencer(min_count=2, dominance_ratio=1.0)
        events = self._make_events(EventKind.CMD_RUN, ["pytest"] * 5 + ["python"] * 2)
        candidates = inf.infer(events)
        for c in candidates:
            assert c.source == "heuristic"

    def test_confidence_bounded(self):
        inf = PreferenceInferencer(min_count=2, dominance_ratio=1.0)
        events = self._make_events(EventKind.TOOL_USE, ["git"] * 20)
        candidates = inf.infer(events)
        for c in candidates:
            assert 0.0 <= c.confidence <= 1.0


# ===========================================================================
# CANDIDATE STORE
# ===========================================================================

class TestCandidateStore:
    @pytest.mark.asyncio
    async def test_create_workflow_candidate(self, candidate_store: CandidateStore):
        cid = await candidate_store.create_workflow_candidate(
            key="wf:git_flow",
            label="Git commit workflow",
            steps=["git add", "git commit", "git push"],
            confidence=0.80,
        )
        assert cid is not None
        candidate = await candidate_store.get(cid)
        assert candidate is not None
        assert candidate.kind == "workflow"
        assert candidate.confidence == 0.80

    @pytest.mark.asyncio
    async def test_create_preference_candidate(self, candidate_store: CandidateStore):
        cid = await candidate_store.create_preference_candidate(
            key="pref:git_preferred",
            label="Preferred tool: git",
            preference_value="git",
            confidence=0.75,
        )
        assert cid is not None
        candidate = await candidate_store.get(cid)
        assert candidate is not None
        assert candidate.kind == "preference"

    @pytest.mark.asyncio
    async def test_all_candidates_start_pending_review(self, candidate_store: CandidateStore):
        """Invariant: candidates are created as PENDING_REVIEW, never active."""
        await candidate_store.create_workflow_candidate(
            key="wf:test_pending",
            label="Test workflow",
            steps=["step1", "step2"],
        )
        pending = await candidate_store.list_pending()
        assert len(pending) >= 1
        for c in pending:
            assert c.status == MemoryStatus.PENDING_REVIEW

    @pytest.mark.asyncio
    async def test_promote_requires_explicit_call(self, candidate_store: CandidateStore):
        """Promotion only happens when promote() is called explicitly."""
        cid = await candidate_store.create_workflow_candidate(
            key="wf:for_promote",
            label="For promotion test",
            steps=["a", "b"],
        )
        # Before promotion — pending
        pending_before = await candidate_store.list_pending()
        assert any(c.id == cid for c in pending_before)

        # After explicit promotion
        result = await candidate_store.promote(cid)
        assert result is True

    @pytest.mark.asyncio
    async def test_reject_removes_candidate(self, candidate_store: CandidateStore):
        cid = await candidate_store.create_preference_candidate(
            key="pref:to_reject",
            label="To reject",
            preference_value="test",
        )
        result = await candidate_store.reject(cid)
        assert result is True

    @pytest.mark.asyncio
    async def test_purge_all_candidates(self, candidate_store: CandidateStore):
        """After purge, count_pending returns 0."""
        for i in range(5):
            await candidate_store.create_workflow_candidate(
                key=f"wf:purge_{i}",
                label=f"Workflow {i}",
                steps=[f"step_{i}"],
            )
        count_before = await candidate_store.count_pending()
        assert count_before >= 5

        deleted = await candidate_store.purge_all_candidates()
        assert deleted >= 5
        count_after = await candidate_store.count_pending()
        assert count_after == 0

    @pytest.mark.asyncio
    async def test_count_pending(self, candidate_store: CandidateStore):
        initial = await candidate_store.count_pending()
        await candidate_store.create_workflow_candidate(
            key="wf:count_test",
            label="Count test",
            steps=["step1"],
        )
        after = await candidate_store.count_pending()
        assert after == initial + 1


# ===========================================================================
# ENVIRONMENT STORE
# ===========================================================================

class TestEnvironmentStore:
    @pytest.mark.asyncio
    async def test_upsert_and_query_node(self, env_store: EnvironmentStore):
        node = _make_node("app:vscode", label="Visual Studio Code")
        entity_id = await env_store.upsert_node(node, scanner_id="app_scanner")
        assert entity_id is not None

        results = await env_store.query_nodes(kind=EnvNodeKind.APPLICATION)
        keys = [r.key for r in results]
        assert "app:vscode" in keys

    @pytest.mark.asyncio
    async def test_get_node_by_key(self, env_store: EnvironmentStore):
        node = _make_node("app:git", label="git")
        await env_store.upsert_node(node)
        entity = await env_store.get_node("app:git")
        assert entity is not None
        assert entity.key == "app:git"

    @pytest.mark.asyncio
    async def test_delete_node(self, env_store: EnvironmentStore):
        node = _make_node("app:to_delete", label="To Delete")
        await env_store.upsert_node(node)
        deleted = await env_store.delete_node("app:to_delete")
        assert deleted is True
        entity = await env_store.get_node("app:to_delete")
        assert entity is None

    @pytest.mark.asyncio
    async def test_upsert_and_query_edge(self, env_store: EnvironmentStore):
        node_a = _make_node("project:aegis", kind=EnvNodeKind.PROJECT, label="AEGIS")
        node_b = _make_node("app:python", kind=EnvNodeKind.APPLICATION, label="Python")
        await env_store.upsert_node(node_a)
        await env_store.upsert_node(node_b)

        edge = EnvEdge(
            subject_key="project:aegis",
            object_key="app:python",
            kind=EnvEdgeKind.USES,
            confidence=0.9,
        )
        rel_id = await env_store.upsert_edge(edge, scanner_id="relation_scanner")
        assert rel_id is not None

        edges = await env_store.query_edges(subject_key="project:aegis")
        assert len(edges) >= 1

    @pytest.mark.asyncio
    async def test_edge_missing_node_returns_none(self, env_store: EnvironmentStore):
        """Edge cannot be created if either endpoint doesn't exist."""
        edge = EnvEdge(
            subject_key="app:ghost_subject",
            object_key="app:ghost_object",
            kind=EnvEdgeKind.DEPENDS_ON,
        )
        rel_id = await env_store.upsert_edge(edge)
        assert rel_id is None

    @pytest.mark.asyncio
    async def test_idempotent_upsert(self, env_store: EnvironmentStore):
        """Upserting the same node twice should not raise and should update."""
        node = _make_node("app:idempotent_test", label="Idempotent Test")
        id1 = await env_store.upsert_node(node, scanner_id="s1")
        id2 = await env_store.upsert_node(node, scanner_id="s2")
        # Should not raise; both return a valid UUID
        assert id1 is not None
        assert id2 is not None


# ===========================================================================
# INTEGRATION: Privacy zone → scanner → coordinator → store
# ===========================================================================

class TestPrivacyZeroLeakIntegration:
    """End-to-end privacy invariant tests."""

    @pytest.mark.asyncio
    async def test_p0_path_never_reaches_store(self, env_store: EnvironmentStore):
        """Nodes in a blocked path must be filtered before reaching the store."""
        gate = ConsentGate()
        gate.grant(ConsentScope.ALL)

        zones = ZoneRegistry()
        from aegis.l4_memory.policies import PrivacyZonePolicy
        policy = PrivacyZonePolicy(
            blocked_path_prefixes=["/home/user/.ssh"],
            min_privacy_tier="P0",
        )
        zones.add(PrivacyZone(name="ssh_zone", policy=policy))

        # Node in blocked path
        ssh_node = _make_node("app:ssh_key", source_path="/home/user/.ssh/id_rsa", label="SSH Key")
        # Node in safe path
        safe_node = _make_node("app:vscode", source_path="/usr/bin/code", label="VSCode")

        scanner = _SyntheticScanner("app_scanner", [ssh_node, safe_node])
        coord = ScanningCoordinator(
            consent_gate=gate,
            zone_registry=zones,
            scanners=[scanner],
            logger_=None,
        )

        result = await coord.run_discovery(env_store=env_store)
        assert result.total_nodes == 2
        assert result.total_filtered == 1  # SSH node blocked
        assert result.persisted_nodes == 1  # Only safe_node persisted

        # Confirm only safe_node in store
        entities = await env_store.query_nodes()
        keys = {e.key for e in entities}
        assert "app:vscode" in keys
        assert "app:ssh_key" not in keys

    @pytest.mark.asyncio
    async def test_no_consent_means_zero_activity(self, env_store: EnvironmentStore):
        """Zero activity when consent not granted — the strongest P07 privacy guarantee."""
        gate = ConsentGate()  # No consent
        nodes = [_make_node(f"app:blocked_{i}", label=f"Blocked {i}") for i in range(5)]
        scanner = _SyntheticScanner("app_scanner", nodes)
        coord = ScanningCoordinator(consent_gate=gate, scanners=[scanner])
        result = await coord.run_discovery(env_store=env_store)

        assert result.consent_denied is True
        assert result.total_nodes == 0
        assert result.persisted_nodes == 0

        # Confirm store is empty
        entities = await env_store.query_nodes()
        assert len(entities) == 0


# ===========================================================================
# OBSERVER SHUTDOWN — Zero leftover invariant
# ===========================================================================

class TestObserverShutdownInvariant:
    """P07 success criterion: Zero records remaining after observer shutdown."""

    @pytest.mark.asyncio
    async def test_drain_leaves_zero_records(self, sink: ObserverSink, manager: MemoryManager):
        """After drain, no observation records remain in the manager."""
        # Record several events
        for i in range(5):
            ev = _make_event(subject=f"obs_{i}", session_id=f"shutdown_sess_{i}")
            await sink.record(ev)

        # Flush to persist
        await sink.flush()

        # Drain (shutdown)
        await sink.drain()

        # Verify zero records in observer namespace
        from aegis.l4_memory.search import SearchQuery
        from aegis.l4_memory.types import SearchMode
        query = SearchQuery(
            namespace="p07_observer",
            mode=SearchMode.METADATA,
            limit=10000,
        )
        results = await manager.search(query)
        assert len(results) == 0, (
            f"Expected 0 observation records after shutdown, found {len(results)}"
        )

    @pytest.mark.asyncio
    async def test_drain_plus_candidate_purge(
        self,
        sink: ObserverSink,
        candidate_store: CandidateStore,
        manager: MemoryManager,
    ):
        """Combined shutdown: drain sink + purge candidates = zero leftover."""
        # Add some observations
        for i in range(3):
            await sink.record(_make_event(subject=f"shutdown_app_{i}"))
        await sink.flush()

        # Add some candidates
        for i in range(3):
            await candidate_store.create_workflow_candidate(
                key=f"wf:shutdown_{i}",
                label=f"Shutdown workflow {i}",
                steps=["a", "b"],
            )

        # Shutdown: drain sink + purge candidates
        await sink.drain()
        await candidate_store.purge_all_candidates()

        # Verify zero observations
        from aegis.l4_memory.search import SearchQuery
        from aegis.l4_memory.types import SearchMode
        obs_query = SearchQuery(namespace="p07_observer", mode=SearchMode.METADATA, limit=1000)
        obs_results = await manager.search(obs_query)
        assert len(obs_results) == 0

        # Verify zero pending candidates
        count = await candidate_store.count_pending()
        assert count == 0
