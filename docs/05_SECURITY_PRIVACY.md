# PROJECT AEGIS — SECURITY MODEL, PERMISSION SYSTEM, AND PRIVACY BOUNDARIES

**Document ID:** AEGIS-DOC-006
**Version:** 0.1.0 (Prompt 01 Foundation)
**Status:** DRAFT — Architecture Phase Only
**Last Updated:** 2026-07-24

---

## 1. SECURITY FOUNDATION — TRUSTED COMPUTE BASE (TCB)

The AEGIS TCB is intentionally small. Everything outside the TCB is treated as untrusted and sandboxed.

```
┌─────────────────────────────────────────────────────────────┐
│                     TRUSTED COMPUTE BASE                     │
│                                                               │
│  L1 Core Runtime           (module container, lifecycle)     │
│  L2 crypto                 (AEAD, MAC, KDF — Rust)           │
│  L2 secrets_vault          (encrypted-at-rest storage)       │
│  L3 permission_engine      (SVRC checks — deny-by-default)   │
│  L3 policy_engine          (risk scoring + approval gates)   │
│  L3 audit                  (append-only, integrity-protected)│
│  L3 sandbox.manager        (tier selector, resource limits)  │
│  Rust FFI boundary         (PyO3 types, error propagation)   │
│                                                               │
│  Size target: < 25 KLOC of human-auditable code              │
└─────────────────────────────────────────────────────────────┘
            │  Calls INTO TCB via stable, typed interfaces ONLY
            ▼
┌─────────────────────────────────────────────────────────────┐
│                       UNTRUSTED CODE                         │
│                                                               │
│  All LLM provider plugins       All executor plugins         │
│  All MCP servers/tools           Generated tools/MCPs        │
│  Browser automation             Computer control             │
│  All domain modules (finance…)  All user scripts             │
│  Vision perception models       Third-party plugins          │
│                                                               │
│  Any code NOT in the TCB list above = UNTRUSTED by default   │
└─────────────────────────────────────────────────────────────┘
```

**Security Principle #1:** The TCB alone decides whether an action is allowed. Untrusted code cannot self-grant permissions, cannot mutate audit log, cannot read secrets vault.

**Security Principle #2:** TCB code changes require: 4-eyes review, dedicated test suite (including negative tests), automated sandbox-escape attempt battery, version bump.

---

## 2. PERMISSION MODEL — SUBJECT / VERB / RESOURCE / CONTEXT (SVRC)

Every side-effecting action in AEGIS passes a permission check. The check is always structured as four components — **never abbreviated, never partial**:

| Component | Definition | Examples |
|---|---|---|
| **Subject (S)** | Who or what is attempting the action | `system:cognitive_planner`, `plugin:com.example.obsidian`, `user:primary`, `generated:tool_abc123` |
| **Verb (V)** | The action type (granular, hierarchical) | `fs.read`, `fs.write`, `fs.delete`, `proc.spawn`, `net.request`, `ai.completion`, `memory.write`, `camera.capture`, `browser.navigate` |
| **Resource (R)** | What the verb targets; hierarchically scoped | `fs:~/Projects/AGIES/**`, `proc:type=powershell`, `net:host=api.openrouter.io,port=443,tls=true`, `memory:tier=personal` |
| **Context (C)** | Why, where, under what policy | `reason:"read source file for plan step 3"`, `plan_id:plan_20260724_001`, `approval:user_granted_20260724T221500Z` |

### 2.1 Verb Hierarchy (Inheritance Rules)

Verbs are colon-separated and hierarchical. Granting `fs` grants every sub-verb unless explicitly denied.

```
* (root — NEVER granted by default)
├─ fs
│   ├─ fs.read
│   ├─ fs.write
│   ├─ fs.append
│   ├─ fs.delete
│   ├─ fs.chmod
│   └─ fs.exec
├─ proc
│   ├─ proc.spawn
│   ├─ proc.read
│   ├─ proc.signal
│   └─ proc.network_access  (within process sandbox)
├─ net
│   ├─ net.request
│   ├─ net.listen
│   └─ net.upload
├─ ai
│   ├─ ai.completion
│   ├─ ai.embedding
│   └─ ai.fine_tune
├─ memory
│   ├─ memory.read
│   ├─ memory.write
│   ├─ memory.delete
│   └─ memory.export
├─ exec
│   ├─ exec.tool
│   ├─ exec.mcp
│   └─ exec.generated
├─ camera
│   ├─ camera.list
│   ├─ camera.capture
│   └─ camera.stream
├─ mic
│   ├─ mic.listen
│   └─ mic.stream
├─ browser
│   ├─ browser.navigate
│   ├─ browser.read
│   ├─ browser.fill_form
│   ├─ browser.download
│   └─ browser.upload
├─ desktop
│   ├─ desktop.screenshot
│   ├─ desktop.mouse
│   ├─ desktop.keyboard
│   └─ desktop.window_manage
└─ aegis
    ├─ aegis.config.write
    ├─ aegis.plugin.load
    ├─ aegis.core.mutate
    └─ aegis.user.impersonate
```

