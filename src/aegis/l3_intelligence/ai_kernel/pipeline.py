"""L3 AI Kernel PromptPipeline (Prompt 03 §17).

Composable stage pipeline for AI requests. Future subsystems can add stages
without rewriting the kernel. Standard stages (non-exhaustive example flow):
normalize, context_prep, prompt_construct, validate, route, inference,
output_validate, post_process.

Pipeline itself is generic — no provider/router coupling here. Callers store
optional context['request'] (AIRequest) or other keys; the pipeline only
ensures StageResult.data mutations are merged into the shared context dict.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Iterable, Protocol, runtime_checkable

from aegis.l3_intelligence.ai_kernel.types import PromptStageKind


__all__ = [
    "PromptPipeline",
    "PromptStageKind",
    "PipelineStage",
    "StageResult",
]


# ---------------------------------------------------------------------------
# 1. StageResult — dataclass carrying per-stage outcome, side-effect data,
#    diagnostics (errors/warnings), timing, and opaque metadata.
# ---------------------------------------------------------------------------


@dataclass
class StageResult:
    """Outcome of a single PipelineStage invocation.

    Attributes:
        stage_id: Matches the originating PipelineStage.stage_id.
        success: True if the stage completed its contract successfully.
        data: Dict of key→value mutations the pipeline will merge into ctx.
        errors: Human-readable error strings (empty when success=True).
        warnings: Non-fatal diagnostic strings.
        time_ms: Wall-clock duration of stage.run() in milliseconds.
        metadata: Opaque key/value store for stage-specific telemetry.
    """

    stage_id: str
    success: bool
    data: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 2. PipelineStage — runtime-checkable Protocol. Any object with a stage_id
#    attribute and an async run(ctx) -> StageResult method qualifies.
# ---------------------------------------------------------------------------


@runtime_checkable
class PipelineStage(Protocol):
    """Contract for a PromptPipeline stage.

    Stages receive the shared mutable `ctx` dict and return a StageResult.
    Context keys written via StageResult.data are merged after each attempt;
    stages may also mutate ctx directly but using StageResult.data is preferred
    for traceability (the merge is captured in results).
    """

    stage_id: str

    async def run(self, ctx: dict[str, Any]) -> StageResult:
        """Execute the stage. Return StageResult (never raise)."""
        ...


# ---------------------------------------------------------------------------
# 3. PromptPipeline — ordered, retryable, composable DAG (currently linear)
#    of PipelineStage instances. Callers use add_stage / remove_stage /
#    insert helpers or the from_stages() classmethod constructor.
# ---------------------------------------------------------------------------


class PromptPipeline:
    """§17 PromptPipeline — composable, ordered stage runner.

    Args:
        name: Human-readable pipeline label (used in metadata / tracing).
        stop_on_error: If True (default), halt after the first failing stage
            once its retries are exhausted. If False, continue through all
            stages regardless of individual outcomes.
        max_stage_retries: Per-stage retry ceiling (minimum 1, the initial
            attempt counts as attempt 0). Values < 1 are clamped to 1.
    """

    def __init__(
        self,
        *,
        name: str = "default",
        stop_on_error: bool = True,
        max_stage_retries: int = 1,
    ) -> None:
        self.name: str = name
        self.stop_on_error: bool = stop_on_error
        self.max_stage_retries: int = max(1, max_stage_retries)
        self._stages: dict[str, PipelineStage] = {}
        self._order: list[str] = []

    # ------------------------------------------------------------------
    # Mutation helpers — add / remove / reorder stages.
    # ------------------------------------------------------------------

    def add_stage(
        self,
        stage: PipelineStage,
        *,
        after_stage_id: str | None = None,
    ) -> None:
        """Append a stage, or insert it immediately after `after_stage_id`.

        Raises:
            ValueError: If stage.stage_id is already registered, or if
                `after_stage_id` is supplied but does not exist.
        """
        sid = stage.stage_id
        if sid in self._stages:
            raise ValueError(f"Duplicate stage_id: {sid!r}")
        if after_stage_id is None:
            self._stages[sid] = stage
            self._order.append(sid)
            return
        if after_stage_id not in self._stages:
            raise ValueError(
                f"after_stage_id {after_stage_id!r} not found; "
                f"existing stages: {self._order!r}"
            )
        idx = self._order.index(after_stage_id) + 1
        self._stages[sid] = stage
        self._order.insert(idx, sid)

    def remove_stage(self, stage_id: str) -> bool:
        """Remove a stage by id. Returns True if removed, False if absent."""
        if stage_id not in self._stages:
            return False
        del self._stages[stage_id]
        self._order.remove(stage_id)
        return True

    def insert_stage_at(self, index: int, stage: PipelineStage) -> None:
        """Insert `stage` at integer `index` in the ordered stage list.

        Negative indices follow list.insert() semantics. Raises ValueError on
        duplicate stage_id.
        """
        sid = stage.stage_id
        if sid in self._stages:
            raise ValueError(f"Duplicate stage_id: {sid!r}")
        self._stages[sid] = stage
        self._order.insert(index, sid)

    # ------------------------------------------------------------------
    # Read helpers.
    # ------------------------------------------------------------------

    def list_stage_ids(self) -> list[str]:
        """Return a new list of stage ids in execution order."""
        return list(self._order)

    def get_stage(self, stage_id: str) -> PipelineStage | None:
        """Lookup a stage by id. Returns None if absent."""
        return self._stages.get(stage_id)

    # ------------------------------------------------------------------
    # Execution.
    # ------------------------------------------------------------------

    async def run(
        self,
        ctx: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[StageResult]]:
        """Run every stage in order, honoring retries and stop_on_error.

        Args:
            ctx: Shared pipeline context. If None, an empty dict is used.
                Stages may read/write ctx directly; in addition, any non-empty
                StageResult.data dict is merged via ctx.update(...) after the
                stage's attempt completes.

        Returns:
            (ctx, results) — the final context dict and a list of StageResult
            entries, one per stage **attempt** (so a retried stage produces
            more than one entry, in chronological order).
        """
        if ctx is None:
            ctx = {}
        results: list[StageResult] = []

        for sid in self._order:
            stage = self._stages[sid]
            for attempt in range(self.max_stage_retries):
                start = perf_counter()
                try:
                    sr = await stage.run(ctx)
                except Exception as e:  # noqa: BLE001
                    sr = StageResult(
                        stage_id=sid,
                        success=False,
                        data={},
                        errors=[f"stage_exception:{type(e).__name__}: {e}"],
                    )
                sr.time_ms = (perf_counter() - start) * 1000
                results.append(sr)
                if sr.data:
                    ctx.update(sr.data)
                if sr.success or not self.stop_on_error:
                    break
                if attempt < self.max_stage_retries - 1:
                    continue
                if self.stop_on_error and not sr.success:
                    return ctx, results
        return ctx, results

    def run_sync(
        self,
        ctx: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[StageResult]]:
        """Synchronous wrapper around :meth:`run`.

        Uses ``asyncio.run`` when no event loop is running. If a loop is
        already active (e.g. inside a notebook or async server handler), this
        raises a RuntimeError to avoid silently nesting event loops.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            raise RuntimeError(
                "PromptPipeline.run_sync called inside a running event loop; "
                "await PromptPipeline.run() instead."
            )
        return asyncio.run(self.run(ctx))

    # ------------------------------------------------------------------
    # Convenience constructors.
    # ------------------------------------------------------------------

    @classmethod
    def from_stages(
        cls,
        stages: Iterable[PipelineStage],
        **kw: Any,
    ) -> PromptPipeline:
        """Build a PromptPipeline from an iterable of stages (order preserved).

        Extra keyword arguments are forwarded to :class:`PromptPipeline`
        constructor (``name``, ``stop_on_error``, ``max_stage_retries``).

        Raises:
            ValueError: If any duplicate ``stage_id`` is encountered.
        """
        pipe = cls(**kw)
        for stage in stages:
            pipe.add_stage(stage)
        return pipe
