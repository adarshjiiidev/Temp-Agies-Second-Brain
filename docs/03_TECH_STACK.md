# PROJECT AEGIS — TECHNOLOGY STACK SELECTION

**Document ID:** AEGIS-DOC-004
**Version:** 0.1.0 (Prompt 01 Foundation)
**Status:** DRAFT — Architecture Phase Only
**Last Updated:** 2026-07-24

---

## 1. STACK SELECTION METHODOLOGY

For each technology dimension below, we compare multiple candidates against weighted criteria and select a **recommended default**. All selections are provisional and validated during their target milestone via prototype + benchmark. All selections respect Provider Neutrality (Principle P3): no concrete backend is hardcoded in the kernel; the recommended default is the first plugin implemented.

Decision criteria and their weights:

| Criterion | Weight | Description |
|---|---|---|
| **Local-First** | 1.5 | Runs offline-first, no mandatory cloud for core features |
| **Security Auditability** | 1.5 | Small trusted compute base; auditable; proven track record |
| **Interface Ecosystem** | 1.3 | Rich FFI / IPC / plugin model; MCP support; broad provider support |
| **Performance** | 1.2 | Latency, throughput, footprint consistent with NFR-PERF |
| **Maintainability** | 1.1 | Typed, testable, readable; strong tooling and community |
| **Cross-Platform** | 1.1 | Runs natively on Windows (primary), Linux, and macOS |
| **Longevity** | 1.0 | Project governance, version stability, migration path |
| **Learning Curve** | 0.7 | Team familiarity, onboarding docs |

Each candidate is scored 1–5 per criterion, multiplied by weight, then summed. The **recommended** candidate has the highest score and a validation plan.

---

## 2. PRIMARY LANGUAGE & RUNTIME

| Criterion (Weight) | **Python 3.12+** | **Rust 1.75+** | **TypeScript/Node 20+** | **Go 1.21+** |
|---|---|---|---|---|
| Local-First (1.5) | 5 — pure stdlib works offline; native packages | 5 — static binary, no runtime | 3 — npm-dependent, heavy node_modules | 4 — single binary |
| Security Audit (1.5) | 3 — GIL + C extensions; supply chain large | 5 — memory safe, unsafe blocks explicit, cargo audit | 2 — npm supply chain historically risky | 4 — memory safe, small stdlib |
| Interface Ecosystem (1.3) | 5 — LLM SDKs, Ollama/vLLM, MCP libs, data stacks | 3 — growing, but many AI SDKs lag Python by months | 4 — MCP reference impl is TS; browser stacks are rich | 4 — good IPC, gRPC, native HTTP |
| Performance (1.2) | 2 — GIL; slow for CPU hot paths | 5 — excellent | 3 — async I/O good; CPU-bound weak | 4 — strong concurrent I/O |
| Maintainability (1.1) | 4 — readable; typing (mypy) optional in practice | 3 — steep initial curve; compiler is a gatekeeper | 4 — strong typing (TS); ESM churn is cost | 5 — extremely consistent; opinionated toolchain |
| Cross-Platform (1.1) | 5 — excellent Windows support; PowerShell love | 4 — good; some C/crate issues on Windows | 4 — good; Windows Node is solid | 5 — excellent Windows |
| Longevity (1.0) | 4 — mature; 3.13+ improving perf | 4 — very strong governance; stable editions | 3 — framework/tooling churn high | 5 — Go 1 compatibility promise legendary |
| Learning (0.7) | 5 — broad familiarity | 2 — borrow checker | 4 — JS is ubiquitous | 4 — straightforward |
| **Weighted Score** | **27.0** | **26.3** | **23.4** | **27.0** |

### Decision: HYBRID — Python as primary, Rust as performance kernel

**Rationale:** Python and Go tie on raw score. Python wins for AEGIS due to (a) first-class AI/ML SDK ecosystem — LLM clients, Ollama, vLLM, embeddings, vector DB bindings, future perception models are all Python-first or Python-only; (b) rapid iteration for cognitive/planning/adaptive-intelligence logic; (c) Windows + PowerShell scripting is Python-friendly. Rust is used for: (i) hot paths in memory/vector/knowledge-graph storage; (ii) sandbox enforcement; (iii) audit log integrity; (iv) FFI-based plugin boundary for critical security.