### 2.2 Decision Algorithm — Allow / Deny / Needs-Approval

```
def evaluate_permission(S, V, R, C):
    1. Compute applicable rules (order by priority):
       a. Explicit DENY → HARD DENY, audit, alert
       b. Explicit ALLOW by S+V+R with context C satisfied → ALLOW
       c. Default-deny policy for verb tier → NEEDS_APPROVAL or DENY based on risk
       d. Fallback → DENY
    2. If result = ALLOW but risk score ≥ HIGH → UPGRADE to NEEDS_APPROVAL
    3. Record decision + inputs in audit log (immutable)
    4. Return decision
```

### 2.3 Permission Decision Outcomes

| Outcome | Meaning | Required Next Step |
|---|---|---|
| `ALLOW` | Explicitly permitted by rules | Execute; audit; verify |
| `DENY` | Explicitly denied or default-deny + no approval path | Halt action; audit; surface to user as blocked; never silently |
| `NEEDS_APPROVAL` | Allowed only if user (or designated approval policy) grants explicit consent | Route to HCI approval UI; record user's response; timeout = DENY |

**No "trusted" path that skips the check.** Even L1 Core Runtime's own internal mutations go through SVRC with subject=`system:core_runtime`.

---

## 3. POLICY ENGINE — RISK SCORES & APPROVAL GATES

The Policy Engine sits **between** the Permission Engine and the Execution Kernel. It enforces risk-based controls even when the permission engine says ALLOW.

### 3.1 Risk Taxonomy Per Action

| Risk Level | Criteria | Approval Requirement |
|---|---|---|
| **LOW** | Read-only actions on explicitly allowed low-sensitivity resources. No external side effects. | Automatic ALLOW if permission is ALLOW |
| **MEDIUM** | Writes to non-sensitive data; local CLI invocations; local-only AI calls; browser reads. | Auto-allow first N per session; after threshold or pattern anomaly → approval |
| **HIGH** | Any delete; any outbound network to unknown host; any process spawn outside allowlist; generated/generated tool execution; memory export; camera capture; desktop keyboard/mouse action. | **Always user approval.** No auto. No bypass. |
| **CRITICAL** | aegis.core.mutate; aegis.plugin.load of unsigned plugin; financial live-trade; browser upload of >1MB file to unknown host; camera stream. | **Explicit user approval per-call with text confirmation prompt + cooldown.** |

### 3.2 Policy-as-Code — Versioned Rules Engine

Policies are **versioned, typed, auditable** YAML documents with signed hashes stored in the audit log. Example:

```yaml
policy_version: 1
policy_id: aegis.builtin.desktop_gate.v1
effective: 2026-07-24T00:00:00Z
rules:
  - id: mouse_always_approve
    match: { verb_prefix: desktop.mouse }
    risk_override: HIGH
    approval: { type: per_call, channel: text_ui, timeout_seconds: 60 }
  - id: fs_delete_sensitive_paths
    match: { resource_pattern: "fs:~/.ssh/**, fs:~/.aegis/secrets/**" }
    verb: fs.delete
    decision: DENY
    reason: "Explicitly protected paths; manual override via config change required."
  - id: net_local_default_deny
    match: { verb: net.request, resource_host_category: unknown }
    decision: NEEDS_APPROVAL
    approval: { type: per_call, risk_banner: true }
```

Policy changes are themselves actions — they require approval, are versioned, are auditable, and support rollback to any prior policy version.

---

## 4. SANDBOX MODEL — TIERED ISOLATION

Sandbox tiers are the security boundary for generated tools, MCP tools, scripts, and untrusted plugins. Tier assignment is automatic based on provenance + required permissions.

