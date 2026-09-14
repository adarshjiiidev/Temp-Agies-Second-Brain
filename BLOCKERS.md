# TEMPORARY AEGIS — ACTIVE BLOCKERS & HARDWARE LIMITATIONS

**Date:** 2026-09-13  
**Status:** Zero Critical Blockers. Platform limitations properly mapped with deterministic fallbacks.  

---

## 1. Resolved Blockers
1. **Broken OpenClaw & DeepSeek Harnesses:** Resolved. Replaced broken model IDs (`cl/*`) with working 9Router backbones (`gemini/gemini-3.7-flash`, `gemini/gemini-3.6-flash`, `gemini/gemini-3.8-flash`) and implemented robust line-by-line SSE chunk collectors.
2. **Missing OpenCode Integration:** Resolved. Wired `/home/adarshjii/.opencode/bin/opencode` into PTY manager and dashboard tabs.
3. **Missing Projects in Vault:** Resolved. Added all 9 projects and dev repos to `ObsidianVault/memory/1-Projects/` and `ObsidianVault/agies/PROJECTS/`.
4. **Agies Systematic File Reading:** Resolved. Added workspace crawler, `/api/files/tree`, `/api/files/read`, and the `systematic-file-reader` skill.

---

## 2. Platform / Hardware Limitations & Fallback Mappings
1. **Physical GPU Dedicated Memory:** Machine uses Intel Integrated UHD Graphics.
   - *Impact:* Cannot run local 70B+ LLMs locally on GPU VRAM.
   - *Handling:* 9Router handles frontier model routing locally and upstream with zero cold start.
2. **Physical Text-to-Speech (TTS) Engine:** `espeak-ng` and `piper` are not installed on host.
   - *Impact:* Audio playback of synthesized speech is offline.
   - *Handling:* Audio capture (`arecord`, `sounddevice`) and playback (`aplay`, `ffplay`) are verified and operational. Marked as external dependency if speech output is required.
3. **RAM Discipline:** Physical RAM is 7.8 GB (2.5 GB free).
   - *Handling:* Strict context window pruning and transient image/video analysis implemented.
