"""P08 Tests — MCP Registry and Schema Normalizer."""

from __future__ import annotations

import pytest

from aegis.capabilities.mcp.schema_normalizer import MCPSchemaNormalizer
from aegis.capabilities.mcp.server_registry import MCPServerRegistry
from aegis.capabilities.mcp.tool_registry import MCPToolRegistry
from aegis.capabilities.mcp.types import MCPServerRecord, MCPToolRecord, MCPTransport
from aegis.capabilities.model.capability import TrustState
from aegis.capabilities.model.health import CapabilityHealth, HealthStatus


class TestMCPServerRegistry:
    def _registry(self) -> MCPServerRegistry:
        return MCPServerRegistry()

    def test_register_server_starts_unverified(self):
        """SECURITY: any server registered must start UNVERIFIED."""
        reg = self._registry()
        server = MCPServerRecord(
            server_id="s1", name="Server1", trust_state=TrustState.TRUSTED  # forced down
        )
        reg.register_server(server)
        stored = reg.get_server("s1")
        assert stored is not None
        assert stored.trust_state == TrustState.UNVERIFIED, \
            "Server must be forced to UNVERIFIED regardless of provided trust_state"

    def test_register_and_get_server(self):
        reg = self._registry()
        server = MCPServerRecord(server_id="s2", name="Server2")
        reg.register_server(server)
        assert reg.get_server("s2") is not None
        assert reg.server_count() == 1

    def test_unregister_server_removes_tools(self):
        reg = self._registry()
        server = MCPServerRecord(server_id="s3", name="Server3")
        reg.register_server(server)
        tool = MCPToolRecord(server_id="s3", tool_name="t1", tool_id="s3:t1")
        reg.register_tool(tool)
        assert reg.tool_count() == 1

        result = reg.unregister_server("s3")
        assert result
        assert reg.server_count() == 0
        assert reg.tool_count() == 0

    def test_set_trust_elevates(self):
        reg = self._registry()
        server = MCPServerRecord(server_id="s4", name="Server4")
        reg.register_server(server)
        reg.set_trust("s4", TrustState.VERIFIED)
        assert reg.get_server("s4").trust_state == TrustState.VERIFIED

    def test_disable_server(self):
        reg = self._registry()
        server = MCPServerRecord(server_id="s5", name="Server5")
        reg.register_server(server)
        reg.disable_server("s5")
        assert reg.get_server("s5").trust_state == TrustState.DISABLED

    def test_set_trust_missing_server_returns_false(self):
        reg = self._registry()
        assert not reg.set_trust("nonexistent", TrustState.TRUSTED)

    def test_register_tool_requires_known_server(self):
        reg = self._registry()
        tool = MCPToolRecord(server_id="unknown", tool_name="t", tool_id="unknown:t")
        with pytest.raises(ValueError, match="unknown server"):
            reg.register_tool(tool)

    def test_list_servers_filtered_by_trust(self):
        reg = self._registry()
        for i in range(3):
            s = MCPServerRecord(server_id=f"s{i}", name=f"Server{i}")
            reg.register_server(s)
        reg.set_trust("s1", TrustState.VERIFIED)

        verified = reg.list_servers(trust_state=TrustState.VERIFIED)
        assert len(verified) == 1
        assert verified[0].server_id == "s1"

        unverified = reg.list_servers(trust_state=TrustState.UNVERIFIED)
        assert len(unverified) == 2

    def test_update_health(self):
        reg = self._registry()
        server = MCPServerRecord(server_id="s6", name="Server6")
        reg.register_server(server)
        health = CapabilityHealth(status=HealthStatus.AVAILABLE)
        reg.update_health("s6", health)
        assert reg.get_server("s6").health.status == HealthStatus.AVAILABLE

    def test_list_tools_by_server(self):
        reg = self._registry()
        for i in range(2):
            s = MCPServerRecord(server_id=f"srv{i}", name=f"Srv{i}")
            reg.register_server(s)
        for j in range(3):
            t = MCPToolRecord(server_id="srv0", tool_name=f"tool{j}", tool_id=f"srv0:tool{j}")
            reg.register_tool(t)
        t = MCPToolRecord(server_id="srv1", tool_name="tool0", tool_id="srv1:tool0")
        reg.register_tool(t)

        srv0_tools = reg.list_tools(server_id="srv0")
        assert len(srv0_tools) == 3
        srv1_tools = reg.list_tools(server_id="srv1")
        assert len(srv1_tools) == 1
        all_tools = reg.list_tools()
        assert len(all_tools) == 4

    def test_disable_tool(self):
        reg = self._registry()
        server = MCPServerRecord(server_id="s7", name="Server7")
        reg.register_server(server)
        tool = MCPToolRecord(server_id="s7", tool_name="t1", tool_id="s7:t1")
        reg.register_tool(tool)
        reg.disable_tool("s7:t1")
        assert not reg.get_tool("s7:t1").enabled

    def test_tool_registry_delegates(self):
        reg = MCPServerRegistry()
        tool_reg = MCPToolRegistry(reg)
        server = MCPServerRecord(server_id="ts1", name="TS1")
        reg.register_server(server)
        tool = MCPToolRecord(server_id="ts1", tool_name="do_thing", tool_id="ts1:do_thing")
        tool_reg.register_tool(tool)
        assert tool_reg.get_tool("ts1:do_thing") is not None


