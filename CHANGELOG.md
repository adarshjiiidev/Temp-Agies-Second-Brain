# TEMPORARY AEGIS — CHANGELOG

## [1.0.0] - 2026-09-13
### Added
- **All 9 Projects & Dev Repos Integrated:** Added `aegis-dashboard`, `Aegis`, `chrome-extra`, `repusense`, `world-viewer`, `DeepSeek-V3`, `hermes-agent`, `openclaw`, and `opencode` to Obsidian Vault (`1-Projects/` and `agies/PROJECTS/`).
- **OpenCode Agent Integration:** Wired `/home/adarshjii/.opencode/bin/opencode` into PTY manager (`agent_pty.py`), `AgentTabs.tsx`, and `AGENT_REGISTRY.json`.
- **Harness Reliability:** Rewrote `backend/openclaw_harness.py` and `backend/deepseek_harness.py` with robust SSE streaming chunk collectors and verified 9Router model matrix (`gemini/gemini-3.7-flash`, `gemini/gemini-3.6-flash`, `gemini/gemini-3.8-flash`).
- **Universal Agent Runner:** Created `backend/agent_runner.py` for headless and test-mode agent launching.
- **Vision Engine Subsystem:** Created `backend/vision_engine.py` with safe camera capture (`/dev/video0`), hard killswitch (`HARD_DENY`), Wayland screen capture (`grim`), and deterministic OCR (`tesseract`).
- **Computer Control Subsystem:** Created `backend/computer_control.py` supporting Wayland typing (`wtype`) and clipboard (`wl-copy`/`wl-paste`).
- **AgentMoe Operational Fabric:** Created `backend/agent_moe.py` supporting capability discovery and 8 specialized worker roles.
- **Systematic File Reader Engine:** Implemented recursive workspace crawler, `/api/files/tree`, `/api/files/read`, and `systematic-file-reader` skill for Agies.
- **Documentation Suite:** Generated all 11 technical architecture and audit specifications in `docs/` and `.temporary-aegis/docs/`.
- **Systemd Automation:** Verified auto-start and background execution of `aegis-frontend`, `aegis-backend`, `aegis-consolidate.timer`, `aegis-consolidate-daily.timer`, and `9router.service`.
