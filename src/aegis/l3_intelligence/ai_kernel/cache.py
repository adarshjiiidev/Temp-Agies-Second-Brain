"""L3 AI Kernel ResponseCache abstraction (Prompt 03 §21).

Request fingerprinting, TTL-based expiry, privacy-aware caching policy
(P0 NEVER cached by default, P1+ permitted per policy), LRU eviction on
capacity/size thresholds, and explicit invalidation.

The in-memory implementation is synchronous internally but exposes async
lookup/store signatures to keep the public API compatible with future
SQLite / Redis persistence backends that require I/O.

This module MUST remain free of circular imports — it depends only on:
  * types.py (PrivacyTier)
  * contracts.py (AIRequest)
  * stdlib + Pydantic v2
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis.l3_intelligence.ai_kernel.contracts import AIRequest
from aegis.l3_intelligence.ai_kernel.types import PrivacyTier


# ---------------------------------------------------------------------------
# CacheEntry — frozen pydantic record of a single cached response.
# Frozen + extra=forbid guarantees the identifying fields are immutable
# after construction; only access-tracking fields mutate via object.__setattr__.
# ---------------------------------------------------------------------------


class CacheEntry(BaseModel):
    """Immutable cached response record with access-tracking metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fingerprint: str
    provider_id: str
    model_id: str
    content: str
    structured_data_json: dict | None = None
    raw_response: dict | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    ttl_seconds: float = 0.0
    created_at: float = Field(default_factory=time.time)
    accessed_at: float = 0.0
    access_count: int = 0
    privacy_tier: PrivacyTier = PrivacyTier.P2
    is_local_only: bool = False

    @model_validator(mode="after")
    def _sync_accessed_at(self) -> CacheEntry:
        if self.accessed_at == 0.0:
            object.__setattr__(self, "accessed_at", self.created_at)
        return self


# ---------------------------------------------------------------------------
# CacheHit — lightweight tuple-alike dataclass returned from lookups.
# ---------------------------------------------------------------------------


@dataclass
class CacheHit:
    """Result of a ResponseCache.lookup() call."""

    hit: bool
    entry: CacheEntry | None = None
    fingerprint: str = ""


# ---------------------------------------------------------------------------
# CachePolicy — collection of knobs controlling what enters the cache.
# ---------------------------------------------------------------------------


@dataclass
class CachePolicy:
    """Privacy + tier + provider/model allow/deny configuration."""

    enabled: bool = True
    ttl_default_seconds: float = 3600.0
    respect_privacy: bool = True
    cache_p0: bool = False
    cache_p1: bool = True
    cache_p2: bool = True
    cache_p3: bool = True
    max_entries: int = 10_000
    max_bytes_approx: int = 50 * 1024 * 1024
    provider_allowlist: list[str] | None = None
    provider_denylist: list[str] = field(default_factory=list)
    model_allowlist: list[str] | None = None
    model_denylist: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# fingerprint_request — deterministic SHA-256 truncated fingerprint helper.
# Works on raw dicts (sorted-key normalization) or AIRequest models.
# ---------------------------------------------------------------------------


def fingerprint_request(req: AIRequest | dict) -> str:
    """Compute a deterministic 32-hex-char fingerprint of a request.

    For dict input: normalize via sorted-key JSON dump.
    For AIRequest: hash messages (sorted serialized) + temperature +
    max_output_tokens + system_instruction + routing.required_capabilities
    (sorted) + routing.task_type + structured effective JSON schema
    (if set) + privacy_tier.value.
    """
    if isinstance(req, dict):
        payload = json.dumps(req, sort_keys=True, default=str, ensure_ascii=False)
    else:
        messages_norm: list[dict[str, Any]] = []
        for msg in req.messages:
            if hasattr(msg, "__dataclass_fields__"):
                d = {
                    "role": getattr(msg, "role", None),
                    "content": getattr(msg, "content", None),
                    "name": getattr(msg, "name", None),
                    "tool_call_id": getattr(msg, "tool_call_id", None),
                }
            elif isinstance(msg, dict):
                d = {
                    "role": msg.get("role"),
                    "content": msg.get("content"),
                    "name": msg.get("name"),
                    "tool_call_id": msg.get("tool_call_id"),
                }
            else:
                d = {"role": str(msg)}
            messages_norm.append(d)
        messages_blob = json.dumps(messages_norm, sort_keys=True, default=str, ensure_ascii=False)

        caps_sorted = sorted(req.routing.required_capabilities or [])
        schema_blob = ""
        effective_schema = req.structured.effective_json_schema()
        if effective_schema is not None:
            schema_blob = json.dumps(effective_schema, sort_keys=True, default=str, ensure_ascii=False)

        components: list[str] = [
            messages_blob,
            repr(req.temperature),
            repr(req.max_output_tokens),
            req.system_instruction or "",
            json.dumps(caps_sorted, sort_keys=True),
            req.routing.task_type.value if req.routing.task_type else "",
            schema_blob,
            req.routing.privacy_tier.value,
        ]
        payload = "\x00".join(components)

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest[:32]


