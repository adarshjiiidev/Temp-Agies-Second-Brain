# PROJECT AEGIS — RISK REGISTER, SECURITY BOUNDARIES, PRIVACY BOUNDARIES, AND MITIGATIONS

**Document ID:** AEGIS-DOC-011
**Version:** 0.1.0 (Prompt 01 Foundation)
**Status:** DRAFT — Architecture Phase Only
**Last Updated:** 2026-07-24

---

## 1. RISK REGISTER METHODOLOGY

Every risk is rated on two axes:

| **Severity** | Definition | **Likelihood** | Definition |
|---|---|---|---|
| **Critical** | Data loss, privacy breach, system takeover, financial loss ≥ 1 month budget | **Almost Certain** | ≥ 70% chance per year |
| **High** | Persistent compromise of TCB, unauthorized file exfiltration, voice/camera silent capture, ≥ 4h outage | **Likely** | 40–70% |
| **Medium** | Significant feature regression, moderate cost overrun, partial privacy leak (non-P0 data), 1–4h outage | **Possible** | 15–40% |
| **Low** | Minor degradation, minor cost overrun, annoying UX bugs | **Unlikely** | 5–15% |
| **Negligible** | Cosmetic issues, typographical, doc bugs | **Rare** | < 5% |

Risk Rating = Severity × Likelihood. We track every rating ≥ Medium in this register and assign an owner milestone and mitigation plan.

After mitigations, we re-rate. Target state: **no Unmitigated Critical or High risks remain before Prompt 09 ships code that touches real user environment.**

---

## 2. RISK REGISTER — ARCHITECTURAL PHASE (PROMPT 01)