| Tier | Who Goes Here | Isolation Mechanism | Enforceable Controls |
|---|---|---|---|
| **T1** | Pure Python expressions, no external imports, no I/O; auto-harness evaluation of pure functions | Python AST interpreter subset + whitelisted AST node types; no `import`, no `open`, no `subprocess` | Wall time, CPU time, recursion depth, heap size, I/O deny-all |
| **T2** | Generated CLI scripts; MCP tool stdlib calls; shell one-liners generated by planner | Subprocess + temp overlay dir + Windows Job Objects / systemd-run / launchd + seccomp-bpf (Linux) | Filesystem: only r/w inside temp dir; network: default-deny; resource caps (CPU, mem, processes); no setuid; parent kill propagates |
| **T3** | Untrusted plugins; generated tools with many deps; browser automation; Docker-backed MCP servers | Docker container (WSL2 backend on Windows) with custom image | Read-only root FS except scratch volume; Linux capabilities drop ALL; network policies via nftables/iptables; CPU/mem/pids caps; seccomp default profile; no --privileged ever |
| **T4** | High-risk long-running workloads; generated code the user explicitly wants extra isolation for | Firecracker/Kata microVM (optional advanced plugin; Linux-only initially) | Full VM boundary; independent kernel; snapshot + revert per run; no shared FS with host |

### Sandbox Guarantees (Tested Continuously)

A security test suite attempts sandbox-escape attacks against every sandbox tier **on every CI run** (M23) and on every developer workstation's `just test` from M05 onward:

- T1 escape: attempt `__import__('os').system`, `eval(compile(...))`, attribute access via `getattr` on builtins
- T2 escape: attempt `cd ../ && ls ~/.ssh`, write to `/tmp/escape_attempt`, spawn background process, attempt network socket
- T3 escape: attempt container escape CVEs from the last 5 years as negative regression tests
- T4 escape: VM hardening checklist

All escape-attempt tests must fail the action and produce an audit log entry. If an escape test *succeeds*, the tier is marked as broken and all workloads are automatically downgraded to a stricter tier.

---

## 5. AUDIT LOG — INTEGRITY-PROTECTED APPEND-ONLY STORE

The Audit Log is the source of truth for everything that happened, was decided, was attempted, or was blocked.

### 5.1 Schema — Typed Audit Record

```python
class AuditRecord:
    record_id: UUID               # v7 UUID (time-ordered)
    timestamp: DateTime           # monotonic UTC clock; NTP-synced; includes clock-skew flag
    subject: Subject              # SVRC Subject
    action_type: str              # e.g., "permission.evaluate", "fs.write", "plan.execute"
    permission_request: SVRC | None
    decision: Decision | None     # ALLOW / DENY / NEEDS_APPROVAL / APPROVAL_GRANTED / APPROVAL_DENIED
    resource_target: str | None
    context: dict[str, Any]       # plan_id, reason, provenance, correlation_id
    result: ActionResult | None   # outcome, latency_ms, error_code if failed
    user_safe_message: str | None # human-readable, redacted, never contains secrets
    prev_record_hash: bytes32     # hash-chained integrity
    record_hash: bytes32          # SHA-256 of all fields except this + signature
    signature: bytes | None       # optional: HMAC with vault key or Ed25519 for tamper evidence
```

### 5.2 Integrity Mechanism

- Hash chain: every record includes the hash of the previous record. Truncation = corruption.
- Root MAC: periodic snapshot of last-record-hash is signed by an offline user key or KMS key stored **outside** `~/.aegis/`.
- Read-only verification: `aegis audit verify` replays every record; reports tamper, gap, or reorder.
- Append-only enforcement (Rust): only one writer (L3 audit module) using exclusive file lock; mmap reads. Core Runtime supervises.

### 5.3 Retention

- Default retention: 365 days for normal; forever for CRITICAL-denied or failed-escape-attempt records.
- User can change retention; change is itself an audited action.
- Legal hold flag: records tagged legal_hold are never auto-deleted; deleting them requires explicit override.

---

## 6. SECRETS VAULT & CRYPTOGRAPHY

### 6.1 Secrets Store

