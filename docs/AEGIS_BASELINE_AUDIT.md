# AEGIS BASELINE AUDIT
## Phase 0 Inspection Results
Date: 2026-09-18

### 1. Repository Structure
The `aegis-dashboard` directory contains the frontend (React/Vite), backend (FastAPI), scripts (`aegis_consolidate.py`, `aegis_ingest_all.py`), and documentation in `docs/`.

### 2. Backend Modules
Found 32 python files in `backend/` covering all major domains: memory (`memory_engine.py`), models (`model_router.py`), agents (`agent_moe.py`, `agent_pty.py`), vision (`vision_engine.py`), etc. Config is partially centralized in `config.py`.

### 3. Frontend & Build
Uses standard Vite + React setup (`vite.config.ts`, `package.json`, `index.html`).

### 4. Configuration & Security
- `backend/server.py` binds to `127.0.0.1` by default using config, but CORS and tokens must be verified.
- `backend/config.py` contains some hardcoded paths and `HOME` variable usage.

### 5. Remaining Gap-Closure Issues (Mandatory)
1. CORS wildcard + `0.0.0.0` bind (claimed fixed in old reports, but requires strict verification).
2. Plaintext OpenClaw gateway token.
3. Hardcoded `$HOME/` paths.
4. Failed snapshot/ChatGPT ingest services.
5. 54 hardcoded model IDs.
6. `agent_pty.py` bypasses `AGENT_REGISTRY`.

### Conclusion
Baseline established. The backend architecture is sound but needs strict Phase 1 security hardening and Phase 2 centralization before building higher autonomy features.