class TestMCPSchemaNormalizer:
    def _norm(self) -> MCPSchemaNormalizer:
        return MCPSchemaNormalizer()

    def test_normalize_simple_tool(self):
        raw = {
            "name": "search_web",
            "description": "Search the web for information",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
        }
        result = self._norm().normalize(raw, server_id="srv1")
        assert result["tool_name"] == "search_web"
        assert result["tool_id"] == "srv1:search_web"
        assert result["description"] == "Search the web for information"
        assert "query" in result["input_schema"].get("properties", {})

    def test_normalize_missing_name_raises(self):
        with pytest.raises(ValueError, match="missing required fields"):
            self._norm().normalize({"description": "no name"}, server_id="srv1")

    def test_high_risk_words_detected(self):
        raw = {"name": "delete_file", "description": "Delete a file from disk"}
        result = self._norm().normalize(raw, server_id="srv1")
        assert result["risk_hints"]["has_side_effects"]
        assert result["risk_hints"]["estimated_risk"] in ("medium", "high")

    def test_network_keyword_adds_network_permission(self):
        raw = {"name": "fetch_url", "description": "Fetch a URL via HTTP"}
        result = self._norm().normalize(raw, server_id="srv1")
        assert "network.request" in result["risk_hints"]["required_permissions"]

    def test_privacy_keyword_elevates_tier(self):
        raw = {"name": "get_user_email", "description": "Get the user email address"}
        result = self._norm().normalize(raw, server_id="srv1")
        assert result["privacy_tier"] in ("P0", "P1")

    def test_safe_tool_low_risk(self):
        raw = {"name": "get_weather", "description": "Returns current weather"}
        result = self._norm().normalize(raw, server_id="srv1")
        assert result["risk_hints"]["has_side_effects"] is False

    def test_strip_unknown_schema_fields(self):
        raw = {
            "name": "my_tool",
            "description": "desc",
            "inputSchema": {
                "type": "object",
                "x-custom-extension": "should-be-stripped",
                "properties": {"foo": {"type": "string"}},
            },
        }
        result = self._norm().normalize(raw, server_id="s")
        assert "x-custom-extension" not in result["input_schema"]
        assert "properties" in result["input_schema"]

    def test_no_description_generates_warning(self):
        raw = {"name": "mystery_tool", "description": ""}
        result = self._norm().normalize(raw, server_id="s")
        assert any("description" in w.lower() for w in result["warnings"])