| ID | Risk | Severity | Likelihood | Rating | Owner Milestone | Mitigation Plan | Post-Mitigation Target Rating |
|---|---|---|---|---|---|---|---|
| R01 | **LLM hallucination is treated as truth, leading to incorrect tool execution / incorrect memory writes / bad financial advice.** | High | Almost Certain | **Critical** | P03 + P05 | 1. All LLM outputs go through structured output validation. Never raw text to executor. 2. Post-execution verification stage re-checks intent vs. outcome. 3. Memory promotions require corroboration / user confirmation, never single LLM output. 4. Financial outputs marked "not advice" + evidence-only. | Medium |
| R02 | **Prompt injection via ingested data (web page, notes, user document) causes AEGIS to leak memory or take forbidden actions.** | Critical | Likely | **Critical** | P03 + P05 + P08 | 1. Variables wrapped in `UNTRUSTED_VAR_BEGIN/END` with system prompt. 2. LLM outputs validated before downstream. 3. Permission Engine checks every action regardless of what the LLM said to do. 4. Sandbox for all generated/untrusted execution. 5. Automated negative prompt-injection test battery in CI. | Low |
| R03 | **Sandbox escape of generated tool / MCP server → host file read or shell execution.** | Critical | Possible | **Critical** | P05 + P08 | 1. Four-tier sandbox; pick tier by provenance. 2. Ongoing escape-attempt regression test battery on every CI. 3. Rust enforcement of T1/T2 limits. 4. Docker security hardening guide: no --privileged, drop caps, seccomp, read-only root, scratch volume only. 5. Audit of all syscalls/file ops from sandbox tier. | Low |
| R04 | **Privacy tier P0 data silently routed to cloud LLM due to a router bug → user biometrics or personal data leaked to 3rd party.** | Critical | Possible | **Critical** | P03 + P04 | 1. Router HARD RULE: if prompt has P0, candidates = local models ONLY. If empty → error. Never silent drop. 2. Pre-routing scrubber classifies secrets and PII into P0 unconditionally. 3. End-to-end test 50 samples: 0 cloud calls when prompt has P0. 4. Audit log every cloud call with privacy_tier field; daily report of P2+/P0+P1 counts. | Low |
| R05 | **Self-repair mutates TCB module (L1/L2/L3 permission/policy/audit/sandbox) via repair loop → trust boundary silently broken.** | Critical | Unlikely | **High** | P08 + P23 | 1. HARD LINE: Self-repair does not touch TCB. Escalates CRITICAL approval ticket only. 2. TCB source files under `l1_core/` + `l2_foundation/{crypto,sandbox,audit}` marked TCBPROTECTED in repo; lint denies write by non-human code path. 3. TCB code review requires 2nd human reviewer from P23 onward. | Low |
| R06 | **Generated capabilities / MCP servers with malicious dependency chain → supply chain attack surfaces persistent backdoor.** | High | Possible | **High** | P08 + P23 | 1. Generated code uses pinned deps with hash. 2. All dependency installations run `pip-audit` / `cargo audit` / `npm audit` before load. 3. Generated MCP servers run in T2/T3 sandbox by default; never host privilege. 4. MCP manifest integrity_hash mandatory; load fails on mismatch. 5. Plugin signatures optional but recommended. | Medium |
| R07 | **AEGIS camera/microphone silently records without user knowledge → catastrophic privacy violation.** | Critical | Unlikely | **High** | P14 + P13 | 1. Kill switch in memory + enforced before every capture. 2. OS-level indicator library called for every frame/second of capture. 3. UI indicator visible during capture. 4. Capture attempts with kill-switch=off → HARD DENY + CRITICAL audit entry. 5. Vision/Microphone CRITICAL risk tier by default → per-session consent. | Low |
| R08 | **Computer control module (mouse/keyboard) used in unintended destructive action → data loss (delete file, click format dialog, send destructive message).** | Critical | Possible | **High** | P09 + P05 | 1. All computer_control verbs = HIGH risk by default → per-call approval until user promotes specific trusted workflow. 2. Require 3-way confirmation for any destructive action pattern. 3. Transactional undo log: try to snapshot state before destructive desktop action. 4. "Emergency stop" hotkey kills desktop automation instantly. 5. Test: attempt to format drive → policy engine blocks before mouse moves. | Medium |
| R09 | **Financial live-trading feature enabled accidentally or via policy bug → real monetary loss due to unproven strategy.** | Critical | Unlikely | **High** | P17 + P05 | 1. Live-trading capability = CRITICAL risk tier by default. 2. Live-trading OFF BY DEFAULT in feature flag; enabling it requires password/2nd factor in settings. 3. Trust ladder: Research → Analysis → Backtest → Paper → **(explicit human approval per order)** before Live. 4. Slippage/paper vs. live discrepancy alert; circuit breaker after X loss. 5. All financial outputs marked "not investment advice." | Medium |
| R10 | **Cybersecurity offensive tools used against targets without authorization → legal and ethical violation.** | Critical | Unlikely | **High** | P18 + P05 | 1. Offensive-capable plugins only run inside authorized sandboxed labs. 2. Every offensive-class action checks LAB_TOKEN present and lab-network-scoped. 3. Try to scan internet/host → SVRC DENY; audit OFFENSIVE_UNAUTHORIZED event. 4. User must sign "lab authorization" consent in config before enabling offensive modules. 5. Legal disclaimer on first use. | Low |
| R11 | **Cloud AI budget runaway → $thousands surprise bill (loop, retries, misconfigured per-call output).** | Medium | Likely | **High** | P03 + P05 | 1. Budget enforcement at 4 points: pre-call, mid-stream, post-call, daily rollup. 2. Default $2/day $40/mo caps. 3. Per-task cost caps; planning loop budgets cost before plan. 4. Retry loop bounded (N default 3) + exponential backoff. 5. Billing anomaly alerts: spend > 3× rolling average → auto-pause + alert. 6. Ledger export daily to audit. | Low |
| R12 | **Obsidian sync conflict overwrites user hand-edited note → data loss or frustration.** | Medium | Likely | **Medium** | P11 | 1. Bidirectional sync: reads `aegis_revision` frontmatter; detects user hand-edit; never silently overwrites. 2. 3-way merge; non-trivial conflict writes `.aegis-conflict-<ts>.md` showing both versions. 3. Vault backup before every sync batch. 4. User approval for conflict resolution. 5. Tests: hand-edit scenario roundtrip = 0 lost user content. | Low |
| R13 | **AEGIS becomes a hardcoded integration collection despite vision — architecture leaks. Over time each "product" gets its own special case instead of generic capability.** | Medium | Almost Certain | **High** | P08 + P23 | 1. Lint rule: no `if product=X` code in L1–L4, allowed only in plugin wrappers. 2. Product-specific modules live in `plugins/` only; `src/aegis/*` is product-agnostic generic. 3. Code review checklist item for every PR: "Does this introduce a per-product branch when a generic capability abstraction would work?" 4. P21 self-improvement actively decomposes hardcoded branches into discovered capabilities. | Medium |
| R14 | **Python/Rust FFI overhead is so high that local models and memory indexes are unusably slow → need to rewrite core in Rust later, delaying roadmap by months.** | Medium | Possible | **Medium** | P02 validation | 1. Prompt 02 exit gate includes FFI microbenchmark: Python↔Rust roundtrip p95 < 50µs. If not, redesign FFI strategy (batch calls, shared memory, less chattiness). 2. Hot path selection: only sandbox/crypto/audit/hot-index in Rust; rest pure Python. 3. Benchmark before commit to any module; fail on regression. | Low |
| R15 | **Roadmap too ambitious → project runs out of steam before first useful slice → abandonware.** | Medium | Likely | **High** | P06 | 1. First useful vertical slice at P06 (after Planner + Memory + AI + Execution + Text). 2. Ship small, demo-able value every prompt; not wait for P22. 3. User demos after each prompt gate. 4. Easy demotion of advanced features (T4 Firecracker, Tauri UI, multi-worker) to optional plugins to keep mainline lean. | Medium |
| R16 | **Knowledge graph link suggestions hallucinate → user trusts graph, makes decisions based on fake relationships → bad outcomes.** | Medium | Likely | **High** | P04 + P06 | 1. Auto-suggested edges = `is_draft=true` by default. 2. Draft edges NOT traversed by planner queries. 3. Promoted only after user confirm OR ≥ 2 corroborating episodic observations. 4. UI shows draft/solid edges distinctly in inspector and Obsidian projection. 5. "Confidence of edge" metadata per KG edge; exposed in memory inspector. | Low |
| R17 | **Meta-memory is systematically overconfident → user trusts wrong answers → bad outcomes.** | Medium | Likely | **Medium** | P04 + P21 | 1. Post-promotion, meta-memory does NOT set confidence = 1.0 ever. Calibration dataset tracks (predicted_confidence, actual_truth) continuously. 2. Daily calibration sweep (P21) forces re-scoring. 3. Every answer exposed to user optionally shows "Confidence: X% | Evidence: N sources." 4. Confidence < 0.7 by default: AEGIS adds "Low confidence; verify before relying on this." 5. Brier score target ≤ 0.05 (well-calibrated). | Low |
| R18 | **Personal / social intelligence module makes harmful inferences about unenrolled people → misclassification or creepy personal data hoarding.** | High | Possible | **High** | P15 | 1. Person models for EXPLICITLY ENROLLED PEOPLE ONLY. 2. Detection: "Person detected (enrolled=Alice)" or "Unfamiliar person" only. Never guesses identity of unenrolled. 3. No affective inferences ("angry Alice"). Only "Possible explanations: busy/distracted/frustrated + Confidence + Evidence." 4. Predictions probabilistic not definitive. 5. Person P0 tier; never sent to cloud LLMs. 6. Delete-forgotten = 1-click per person, fully atomic. | Low |
| R19 | **Auto-learning default-on builds up huge profile on user without user awareness → GDPR/privacy violations and trust loss.** | High | Likely | **High** | P07 + P21 | 1. All learning triggers OPT-IN BY DEFAULT. No silent memory promotion. 2. First-run onboarding: explicit consent wizard lists each learning type; user toggles each. 3. Weekly memory digest email/popup shows what AEGIS learned that week; user can delete in bulk. 4. "Forget everything about last week" = 1-click action, fully atomic, with audit trace of delete. 5. T5 promotion gate ALWAYS requires user confirm; never auto. | Low |
| R20 | **Dependencies (Python/Rust/npm) introduce known vulnerabilities → supply chain compromise of AEGIS itself.** | High | Likely | **High** | P02 start + P23 | 1. Lockfiles with content hashes mandatory. `uv.lock`, `Cargo.lock` in repo; build fails on mismatch. 2. `just audit` = `pip-audit && cargo audit && syft scan && trivy fs scan`; P23 CI gate fails on known CRITICAL fixes unapplied. 3. Minimal dependencies: prefer stdlib; each new dependency requires explicit "need, alternative considered" note in PR. 4. P23: SBOM generated per release; sigstore signing; provenance attestation. | Medium |
| R21 | **Audit log tampering by attacker who gained low-privilege access → covers their tracks, or frames user for actions they didn't take.** | High | Unlikely | **High** | P05 + P23 | 1. Hash chain: every record contains previous-hash; truncation/gap/reorder detected by `aegis audit verify`. 2. Periodic root MAC signed with offline user key or OS keychain; stored outside `~/.aegis/` (e.g., Win Cred Manager). 3. Append-only file lock; only one writer; Linux immutable attribute / Windows read-only ACL toggled post-write. 4. Optional remote audit mirror (syslog server / cloud log sink) with write-only creds. 5. P23: fuzz suite for audit integrity chain. | Low |
| R22 | **TurboQuant / any other proposed memory technology is adopted without research → silently introduces errors or hallucinations in memory compression/quantization.** | Medium | Unlikely | **Medium** | P04 + Research topic gate | 1. Standing operational rule (§06.6.5): any new memory/storage technology must first create a Research Topic, be benchmarked against the default on AEGIS-specific workloads (recall@k, error rate, P0 privacy), and be strictly superior before adoption. 2. By default, Tech Stack Document chooses default conservative stack (SQLite + Qdrant + NetworkX + plaintext). No speculative new tech. 3. Always plugin, never core replace. 4. Benchmarks are public in repo; reviewed before switch. | Low |
| R23 | **User loses or forgets vault passphrase → all P1 E2EE synced memory + P0 local key material unrecoverable → permanent data loss.** | High | Possible | **High** | P02 + P11 | 1. First-run: guided key backup (recovery key printed / offline export). 2. Recovery key stored separately from vault; user required to click-through "I have stored my recovery key in a safe place" check. 3. KMS plugin option (OS keychain) for users who prefer convenience with OS trust. 4. Regular "test your backup recovery" reminder popup every 90 days. 5. Non-encrypted local-only option available explicitly for users who don't want cross-device sync. | Medium |
| R24 | **Capability discovery + auto-harness is slow or rarely succeeds → user experience is just another tool-call bot with handwritten tools instead of "learns new software."** | Medium | Likely | **Medium** | P08 + P21 | 1. P08 exit gate: 4/5 synthetic new-capability goals register ACTIVE capability with harness. If not, improve familiarization loop before closing P08. 2. User-initiated "Teach me this software" wizard: semi-supervised familiarization where user can answer prompts to speed discovery. 3. Pre-ship curated MCP ecosystem of 20 most popular tools to cover 80% of common cases. Generic loop covers long tail. 4. P21 daily loop re-evaluates failed-discovery goals to iterate on discovery heuristics. | Low |
| R25 | **Noisy or wrong "Unfamiliar person entered room" alerts from vision → user disables alerts entirely, then misses a real incident → cry-wolf failure.** | Medium | Possible | **Medium** | P14 | 1. Alerts graded by confidence + evidence. "An unfamiliar person entered the restricted area and remained there for five minutes. Confidence: medium." (Evidence: frames, size, duration.) 2. User feedback on alerts ("this was a false positive") → retrains per-room threshold. 3. Scheduled "quiet hours" suppress low-confidence alerts. 4. 30-day alert precision target precision ≥ 0.8 on user's real data. If not, tune or disable. 5. Privacy zones allow user to mask off areas that frequently trigger false detections. | Low |