# ---------------------------------------------------------------------------
# ResponseCache — privacy-aware, TTL-bounded, LRU-evicted in-memory cache.
# ---------------------------------------------------------------------------


class ResponseCache:
    """Deterministic AI response cache with privacy tiers and LRU eviction.

    Default policy (see CachePolicy):
      * P0 — NEVER cached unless policy.cache_p0=True AND local_only.
      * P1/P2/P3 — cached normally per policy.cache_pN flags.
      * TTL default: 1 hour (ttl_default_seconds=3600).
      * Capacity: 10,000 entries / 50 MB soft size cap.
    """

    def __init__(self, policy: CachePolicy | None = None) -> None:
        self._policy: CachePolicy = policy or CachePolicy()
        self._entries: dict[str, CacheEntry] = {}
        self._order: deque[str] = deque()

    # ------------------------------------------------------------------
    # Policy check — used by store + also re-validated on lookup.
    # ------------------------------------------------------------------

    def can_cache(
        self,
        *,
        privacy_tier: PrivacyTier,
        provider_id: str,
        model_id: str,
        local_only: bool = False,
    ) -> bool:
        """Return True if an entry with the given attributes may be cached."""
        p = self._policy
        if not p.enabled:
            return False

        # Privacy tier enforcement — P0 local-mandatory is the strictest gate.
        if p.respect_privacy:
            if privacy_tier.is_local_mandatory and not p.cache_p0 and not local_only:
                return False

        tier_value = privacy_tier.value
        if tier_value == "P0":
            if not p.cache_p0:
                return False
            if privacy_tier.is_local_mandatory and not local_only:
                return False
        elif tier_value == "P1":
            if not p.cache_p1:
                return False
        elif tier_value == "P2":
            if not p.cache_p2:
                return False
        elif tier_value == "P3":
            if not p.cache_p3:
                return False

        # Provider allow/deny
        if p.provider_allowlist is not None and provider_id not in p.provider_allowlist:
            return False
        if provider_id in p.provider_denylist:
            return False

        # Model allow/deny
        if p.model_allowlist is not None and model_id not in p.model_allowlist:
            return False
        if model_id in p.model_denylist:
            return False

        return True

    # ------------------------------------------------------------------
    # Lookup — async signature for future I/O backends; in-mem is fast.
    # ------------------------------------------------------------------

    async def lookup(
        self,
        fingerprint: str | AIRequest,
        *,
        now: float | None = None,
    ) -> CacheHit:
        """Return CacheHit for fingerprint or request; miss if expired or policy now rejects."""
        fp = fingerprint if isinstance(fingerprint, str) else fingerprint_request(fingerprint)
        entry = self._entries.get(fp)
        if entry is None:
            return CacheHit(hit=False, fingerprint=fp)

        current_time = now if now is not None else time.time()

        # TTL check: ttl_seconds == 0 means "never expires" (infinite TTL semantics).
        ttl = entry.ttl_seconds
        if ttl > 0.0 and (entry.created_at + ttl) < current_time:
            del self._entries[fp]
            try:
                self._order.remove(fp)
            except ValueError:
                pass
            return CacheHit(hit=False, fingerprint=fp)

        # Re-check policy (deny lists may have changed since store time).
        if not self.can_cache(
            privacy_tier=entry.privacy_tier,
            provider_id=entry.provider_id,
            model_id=entry.model_id,
            local_only=entry.is_local_only,
        ):
            return CacheHit(hit=False, fingerprint=fp)

        # Update access tracking (mutate frozen fields via object.__setattr__).
        object.__setattr__(entry, "accessed_at", current_time)
        object.__setattr__(entry, "access_count", entry.access_count + 1)

        # LRU refresh: remove then re-append to mark most-recently-used.
        try:
            self._order.remove(fp)
        except ValueError:
            pass
        self._order.append(fp)

        return CacheHit(hit=True, entry=entry, fingerprint=fp)

    # ------------------------------------------------------------------
    # Store — policy gate, then insert + evict if over capacity/size.
    # ------------------------------------------------------------------

    async def store(
        self,
        req_or_fp: AIRequest | str,
        *,
        content: str,
        provider_id: str,
        model_id: str,
        privacy_tier: PrivacyTier,
        tokens_in: int = 0,
        tokens_out: int = 0,
        ttl: float | None = None,
        structured: dict | None = None,
        raw: dict | None = None,
        local_only: bool = False,
        now: float | None = None,
    ) -> CacheEntry | None:
        """Create and persist a CacheEntry; return None if policy rejects."""
        fp = req_or_fp if isinstance(req_or_fp, str) else fingerprint_request(req_or_fp)

        if not self.can_cache(
            privacy_tier=privacy_tier,
            provider_id=provider_id,
            model_id=model_id,
            local_only=local_only,
        ):
            return None

        effective_ttl = ttl if ttl is not None else self._policy.ttl_default_seconds
        current_time = now if now is not None else time.time()

        entry = CacheEntry(
            fingerprint=fp,
            provider_id=provider_id,
            model_id=model_id,
            content=content,
            structured_data_json=structured,
            raw_response=raw,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            ttl_seconds=effective_ttl,
            created_at=current_time,
            accessed_at=current_time,
            access_count=0,
            privacy_tier=privacy_tier,
            is_local_only=local_only,
        )

        # If fingerprint already present, remove from order before re-inserting
        # (we replace the stored entry but maintain single LRU node).
        if fp in self._entries:
            try:
                self._order.remove(fp)
            except ValueError:
                pass

        self._entries[fp] = entry
        self._order.append(fp)

        self._evict_if_over_limits()
        return entry

    # ------------------------------------------------------------------
    # Invalidation helpers.
    # ------------------------------------------------------------------

    def invalidate(self, fingerprint_prefix_or_exact: str, *, prefix_match: bool = False) -> int:
        """Remove entries by exact fingerprint or prefix; returns count removed."""
        removed = 0
        if prefix_match:
            for fp in list(self._entries.keys()):
                if fp.startswith(fingerprint_prefix_or_exact):
                    del self._entries[fp]
                    try:
                        self._order.remove(fp)
                    except ValueError:
                        pass
                    removed += 1
        else:
            if fingerprint_prefix_or_exact in self._entries:
                del self._entries[fingerprint_prefix_or_exact]
                try:
                    self._order.remove(fingerprint_prefix_or_exact)
                except ValueError:
                    pass
                removed += 1
        return removed

    def clear(self) -> int:
        """Remove every entry; returns count removed."""
        count = len(self._entries)
        self._entries.clear()
        self._order.clear()
        return count

    # ------------------------------------------------------------------
    # Diagnostics + maintenance.
    # ------------------------------------------------------------------

    def info(self) -> dict:
        """Return dict with entry count and approximate size in bytes."""
        approx = 0
        for entry in self._entries.values():
            approx += len(entry.content) if entry.content else 0
            if entry.structured_data_json is not None:
                try:
                    approx += len(json.dumps(entry.structured_data_json, default=str))
                except Exception:
                    approx += 256
            if entry.raw_response is not None:
                try:
                    approx += len(json.dumps(entry.raw_response, default=str))
                except Exception:
                    approx += 256
        return {"count": len(self._entries), "approx_size_bytes": int(approx)}

    def sweep_expired(self, now: float | None = None) -> int:
        """Remove entries whose TTL has elapsed; returns count evicted."""
        current_time = now if now is not None else time.time()
        evicted = 0
        for fp in list(self._entries.keys()):
            entry = self._entries[fp]
            ttl = entry.ttl_seconds
            if ttl > 0.0 and (entry.created_at + ttl) < current_time:
                del self._entries[fp]
                try:
                    self._order.remove(fp)
                except ValueError:
                    pass
                evicted += 1
        return evicted

    # ------------------------------------------------------------------
    # Internal: LRU + size eviction loop.
    # ------------------------------------------------------------------

    def _evict_if_over_limits(self) -> None:
        """Evict oldest entries until both count and approx-size are under policy caps."""
        while len(self._entries) > self._policy.max_entries and self._order:
            oldest = self._order.popleft()
            self._entries.pop(oldest, None)

        info = self.info()
        while info["approx_size_bytes"] > self._policy.max_bytes_approx and self._order:
            oldest = self._order.popleft()
            popped = self._entries.pop(oldest, None)
            if popped is None:
                continue
            info = self.info()


__all__ = [
    "CacheEntry",
    "CacheHit",
    "CachePolicy",
    "ResponseCache",
    "fingerprint_request",
]