| Property | Design |
|---|---|
| At-rest encryption | AES-256-GCM (nonce-reuse resistant; additional data = scope label + record_id) |
| Key derivation | Argon2id of user passphrase (if user-protected vault) → master key → per-scope derived keys |
| Scope keys | Per-scope derived keys: `llm_provider_keys`, `account_creds`, `user_personal_secrets`, `audit_signing_key` |
| KMS option | Optional plugin to wrap master key with OS-level keychain (Win Credential Manager / macOS Keychain / Linux Secret Service / KMS) |
| Redaction | Pattern-based automatic redaction in all logs, traces, telemetry, crash dumps, and exception messages |
| Access | Only `secrets_vault` module reads vault file; requests through typed `get_secret(scope, id, caller_subject, svrc_context)` with permission check |

### 6.2 Forbidden Patterns (Lint + Runtime Check)

- ❌ `print(api_key)` — always redacted at runtime; lint catches literal assignment to open var
- ❌ Secrets in environment variables passed to subprocess — instead, secrets go through in-memory file descriptor on demand
- ❌ Storing secrets in Git — pre-commit hook + `gitleaks` + CI scan
- ❌ Secrets in `config.yaml` — config references `secret://scope/id` which resolves via vault at load time; never literal

---

## 7. PROMPT INJECTION & OUTPUT VALIDATION

Because AEGIS uses LLMs extensively, LLM output is **never trusted as executable** without validation. This is a security boundary.

### 7.1 LLM Output Trust Pipeline

```
LLM produces raw text / tool calls
        │
        ▼
  STAGE 1: Structured parsing — Pydantic v2 schema validation
        │   Pass → next
        │   Fail → retry loop with schema diagnostic (max N retries)
        │
        ▼
  STAGE 2: Output encoding — if the output will be injected anywhere downstream
        │   (shell, SQL, HTML, URLs, JS), apply canonical encoder for that context
        │
        ▼
  STAGE 3: Permission Engine — output-driven actions go through full SVRC
        │
        ▼
  STAGE 4: Sandbox — if output is code/script, sandbox tier assignment happens automatically
        │
        ▼
  Execute; then Stage 5 Verification; then Audit
```

### 7.2 Input Variable Hygiene (Prompt Injection Mitigation on Input Side)

- User-supplied / web-scraped / third-party text is NEVER concatenated bare into system prompts. It always goes through a typed template variable with explicit boundaries and **length caps**.
- "Ignore previous instructions" attack mitigation: variable content is prefixed with `--- BEGIN UNTRUSTED INPUT BLOCK (N chars) ---` and suffixed; system prompt instructs the model to treat this block as data only, never as instructions.
- Role separation: system prompt, user intent, untrusted data, tool outputs — all sent as separate message roles; never merged.

---

## 8. PRIVACY MODEL — DATA CLASSIFICATION, LOCAL-FIRST, AND USER RIGHTS

### 8.1 Data Classification Tiers

**Every datum written to storage is tagged with a tier.** The tag is immutable for that record; reclassification requires a new record with migration provenance.

| Tier | Label | Definition | Where it can go |
|---|---|---|---|
| **P0** | DEVICE_LOCAL_ONLY | Highly sensitive personal data, biometrics, camera frames, personal memories | Never leaves this device. Never sent to cloud AI. Only local models. |
| **P1** | E2EE_CLOUD_SYNC | Personal data the user opts to sync across their devices | E2EE with keys derived from user passphrase. Cloud storage sees ciphertext only. |
| **P2** | USER_APPROVED_CLOUD_AI | Data the user explicitly approves sending to cloud LLMs for processing | User approval per data category or per datum; audit trail of every cloud AI call with data tier |
| **P3** | PUBLIC | Data the user has explicitly published or marked public | Open export; no restrictions beyond attribution |

### 8.2 Local-First Principle (NFR-PRIV-001) — Operationalized

The Model Router (M03) routes based on **data tier**:

```
If datum.tier is P0:
  → MUST route to local model only.
  → If no suitable local model exists, FAIL with error "LOCAL_MODEL_UNAVAILABLE_FOR_P0_TIER"
    and NEVER silently fall back to cloud.
If datum.tier is P1:
  → Prefer local model if suitable.
  → If cloud is used, data is decrypted ONLY in memory for the call; never written to cloud provider's logs
    (send via provider privacy endpoints; set do-not-store / zero-log retention headers when available).
If datum.tier is P2 or P3:
  → Router considers cost/latency/quality normally.
```

### 8.3 Privacy Zones & Data Subject Rights