---

## 3. SECURITY BOUNDARIES — DEFINED & ENFORCED

The following security boundaries are architectural commitments. They are not features; they are red lines the system will not cross even if a subsystem is compromised.

| Boundary ID | Definition | Enforcement Mechanism |
|---|---|---|
| SB01 | **TCB writes are auditable, versioned, and non-silent.** | Lint rule, 4-eyes code review for TCB paths, self-repair cannot touch TCB (R05 mitigation), core mutate policy CRITICAL tier |
| SB02 | **Permission Engine is single source of truth for all side effects.** | No bypass; all executor modules MUST call `permission_engine.evaluate(SVRC)` before any side effect; lint rule; integration test battery |
| SB03 | **Audit Log is append-only and integrity-protected.** | Rust audit chain + hash chain + offline root MAC (R21 mitigation) |
| SB04 | **Untrusted code (generated tools, plugins, MCP servers, user scripts) never runs unsandboxed.** | Provenance-based tier selector: provenance != core_builtin → sandbox tier ≥ T2; escape tests on every CI (R03, R06) |
| SB05 | **LLM output is never executable without structured validation + sandbox + permission check.** | 7-stage execution pipeline; planner outputs typed Actions never raw strings; LLM text → user display only; never direct execution path |
| SB06 | **Secrets never appear in logs, traces, audit payloads, crash dumps, stdout.** | Pre-routing Prompt Scrubber + L2 crypto.redact runtime + regex CI log scan + lint rule forbidding printing vars named `*secret*` `*_key` `*token` |
| SB07 | **No default network access for sandbox-generated code.** | T2: default network deny (Windows Filtering Platform / iptables wrapper / subprocess net ns) T3: Docker with custom network profile. User must explicitly permit per capability. |
| SB08 | **Camera/Microphone cannot capture without live kill-switch=ON AND per-session consent AND OS indicator confirmation.** | Vision/voice module checks kill-switch synchronously before every driver call; hard fail if off; CRITICAL audit on attempt |
| SB09 | **Live-trading and offensive-capable tooling are CRITICAL gating tier — always require explicit consent.** | Policy engine risk tier assignment; per-call CRITICAL approval path not subject to auto-promotion thresholds |
| SB10 | **Generated code never runs with user account privilege; always runs in least-privilege sandbox identity.** | On Windows: Job Objects with restricted token; Linux: separate user + namespace; Docker: non-root container. All default. |

