# PROJECT AEGIS — CAPABILITY DISCOVERY, MCP ECOSYSTEM, AUTO-HARNESS, SELF-LEARNING, AND SELF-REPAIR STRATEGY

**Document ID:** AEGIS-DOC-009
**Version:** 0.1.0 (Prompt 01 Foundation)
**Status:** DRAFT — Architecture Phase Only
**Last Updated:** 2026-07-24

---

## 1. THE CORE PROMISE OF CAPABILITY NEUTRALITY

This document is the operationalization of Vision §3 — *AEGIS is NOT a hard-coded integration collection*.

Instead of:

```
if user asks Obsidian → call Obsidian API
if user asks GitHub   → call GitHub API
if user asks Browser  → call Browser API
```

AEGIS implements a generic capability discovery pipeline that asks:

```
What capability is required?
   → Do I have it already? (registry lookup)
   → Can I build it from tools I do have? (tool composition)
   → Can I find an MCP server that provides it? (MCP discovery)
   → Can I wrap a CLI/API that already exists? (code generator)
   → Can I study the software's docs/UI and learn how to use it? (software familiarization loop)
   → Can I observe the user's workflow and extract a procedural recipe? (workflow learning)
   → If I build it, can I safely test it in a sandbox before using it for real? (auto-harness)
   → If it breaks later, can I diagnose and fix it? (self-repair)
```

This is the *differentiator* between AEGIS and every "LLM + function-calling wrapper" product in existence.

---

## 2. CAPABILITY REGISTRY — THE UNIFIED CATALOG

Every "way to do something" in AEGIS is a Capability in the registry. The registry is one source of truth; the planner never looks anywhere else.

### 2.1 Capability Model

```python
class Capability:
    id: str                                    # e.g. "notes.vault.create_note.v2"
    name: str                                  # human-readable
    description: str                           # semantic description (for vector lookup)
    category: CapabilityCategory               # computer_use / browser_use / knowledge / coding / ...
    verbs: set[str]                            # {"notes.create", "files.write"}
    input_schema: JSONSchema                   # typed input contract
    output_schema: JSONSchema                  # typed output contract
    required_permissions: list[PermissionRule] # SVRCs needed to invoke
    implementation: ImplementationRef          # where the code lives:
                                               #   {type: builtin_tool,  ref}
                                               #   {type: mcp_tool,       server_id, tool_name}
                                               #   {type: generated_tool, version, skill_id}
                                               #   {type: composite,       steps: [capability_ids]}
    confidence: float                          # 0.0..1.0 — current aggregate
    success_rate_n: int                        # number of real invocations scored
    success_rate_pct: float                    # 0..100 on those
    last_tested: DateTime | None               # last auto-harness run
    limitations: list[str]                     # known failure modes
    dependencies: list[str]                    # required packages / binaries / MCPs
    version: Version                           # semver
    is_deprecated: bool
    deprecation_reason: str | None
    provenance: ProvenanceChain                # §06 provenance chain
```

### 2.2 Registry Lookup Flow

```
Planner needs: "create a note in the user's vault with markdown content"
                │
                ▼
1. SEMANTIC SEARCH: Qdrant vector search on description → top 20 candidates
2. FILTER BY VERBS: candidates where verbs intersect "notes.create, files.write"
3. FILTER BY INPUT SCHEMA COMPATIBILITY: can we map the planner's intent args to input_schema?
4. FILTER BY REQUIRED PERMISSIONS: do we currently hold or can obtain the SVRCs?
5. FILTER BY HEALTH: success_rate_pct >= MIN_RELIABLE (default 60%) AND
                      (last_tested < 30 days OR confidence >= 0.85)
6. RANK: Score = confidence * 0.3 + success_rate_pct/100 * 0.4
               + freshness(last_tested) * 0.1
               + implementation_type_priority(builtin > composite > generated > mcp_3rd_party) * 0.2
7. PICK TOP 1 → return to planner. If none, enter CAPABILITY DISCOVERY PIPELINE.
```

