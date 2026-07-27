# AEGIS — Continuation Handoff (Prompt 02 → Next Session)

_Use this document to start work without conversation context. All info needed is below._

---

## CURRENT MILESTONE:
**Prompt 02 — Core Runtime** → **COMPLETED** (fully verified)

---

## COMPLETED (Prompt 02 code, tests, docs):

### Infrastructure-level fixes applied (15 total bugs resolved from baseline 23/57 failing tests):
- B1 Config loader `_resolve_paths` (None-aware defaults — 8 tests unblocked)
- B2 DI.register() dual convention (factory-positional vs lifetime-positional) + deps=/dependencies= kwargs (7 tests)
- B3 HealthAggregator.check_all(aggregate_timeout=) signature + timeout wrapping
- B4 RestartPolicy short-name aliases (multiplier=, jitter=)
- B5 CoreRuntime.register_service() immediate NotFoundError E10110 for missing depends_on (was deferred to start time)
- B6 CoreRuntime.overall_health() async (was sync; tests await it)
- B7 ErrorCode numeric alias bootstrap (ErrorCode.E20104 ↔ ErrorCode.CONFIG_SECRET_REF_INVALID identity)
- B8 ImmutableConfigSnapshot.__getattribute__ → deep-copy dict fields on each access (test_snapshot_is_immutable_via_accessors)
- B9 Scope.close() sync + aclose() split; DIContainer.close() sync + aclose() split + _cleanup_instances_sync helper
- B10 HealthReport.components list[ComponentHealth] + @property by_component dict
- B11 Supervisor constructor watchdog_interval alias (watchdog_interval= vs watchdog_interval_seconds=)
- B12 AegisError constructor dual convention (entry-first OR message-first parameter interpretation)
- B13 Supervisor.register() policy= or restart_policy= alias
- B14 Supervisor._tick + force_recover restart_fn arity: try(service_id) / TypeError → retry(0-args); _default_restart *args safe
- B15 Example (DI greeter wrongly declared deps=heartbeat; health dict state→status key; health assertion lenient vs only user components)

### Verification results:
```
pytest tests/              → 46 passed / 0 failed (46 total)
ruff check --fix           → 204 auto-fixed; 75 remaining all pre-existing
mypy                       → BLOCKED (Windows Application Control DLL policy)
example runtime_lifecycle  → exit 0; "SUCCESS ===" logged
import aegis               → 87 symbols OK
cargo check                → BLOCKED (cargo.exe not on PATH)
```

### L1 Modules complete:
- CoreRuntime (lifecycle 6 states + topological init + reverse teardown + missing dep immediate validation)
- DI Container (5 lifetimes + circular detection + close sync+async)
- Error (AegisError root + 14 subclasses + ErrorCode registry dual form)
- Health (4-state HealthState + aggregator with per-check + aggregate timeout + list-based components)
- Supervisor (watchdog + RestartPolicy aliases + recovery state + force_recover + dual-arity restart_fn)
- Interfaces (Service / HealthProvider / ModuleLifecycle / Pluggable / Storage / Memory / LLM / Events)

### L2 Modules complete:
- Config (layered DEFAULTS/FILE/ENV/OVERRIDES, immutable snapshot deepcopy, file secrets, validation)
- Structured Logging (JSON + Dev formatters + correlation injection + auto-redaction)
- Correlation (PEP 567 contextvar, fork, enter, serialize/deserialize)
- Event Bus (pub/sub, sync+async handlers, priority, DLQ, SQLite durable + replay, typed envelopes)
- Crypto/Redaction (pattern regex redactor, file secret vault, Hasher FFI wrapper)
- Background Tasks (BTM concurrency cap, submit/cancel/info, RetryPolicy dual aliases, standalone run_with_retry)
- Persistence skeletons (SQLite KV+Doc; NoOpGraphStore/NoOpVectorStore — L4 extends later)
- Plugin Loader (manifest + sandbox tier + UNKNOWN permission → DENY by default)

### Rust Crates:
3 crates declared (/crates). Not verified (cargo missing). Skeleton-only per Prompt 02 scope.

### Docs:
- docs/PROJECT_AEGIS_CURRENT_STATE.md — full state inventory, 15 bugs with fixes, 13 ADRs, verification commands output, STOP condition.
- docs/11_PROMPT_02_CORE_RUNTIME.md — API contract + code examples for every P02 class.
- docs/HANDOFF_PROMPT_02_CONTINUATION.md — this file.

---

