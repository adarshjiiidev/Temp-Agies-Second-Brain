# PROMPT — FIX L5 FULL-SUITE HANG (STABILIZATION)

**Document ID:** AEGIS-PROMPT-STAB-01
**Author:** System Architect / Principal Engineer
**Date:** 2026-08-07
**Status:** READY FOR IMPLEMENTATION
**Goal:** Make `pytest tests/` terminate and pass. This is a stabilization task, not a new milestone.

---

## 1. BACKGROUND (verified, 2026-08-07)

The full test suite `python -m pytest tests/` never completed (observed: still running after 45s).
A live fault-hunt isolated the cause; it is **not** a test design flaw but a real executor bug.

Layer status as implemented: L1–L6 exist (docs previously claimed L1+L2 only). Audit report:
`docs/AEGIS_MASTER_AUDIT.md`. Baseline numbers before this prompt:

- 791 tests collected
- L1/L2 = 57, L3 = 256, L4 = 130 (pass individually)
- L5 = hangs; L6 = 180 collected, blocked by L5 in a full run

---

## 2. ROOT CAUSE

`src/aegis/l5_execution/executors/filesystem.py` — `FilesystemExecutor._search()`:

```python
if recursive:
    matches = list(root.rglob(pattern))   # ← eager, unbounded full-tree walk
else:
    matches = list(root.glob(pattern))
matches = matches[:max_results]
```

`tests/integration_l5/test_pipeline.py` cycles this in the E2E test:

```python
(ActionKind.FS_SEARCH, {"root": "~", "pattern": "*.txt", "max_results": 5}),
```

The test triggers `_search(root="~")` **~8 times** (once per 6 actions × 50 iterations). On a large
home directory, `list(root.rglob("*.txt"))` materialises the **entire tree** before slicing to 5.

**Empirical proof:**

| Command | Result |
|---|---|
| `list(Path.home().rglob('*.txt'))[:5]` | **>120 s (never returned in test window)** |
| `list(itertools.islice(Path.home().rglob('*.txt'), 5))` | **0.0 s** |

---

## 3. AUTHORIZED IMPLEMENTATION (exact)

### 3.1 Fix `_search` in `src/aegis/l5_execution/executors/filesystem.py`

Requirements:

1. **Lazy walk** — never materialise the full tree. Stop as soon as `max_results` matches are found.
2. **Wall-clock budget** — guarantee termination even when a tree yields few/no matches (add
   `max_seconds` param, default `10.0`), so pathological/networked roots can't hang the process.
3. **Return shape compatible** with existing callers: keys `root`, `pattern`, `matches`, `count`.
4. Add a `truncated: bool` field (`True` when the cap or time budget ended the walk early).
5. Keep it `@staticmethod`, stdlib only (`time`, `pathlib` already imported).