---

## 3. CAPABILITY DISCOVERY PIPELINE — WHEN IT DOESN'T EXIST YET

This is the *heartbeat loop* of AEGIS's "learn unfamiliar software" promise.

```
ENTRY: Planner found NO suitable capability in registry (section 2.2 step 7 empty)
   │
   ▼
STAGE 1 — TOOL RUNTIME SCAN
   Query built-in tool runtime. Any tool whose semantic description ~matches?
   → YES: Wrap tool invocation as a Capability. Write to registry as DRAFT.
          Skip ahead to STAGE 6 (Auto-Harness).
   → NO: Continue.
   │
   ▼
STAGE 2 — MCP ECOSYSTEM SCAN
   2a. Query locally-registered MCP servers (section 4) by tool schema.
   2b. Query public MCP server registry (user-approved sources only).
   2c. Offer to install candidate MCP server (with user approval gate + sandbox).
   → ANY MATCH: Wrap as Capability {type: mcp_tool}. Skip to STAGE 6.
   → NO: Continue.
   │
   ▼
STAGE 3 — CLI / LOCAL API SCAN
   3a. Environment model: what executables are on PATH / installed apps?
   3b. Read --help / man page / swagger / openapi.yaml for candidate CLIs/APIs.
   3c. Map "required verbs" to CLI subcommands / API endpoints.
   → MAPPING POSSIBLE: Generate typed wrapper. Skip to STAGE 6.
   → NO: Continue.
   │
   ▼
STAGE 4 — SOFTWARE FAMILIARIZATION LOOP
   This is the "human-like" learning path. It is the slowest but most general.
   4a. IDENTIFY SOFTWARE: From environment model, which installed app / website
       / local system COULD provide the capability?
   4b. FIND DOCUMENTATION:
       - Check local help, /usr/share/doc, app built-in docs
       - Search web (with P2 data only — no P0/P1 in search)
       - Fetch README, docs site, API reference, CLI --help
   4c. STUDY UI / CLI / API:
       - For desktop apps: screen capture + OCR + accessibility tree (with permission)
       - For websites: browser read DOM + network requests
       - For CLIs: run --help, run minimal read-only invocations in sandbox
   4d. BUILD CAPABILITY MODEL:
       - Extract verbs, inputs, outputs, error patterns
       - Write T4 Procedural candidate memory (DRAFT)
       - Write KG entities: Software, API, CLI, Workflow
   4e. EXPERIMENT SAFELY:
       - Generate sandboxed read-only invocations
       - Validate outputs against model
       - Iterate
   → MODEL CONVERGED (error rate < threshold in sandbox): Proceed to STAGE 5.
   → FAILURE AFTER N ITERATIONS: Escalate to user —
        "I couldn't figure out how to <goal>. Here's what I tried.
         Want to (a) show me, (b) point me at docs, (c) drop the goal,
         or (d) install a known MCP that does this?"
   │
   ▼
STAGE 5 — TOOL / MCP GENERATOR
   Input: capability model from STAGE 4d, sample invocations from STAGE 4e.
   5a. Generate typed Python tool wrapper (or) MCP server definition, depending on
       complexity and required isolation.
   5b. Type-check generated code (mypy --strict + ruff + ast-parsing checks).
   5c. If failed → repair loop.
   → Code compiles and passes type checks: proceed.
   │
   ▼
STAGE 6 — AUTO-HARNESS (section 6)
   Run the new capability through the full automated evaluation harness.
   → SCORE >= THRESHOLD AND REQUIRED PERMISSIONS RESOLVED:
        Register capability into registry with real confidence.
        Write as T8 Skill with auto-harness record.
        Return to Planner → retry original goal.
   → SCORE TOO LOW:
        Repair loop (section 7): root-cause → fix → re-harness.
        If repair loop fails 3 times → register as DRAFT +
        "Requires user familiarization" flag. Escalate to user only when
        Planner tries to use it.
   │
   ▼
STAGE 7 — REFLECT + REMEMBER
   Write the entire discovery path to episodic memory:
   - What was missing?
   - Which stages succeeded/failed?
   - What docs did I read?
   - What did I learn about this software?
   Write to KG: required_goal --> discovered --> capability.
```

