# Temporary AEGIS → Production AEGIS Migration Roadmap

---

## 1. Current State (Temporary AEGIS)
- Operates on host machine with user systemd units:
  - `aegis-frontend.service` (Vite SPA on `:2981`)
  - `aegis-backend.service` (FastAPI + PTY bridge on `:8787`)
  - `aegis-consolidate.timer` (15-min background sync)
  - `9router.service` (Model gateway on `:20128`)
- Ingests memory into `/home/adarshjii/ObsidianVault/`
- Employs AgentMoe capability fabric for vision, OCR, computer control, and multi-agent harnesses.

---

## 2. Production AEGIS Target Architecture (7-Layer AI OS)
- **Layer 0 (Hardware & Kernel):** Direct kernel scheduler interfaces, eBPF telemetry hooks, dedicated neural NPU integration.
- **Layer 1 (Memory Engine):** Native Rust vector index + semantic graph database replacing flat markdown sync for sub-millisecond retrieval.
- **Layer 2 (Model Gateway):** Local dynamic MoE orchestration with speculative decoding across GPU/NPU.
- **Layer 3 (Agent Core):** Rust-native AgentMoe actor runtime with deterministic state machines.
- **Layer 4 (Tool & Sandbox):** WebAssembly (WASM) capability sandboxes isolating third-party tools.
- **Layer 5 (Interface Plane):** Native desktop control plane with sub-millisecond frame rendering and spatial visual overlays.
- **Layer 6 (Governance & Alignment):** Cryptographically signed capability tokens and audit chains.

---

## 3. Migration Milestones
1. **Milestone 1:** Memory schema stabilization (Completed with Obsidian PARA + agies living memories).
2. **Milestone 2:** Harness unification (Completed with OpenClaw, DeepSeek R1, OpenCode, Hermes, Codex under 9Router).
3. **Milestone 3:** Native Rust kernel core (`Projects/Aegis`) integration.
4. **Milestone 4:** Full WASM capability sandboxing.
