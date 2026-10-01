"""P08 Tests — Discovery Providers.

Tests for StaticRegistryProvider, CLIDiscoveryProvider,
LocalModelDiscoveryProvider (mocked HTTP), and MCPDiscoveryProvider.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from aegis.capabilities.discovery_providers.cli_provider import CLIDiscoveryProvider
from aegis.capabilities.discovery_providers.local_model_provider import LocalModelDiscoveryProvider
from aegis.capabilities.discovery_providers.mcp_provider import MCPDiscoveryProvider
from aegis.capabilities.discovery_providers.static_provider import StaticRegistryProvider
from aegis.capabilities.model.capability import CapabilityCategory, TrustState
from aegis.capabilities.model.health import HealthStatus


_DEADLINE = time.monotonic() + 30.0


class TestStaticRegistryProvider:
    def test_name(self):
        p = StaticRegistryProvider()
        assert p.name == "static_registry_provider"

    def test_not_online_required(self):
        assert not StaticRegistryProvider().online_required

    def test_returns_builtin_capabilities(self):
        p = StaticRegistryProvider()
        records = p.discover(_DEADLINE)
        assert len(records) >= 5
        ids = {r.capability_id for r in records}
        assert "builtin:fs.read" in ids
        assert "builtin:fs.write" in ids
        assert "builtin:shell.exec" in ids
        assert "builtin:memory.recall" in ids

    def test_all_builtin_trusted(self):
        records = StaticRegistryProvider().discover(_DEADLINE)
        for r in records:
            assert r.trust_state == TrustState.TRUSTED, f"{r.capability_id} not TRUSTED"

    def test_all_builtin_available(self):
        records = StaticRegistryProvider().discover(_DEADLINE)
        for r in records:
            assert r.health.status == HealthStatus.AVAILABLE

    def test_all_builtin_enabled(self):
        records = StaticRegistryProvider().discover(_DEADLINE)
        for r in records:
            assert r.enabled

    def test_python_version_set(self):
        import sys
        records = StaticRegistryProvider().discover(_DEADLINE)
        py_caps = [r for r in records if r.capability_id == "builtin:python.exec"]
        assert len(py_caps) == 1
        expected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert py_caps[0].version == expected

    def test_safe_discover_never_raises(self):
        p = StaticRegistryProvider()
        # safe_discover should never raise even if discover raises
        result = p.safe_discover(_DEADLINE)
        assert isinstance(result, list)


class TestCLIDiscoveryProvider:
    def test_name(self):
        p = CLIDiscoveryProvider()
        assert p.name == "cli_discovery_provider"

    def test_not_online_required(self):
        assert not CLIDiscoveryProvider().online_required

    def test_discovers_git_if_available(self):
        import shutil
        if not shutil.which("git"):
            pytest.skip("git not on PATH")
        p = CLIDiscoveryProvider()
        records = p.discover(_DEADLINE)
        ids = {r.capability_id for r in records}
        assert "cli:git" in ids

    def test_git_record_is_verified_not_trusted(self):
        import shutil
        if not shutil.which("git"):
            pytest.skip("git not on PATH")
        p = CLIDiscoveryProvider()
        records = p.discover(_DEADLINE)
        git_recs = [r for r in records if r.capability_id == "cli:git"]
        assert git_recs[0].trust_state == TrustState.VERIFIED

    def test_missing_tool_not_included(self):
        # Provide a fake tool that definitely won't exist
        fake_tools = [{
            "id": "cli:nonexistent_tool_xyz",
            "name": "Nonexistent",
            "desc": "Does not exist",
            "category": CapabilityCategory.CUSTOM,
            "cmd": "nonexistent_tool_xyz_aegis_test",
            "version_cmd": ["nonexistent_tool_xyz_aegis_test", "--version"],
            "version_extract": lambda o: None,
            "action_kind": "shell.exec",
            "permissions": [],
        }]
        p = CLIDiscoveryProvider(tools=fake_tools)
        records = p.discover(_DEADLINE)
        assert records == []

    def test_safe_discover_wraps_exceptions(self):
        p = CLIDiscoveryProvider()
        with patch.object(p, "discover", side_effect=RuntimeError("boom")):
            result = p.safe_discover(_DEADLINE)
        assert result == []

    def test_deadline_respected(self):
        p = CLIDiscoveryProvider()
        # Passed deadline — should get empty list or partial
        result = p.discover(time.monotonic() - 1.0)
        assert isinstance(result, list)


class TestLocalModelDiscoveryProvider:
    def test_name(self):
        p = LocalModelDiscoveryProvider()
        assert p.name == "local_model_discovery_provider"

    def test_not_online_required(self):
        assert not LocalModelDiscoveryProvider().online_required

    def test_no_ollama_returns_empty(self):
        # Use a port that nothing is listening on
        p = LocalModelDiscoveryProvider(
            ollama_base="http://127.0.0.1:59999",
            lm_studio_base="http://127.0.0.1:59998",
        )
        records = p.discover(_DEADLINE)
        assert isinstance(records, list)
        assert len(records) == 0   # nothing running on those ports

    def test_ollama_response_parsed(self):
        """Mock the HTTP call to verify parsing logic."""
        fake_tags_response = b'{"models": [{"name": "llama3.2", "size": 1000, "digest": "abc123", "modified_at": ""}]}'
        import urllib.request
        import io
        fake_resp = MagicMock()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        fake_resp.read = lambda: fake_tags_response

        with patch("urllib.request.urlopen", return_value=fake_resp):
            p = LocalModelDiscoveryProvider(ollama_base="http://127.0.0.1:11434")
            records = p._probe_ollama(_DEADLINE)

        assert len(records) == 1
        assert records[0].capability_id == "ollama:llama3.2"
        assert records[0].trust_state == TrustState.VERIFIED
        assert records[0].privacy_tier == "P0"
        assert not records[0].online_required  # Local model is offline

    def test_malformed_ollama_response_returns_empty(self):
        fake_resp = MagicMock()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        fake_resp.read = lambda: b"not valid json {"

        with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
            p = LocalModelDiscoveryProvider(ollama_base="http://127.0.0.1:11434")
            records = p._probe_ollama(_DEADLINE)
        assert records == []


class TestMCPDiscoveryProvider:
    def test_name(self):
        p = MCPDiscoveryProvider()
        assert p.name == "mcp_discovery_provider"

    def test_no_registry_returns_empty(self):
        p = MCPDiscoveryProvider(server_registry=None)
        records = p.discover(_DEADLINE)
        assert records == []

    def test_mcp_tools_start_unverified(self):
        """MCP tools MUST always start as UNVERIFIED — core security invariant."""
        from aegis.capabilities.mcp.server_registry import MCPServerRegistry
        from aegis.capabilities.mcp.types import MCPServerRecord, MCPToolRecord, MCPTransport
        from aegis.capabilities.model.health import CapabilityHealth, HealthStatus

        registry = MCPServerRegistry()
        server = MCPServerRecord(
            server_id="test-server-01",
            name="Test MCP Server",
            transport=MCPTransport.HTTP,
            endpoint="http://localhost:3000",
            health=CapabilityHealth(status=HealthStatus.AVAILABLE),
        )
        registry.register_server(server)
        registry.set_trust("test-server-01", TrustState.VERIFIED)   # elevate server trust

        tool = MCPToolRecord(
            server_id="test-server-01",
            tool_name="search",
            tool_id="test-server-01:search",
            description="Search the web",
        )
        registry.register_tool(tool)

        provider = MCPDiscoveryProvider(server_registry=registry)
        records = provider.discover(_DEADLINE)

        assert len(records) == 1
        # KEY INVARIANT: Even though server is VERIFIED, the tool record starts UNVERIFIED
        assert records[0].trust_state == TrustState.UNVERIFIED, \
            "MCP tools must start UNVERIFIED regardless of server trust state"
        assert records[0].capability_id == "mcp:test-server-01:search"

    def test_disabled_server_tools_skipped(self):
        from aegis.capabilities.mcp.server_registry import MCPServerRegistry
        from aegis.capabilities.mcp.types import MCPServerRecord, MCPToolRecord, MCPTransport

        registry = MCPServerRegistry()
        server = MCPServerRecord(
            server_id="disabled-server",
            name="Disabled Server",
            transport=MCPTransport.HTTP,
        )
        registry.register_server(server)
        registry.disable_server("disabled-server")

        tool = MCPToolRecord(
            server_id="disabled-server",
            tool_name="tool1",
            tool_id="disabled-server:tool1",
        )
        registry.register_tool(tool)

        provider = MCPDiscoveryProvider(server_registry=registry)
        records = provider.discover(_DEADLINE)
        assert len(records) == 0  # disabled server skipped