---

## 4. PRIVACY BOUNDARIES — DEFINED & ENFORCED

Privacy boundaries are user-data red lines. They are not defaults; they are guarantees.

| Boundary ID | Definition | Enforcement Mechanism |
|---|---|---|
| PB01 | **P0 DEVICE_LOCAL_ONLY data never leaves the user's device. EVER. Under no circumstances does AEGIS send it to any cloud API, even if router thinks there's no alternative.** | Router Stage 1 HARD FILTER: P0 in prompt → candidates = local models only. If empty → error `LOCAL_MODEL_REQUIRED_FOR_P0_TIER`; never silent drop. Prompt Scrubber auto-tags PII-secrets to P0. Audit: every cloud call includes privacy_tier; daily scan for P0-tagged calls (should be 0). (R04) |
| PB02 | **P1 E2EE_CLOUD_SYNC data: cloud storage provider sees ciphertext only.** | Encrypt before write; master key derived offline via Argon2id from user passphrase + per-scope keys. Optional KMS wrapper. |
| PB03 | **No cross-user data mixing ever.** AEGIS is single-user by design; no multi-tenant model. No telemetry uploads of user data. | Single `user:primary` subject in permission system; no multi-user code paths in core; telemetry = local unless user opts into (separate) anonymous usage metrics. |
| PB04 | **User has 7 rights on their data: Inspect, Correct, Delete, Export, Disable Learning, Retention Control, Control What Is Learned.** | Memory Inspector UI (P11 text + P22 desktop); atomic delete; export to open formats; per-tier toggles; TTL controls. Tested per P04 exit gate. (§05.8.3) |
| PB05 | **Camera/microphone require explicit per-session consent AND software kill switch AND OS indicator on screen.** | Three-factor before capture. Silent capture impossible by design. UI indicator live during capture. R07 mitigation. |
| PB06 | **AEGIS does NOT build person models on unenrolled people. It does NOT guess identities. It does NOT infer internal mental states.** | Detection output limited to "Unfamiliar person." No affective labels without "Possible explanations + Confidence + Evidence" triplet. No name guessing. Enrollment workflow is explicit only. R18 mitigation. |
| PB07 | **Personal/social learning triggers are ALL OPT-IN BY DEFAULT.** No silent profile building. Weekly digest shows what was learned. R19 mitigation. | First-run consent wizard per learning trigger. Global disable toggle. Bulk forget by week/month/topic. T5 Personal promotion requires explicit user confirm. |
| PB08 | **Financial and cybersecurity modules are NEVER auto-enrolled. User explicitly enables them; passes feature-specific consent.** | Feature flags in config; enabling triggers explicit consent dialog; CRITICAL tier default for high-risk verbs. |
| PB09 | **Secret directories: `~/.ssh`, `~/.gnupg`, all password-manager data dirs, browser profile dirs, the secrets vault itself, and paths matching `**/secrets/**` are in the FS scanner default DENYLIST. AEGIS will NOT read them unless user explicitly removes them from DENYLIST.** | Scanner default denylist; add denylist entries append-only; removal requires user-confirm dialog; T6 Environmental scans never descend into denylisted paths. |
| PB10 | **If user says "Forget X about me / about last week / about project Y," that deletion is atomic, verified, irreversible (audit trail retains content hash only, never content).** | Delete writes atomic tombstone; background compaction job scrubs underlying KV/vector/KG stores; verify query returns 0 hits post-delete. |