---

## 4. MCP ECOSYSTEM STRATEGY

MCP (Model Context Protocol) is AEGIS's **standard pluggable surface** for external capabilities. We do **not** re-invent the MCP protocol; we implement a strict client + optional bundled MCP servers.

### 4.1 MCP Runtime Module

```python
class MCPRuntime:
    """Standard MCP client with schema validation, lifecycle, sandbox, pooling."""

    def register_server(self, manifest: MCPServerManifest) -> None: ...
    def list_tools(self, server_id: str) -> list[MCPToolSpec]: ...
    def call_tool(self, server_id: str, tool_name: str, args: dict) -> MCPCallResult: ...
    def list_resources(self, server_id: str) -> list[MCPResourceSpec]: ...
    def read_resource(self, server_id: str, uri: str) -> MCPResourceContent: ...
    def list_prompts(self, server_id: str) -> list[MCPPromptSpec]: ...
```

### 4.2 MCPServerManifest — Deny-by-Default Loading

```yaml
manifest_version: 1
server_id: com.example.obsidian
display_name: Obsidian MCP Server
install_source:
  type: local_path | github_release_url | docker_image | npm_package
  ref: "v1.2.3"
  integrity_hash: sha256:...   # pinned — never load if hash mismatch
transport: stdio | sse | websocket
required_permissions:        # what SVRCs does THIS MCP server itself require?
  - resource: fs:~/Obsidian/**
    verbs: [fs.read, fs.write]
    rationale: "Manages markdown notes in the vault."
exposed_tools_allowlist:     # Optional: only import these tool names
  - obsidian_list_notes
  - obsidian_create_note
default_sandbox_tier: T2     # T2 subproc jail; upgrade to T3 if server requires network
risk_tier: medium            # medium = approval on first use; high = per-call approval
```

### 4.3 MCP Lifecycle & Security

```
REGISTER (require user approval + integrity pin)
   │
   ▼
LOAD  (apply sandbox tier, apply required permission filter via Permission Engine)
   │
   ▼
DISCOVER TOOLS/RESOURCES/PROMPTS (schema-validate every tool spec)
   │
   ▼
REGISTER EACH EXPOSED TOOL → Capability Registry (section 2)
   with implementation = {type: mcp_tool, server_id, tool_name}
   │
   ▼
ON TOOL CALL:
   1. Permission engine checks caller SVRC
   2. Apply required_permissions manifest entries to the call
   3. Wrap call in assigned sandbox tier
   4. Timeout + retry
   5. Audit write: all MCP calls traced with server_id, tool, args_hash, result_hash
   6. Update Capability success_rate on return
   │
   ▼
UNLOAD / HOT-RELOAD: kill subprocess; flush active call state; deregister capabilities
```

### 4.4 Generated MCPs (Capability Discovery Stage 5)

When the tool generator decides a capability is complex enough to warrant its own process boundary, it generates a **bundled MCP server** rather than an in-process tool:

- Generated source code (TypeScript or Python) for an MCP stdio server
- Packaged with pinned deps, pinned version, integrity hash
- Registered with the MCP Runtime using a generated manifest with T2/T3 sandbox
- Harness runs against the generated MCP server, not against the raw code
- This way, generated capabilities live behind the **same isolation guarantees** as third-party MCPs

---

## 5. COMPOSITE CAPABILITIES — GLUING WHAT YOU HAVE

Before writing new code, the system tries to compose existing capabilities into a workflow.

