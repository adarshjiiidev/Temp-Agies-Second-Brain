"""P08 Tests — Capability Model Layer.

Tests for CapabilityRecord, CapabilityHealth, CapabilityMetrics,
ImplementationRef, CapabilityComposition, and all enums.
"""

from __future__ import annotations

import time

import pytest

from aegis.capabilities.model.capability import (
    CapabilityCategory,
    CapabilityRecord,
    ProvenanceSource,
    TrustState,
)
from aegis.capabilities.model.composition import (
    BuiltinRef,
    CapabilityComposition,
    CompositeRef,
    ExternalAgentRef,
    ImplementationType,
    MCPToolRef,
)
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus
from aegis.capabilities.model.metrics import CapabilityMetrics


# ---------------------------------------------------------------------------
# CapabilityHealth
# ---------------------------------------------------------------------------

class TestCapabilityHealth:
    def test_default_is_unknown(self):
        h = CapabilityHealth()
        assert h.status == HealthStatus.UNKNOWN
        assert not h.is_usable
        assert not h.is_available

    def test_available_is_usable(self):
        h = CapabilityHealth(status=HealthStatus.AVAILABLE)
        assert h.is_usable
        assert h.is_available

    def test_degraded_is_usable_not_available(self):
        h = CapabilityHealth(status=HealthStatus.DEGRADED)
        assert h.is_usable
        assert not h.is_available

    def test_unavailable_not_usable(self):
        h = CapabilityHealth(status=HealthStatus.UNAVAILABLE)
        assert not h.is_usable

    def test_disabled_not_usable(self):
        h = CapabilityHealth(status=HealthStatus.DISABLED)
        assert not h.is_usable

    def test_record_success_updates_status(self):
        h = CapabilityHealth(status=HealthStatus.UNKNOWN)
        h2 = h.record_success(latency_ms=42.0)
        assert h2.status == HealthStatus.AVAILABLE
        assert h2.latency_ms_p50 == 42.0
        assert h2.last_error is None
        # original unchanged (frozen model)
        assert h.status == HealthStatus.UNKNOWN

    def test_record_failure_increments_count(self):
        h = CapabilityHealth(status=HealthStatus.AVAILABLE)
        h2 = h.record_failure("timeout")
        assert h2.failure_count == 1
        assert h2.last_error == "timeout"
        assert h2.status == HealthStatus.DEGRADED

    def test_record_three_failures_marks_unavailable(self):
        h = CapabilityHealth(status=HealthStatus.AVAILABLE)
        for _ in range(3):
            h = h.record_failure("connection refused")
        assert h.status == HealthStatus.UNAVAILABLE
        assert h.failure_count == 3


# ---------------------------------------------------------------------------
# CapabilityMetrics
# ---------------------------------------------------------------------------

class TestCapabilityMetrics:
    def test_initial_success_rate_neutral(self):
        m = CapabilityMetrics()
        assert m.success_rate == 0.5
        assert m.average_latency_ms is None

    def test_success_rate_after_invocations(self):
        m = CapabilityMetrics()
        m = m.record_invocation(success=True, latency_ms=10.0)
        m = m.record_invocation(success=True, latency_ms=20.0)
        m = m.record_invocation(success=False)
        assert m.invocation_count == 3
        assert m.success_count == 2
        assert m.failure_count == 1
        assert abs(m.success_rate - 2 / 3) < 0.001
        assert abs(m.average_latency_ms - 15.0) < 0.001

    def test_user_approval_rate_defaults_to_1(self):
        m = CapabilityMetrics()
        assert m.user_approval_rate == 1.0

    def test_user_feedback(self):
        m = CapabilityMetrics()
        m = m.record_user_feedback(approved=True)
        m = m.record_user_feedback(approved=False)
        assert m.user_approval_count == 1
        assert m.user_rejection_count == 1
        assert m.user_approval_rate == 0.5

    def test_last_used_timestamp_updated(self):
        m = CapabilityMetrics()
        before = time.time()
        m = m.record_invocation(success=True)
        assert m.last_used_at is not None
        assert m.last_used_at >= before