- **Primary Language:** Python 3.12+ (3.13 targeted once stable — free-threaded GIL benefits)
- **Performance Kernel:** Rust 1.75+ (PyO3 FFI to Python)
- **Type Safety:** Strict mypy with `--strict` for all Python; clippy `deny(warnings)` for Rust
- **Packaging:** Rye / uv for Python; cargo workspace for Rust
- **No TypeScript/Node in core** — TS is reserved for optional web/desktop UI (Control Center M22) and MCP servers; never required for runtime.

**Validation Plan (Prompt 02):** Build core_runtime prototype in strict-Python + Rust FFI skeleton; measure boot time, idle footprint, call overhead across FFI.

---

## 3. PERSISTENCE LAYERS — PLUGIN INTERFACES + RECOMMENDED DEFAULTS

All persistence uses a stable interface defined in L2. The kernel never imports a concrete DB directly. Below are the **recommended first plugin** per storage type.

### 3.1 KEY-VALUE / DOCUMENT STORE (for config, session, episodic memory indices, audit log)

| Criterion | **SQLite 3.45+** | **DuckDB** | **RocksDB** | **LMDB** |
|---|---|---|---|---|
| Local-First | 5 — embedded, zero server | 5 — embedded | 5 — embedded | 5 — embedded |
| Security | 4 — battle-tested; single file easy to encrypt-at-rest via SQLCipher | 3 — newer; fewer audit years | 3 — C lib, mobile-heavy | 3 — known DB bugs historically |
| Interface | 5 — SQL = queryable; JSONB good; FTS5 | 4 — SQL analytical | 2 — KV-only | 2 — KV-only |
| Performance | 4 — excellent for mixed read/write single-user | 5 — analytical read, bulk load | 5 — write heavy | 5 — read heavy |
| Maintainability | 5 — DB-API / aiosqlite standard | 4 — good Python support | 3 — Python bindings fragmented | 3 — same |
| Cross-Platform | 5 — ships on all systems | 5 — good | 4 — Windows builds not trivial | 4 — same |
| Longevity | 5 — legendary stability | 4 — very healthy | 4 — Facebook/meta-backed | 3 — OpenLDAP, quieter |
| **Score** | **32.9** | **30.6** | **26.9** | **25.3** |

**Recommended Default:** **SQLite** (with **SQLCipher** plugin option for encrypted-at-rest stores). SQL is an advantage: audit log queries, memory filters, KG edge traversal filters are all expressible. Single-file = easy backup/port. FTS5 supports full-text search out-of-the-box.

### 3.2 VECTOR STORE (semantic memory, embeddings)

| Criterion | **Chroma (embedded)** | **Qdrant (local mode)** | **FAISS (embedded)** | **pgvector (via SQLite-vss option)** |
|---|---|---|---|---|
| Local-First | 5 | 4 — has server mode but local binary works | 5 | 4 — requires SQLite-vss extension |
| Security | 4 — Python; auditable | 4 — Rust impl, good | 3 — Meta, C++ | 3 — C extension |
| Interface | 5 — simple Python API; filtering | 4 — richer; slightly more complex | 3 — raw index, no metadata filter | 4 — SQL queries with vector ops |
| Performance | 3 — OK for <1M; Python overhead | 5 — Rust, HNSW, excellent | 4 — good for pure similarity | 3 — nascent for SQLite |
| Maintainability | 4 — decent; rapid iteration | 4 — good | 3 — low-level | 3 — niche |
| Cross-Platform | 5 | 4 | 4 | 3 |
| Longevity | 3 — startup-backed; pivots possible | 4 — stable Rust core | 5 — Meta industry standard | 3 — experimental |
| **Score** | **29.7** | **30.3** | **27.6** | **25.3** |

**Recommended Default:** **Qdrant (local mode)** — Rust-based, HNSW indexing, native filtering, metadata-rich, embeddable, strong Windows support. Chroma as fallback plugin. FAISS as advanced high-performance path.

### 3.3 KNOWLEDGE GRAPH STORE

| Criterion | **SQLite (Edge Table + JSONB)** | **Neo4j (local)** | **Apache Age (Postgres)** | **NetworkX (in-mem + SQLite persist)** |
|---|---|---|---|---|
| Local-First | 5 | 3 — JVM required; heavy | 2 — Postgres required | 5 |
| Security | 5 | 3 | 3 | 5 |
| Interface | 3 — manual SQL; no Cypher | 5 — Cypher industry standard | 4 — Cypher over PG | 2 — programmatic only |
| Performance | 3 — adequate for <100k nodes | 5 — excellent | 4 — good | 2 — in-memory; not for 1M+ |
| Maintainability | 5 | 3 | 3 | 5 |
| Cross-Platform | 5 | 3 | 2 | 5 |
| Longevity | 5 | 4 | 3 | 5 |
| **Score** | **30.9** | **28.0** | **23.7** | **30.2** |

