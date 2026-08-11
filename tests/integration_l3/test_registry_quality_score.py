"""Regression test for registry.quality_score_for — H12 double-count fix.

Verifies that reliability contributes EXACTLY ONCE to the quality score
(i.e., the old `+ reliability` double-count is gone).
"""

from __future__ import annotations

import pytest

from aegis.l3_intelligence.ai_kernel.registry import ModelRegistry, ModelMetadata
from aegis.l3_intelligence.ai_kernel.types import (
    DeploymentKind,
    PrivacyTier,
    TaskType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_model(
    *,
    provider_id: str = "test_provider",
    model_id: str = "test_model",
    structural_compliance_score: float = 0.8,
    reliability_score: float = 0.9,
    capabilities: list[str] | None = None,
) -> ModelMetadata:
    return ModelMetadata(
        provider_id=provider_id,
        model_id=model_id,
        family="test",
        display_name=model_id,
        deployment=DeploymentKind.LOCAL,
        context_window=4096,
        output_limit=2048,
        supported_privacy_tiers={PrivacyTier.P0, PrivacyTier.STANDARD},
        capabilities=set(capabilities or []),
        structural_compliance_score=structural_compliance_score,
        reliability_score=reliability_score,
        cost_per_input_1k=0.0,
        cost_per_output_1k=0.0,
    )


def _make_registry(model: ModelMetadata) -> ModelRegistry:
    registry = ModelRegistry()
    registry.register(model)
    return registry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestQualityScoreReliabilityContributesOnce:
    """Verify reliability contributes exactly once (H12 regression)."""

    def test_reliability_contributes_once_no_long_context(self):
        """Score = structural*0.35 + reliability*0.35 + 0.0 (no long context)."""
        model = _make_model(structural_compliance_score=0.8, reliability_score=0.9)
        registry = _make_registry(model)

        score = registry.quality_score_for(model, TaskType.REASON)

        expected = 0.8 * 0.35 + 0.9 * 0.35  # = 0.28 + 0.315 = 0.595
        assert abs(score - expected) < 1e-9, (
            f"Expected {expected}, got {score}. "
            "Reliability may be double-counted."
        )

    def test_reliability_does_NOT_appear_twice(self):
        """With reliability=1.0, old buggy formula would give > 1.0 for high structural."""
        # Bug: structural*0.35 + reliability*0.35 + reliability = 0.7 + 1.0 = 1.7 → clamped to 1.0
        # Fix: structural*0.35 + reliability*0.35 = 0.35 + 0.35 = 0.70 (within range)
        model = _make_model(structural_compliance_score=1.0, reliability_score=1.0)
        registry = _make_registry(model)

        score = registry.quality_score_for(model, TaskType.REASON)

        # Bug would produce 1.7 (clamped to 1.0), fix produces 0.70
        # The score must NOT equal 1.0 when there's no long-context bonus
        assert score < 1.0, (
            f"Score={score} suggests the old double-count bug is present. "
            "Expected < 1.0 with no long_context_bonus."
        )
        expected = 1.0 * 0.35 + 1.0 * 0.35  # = 0.70
        assert abs(score - expected) < 1e-9, (
            f"Expected {expected}, got {score}"
        )

    def test_long_context_bonus_still_applies(self):
        """Ensure the long_context_bonus of 0.5 is still added correctly."""
        model = _make_model(
            structural_compliance_score=0.5,
            reliability_score=0.5,
            capabilities=["long_context"],
        )
        registry = _make_registry(model)

        score = registry.quality_score_for(model, TaskType.REASON)

        # 0.5*0.35 + 0.5*0.35 + 0.5 = 0.175 + 0.175 + 0.5 = 0.85
        expected = min(1.0, 0.5 * 0.35 + 0.5 * 0.35 + 0.5)
        assert abs(score - expected) < 1e-9, (
            f"Expected {expected}, got {score}"
        )

    def test_preset_quality_score_bypasses_formula(self):
        """If a model has a preset quality_score for the task, it's used directly."""
        model = _make_model()
        model.quality_scores[TaskType.REASON] = 0.75
        registry = _make_registry(model)

        score = registry.quality_score_for(model, TaskType.REASON)
        assert score == 0.75

    def test_score_clamped_to_zero_minimum(self):
        """Score floor is 0.0 (but if both are 0.0, falls back to 0.5 sentinel)."""
        model = _make_model(structural_compliance_score=0.0, reliability_score=0.0)
        registry = _make_registry(model)

        score = registry.quality_score_for(model, TaskType.REASON)
        # 0*0.35 + 0*0.35 + 0 = 0.0 → sentinel 0.5
        assert score == 0.5, f"Expected sentinel 0.5 for zero inputs, got {score}"

    def test_score_clamp_does_not_exceed_one(self):
        """Score cannot exceed 1.0 even with long_context bonus."""
        model = _make_model(
            structural_compliance_score=1.0,
            reliability_score=1.0,
            capabilities=["long_context"],
        )
        registry = _make_registry(model)

        score = registry.quality_score_for(model, TaskType.REASON)
        # 0.35 + 0.35 + 0.5 = 1.2 → clamped to 1.0
        assert score == 1.0, f"Expected clamped to 1.0, got {score}"

    def test_score_changes_with_reliability(self):
        """Verify score is proportional to reliability (not 1.35x)."""
        model_low = _make_model(
            model_id="test_model_low",
            structural_compliance_score=0.5,
            reliability_score=0.2,
        )
        model_high = _make_model(
            model_id="test_model_high",
            structural_compliance_score=0.5,
            reliability_score=0.8,
        )
        registry_low = _make_registry(model_low)
        registry_high = _make_registry(model_high)

        score_low = registry_low.quality_score_for(model_low, TaskType.REASON)
        score_high = registry_high.quality_score_for(model_high, TaskType.REASON)

        # Fixed: difference is 0.35*(0.8-0.2) = 0.21
        # Buggy: difference would be 1.35*(0.8-0.2) = 0.81
        diff = score_high - score_low
        assert abs(diff - 0.35 * 0.6) < 1e-9, (
            f"Reliability delta mismatch: expected {0.35 * 0.6:.4f}, got {diff:.4f}. "
            "Reliability may still be double-counted."
        )