---

## 5. CONTINUOUS RISK MANAGEMENT

The risk register is not one-and-done:

1. **Per-prompt review:** Every prompt exit gate includes a risk register review — are any items now mitigated? Are any new risks identified? Update this document.
2. **Prompt 21 weekly self-improvement loop includes risk calibration:** Re-score R01–R25 using empirical data from the last week (how many prompt injection attempts blocked, sandbox escape attempts blocked, budget caps hit, alerts sent vs false positives, etc.).
3. **Prompt 23 production hardening ships a formal threat model document:** STRIDE/DREAD per subsystem; additional risks captured; all mitigations verified against actual code and fuzz results.
4. **Incident Response (§05.11):** Panic button + audit forensics + rollback toolkit are part of Prompt 05+ and hardened by P23.

---

## 6. RESIDUAL RISK ACCEPTANCE STATEMENT

After all mitigations above are implemented, the following residual risks remain at Medium or higher rating. These are **documented, accepted, and monitored**. They do NOT block release. They DO require ongoing metrics:

| ID | Residual Post-Mitigation Rating | Why Accepted | Mitigation Ongoing |
|---|---|---|---|
| R01 | Medium | LLM hallucination is inherent; cannot eliminate, only bound via validation + verification. | Monthly eval of hallucination rate; retune prompts/models as needed. |
| R13 | Medium | Architecture discipline requires ongoing code review effort. | Lint rule + review checklist + P21 automated decomposition. |
| R15 | Medium | Project ambition risk; depends on user commitment and scheduling. | First useful slice at P06; demonstrate value early. |
| R20 | Medium | 0-day vulnerabilities in 3rd-party deps are unknowable in advance. | Daily CVE feed + auto-SBOM scan; P23 hardening. |
| R23 | Medium | Passphrase/backup hygiene depends on user behavior; system can encourage but not enforce. | Onboarding wizard + 90-day recovery test reminders. |
| R24 | Medium | Real-world unfamiliar-software discovery success rate is unknown without testing. | P08 exit gate; user-initiated "Teach Me" wizard as safety net. |

All residual Medium+ risks have monthly KPIs tracked in Meta-Memory. If any KPI trends adverse for 2 consecutive months, the system auto-generates a mitigation proposal ticket for user approval.

---

*End of Document 10_RISKS.md*

End of Prompt 01 document set (11/11).