| Right | Implementation |
|---|---|
| **Inspect** | Memory inspector UI (M11 text; M22 desktop) lists every record with tier, provenance, and access history |
| **Correct** | User can edit any user-tier memory; original version retained as previous revision with "corrected_by_user" flag |
| **Delete** | Atomic delete per memory id / project scope / date range / tier. Audit retains DELETE record (with content hash only, not content) for integrity chain but not the plaintext |
| **Export** | One-command export to JSONL, Markdown, Obsidian Vault, SQLite. P0 data export requires re-authentication. |
| **Disable** | Per-tier disable switches: e.g., disable environmental memory entirely. |
| **Retention Control** | Per-tier TTLs, per-project retention overrides, auto-archive rules. Defaults: Working = 1 hour, Session = 30 days, Episodic = 2 years, Personal/P0 = forever unless user deletes. |
| **Sensitive Directories** | User-defined allowlist + denylist for FS scanning. Default denylist includes `~/.ssh`, `~/.gnupg`, browser profiles, all password manager data dirs, any path matching **/secrets/**, the secrets vault itself. |
| **Camera/Mic Kill Switch** | Software toggle + OS indicator. If toggle off, camera/mic APIs return HARD DENY regardless of permission status. Explicit per-session consent. No continuous capture without live indicator. |

---

## 9. SUPPLY CHAIN SECURITY (M23 — Prod Hardening)

Prompt 01 cannot ship these, but the architecture reserves extension points:

1. **Pinned lockfiles + hashes:** uv.lock, Cargo.lock both contain content hashes; build fails on mismatch.
2. **SBOM generation:** `just sbom` outputs SPDX 2.3 for Python+Rust dependencies.
3. **Vulnerability scanning:** `pip-audit`, `cargo audit`, `trivy` for Docker images; CI gates on CVSS ≥ 7.0.
4. **Reproducible builds:** Python wheel + Rust crate with locked toolchains; `just build-reproducible`.
5. **Plugin signing:** Optional Ed25519 signature verification on plugins; unsigned plugins = always NEEDS_APPROVAL before load.
6. **Pre-commit hooks:** `detect-secrets`, `ruff`, `mypy`, `cargo fmt --check`, `clippy`.

---

## 10. SECURITY BOUNDARY SUMMARY TABLE

| Concern | Boundary Location | Enforcement Mechanism |
|---|---|---|
| Permission decision | L3 `permission_engine` | Deny-by-default SVRC; audit every decision; upgrade to approval |
| Policy / Risk gating | L3 `policy_engine` | Risk scoring → approval matrix; policy-as-code versioned |
| Untrusted code execution | L3 `sandbox.manager` | Tiered isolation T1/T2/T3/T4; ongoing escape regression tests |
| Secrets at rest | L2 `crypto` + `secrets_vault` | AES-256-GCM + Argon2id; per-scope keys; redaction everywhere |
| Audit integrity | L3 `audit` + Rust FFI `aegis_audit_chain` | Hash-chained append-only; root MAC; verification CLI |
| LLM output trust | L3 `ai_kernel.structured` + full pipeline | Pydantic v2 → encoding → SVRC → sandbox → verify → audit |
| Data privacy tiers | L4 `memory_engine` write path | P0 → local only; P1 → E2EE; P2 → user-approved cloud; never silent promotion |
| Local-first routing | L3 `ai_kernel.router` | Data tier drives model selection; P0 fails if no local model; no silent fallback |
| Plugin load | L2 `plugin_loader` + L3 permission | Manifest + required_permissions; load = NEEDS_APPROVAL for unsigned/new |
| Core mutation | L1 runtime + policy CRITICAL tier | Per-call approval + cooldown + versioned + rollback required |

---

## 11. INCIDENT RESPONSE — ARCHITECTURAL PREPARATION

AEGIS ships with an incident response toolkit that uses its own subsystems:

1. **Panic button:** `aegis lockdown` — instantly sets all permissions to DENY except user-read; kills all sandboxed processes; freezes audit log with signed snapshot; closes all network connections to cloud providers.
2. **Audit forensics:** `aegis audit query --since --subject --resource --risk`; `aegis audit verify --since` with integrity report.
3. **Rollback:** `aegis rollback --module --to-version` for core, plugins, skills, policies.
4. **Export for analysis:** `aegis export --audit --memory --tier --range` exports to forensics package (signed).

These are architectural guarantees — the modules exist in the plan even though the code ships in later prompts.

---

*End of Document 05_SECURITY_PRIVACY.md*