**Recommended Default:** **SQLite edge tables with NetworkX hybrid.** Keep the KG primary store in SQLite (zero new operational dependency, easy backup). Use NetworkX for in-memory traversals, algorithms, link prediction; persist snapshots back to SQLite. Add Neo4j plugin as an advanced (≥1M node) option with Cypher support. Trade-off: lose native Cypher for zero operational overhead; accept that Cypher queries can route through a plugin layer.

---

## 4. AI KERNEL — PROVIDERS & ROUTING

The AI Kernel defines one interface: `LLMProvider`. Provider plugins are independent modules. Recommended **first-implemented** providers:

| Provider Plugin | Use Case Priority | Milestone |
|---|---|---|
| **Ollama (local)** | Local-first privacy-sensitive workloads; fallback when offline | M03 |
| **OpenRouter (multi-provider cloud)** | Cloud routing; 100+ models via single-key API; cost/latency arbitrage | M03 |
| **Groq** | High-throughput, low-latency tasks (planning, tool-use loops) | M03 |
| **vLLM (self-hosted local)** | High-throughput local for GPU-heavy workstations | M03 (skeleton; fully tuned by M08) |
| **Direct OpenAI / Anthropic / Google** | Optional direct plugins for users who want native SDKs instead of OpenRouter routing | M03 (skeleton) |

### Embedding Model Plugins

| Provider Plugin | Priority | Rationale |
|---|---|---|
| **sentence-transformers (local)** | P0 | Local, no API key, excellent for privacy; default embedding |
| **Ollama (embed endpoint)** | P1 | Unified with local LLM provider for simplicity |
| **OpenRouter (multi-embed)** | P1 | For users who prefer cloud embeddings with model choice |

### Structured Output Enforcement

**Recommended:** Pydantic v2 + `instructor` library (as plugin, not hardcoded). Rationale: instructor supports function-calling, JSON mode, and retry-with-validation loop across all major providers via unified interface. Alternative: PydanticAI — evaluated before M03; switch if it provides better structured retries.

---

## 5. SANDBOX & ISOLATION

| Criterion | **Docker (container)** | **Firecracker (microVM)** | **Python Restricted + Subprocess Jail** | **Process + OverlayFS (bubblewrap/runsc style)** |
|---|---|---|---|---|
| Local-First | 3 — requires Docker Desktop on Windows | 2 — heavy lift on Windows | 5 — pure stdlib-ish | 4 |
| Security | 4 — solid for workloads; escape CVEs happen | 5 — strong isolation KVM boundary | 2 — Python sandbox is leaky | 4 — strong if implemented correctly |
| Interface | 4 — container APIs | 2 — complex | 5 — trivial API | 3 — more plumbing |
| Performance | 3 — cold start 1-5s | 3 — cold start 100-500ms but KVM req | 5 — ms cold start | 4 — sub-100ms cold start |
| Maintainability | 4 — well-understood | 2 — advanced ops | 4 | 3 |
| Cross-Platform | 4 — works on Windows via WSL2/Hyper-V | 1 — Linux-only effectively | 5 | 3 — Windows requires custom solution |
| Longevity | 5 — industry standard | 4 — AWS-backed | 3 — no one ships pure-Python jail as trust boundary | 4 — gVisor, systemd are mature patterns |
| **Score** | **29.4** | **21.5** | **29.5** | **28.3** |

**Recommended Default — TIERED SANDBOX (progressive):**

| Sandbox Tier | Use Case | Implementation |
|---|---|---|
| T1 — Python Restricted Eval | Pure Python tool code with no external imports, AST-limited | Restricted AST interpreter + resource limits (CPU time, wall time, recursion) |
| T2 — Subprocess + Resource Limits | CLI tools, generated shell scripts | subprocess with cwd scoped to temp overlay dir, ulimits/Job Objects on Windows, network default-deny, Windows Job Objects / systemd-run / launchd depending on OS |
| T3 — Docker Container | Untrusted generated code requiring full OS, many deps | Docker (Windows: WSL2 backend) with read-only FS except scratch volume, network ACL, CPU/mem caps |
| T4 — Firecracker / Kata | Advanced: high-risk long-running generated workloads | Optional plugin; Linux-only initially; gated behind explicit user approval |

