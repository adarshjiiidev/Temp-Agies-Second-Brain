<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# AEGIS Dashboard & Second Brain OS Agent Guidelines

## 1. Zero 9Router Dependency
- **All 9Router references and ports (:20128) are completely removed.**
- Model routing is 100% powered by the multi-provider free engine (`backend/free_router.py`), balancing across OpenRouter free tier, Groq Cloud, and local LM Studio.
- The default model in all chat and reasoning harnesses is always `auto` with round-robin failover.

## 2. Vault Explorer & Obsidian Knowledge Graph
- Vault Explorer provides dual views:
  1. **Constellation Graph (`ObsidianGraph.tsx`)**: High-performance interactive force-directed graph mapping Obsidian PARA notes, wikilinks, and cluster relationships with galaxy starfields and photon energy pulses.
  2. **Spatial Memory Canvas (`SpatialMemoryCanvas.tsx`)**: Organic card-and-wire board for architectural entities and domain hubs.
- Every note in the graph must be clickable to instantly open in the Vault Explorer viewer/editor.

## 3. UI Aesthetics & Responsive Standards
- Rich dark-mode glassmorphic styling with subtle glow borders (`#0e0e11`, `#050608`).
- Smooth physics, no jitter, accurate bounding-box view fitting, and zero offset disconnect bugs.
- Every interactive element has descriptive accessibility labels, tooltips, and keyboard accessibility.

