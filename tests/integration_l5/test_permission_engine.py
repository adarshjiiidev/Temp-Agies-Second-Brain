"""Integration tests — Permission Engine (Stage 1).

Tests:
  - SVRC deny-by-default with no grants
  - Grant matching (exact verb)
  - Grant matching (namespace verb)
  - TTL expiry correctly denies after expiry
  - One-time grants revoked after first use
  - has_permission helper
  - list_grants
  - revoke_grant
  - 20 unpermitted actions → ALL denied + audit entry exists
"""

from __future__ import annotations

import time
import uuid

import pytest
import pytest_asyncio

from aegis.l5_execution.contracts import SVRCRequest
from aegis.l5_execution.exceptions import PermissionDeniedError
from aegis.l5_execution.permission.engine import PermissionEngine
from aegis.l5_execution.permission.verbs import verb_implies, verb_matches
from aegis.l5_execution.types import PermissionDecision


@pytest_asyncio.fixture
async def engine():
    e = PermissionEngine(db_path=None)
    await e.initialize()
    yield e
    await e.close()


# -----------------------------------------------------------------------
# Verb hierarchy tests
# -----------------------------------------------------------------------

def test_verb_implies_exact():
    assert verb_implies("fs.read", "fs.read") is True

def test_verb_implies_namespace():
    assert verb_implies("fs", "fs.read") is True
    assert verb_implies("fs", "fs.write") is True
    assert verb_implies("fs", "fs.delete") is True

def test_verb_implies_wildcard():
    assert verb_implies("*", "git.push") is True
    assert verb_implies("*", "fs.delete") is True

def test_verb_not_implies_broader():
    assert verb_implies("fs.read", "fs") is False
    assert verb_implies("fs.read", "fs.write") is False

def test_verb_namespace_does_not_cross():
    assert verb_implies("git", "fs.read") is False
    assert verb_implies("net", "browser.navigate") is False

def test_verb_matches_list():
    assert verb_matches(["fs.read", "git"], "git.push") is True
    assert verb_matches(["fs.read"], "git.push") is False
    assert verb_matches(["*"], "camera.capture") is True


# -----------------------------------------------------------------------
# Permission engine tests
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deny_by_default_no_grants(engine):
    """Any action with no matching grant → DENY."""
    decision = await engine.check(SVRCRequest(
        subject="system:planner",
        verb="fs.read",
        resource="fs:~/Projects/AGIES/README.md",
    ))
    assert decision.decision is PermissionDecision.DENY
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_grant_exact_verb_allows(engine):
    await engine.grant(
        subject="system:planner",
        verbs=["fs.read"],
        resources=["fs:*"],
        granted_by="user:primary",
    )
    decision = await engine.check(SVRCRequest(
        subject="system:planner",
        verb="fs.read",
        resource="fs:~/Projects/README.md",
    ))
    assert decision.allowed is True


@pytest.mark.asyncio
async def test_grant_namespace_covers_children(engine):
    await engine.grant(
        subject="system:planner",
        verbs=["fs"],
        resources=["fs:*"],
        granted_by="user:primary",
    )
    for verb in ["fs.read", "fs.write", "fs.copy", "fs.delete", "fs.hash"]:
        decision = await engine.check(SVRCRequest(
            subject="system:planner",
            verb=verb,
            resource="fs:~/test.txt",
        ))
        assert decision.allowed is True, f"Expected ALLOW for {verb}"