Reference implementation (apply the same semantics; keep the codebase's style):

```python
@staticmethod
def _search(p: dict) -> dict:
    root = Path(p.get("root", ".")).expanduser().resolve()
    pattern = p.get("pattern", "*")
    recursive = p.get("recursive", True)
    max_results = p.get("max_results", 200)
    max_seconds = float(p.get("max_seconds", 10.0))

    if not root.exists():
        raise ExecutorError(f"Search root not found: {root}")

    # Lazy walk: stop as soon as max_results matches are found, or the
    # wall-clock budget expires. Materialising the full result set is
    # unbounded and can take minutes on large/networked roots.
    iterable = root.rglob(pattern) if recursive else root.glob(pattern)
    deadline = time.monotonic() + max_seconds

    matches: list[str] = []
    for match in iterable:
        if time.monotonic() > deadline:
            break
        matches.append(str(match))
        if len(matches) >= max_results:
            break

    return {
        "root": str(root),
        "pattern": pattern,
        "matches": matches,
        "count": len(matches),
        "truncated": len(matches) >= max_results or time.monotonic() > deadline,
    }
```

### 3.2 Make the E2E search deterministic in `tests/integration_l5/test_pipeline.py`

Change the shared action table so FS_SEARCH does **not** scan the real home directory (slow, machine
dependent). Use a non-existent scratch path so the executor fast-fails/returns quickly:

```python
(ActionKind.FS_SEARCH, {"root": "~/nonexistent_search_root_xyz", "pattern": "*.txt", "max_results": 5}),
```

### 3.3 Add regression tests (same file, near the filesystem section)

Add two async tests using the `pipeline` fixture + `_grant_all(pipeline)`:

1. `test_fs_search_respects_max_results(pipeline, tmp_path)` — create 20 `*.txt` in `tmp_path`, run
   FS_SEARCH with `max_results=5`; assert `count == 5`, `len(matches) == 5`, `truncated is True`.
2. `test_fs_search_large_root_terminates(pipeline, tmp_path)` — search an empty dir non-recursively;
   assert it returns (`count == 0`, `truncated is False`). This pins the termination guarantee.

### 3.4 Fix the newly-exposed L6 test (caused by 3.1/3.2 unblocking the suite)

With the hang fixed, the full run exposes one pre-existing failure:

`tests/integration_l6/test_reasoning_provider.py::TestStrategyMapping::test_known_strategies_map_correctly`

```
AttributeError: type object 'PlanningStrategy' has no attribute 'SPEED_FIRST'
```

Root cause: the test asserts enum members that **do not exist**. The real contract is in
`src/aegis/l6_planning/types.py` (PlanningStrategy) and the alias map in
`src/aegis/l6_planning/orchestration/planner_service.py::_parse_strategy`:

```python
"speed_first": PlanningStrategy.FASTEST,   # not SPEED_FIRST
"safe_mode":   PlanningStrategy.BALANCED,  # not SAFE_MODE
```

**The enum and `_parse_strategy` are correct and are the source of truth. Fix the test, not the
code.** Replace those two expected values:

```python
("speed_first", PlanningStrategy.FASTEST),
("safe_mode", PlanningStrategy.BALANCED),
```

---

## 4. VERIFICATION (must all pass)

1. `python -m pytest tests/integration_l5/test_pipeline.py -q` → **13 passed** (previously hung).
2. `python -m pytest tests/integration_l5 -q` → all pass (~103 tests), fast (<10s).
3. `python -m pytest tests/integration_l6/test_reasoning_provider.py -q` → all pass.
4. `python -m pytest tests/ -q` → **791 passed** (full suite completes in ~15s).
5. `python -m ruff check src/aegis/l5_execution/executors/filesystem.py tests/integration_l5/test_pipeline.py tests/integration_l6/test_reasoning_provider.py` → **no NEW lint issues** introduced (pre-existing F401/ARG/SIM findings in these files are acceptable and listed in the audit; do not fix unrelated pre-existing lint).

---

## 5. EXIT GATE / DO NOT

- Do **not** touch the enum, `_parse_strategy`, or any L6 production code.
- Do **not** fix unrelated pre-existing lint issues.
- Do **not** begin any roadmap milestone (this is stabilization only).
- Do **not** commit unless explicitly authorised.
- After verification, update the verification record in `docs/PROJECT_AEGIS_CURRENT_STATE.md` and
  the session log in `.agents/AGENTS.md` (the suite now completes: 791 passed).

---

## 6. RELATED FINDINGS (not part of this prompt — backlog only)

- `reasoning/` packages exist but are unwired/untested (`KernelReasoningProvider` calls
  `AIKernel.has_models()`/`infer_text()` which don't exist).
- Rust crates unverified (no Cargo on host) and fail to compile once a toolchain is available.
- `vault.py:94` zero-key fallback; `registry.py` quality score double-count; stale import-linter
  contracts in `pyproject.toml`; 642 pre-existing ruff issues. See `docs/AEGIS_MASTER_AUDIT.md`.
