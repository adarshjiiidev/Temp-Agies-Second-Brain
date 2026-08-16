"""P08 Tests — Capability Store and Semantic Registry."""

from __future__ import annotations

import asyncio
import time

import pytest

from aegis.capabilities.discovery_providers.static_provider import StaticRegistryProvider
from aegis.capabilities.model.capability import (
    CapabilityCategory,
    CapabilityRecord,
    ProvenanceSource,
    TrustState,
)
from aegis.capabilities.model.composition import BuiltinRef, MCPToolRef
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus
from aegis.capabilities.model.metrics import CapabilityMetrics
from aegis.capabilities.registry_v2.capability_registry import CapabilityRegistry
from aegis.capabilities.store.capability_store import CapabilityStore


def _make_record(cap_id: str, category=CapabilityCategory.FILESYSTEM, **kwargs) -> CapabilityRecord:
    return CapabilityRecord(
        capability_id=cap_id,
        name=f"Cap {cap_id}",
        category=category,
        implementation=BuiltinRef(executor_name="test", action_kind="test.exec"),
        trust_state=TrustState.TRUSTED,
        health=CapabilityHealth(status=HealthStatus.AVAILABLE),
        enabled=True,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# CapabilityStore
# ---------------------------------------------------------------------------

class TestCapabilityStore:
    def test_register_and_get(self):
        store = CapabilityStore()
        rec = _make_record("cap1")
        store.register(rec)
        assert store.has("cap1")
        assert store.get("cap1") is not None
        assert store.count() == 1

    def test_unregister(self):
        store = CapabilityStore()
        store.register(_make_record("cap2"))
        assert store.unregister("cap2")
        assert not store.has("cap2")
        assert store.count() == 0

    def test_unregister_missing_returns_false(self):
        store = CapabilityStore()
        assert not store.unregister("nonexistent")

    def test_update_health(self):
        store = CapabilityStore()
        store.register(_make_record("cap3"))
        new_health = CapabilityHealth(status=HealthStatus.DEGRADED)
        store.update_health("cap3", new_health)
        assert store.get("cap3").health.status == HealthStatus.DEGRADED

    def test_update_trust(self):
        store = CapabilityStore()
        store.register(_make_record("cap4", trust_state=TrustState.VERIFIED))
        store.update_trust("cap4", TrustState.TRUSTED)
        assert store.get("cap4").trust_state == TrustState.TRUSTED

    def test_set_enabled(self):
        store = CapabilityStore()
        store.register(_make_record("cap5"))
        store.set_enabled("cap5", False)
        assert not store.get("cap5").enabled

    def test_replace_existing(self):
        store = CapabilityStore()
        rec_v1 = _make_record("cap6", description="v1")
        rec_v2 = _make_record("cap6", description="v2")
        store.register(rec_v1)
        store.register(rec_v2)
        assert store.count() == 1
        assert store.get("cap6").description == "v2"

    def test_query_by_category(self):
        store = CapabilityStore()
        store.register(_make_record("c1", category=CapabilityCategory.GIT))
        store.register(_make_record("c2", category=CapabilityCategory.FILESYSTEM))
        store.register(_make_record("c3", category=CapabilityCategory.GIT))
        git_caps = store.query(category=CapabilityCategory.GIT)
        assert len(git_caps) == 2
        fs_caps = store.query(category=CapabilityCategory.FILESYSTEM)
        assert len(fs_caps) == 1

    def test_query_usable_only(self):
        store = CapabilityStore()
        store.register(_make_record("usable1"))                         # usable
        store.register(_make_record("unverified1",
                                    trust_state=TrustState.UNVERIFIED))  # not usable
        store.register(_make_record("disabled1", enabled=False))        # not usable
        usable = store.query(usable_only=True)
        assert len(usable) == 1
        assert usable[0].capability_id == "usable1"

    def test_query_by_trust_state(self):
        store = CapabilityStore()
        store.register(_make_record("v1", trust_state=TrustState.VERIFIED))
        store.register(_make_record("t1", trust_state=TrustState.TRUSTED))
        verified = store.query(trust_state=TrustState.VERIFIED)
        assert len(verified) == 1
        assert verified[0].capability_id == "v1"

    def test_query_by_predicate(self):
        store = CapabilityStore()
        store.register(_make_record("p1", required_permissions=["fs.read"]))
        store.register(_make_record("p2", required_permissions=["shell.exec"]))
        shell_caps = store.query(
            predicate=lambda r: "shell.exec" in r.required_permissions
        )
        assert len(shell_caps) == 1
        assert shell_caps[0].capability_id == "p2"

    def test_query_online_required_filter(self):
        store = CapabilityStore()
        store.register(_make_record("offline1", online_required=False))
        store.register(_make_record("online1", online_required=True))
        # Ask for offline only
        offline_caps = store.query(online_required=False)
        assert all(not r.online_required for r in offline_caps)
        assert len(offline_caps) >= 1

    def test_thread_safety_concurrent_registration(self):
        """Multiple threads registering should not corrupt state."""
        import threading
        store = CapabilityStore()
        errors = []

        def register_batch(start: int) -> None:
            try:
                for i in range(10):
                    store.register(_make_record(f"concurrent:{start}:{i}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_batch, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert store.count() == 50


# ---------------------------------------------------------------------------
# SemanticCapabilityRegistry
# ---------------------------------------------------------------------------

class TestSemanticCapabilityRegistry:
    def test_discover_sync_with_static_provider(self):
        reg = CapabilityRegistry()
        reg.add_provider(StaticRegistryProvider())
        count = reg.discover_sync()
        assert count >= 5

    def test_register_and_get(self):
        reg = CapabilityRegistry()
        rec = _make_record("reg:test1")
        reg.register(rec)
        assert reg.get("reg:test1") is not None
        assert reg.count() >= 1

    def test_unregister(self):
        reg = CapabilityRegistry()
        reg.register(_make_record("reg:test2"))
        assert reg.unregister("reg:test2")
        assert reg.get("reg:test2") is None

    def test_query_by_category(self):
        reg = CapabilityRegistry()
        reg.register(_make_record("q1", category=CapabilityCategory.GIT))
        reg.register(_make_record("q2", category=CapabilityCategory.DOCKER))
        git_caps = reg.query(category=CapabilityCategory.GIT)
        assert any(r.capability_id == "q1" for r in git_caps)

    def test_find_for_task_ranked_output(self):
        reg = CapabilityRegistry()
        # Add a TRUSTED/AVAILABLE builtin (high score)
        reg.register(_make_record("high_score",
                                   category=CapabilityCategory.GIT,
                                   trust_state=TrustState.TRUSTED))
        # Add an UNVERIFIED one (should be excluded from usable_only=True)
        reg.register(_make_record("low_score",
                                   category=CapabilityCategory.GIT,
                                   trust_state=TrustState.UNVERIFIED))
        results = reg.find_for_task("commit code to git",
                                     category=CapabilityCategory.GIT,
                                     usable_only=True)
        ids = [r.capability_id for r in results]
        assert "high_score" in ids
        assert "low_score" not in ids

    def test_find_for_task_keyword_boost(self):
        reg = CapabilityRegistry()
        reg.register(_make_record("search-cap",
                                   name="Filesystem Search",
                                   description="Search for files",
                                   category=CapabilityCategory.FILESYSTEM))
        reg.register(_make_record("read-cap",
                                   name="Filesystem Read",
                                   description="Read file contents",
                                   category=CapabilityCategory.FILESYSTEM))
        results = reg.find_for_task("search for python files",
                                     category=CapabilityCategory.FILESYSTEM)
        # "search" cap should appear in results
        assert any(r.capability_id == "search-cap" for r in results)

    @pytest.mark.asyncio
    async def test_discover_async_with_static_provider(self):
        reg = CapabilityRegistry()
        reg.add_provider(StaticRegistryProvider())
        count = await reg.discover()
        assert count >= 5

    @pytest.mark.asyncio
    async def test_discover_uses_cache_within_refresh_interval(self):
        reg = CapabilityRegistry(refresh_interval=3600.0)
        reg.add_provider(StaticRegistryProvider())
        count1 = await reg.discover()
        count2 = await reg.discover()  # Should use cache
        assert count1 == count2

    @pytest.mark.asyncio
    async def test_discover_force_reruns(self):
        reg = CapabilityRegistry()
        reg.add_provider(StaticRegistryProvider())
        await reg.discover()
        count = await reg.discover(force=True)
        assert count >= 5

    def test_update_trust_state(self):
        reg = CapabilityRegistry()
        reg.register(_make_record("trust-test", trust_state=TrustState.UNVERIFIED))
        reg.update_trust("trust-test", TrustState.VERIFIED)
        assert reg.get("trust-test").trust_state == TrustState.VERIFIED

    def test_set_enabled_disables_capability(self):
        reg = CapabilityRegistry()
        reg.register(_make_record("enable-test"))
        reg.set_enabled("enable-test", False)
        assert not reg.get("enable-test").enabled

    def test_remove_provider(self):
        reg = CapabilityRegistry()
        reg.add_provider(StaticRegistryProvider())
        removed = reg.remove_provider("static_registry_provider")
        assert removed

    def test_to_summary_structure(self):
        reg = CapabilityRegistry()
        reg.add_provider(StaticRegistryProvider())
        reg.discover_sync()
        summary = reg.to_summary()
        assert "total" in summary
        assert "usable" in summary
        assert "by_category" in summary
        assert summary["total"] >= 5

    def test_is_stale_before_discovery(self):
        reg = CapabilityRegistry(refresh_interval=1.0)
        assert reg.is_stale