```python
class CompositeCapability:
    id: str
    steps: list[CompositeStep]
    # Each step: call capability X with input mappings, wait for result,
    #            pass outputs to next step inputs.
    input_mapping: dict[str, str]     # composite-input → step1.input
    step_data_flow: dict[tuple[int,str], tuple[int,str]]
    # step N, output key → step M, input key
    rollback_on_failure: bool
```

Composite capabilities:
- Go through auto-harness **as a whole**, not per-step
- Get their own confidence + success-rate tracking
- Are stored in the T4 Procedural memory as reusable workflows
- Can be auto-generated by the planner from "I have these steps, can I chain them?" or learned from observing the user repeat a multi-step workflow

---

## 6. AUTO-HARNESS — AUTOMATED EVALUATION BEFORE USE

Every newly generated / discovered capability must pass the auto-harness before it can be invoked for a real user task. This is a **security-quality gate**, not optional.

### 6.1 Harness Stages

```
CAPABILITY ENTERS HARNESS:
   │
   ▼
1. TEST CASE GENERATION
   Inputs:
     · capability.input_schema, capability.output_schema
     · semantic description
     · known success examples (from familiarization experiments)
   LLM-assisted generator with validation loop produces N test cases (default 8):
     class TestCase:
         id: str
         inputs: dict           # must validate input_schema
         oracle_kind: exact | fuzzy | asserts | sandbox_safe_output_only
         expected_output: Any | None
         assertions: list[str]  # e.g. "result.markdown contains non-empty string"
         required_passes: int   # fuzzy assertions
   Generator validates each input against JSONSchema; 100% valid before proceeding.
   │
   ▼
2. SANDBOXED EXECUTION
   Assign sandbox tier per capability.
   For each test case:
     · If oracle_kind requires network → network permit for that tier
     · Invoke capability through Execution Kernel (full pipeline: permission →
       policy → sandbox → audit)
     · Record: exit code, wall time, CPU time, stdout/err (redacted), outputs
   All invocations run in parallel up to concurrency_limit.
   Timeout per case: default 60s.
   │
   ▼
3. EXPECTED vs ACTUAL COMPARISON + SCORING
   Per test case:
     · exact: output == expected → pass/fail
     · fuzzy: LLM-as-judge (with different model from generator) rates 1–5;
              ≥ 4 is a pass
     · asserts: evaluate assertion expressions safely in T1 evaluator; all pass → pass
     · sandbox_safe_output_only: "did it produce a parseable output_schema object
                                  without exceptions or dangerous behavior"
   Aggregate:
     pass_rate = passed / total
     avg_latency = mean(case_latency)
     resource_ok = all within tier's CPU/mem/IO limits
     no_escape = security_attempt_tests all blocked
   │
   ▼
4. SCORING + DECISION
   Overall score: S = Wp*pass_rate
                   - Wl*(latency / MAX_ACCEPTABLE)
                   - We*(escape_or_security_violation ? 1 : 0)
                   - Wr*(resource_overages ? penalty : 0)
   Default weights: Wp=0.70, Wl=0.10, We=0.15, Wr=0.05

   DECISION RULES:
     if S >= 0.80  AND  pass_rate >= 0.75  AND  escape == 0:
         → REGISTER as ACTIVE capability
         → confidence = S
         → Write T8 Skill + full harness report
         → Ready for Planner to use
     elif S >= 0.50 AND pass_rate >= 0.50:
         → ENTER REPAIR LOOP (section 7), up to R retries
     else:
         → REGISTER as DRAFT capability with failure report
         → Planner will NOT use it automatically
         → Only user-flagged invocation permitted, with approval gate
   │
   ▼
5. REGISTER + WRITE OUTCOMES
   - Store every test case + full result in the harness history
   - Update capability metadata: confidence, last_tested, success_rate_n/pct, limitations
   - Write episodic memory: harness result
   - Write KG: capability --harness_result--> {score, date, version}
   - If registered active: emit event capability.registered
```

### 6.2 Periodic Re-Harness (Skills Decay Prevention)