Rationale: T1 + T2 cover 90% of auto-harness and generated-tool workloads with ms-scale cold start and zero extra install. T3 covers everything else. Firecracker as advanced plugin, not required.

---

## 6. EVENT BUS & QUEUEING

| Criterion | **In-process (pubsub + SQLite append-log)** | **Redis Streams** | **RabbitMQ** | **NATS** |
|---|---|---|---|---|
| Local-First | 5 | 2 — requires server | 2 — requires server | 3 — embeddable NATS Server possible, but add-on |
| Security | 5 | 3 | 3 | 3 |
| Interface | 4 | 4 | 4 | 5 |
| Performance | 4 (≤10k events/s; enough for single-user) | 5 | 4 | 5 |
| Maintainability | 5 | 3 | 3 | 3 |
| Cross-Platform | 5 | 3 | 3 | 3 |
| Longevity | 4 (custom code) | 5 | 5 | 4 |
| **Score** | **32.2** | **26.8** | **25.9** | **28.4** |

**Recommended Default:** **In-process typed pub/sub + SQLite append-log for durable topics.** AEGIS is single-user; 1,000 events/sec peak is more than enough. No extra network service = zero operational complexity. Add Redis Streams plugin for advanced multi-worker scenarios (M20: Multi-Worker Society) if/when needed.

---

## 7. HUMAN INTERFACE — PRIMARY & DESKTOP UI

### 7.1 First-Class Text Interface (M02)

**Recommended:** **Textual (Python TUI)** for terminal-based control center. Rich CLI via **Typer / Click**. Rationale: both are Python (matches primary language), Textual gives beautiful terminal UI with low effort, no browser engine needed.

### 7.2 Desktop Control Center UI (M22)

| Criterion | **Tauri 2 + React/TS** | **Electron + React/TS** | **PySide6 / Qt** | **Dear ImGui** |
|---|---|---|---|---|
| Local-First | 5 | 3 | 5 | 5 |
| Security | 5 — Rust core + minimal webview; sandboxed IPC | 2 — historically bad security posture | 4 | 4 |
| Interface Richness | 5 — full React ecosystem | 5 | 4 — widget toolkit, less webby | 2 — debug UI only |
| Performance | 5 — tiny binary, fast boot, low RAM | 2 — 300MB+ idle common | 3 — solid Qt perf but C++/bindings overhead | 5 — fastest |
| Maintainability | 3 — TS + Rust, two-language cost | 4 — TS-only, huge ecosystem | 4 — Python-only, but Qt quirks | 2 — C++; hard for complex UI |
| Cross-Platform | 4 — Tauri 2 Win is solid | 5 | 5 | 5 |
| Longevity | 4 — young but healthy | 5 — defacto standard | 5 — Qt commercial support | 3 — niche for end-user UI |
| **Score** | **31.8** | **28.5** | **31.4** | **25.3** |

**Recommended Default:** **Tauri 2 + React/TypeScript (desktop UI only).** AEGIS core is still pure Python+Rust. Tauri provides native desktop shell, system tray, secure IPC between frontend (React/TS in webview) and backend (Rust sidecar or IPC to Python core). This keeps the security story strong (Tauri Rust core, minimal webview attack surface) and UI ecosystem rich (React). Desktop UI ships in M22 only — not required for M02–M21.

### 7.3 Voice System (M13)

- **STT (local):** faster-whisper (CTranslate2) or Whisper.cpp via Python bindings. Local-first default.
- **STT (cloud):** Optional plugin via OpenRouter / Deepgram for higher accuracy with non-sensitive audio.
- **TTS (local):** piper / Coqui TTS (local, fast, private).
- **TTS (cloud):** Optional plugin — ElevenLabs, OpenAI TTS via OpenRouter.
- **Hotword / VAD:** Porcupine (wake word) + WebRTC VAD.

### 7.4 Browser OS (M10)

- **Engine:** Playwright (cross-browser, excellent automation APIs, typed).
- **Isolation:** Per-context browser contexts, persistent vs. ephemeral profiles, cookie scoping, network ACL via proxy.
- **Page Intelligence:** DOM extraction, accessibility tree, screenshot + OCR fallback.

### 7.5 Computer Control (M09)