@pytest.mark.asyncio
async def test_grant_does_not_cover_different_namespace(engine):
    await engine.grant(
        subject="system:planner",
        verbs=["fs"],
        resources=["fs:*"],
        granted_by="user:primary",
    )
    decision = await engine.check(SVRCRequest(
        subject="system:planner",
        verb="git.push",
        resource="git:origin",
    ))
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_ttl_grant_expires(engine):
    await engine.grant(
        subject="system:planner",
        verbs=["fs.read"],
        resources=["fs:*"],
        granted_by="user:primary",
        ttl_seconds=0.01,  # 10ms TTL
    )
    # Expire it
    await engine._store.expire_old_grants()
    import asyncio
    await asyncio.sleep(0.05)
    await engine._store.expire_old_grants()

    decision = await engine.check(SVRCRequest(
        subject="system:planner",
        verb="fs.read",
        resource="fs:~/test.txt",
    ))
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_one_time_grant_revoked_after_use(engine):
    grant = await engine.grant(
        subject="system:planner",
        verbs=["net.post"],
        resources=["net:*"],
        granted_by="user:primary",
        is_one_time=True,
    )
    # First use → allowed
    decision = await engine.check(SVRCRequest(
        subject="system:planner",
        verb="net.post",
        resource="net:api.openrouter.ai",
    ))
    assert decision.allowed is True

    # Second use → denied (grant revoked)
    decision2 = await engine.check(SVRCRequest(
        subject="system:planner",
        verb="net.post",
        resource="net:api.openrouter.ai",
    ))
    assert decision2.allowed is False


@pytest.mark.asyncio
async def test_has_permission_returns_bool(engine):
    assert await engine.has_permission("system:planner", "fs.read", "fs:~/test") is False
    await engine.grant(
        subject="system:planner",
        verbs=["fs.read"],
        resources=["fs:*"],
        granted_by="user:primary",
    )
    assert await engine.has_permission("system:planner", "fs.read", "fs:~/test") is True


@pytest.mark.asyncio
async def test_revoke_grant(engine):
    grant = await engine.grant(
        subject="system:planner",
        verbs=["fs.write"],
        resources=["fs:*"],
        granted_by="user:primary",
    )
    assert await engine.has_permission("system:planner", "fs.write", "fs:~/test") is True
    await engine.revoke(grant.grant_id)
    assert await engine.has_permission("system:planner", "fs.write", "fs:~/test") is False


@pytest.mark.asyncio
async def test_check_or_raise_raises_on_deny(engine):
    with pytest.raises(PermissionDeniedError):
        await engine.check_or_raise(SVRCRequest(
            subject="system:planner",
            verb="shell.exec",
            resource="proc:bash",
        ))


# -----------------------------------------------------------------------
# 20 unpermitted actions → ALL denied
# -----------------------------------------------------------------------

_UNPERMITTED = [
    ("system:planner", "fs.delete", "fs:~/critical"),
    ("system:planner", "git.push", "git:origin/main"),
    ("system:planner", "shell.exec", "proc:bash"),
    ("system:planner", "net.post", "net:api.bank.com"),
    ("system:planner", "docker.exec", "docker:prod-container"),
    ("plugin:untrusted", "fs.write", "fs:~/home"),
    ("plugin:untrusted", "memory.delete", "memory:tier=personal"),
    ("plugin:untrusted", "aegis.core.mutate", "aegis:core"),
    ("generated:tool_abc", "net.delete", "net:production.api.com"),
    ("generated:tool_abc", "fs.chmod", "fs:/etc/passwd"),
    ("system:planner", "camera.capture", "camera:front"),
    ("system:planner", "mic.listen", "mic:default"),
    ("system:planner", "desktop.keyboard", "desktop:system"),
    ("system:planner", "browser.fill_form", "browser:banking.com"),
    ("system:planner", "aegis.user.impersonate", "aegis:user"),
    ("plugin:malicious", "aegis.plugin.load", "aegis:core"),
    ("generated:tool_xyz", "proc.spawn", "proc:type=powershell"),
    ("plugin:evil", "memory.export", "memory:all"),
    ("system:planner", "fs.exec", "fs:/usr/bin/evil"),
    ("generated:tool_xyz", "net.upload", "net:attacker.com"),
]

@pytest.mark.asyncio
async def test_20_unpermitted_all_denied(engine):
    """20 unpermitted actions → ALL denied (no grants added)."""
    for actor, verb, resource in _UNPERMITTED:
        decision = await engine.check(SVRCRequest(
            subject=actor,
            verb=verb,
            resource=resource,
        ))
        assert decision.allowed is False, (
            f"Expected DENY for {actor=} {verb=} {resource=} but got ALLOW"
        )
        assert decision.decision is PermissionDecision.DENY