# ---------------------------------------------------------------------------
# ImplementationRef / CapabilityComposition
# ---------------------------------------------------------------------------

class TestImplementationRef:
    def test_builtin_ref_type(self):
        ref = BuiltinRef(executor_name="fs_executor", action_kind="fs.read")
        assert ref.type == ImplementationType.BUILTIN
        assert ref.executor_name == "fs_executor"

    def test_mcp_tool_ref_type(self):
        ref = MCPToolRef(server_id="my-server", tool_name="search", tool_id="my-server:search")
        assert ref.type == ImplementationType.MCP_TOOL
        assert ref.tool_id == "my-server:search"

    def test_composite_ref_type(self):
        ref = CompositeRef(step_capability_ids=["a", "b", "c"])
        assert ref.type == ImplementationType.COMPOSITE
        assert len(ref.step_capability_ids) == 3

    def test_external_agent_ref_type(self):
        ref = ExternalAgentRef(agent_id="agent-1", agent_type="browser")
        assert ref.type == ImplementationType.EXTERNAL_AGENT
        assert ref.agent_type == "browser"

    def test_composition_defaults_empty(self):
        comp = CapabilityComposition()
        assert comp.depends_on == []
        assert comp.composes_with == []


# ---------------------------------------------------------------------------
# CapabilityRecord
# ---------------------------------------------------------------------------

class TestCapabilityRecord:
    def _make_record(self, **kwargs) -> CapabilityRecord:
        defaults = dict(
            capability_id="test:fs.read",
            name="Filesystem Read",
            description="Read files",
            category=CapabilityCategory.FILESYSTEM,
            implementation=BuiltinRef(executor_name="fs", action_kind="fs.read"),
            trust_state=TrustState.TRUSTED,
            health=CapabilityHealth(status=HealthStatus.AVAILABLE),
            enabled=True,
        )
        defaults.update(kwargs)
        return CapabilityRecord(**defaults)

    def test_is_usable_requires_enabled_trusted_available(self):
        record = self._make_record()
        assert record.is_usable

    def test_unverified_not_usable(self):
        record = self._make_record(trust_state=TrustState.UNVERIFIED)
        assert not record.is_usable

    def test_disabled_not_usable(self):
        record = self._make_record(enabled=False)
        assert not record.is_usable

    def test_is_builtin(self):
        record = self._make_record()
        assert record.is_builtin
        assert not record.is_mcp

    def test_is_mcp(self):
        record = self._make_record(
            implementation=MCPToolRef(server_id="s", tool_name="t", tool_id="s:t")
        )
        assert record.is_mcp
        assert not record.is_builtin

    def test_ranking_score_trusted_available_builtin_high(self):
        record = self._make_record()
        score = record.ranking_score()
        assert score > 0.8   # trusted + available + builtin = high

    def test_ranking_score_unverified_zero(self):
        record = self._make_record(trust_state=TrustState.UNVERIFIED)
        score = record.ranking_score()
        assert score < 0.5

    def test_ranking_score_mcp_lower_than_builtin(self):
        builtin = self._make_record()
        mcp = self._make_record(
            implementation=MCPToolRef(server_id="s", tool_name="t", tool_id="s:t"),
            trust_state=TrustState.TRUSTED,
        )
        assert builtin.ranking_score() > mcp.ranking_score()

    def test_id_auto_generated(self):
        r1 = CapabilityRecord(
            name="Test",
            category=CapabilityCategory.CUSTOM,
            implementation=BuiltinRef(executor_name="x", action_kind="y"),
        )
        r2 = CapabilityRecord(
            name="Test",
            category=CapabilityCategory.CUSTOM,
            implementation=BuiltinRef(executor_name="x", action_kind="y"),
        )
        assert r1.capability_id != r2.capability_id

    def test_record_provenance_and_trust_enums(self):
        for ts in TrustState:
            record = self._make_record(trust_state=ts)
            assert record.trust_state == ts
        for ps in ProvenanceSource:
            record = self._make_record(provenance=ps)
            assert record.provenance == ps
