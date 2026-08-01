"""Integration tests — Risk Analyzer (Stage 2)."""

from __future__ import annotations

import pytest

from aegis.l5_execution.risk.analyzer import RiskAnalyzer
from aegis.l5_execution.types import Action, ActionKind, RiskLevel
from tests.integration_l5.conftest import make_action


@pytest.fixture
def analyzer():
    return RiskAnalyzer()


def test_fs_read_is_low(analyzer):
    action = make_action(ActionKind.FS_READ, resource="fs:~/Projects/README.md")
    result = analyzer.assess(action)
    assert result.risk_level == RiskLevel.LOW


def test_fs_delete_is_high(analyzer):
    action = make_action(ActionKind.FS_DELETE, resource="fs:~/Projects/important.txt")
    result = analyzer.assess(action)
    assert result.risk_level >= RiskLevel.HIGH


def test_git_push_is_high(analyzer):
    action = make_action(ActionKind.GIT_PUSH, resource="git:origin/main")
    result = analyzer.assess(action)
    assert result.risk_level >= RiskLevel.HIGH


def test_shell_exec_is_high(analyzer):
    action = make_action(ActionKind.SHELL_EXEC, resource="proc:bash")
    result = analyzer.assess(action)
    assert result.risk_level >= RiskLevel.HIGH


def test_git_status_is_low(analyzer):
    action = make_action(ActionKind.GIT_STATUS, resource="git:local")
    result = analyzer.assess(action)
    assert result.risk_level == RiskLevel.LOW


def test_net_get_is_low_or_medium(analyzer):
    action = make_action(ActionKind.NET_GET, resource="net:api.openrouter.ai")
    result = analyzer.assess(action)
    assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)


def test_net_post_is_medium_or_higher(analyzer):
    action = make_action(ActionKind.NET_POST, resource="net:api.openrouter.ai")
    result = analyzer.assess(action)
    assert result.risk_level >= RiskLevel.MEDIUM


def test_generated_actor_raises_risk(analyzer):
    action = make_action(
        ActionKind.FS_WRITE,
        actor="generated:tool_abc",
        resource="fs:~/Projects/file.txt",
    )
    result = analyzer.assess(action)
    # Untrusted actor inflates risk
    assert result.risk_level >= RiskLevel.MEDIUM


def test_irreversible_flag(analyzer):
    action = make_action(ActionKind.FS_DELETE, resource="fs:~/test.txt")
    result = analyzer.assess(action)
    assert result.reversible is False


def test_reversible_flag_for_read(analyzer):
    action = make_action(ActionKind.FS_READ, resource="fs:~/test.txt")
    result = analyzer.assess(action)
    assert result.reversible is True


def test_blast_radius_network(analyzer):
    action = make_action(ActionKind.GIT_PUSH, resource="git:origin")
    result = analyzer.assess(action)
    assert result.blast_radius == "network"


def test_blast_radius_local_for_read(analyzer):
    action = make_action(ActionKind.FS_READ, resource="fs:~/doc.md")
    result = analyzer.assess(action)
    assert result.blast_radius == "local"


def test_risk_level_ordering():
    assert RiskLevel.LOW < RiskLevel.MEDIUM
    assert RiskLevel.MEDIUM < RiskLevel.HIGH
    assert RiskLevel.HIGH < RiskLevel.CRITICAL
    assert RiskLevel.CRITICAL >= RiskLevel.HIGH


def test_score_is_normalised(analyzer):
    for kind in [ActionKind.FS_READ, ActionKind.FS_DELETE, ActionKind.SHELL_EXEC]:
        action = make_action(kind, resource="fs:~/test.txt")
        result = analyzer.assess(action)
        assert 0.0 <= result.score <= 1.0
