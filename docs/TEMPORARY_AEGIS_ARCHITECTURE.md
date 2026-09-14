# TEMPORARY AEGIS — COMPLETE SYSTEM ARCHITECTURE

**System Designation:** Temporary AEGIS Personal AI Operating System  
**Host Environment:** Arch Linux (`Linux 7.2.3-arch1-3-x86_64`)  
**Architecture Classification:** 7-Layer Adaptive Cognitive Control Plane  

---

## 1. System Topology

```
                         USER (Adarsh Jii)
                                │
                                ▼
                       TEMPORARY AEGIS
                                │
       ┌────────────────────────┼────────────────────────┐
       ▼                        ▼                        ▼
     BRAIN                    MEMORY                  CONTEXT
  (Orchestrator)        (Obsidian PARA Vault)       (PC Telemetry)
       │                        │                        │
       └────────────────────────┼────────────────────────┘
                                ▼
                           ORCHESTRATOR
                                │
       ┌────────────────────────┼────────────────────────┐
       ▼                        ▼                        ▼
     HERMES                   CODEX                  OPENCODE
  (agies profile)          (OpenAI CLI)           (ACP / MCP CLI)
       │                        │                        │
       └────────────────────────┼────────────────────────┘
                                ▼
                        9ROUTER GATEWAY
                  (http://127.0.0.1:20128/v1)
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
      Gemini 3.7 Flash   Gemini 3.6 Flash  Gemini 3.5 Lite
         (Reasoning)       (Low-Latency)     (Throughput)
                                │
                                ▼
                         AGENTMOE FABRIC
                                │
       ┌────────────────────────┼────────────────────────┐
       ▼                        ▼                        ▼
     TOOLS                   WORKERS                  SKILLS
 (FS, PTY, Git,           (Planner, Coder,         (18 Hermes
  Screen, Camera)          Debugger, Vision)        Workflows)
       │                        │                        │
       ├────────────┬───────────┼───────────┬────────────┤
       ▼            ▼           ▼           ▼            ▼
   COMPUTER      BROWSER      SHELL       CODE        RESEARCH
    CONTROL    (Automated)    (PTY)      (Codex)     (Web Sources)
       │            │           │           │            │
       ▼            ▼           ▼           ▼            ▼
   wtype/wclip   Chrome      xterm.js    9 Repos     Citations
       │
       ▼
     VISION
       │
   ┌───┼───────────┐
   ▼   ▼           ▼
Camera OCR      Screen
(/dev/video0)  (Tesseract)
```

---

## 2. Core Subsystems

### Layer 1: Physical Machine & Hardware Layer
- **CPU & Memory:** 8-core Alder Lake CPU with real-time RAM/Swap monitoring.
- **Display & Input:** Wayland display server (`wayland-1`) with `grim` screen grabbing and `wtype` keystroke simulation.
- **Sensors:** Integrated camera `/dev/video0` (ffmpeg v4l2) and ALC257 analog microphone (`arecord` / `sounddevice`).

### Layer 2: Model Fabric (9Router)
- **Local Gateway:** Port `20128` exposing 870 models.
- **Failover Chain:** `gemini/gemini-3.7-flash` -> `gemini/gemini-3.6-flash` -> `gemini/gemini-3.5-flash-lite`.
- **Protocol:** Robust SSE event-stream chunk collector supporting streaming responses and whole payloads.

### Layer 3: Agent & Orchestration Layer (AgentMoe)
- **Hermes Agent:** Autonomous profile `agies` with 18 skills and 20 tools.
- **Claude Code & Codex:** Terminal-based coding and code-repair agents.
- **OpenCode:** ACP (Agent Client Protocol) and MCP plugin manager.
- **OpenClaw & DeepSeek R1:** Claude-native loop and extended reasoning harnesses.

### Layer 4: Cognitive Memory Layer
- **Hub:** `/home/adarshjii/ObsidianVault/` structured in PARA (`1-Projects`, `2-Areas`, `3-Resources`, `4-Archives`).
- **Living Memory:** `~/ObsidianVault/agies/PROJECTS/` maintaining real-time summaries for all 9 workspace projects.
- **Systematic File Index:** Real-time crawler scanning all source files, line counts, and signatures.

### Layer 5: Operational Tools & Workers
- **Filesystem Engine:** Safe slice reading and non-destructive writes.
- **Computer Vision:** On-demand camera snapshot, privacy filter (hard deny by default), deterministic Tesseract OCR.
- **Computer Control:** Keystroke injection, clipboard synchronization, permission-gated execution.
