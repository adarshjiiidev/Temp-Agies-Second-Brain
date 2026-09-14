# [[[Projects/world-viewer]]]

**Status:** Built
**Priority:** Medium
**Type:** Desktop Application (Electron)
**Last Updated:** 2026-09-12

---

## Overview

Electron-based desktop application for viewing world data/information. Has extensive AI integration via large prompt.md file (44KB).

**Location:** [[Projects/world-viewer]]
**Repository:** /home/adarshjii/Projects/world-viewer

---

## Architecture

- **Framework:** Electron
- **Language:** TypeScript/JavaScript
- **Structure:**
  - `electron/` — Electron main process code
  - `build/` — Build configuration
  - `dist/linux-unpacked/` — Built application output
  - `public/` — Static assets
  - `prompt.md` — 44KB extensive AI interaction prompts
  - `context.md` — Application context

---

## Technology Stack

- Electron (desktop framework)
- TypeScript/JavaScript
- Large dependency tree (32,612 lines in package-lock.json)
- Electron-builder (inferred from dist/ structure)

---

## Current State

- **Last Commit:** 371d443 (Complete Build)
- **Uncommitted Changes:** dist/ build output added
- **Status:** Built and packaged
- **Codex Trusted:** Yes (configured in Codex settings)

---

## Key Observations

### prompt.md (44KB)
This is unusually large for a prompt file. It likely contains:
- Detailed instructions for AI interaction
- Behavior guides for integrated AI features
- System prompts for AI-assisted functionality
- Possibly the "personality" or behavior specification for an AI agent within the app

### context.md
Provides context for the application — likely describes what world-viewer does and how it works. Useful for understanding the application's purpose.

---

## Knowledge Gaps

- [ ] What is world-viewer's actual purpose?
- [ ] What AI features does it have?
- [ ] What's in the prompt.md (beyond knowing it's 44KB)?
- [ ] Is there active development or is it feature-complete?

---

*See also: [[1-Projects]], [[MOCs/AI-Development]]*