- **Windows:** Win32 API via pywin32 + UI Automation API + screen capture via DXGI Desktop Duplication.
- **OCR:** Tesseract 5 (local) or RapidOCR (ONNX, local, fast).
- **Cross-platform fallback:** PyAutoGUI (for quick prototyping only; never as the primary trusted path).

---

## 8. TESTING, BUILD, CI/CD TOOLING

| Category | Recommended Default | Rationale |
|---|---|---|
| Python test runner | **pytest** + **pytest-asyncio** + **hypothesis** (property-based) | Industry standard; plugins rich; async first class |
| Python type | **mypy --strict** (enforced on CI); **ruff** for lint | Type strictness is security boundary |
| Python format | **ruff format** | Single tool, fast, black-compatible |
| Rust test | cargo test; **cargo nextest** for speed | clippy deny-warnings; miri for unsafe |
| Rust format/cov | rustfmt; cargo-llvm-cov | Standard Rust toolchain |
| Lockfiles/deps | **uv / Rye** for Python (fast, lockfiles); **cargo** for Rust | Deterministic builds; SBOM generation later |
| Task runner | **justfile** (cross-platform Make equivalent) | Windows-native; one-command workflows |
| CI (M23 prod hardening) | **GitHub Actions** (self-hosted runner optional) | Prompt 01-22: local-only `just test`; M23: add GHA |
| SBOM/sca | **pip-audit** + **cargo audit** + **syft** (SBOM generation) | M23 production hardening milestone |

---

## 9. RECOMMENDED STACK SUMMARY — INITIAL IMPLEMENTATION ORDER

```
LANGUAGE / RUNTIME
  Primary: Python 3.12+ (mypy --strict, ruff, uv lockfiles)
  Perf/Security Hotspots: Rust 1.75+ (PyO3 FFI into Python)

PERSISTENCE (behind L2 interfaces only)
  KV/Document/Audit: SQLite 3.45+ (SQLCipher encryption option)
  Vector:             Qdrant (local mode, Rust)
  Knowledge Graph:    SQLite edge tables + NetworkX in-memory traversal

AI KERNEL PROVIDERS (plugins)
  Local:   Ollama (P0) · vLLM (P1)
  Cloud:   OpenRouter multi-key (P0) · Groq (P0) · Direct OA/Anthropic/Google (P1)
  Embeddings: sentence-transformers (P0 local) · Ollama embed (P1)
  Structured Output: Pydantic v2 + instructor-style retry/validation loop

SANDBOX (tiered)
  T1 = Restricted Python AST evaluator
  T2 = Subprocess + Job Objects/WSL2 limits + scoped temp dir + network deny
  T3 = Docker container with read-only FS + caps/network ACL (Windows: WSL2 backend)
  T4 = Firecracker/microVM (optional advanced plugin)

EVENT BUS
  In-process typed pub/sub + SQLite append-log for durable topics. No Redis required.

HUMAN INTERFACE
  Text (M02): Textual TUI + Typer CLI
  Desktop UI (M22 only): Tauri 2 + React/TS (non-blocking, zero JS in core runtime)
  Browser (M10): Playwright
  Voice (M13): faster-whisper local STT + piper local TTS + Porcupine hotword
  Computer Control (M09): Windows: Win32/UIA/DXGI Desktop Duplication · RapidOCR

TOOLING
  Python: pytest · mypy --strict · ruff · uv
  Rust:   cargo test · clippy deny · rustfmt · cargo-llvm-cov
  Tasks:  justfile
  SBOM:   pip-audit · cargo audit · syft (M23)
```

---

## 10. VALIDATION GATES BEFORE M02 COMPLETION

Before Prompt 02 is declared done, the recommended stack is validated via concrete benchmarks:

1. **Core Runtime FFI overhead:** Python ↔ Rust roundtrip call p95 < 50µs. If not, switch FFI strategy.
2. **SQLite + SQLCipher:** 10k audit log writes < 2s single-thread; encrypted backup/restore works.
3. **Qdrant local mode:** 100k 1024-dim embeddings insert < 60s; 1k similarity queries p95 < 200ms.
4. **Sandbox T2 (Windows):** Generated script in temp dir cannot read arbitrary paths outside its overlay; cannot make network calls by default. Confirmed by attack-attempt test suite.
5. **Memory footprint:** Core Runtime idle (no models loaded) < 500MB Python+Rust combined.

Failures trigger re-evaluation of the affected technology choice. No silent "we'll fix it later" on P0 stack selections.

---

*End of Document 03_TECH_STACK.md*