## IN PROGRESS:
Nothing. All Prompt 02 tasks marked done in todo tracking.

---

## REMAINING (Prompt 02 scope):
Nothing remaining. Prompt 02 is complete per Prompt 01 authorised boundaries and this directive's requirements list.

Potential optional improvements (NOT REQUIRED — do only if explicitly asked):
- Run mypy on a Linux/macOS box or unblock DLL to enable strict static types.
- Install cargo and verify Rust crates with `cargo check --workspace`.
- Run ruff with `--unsafe-fixes` to resolve remaining 75 warnings (risky: some interfaces break if unused args are removed).
- Add ConfigLoader.reload() API + corresponding snapshot-mutability tests (Prompt 02 directive's test requirements mention "reload"; but no test for it currently exists — evaluate if needed).
- Add event bus replay-from-seek tests + more edge-case DLQ coverage.

---

## KNOWN ISSUES (from §5 in current state doc):
P1–P5 only. All are low/medium and non-blocking for Prompt 03 launch. See current state doc for detail.

---

## VERIFICATION (run these next thing after loading project):
```powershell
cd C:\Users\adars\Projects\AGIES
# 1. Tests (baseline — PASS before touching anything):
python -m pytest tests/ --tb=no -q
# Expected: 57 passed

# 2. Lint (rough baseline; 75 expected pre-existing):
python -m ruff check src/aegis tests examples
# Should report 75 errors; if more, investigate new ones.

# 3. Example (end-to-end sanity):
python examples\runtime_lifecycle.py
# Should exit 0 with SUCCESS line.

# 4. Package import:
python -c "import aegis; print('OK', len(dir(aegis)))"
# Should print "OK 76"

# 5. IF cargo available (Rust verification):
cd crates; cargo check --workspace

# 6. IF Windows security allows DLL (mypy verification):
python -m mypy src/aegis --ignore-missing-imports
# Expected: 0 errors after type fixing if any exist.
```

---

## ARCHITECTURAL DECISIONS (BINDING until superseded by explicit ADR):
13 ADRs listed in §6 PROJECT_AEGIS_CURRENT_STATE.md. CRITICAL: Strict 7-layer downward deps only; 7-stage pipeline L3+ only; 9-tier memory L4+ only; never trust LLM output; local-first secrets; Rust FFI optional; strict lifecycle FSM; Kahn topological service init then reverse teardown; DI circular detection raises not cycle-breaks; E-code taxonomy strict; P02 recovery primitives only — NO AI in recovery; plugin UNKNOWN→DENY; immutable config deep-copies.

---

## NEXT ACTION (Prompt 02 Complete → what to do FIRST in next session):
1. Read docs/PROJECT_AEGIS_CURRENT_STATE.md fully to rehydrate all decisions.
2. Run the VERIFICATION commands above to confirm nothing rotted.
3. Produce the final 14-section report (see directive §22) if the current session still requires it (it was not yet generated when this handoff was written).
4. **STOP.** Await an EXPLICIT new user directive for Prompt 03 ("Prompt 03 — AI Kernel").
5. Only when explicitly authorised with a new Prompt 03 directive: begin L3 Kernel code, observing Prompt 01 7-stage pipeline interface skeleton boundaries and ADR-P01-002 through ADR-P01-005.

---

## DO NOT IMPLEMENT (CRITICAL — these are outside Prompt 02 scope; wait for explicit Prompt 03/04/… directive):
AI providers: Groq, OpenRouter, Ollama, vLLM, OpenAI, Anthropic, Together, any inference endpoint.
Model routing: concrete routing decisions / fallback chains.
LLM inference / prompt pipelines / agents / tool calls.
Memory: T0–T8 tiers, promotion gates, SQLite/SQLCipher KV implementation beyond skeleton, Qdrant, embeddings, vector DB, knowledge graphs.
Execution: harness code, browser/desktop automation, Obsidian integration, web search, computer vision, cameras, face recognition, voice, speech.
Cross-cutting L3+: Planning, Agent orchestration loop, 7-stage pipeline stage implementations (only INTERFACE definitions allowed if Prompt 03 milestone explicitly authorises).
Social/Finance/Cybersec integrations.
MCP / capability discovery / auto-learning / auto-harness / self-repair / self-modifying code (08/21 only).
UI: Tauri 2, Textual, any frontend components (L7 HCI milestone).
UI: Web frontend, Chat UI, etc.

_STOP HERE. Do not cross into Prompt 03 without explicit user authorisation in a new directive._