```
Trigger: capability.last_tested > 30 days OR
         capability.success_rate_pct drops >15% in real use OR
         dependency version changed (package upgrade, MCP server update)

Action: Schedule auto-harness in background.
   → S still ≥ threshold: update last_tested. Done.
   → S dropped below threshold: mark capability as DEGRADED.
        Planner will prefer alternatives until re-harness passes or repair succeeds.
```

---

## 7. SELF-REPAIR — DIAGNOSE, GENERATE FIX, SANDBOX-TEST, DEPLOY VERSIONED

AEGIS's self-repair is **never silent**. It is auditable, versioned, and sandbox-tested before deploy.

```
TRIGGER:
  · Auto-harness failure after retries
  · Real capability call failure + consecutive_failures >= 2
  · User reports: "this is broken"
   │
   ▼
1. ROOT CAUSE ANALYSIS
   Collect:
     - Full audit trace of failing call(s)
     - Harness history of the capability
     - Recent dependency changes
     - Error taxonomy classification
   LLM-assisted analysis produces typed FailureAnalysis:
     class FailureAnalysis:
         failed_capability_id: str
         category: enum { code_bug, dependency_broke, permission_missing,
                          schema_mismatch, upstream_down, undocumented_input,
                          environment_changed, user_workflow_changed }
         hypothesized_root_cause: str
         evidence: list[Evidence]   # each points to an audit record / line
         confidence: float
   │
   ▼
2. RESEARCH (if applicable)
   - If category == dependency_broke / schema_mismatch / environment_changed:
       search changelogs, web docs, new --help output, new OpenAPI schema
   - Write findings to episodic / semantic memory (DRAFT)
   │
   ▼
3. FIX GENERATION
   Generate candidate patch(es):
     - For generated_tool: regenerate or in-place patch
     - For MCP server: regenerate server code
     - For composite capability: rewrite steps / data flow
     - For dependency issue: rewrite version pins + add compatibility shim
   Each patch is versioned: next semver patch (or minor if interface breaks, but we try not to)
   │
   ▼
4. SANDBOX TEST + RE-HARNESS
   Deploy the fix ONLY into the harness sandbox (NOT live registry).
   Re-run full auto-harness §6 against the proposed fix.
   → Passes: proceed.
   → Fails: repeat §7.3 + §7.4 up to MAX_REPAIR_ATTEMPTS (default 3).
   │
   ▼
5. DEPLOY POLICY
   Based on risk:
   ┌──────────────────────────┬────────────────────────────────────────────┐
   │ Risk of change           │ Deploy policy                              │
   ├──────────────────────────┼────────────────────────────────────────────┤
   │ LOW  (pure bug fix, no   │ Auto-deploy new version; write audit;      │
   │       I/F change)        │ notify user non-blocking on next session  │
   ├──────────────────────────┼────────────────────────────────────────────┤
   │ MEDIUM (I/F backward-    │ Canary deploy: route 10% of new invocations│
   │        compatible change)│ to new version; compare metrics 24h; if OK │
   │                          │ promote to 100%.                           │
   ├──────────────────────────┼────────────────────────────────────────────┤
   │ HIGH (breaks callers, or │ ALWAYS needs user approval + shows diff +  │
   │       touches security   │ harness report. If approved: version tag,  │
   │       boundary, or is a  │ rollback snapshot taken before deploy.     │
   │       core-repair)       │                                            │
   └──────────────────────────┴────────────────────────────────────────────┘
   │
   ▼
6. REMEMBER + CLOSE THE LOOP
   - Register new version in skill store
   - Write episodic memory: "what broke, what we learned, what we fixed"
   - Write semantic memory: if fix reveals new fact about dependency
   - Write KG: capability --fixed_to--> new_version
   - Update meta-memory: known limitations of this capability updated
   - If repair loop exhausted without success:
       → DEGRADE capability, propose alternatives to user,
         AND/OR schedule human familiarization intervention:
         "I couldn't fix this. Want to walk me through how it should work?"
```

