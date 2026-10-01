# AEGIS VISION & TURBOQUANT ROADMAP

## VERIFIED_BACKBONE
The following systems were certified in the previous phase and MUST remain fully operational:
- Security (127.0.0.1 Binds, Strict CORS, Token Auth)
- Agent MoE & Hierarchical Planner
- L5 Governance
- Memory & Knowledge Graph
- Browser & Research Engines
- API Endpoints (Intelligence, Projects, Skills)

---

## Phase V0: Environment Discovery
- **Status:** COMPLETE
- **Findings:** `python3`, `ffmpeg`, `v4l2-ctl`, `nmap` available. `cv2` missing. `arp-scan` missing.

## Phase V1 & V2: TurboQuant Research & Implementation
- **Status:** NOT_CONFIGURED
- **Rationale:** Genuine TurboQuant (QJL transform + random rotation) requires Qdrant 1.18+ or the compiled `turbovec` C++ library. No lightweight local Python equivalent officially exists. Faking it with a local JSON vector store violates the Absolute Rule. Therefore, we explicitly mark this as NOT_CONFIGURED and rely on the existing CognitiveMemoryEngine.

## Phase C0: Camera Architecture Review
- **Status:** IN_PROGRESS
- **Goal:** Ensure DISCOVERY != AUTHORIZATION principle is strictly adhered to in `camera_registry.py`.

## Phase C1: Real Camera Discovery
- **Status:** BACKLOG
- **Goal:** Implement local `/dev/video*` and `nmap` network scanning.

## Phase C2: Camera Authorization
- **Status:** BACKLOG
- **Goal:** Enforce `DISCOVERED -> AUTHORIZED` state transitions and wire into L5 Governance.

## Phase C3: Stream Manager
- **Status:** BACKLOG
- **Goal:** Real frame capture via `v4l2` or OpenCV.

## Phase C4: OpenCV Engine
- **Status:** BACKLOG
- **Goal:** Real motion detection and event processing.

## Phase C5: Dashboard Camera Center
- **Status:** BACKLOG
- **Goal:** Live status, APIs, and CLI integrations.
