# CODING TASK — FIX THE L5 FULL-SUITE HANG

Working directory: `C:\Users\adars\Projects\AGIES`

## Objective

Make `python -m pytest tests/` **terminate** and **pass**. It currently hangs (never completes).
This is a stabilization task, not a new feature. Do not add features.

## Disposition

- The bug is in **production code** (an executor), not a test-design issue.
- After you fix it, the full suite will expose **one more** pre-existing test bug (in L6) that was
  previously hidden because the suite never got that far. Fix that test too (see section 4).
- Do NOT commit. Do NOT begin any roadmap milestone. Do NOT fix unrelated lint issues.

---

## 1. Root cause

File: `src/aegis/l5_execution/executors/filesystem.py` — method `FilesystemExecutor._search()`:

```python
if recursive:
    matches = list(root.rglob(pattern))   # BUG: eager, unbounded full-tree walk
else:
    matches = list(root.glob(pattern))
matches = matches[:max_results]
```

`list(root.rglob(pattern))` builds the ENTIRE file tree before slicing to `max_results`.

A test (`tests/integration_l5/test_pipeline.py`) calls this with `root="~"` (the user's home
directory) and `pattern="*.txt"`, **~8 times** within a 50-iteration loop. Walking the whole home
directory takes many minutes → the suite never finishes.

Empirical proof (run on this machine):
- `list(Path.home().rglob('*.txt'))[:5]`  → takes > 120 seconds (effectively hangs).
- `list(itertools.islice(Path.home().rglob('*.txt'), 5))` → ~0.0 seconds.

---

## 2. Fix `_search`

Apply these semantics to `_search()`:

1. **Lazy walk** — iterate the glob generator and stop as soon as `max_results` matches are collected.
   Never materialise the full tree.
2. **Wall-clock budget** — add a `max_seconds` parameter (default `10.0`). Stop if the walk takes
   longer than `max_seconds`, so a tree with few/no matches can never hang the process.
3. Keep the existing return keys: `root`, `pattern`, `matches`, `count`.
4. Add a new key `truncated: bool` — `True` when it stopped due to the cap or the time budget.
5. Keep it a `@staticmethod`. Use only stdlib (`time`, `pathlib` are already imported).

Reference (match this behaviour; keep the file's style):

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

---

## 3. Make the E2E test deterministic

In `tests/integration_l5/test_pipeline.py`, the shared action table currently has:

```python
(ActionKind.FS_SEARCH, {"root": "~", "pattern": "*.txt", "max_results": 5}),
```

Change it so it does NOT scan the real home directory (slow + machine-dependent). Point it at a
non-existent scratch path so it returns quickly:

```python
(ActionKind.FS_SEARCH, {"root": "~/nonexistent_search_root_xyz", "pattern": "*.txt", "max_results": 5}),
```

### Add these two regression tests (same file, near the filesystem section)

Use the `pipeline` fixture and the `_grant_all(pipeline)` helper already in that file.

```python
@pytest.mark.asyncio
async def test_fs_search_respects_max_results(pipeline, tmp_path):
    await _grant_all(pipeline)
    for i in range(20):
        (tmp_path / f"file_{i}.txt").write_text("x")
    result = await pipeline.execute(make_action(
        ActionKind.FS_SEARCH,
        resource=f"fs:{tmp_path}",
        parameters={"root": str(tmp_path), "pattern": "*.txt", "max_results": 5},
    ))
    assert result.succeeded, result.error
    assert result.output["count"] == 5
    assert len(result.output["matches"]) == 5
    assert result.output["truncated"] is True


@pytest.mark.asyncio
async def test_fs_search_large_root_terminates(pipeline, tmp_path):
    await _grant_all(pipeline)
    empty = tmp_path / "empty_dir"
    empty.mkdir()
    result = await pipeline.execute(make_action(
        ActionKind.FS_SEARCH,
        resource=f"fs:{empty}",
        parameters={"root": str(empty), "pattern": "*.txt", "recursive": False, "max_results": 10},
    ))
    assert result.succeeded, result.error
    assert result.output["count"] == 0
    assert result.output["truncated"] is False
```

---

## 4. Fix the newly-exposed L6 test

Once the hang is fixed, `python -m pytest tests/` will reach L6 and reveal a pre-existing failure:

`tests/integration_l6/test_reasoning_provider.py::TestStrategyMapping::test_known_strategies_map_correctly`

```
AttributeError: type object 'PlanningStrategy' has no attribute 'SPEED_FIRST'
```

The test asserts enum members that don't exist. The real contract lives in:
- `src/aegis/l6_planning/types.py` (class `PlanningStrategy`)
- `src/aegis/l6_planning/orchestration/planner_service.py` → `_parse_strategy(...)`, which maps:

```python
"speed_first": PlanningStrategy.FASTEST,   # (there is no SPEED_FIRST)
"safe_mode":   PlanningStrategy.BALANCED,  # (there is no SAFE_MODE)
```

The enum and `_parse_strategy` are correct → **fix the test, not the code**. In the test's `cases`
list, change:

```python
("speed_first", PlanningStrategy.SPEED_FIRST),  →  ("speed_first", PlanningStrategy.FASTEST),
("safe_mode",   PlanningStrategy.SAFE_MODE),    →  ("safe_mode",   PlanningStrategy.BALANCED),
```

Do NOT touch L6 production code.

---

## 5. Verification (all must pass before you are done)

1. `python -m pytest tests/integration_l5/test_pipeline.py -q` → **all pass** (was hanging).
2. `python -m pytest tests/integration_l5 -q` → all pass (~103 tests), fast.
3. `python -m pytest tests/integration_l6/test_reasoning_provider.py -q` → all pass.
4. `python -m pytest tests/ -q` → **791 passed** (full suite completes, ~15s).
5. `python -m ruff check src/aegis/l5_execution/executors/filesystem.py tests/integration_l5/test_pipeline.py tests/integration_l6/test_reasoning_provider.py`
   → **no NEW lint errors introduced.** (A few pre-existing findings in these files are acceptable;
   do not fix unrelated pre-existing lint.)

## 6. Out of scope (do not do)

- Do not touch `PlanningStrategy`, `_parse_strategy`, or any other L6 production code.
- Do not fix unrelated pre-existing lint issues.
- Do not start any roadmap milestone.
- Do not commit / push unless the user explicitly asks.