### 7.1 Repair vs. Core-Mutation — Hard Line

**Repair is for capabilities, skills, and generated tools.** Repair never modifies the TCB (L1/L2 core, L3 permission/policy/sandbox/audit engines).

If the root cause is in the TCB:
- Self-repair writes a detailed failure analysis with code pointers
- Escalates to user as CRITICAL approval ticket: "Core subsystem X has bug Y.
  Proposed patch Z. Review and approve to version + sandbox-test + deploy."
- Deploy is CRITICAL-tier per §05: per-call text confirmation + cooldown.

No silent core rewriting. Period.

---

## 8. AUTO-LEARNING — THE CONTINUOUS IMPROVEMENT LOOP

The familiarization + harness + repair loops cover *when things break*. Auto-learning covers *when things work* and when the user just goes about their day.

### 8.1 Learning Triggers (All Opt-In By Default)

| Trigger | Source | What's Learned | Gate Before Memory Promotes |
|---|---|---|---|
| Successful user workflow | Observer module watching approved user actions | Workflow recipe candidate | 3 consecutive successes OR user confirm |
| Failed workflow | Planner failure + replan | Anti-patterns + recovery patterns | 2 occurrences, then candidate suggestion |
| Repeated choices | Every decision where planner had ≥2 options | Preference candidates (coding style, tool choice, doc structure) | 5 consistent decisions OR user confirm |
| Documentation studied | Research module fetch during familiarization | Software facts, API facts | Corroboration (≥2 docs agree) OR user confirm |
| User direct teaching | User says "Remember that we prefer X" → explicit | Instant T5 Personal promotion with user-written provenance | Immediate; no extra gate (user-origin = highest trust) |
| Harness success/failure | §6 harness results | Skill strengths/limitations, regressions | Auto-promotes into T8 Skill limitations field |
| Self-repair outcome | §7 fix succeeded/failed | Patterns in what breaks | Auto → T2 Episodic + T8 Skill meta |

### 8.2 Stable Core + Learned Artifacts (Vision §7)

AEGIS does **not** self-improve by silently rewriting its own source. Self-improvement = adding *artifacts* to the system, all under versioning and audit:

```
STABLE CORE (L1 + L2 + L3 security-critical)
  Changes only via explicit versioned releases + user approval for CRITICAL.
  Not touched by auto-learning.

     │
     ▼ Interfaces only

LEARNED ARTIFACTS (all versioned, auditable, inspectable, deletable):
  1. T8 Skills / Capability Registry entries — versioned
  2. T4 Procedural workflows — versioned
  3. T5 Personal preferences — user approved, mutable by user
  4. T3 Semantic knowledge — corroborated or approved
  5. T2 Episodic experience log
  6. Evaluation history + harness reports
  7. Generated tools / MCPs — pinned + hash-integrity + rollback
  8. Policy rules (non-core) — versioned, rollback-able
```

---

## 9. VALIDATION PLAN (M08 — Tool & MCP Ecosystem)

Before closing M08:

1. **Capability Registry round-trip (20 cases):**
   Register 20 generated capabilities; retrieve via semantic search + filters → correct match in top 1.
2. **End-to-end Discovery → Harness → Register → Use (5 cases):**
   5 synthetic "user wants X; no pre-existing capability" scenarios. 4/5 must register ACTIVE capability; 1 may correctly escalate to user familiarization.
3. **MCP Runtime security:**
   10 malicious-tool negative tests → sandbox blocks, audit logs escape attempt.
4. **Harness scoring calibration:**
   10 known-good + 10 known-bad capabilities → harness decisions match expected (TP/TN ≥ 90%).
5. **Self-repair (3 scenarios):**
   Inject bug into generated tool → self-repair succeeds in ≤ 3 attempts with ≥ 90% harness pass rate on new version.

---

*End of Document 08_CAPABILITY_DISCOVERY.md*
