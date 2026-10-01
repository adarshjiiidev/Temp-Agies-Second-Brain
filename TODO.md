# AEGIS Overhaul Master Execution Plan (Phase-Wise Stack)

## Phase 1: Complete 9Router Eradication & Free Model Fabric
- [x] **1.1 Backend: Remove 9Router dependency from server.py**
  - Replace `query_9router_chat` with unified free router (`free_router.py`) direct calls.
  - Remove `/api/9router-health` endpoint; add `/api/model-health` backed by free providers.
  - Clean up `/api/models` and `/api/diagnostics/deep` to remove all 9Router status/ports.
  - Remove `9router.service` from systemd service monitors.
- [x] **1.2 Backend: Clean Harnesses & Engines**
  - Update `model_router.py`, `openclaw_harness.py`, `deepseek_harness.py`, `vision_engine.py`, `audio_engine.py`, `aegis_health.py`, `knowledge_graph.py` to remove 9Router branding and hardcoded `20128` port connections.
- [x] **1.3 Frontend: Remove 9Router from UI & Store**
  - `src/lib/api.ts` & `src/lib/store.tsx`: Remove `get9RouterHealth` and rename to `getModelHealth`.
  - `src/components/TopBar.tsx`: Replace 9Router status indicator with "AI Fabric (Free)".
  - `src/components/ModelsPanel.tsx`: Overhaul gateway tab to display OpenRouter / Groq / Free Model Matrix status instead of 9Router.
  - `src/components/ChatPanel.tsx`: Ensure default model is always `auto`, no `union-alpha`, clean provider badges.
  - `src/components/AgentTabs.tsx`: Update harness descriptions.
- [x] **1.4 Phase 1 Documentation Sync**
  - Update `AGENTS.md`, `README.md`, and relevant architecture docs to reflect complete 9Router removal and free router shift.



## Phase 2: Vault Explorer & Obsidian Constellation Graph Overhaul
- [x] **2.1 Backend / API: Real Obsidian Link Resolution**
  - Ensure `/api/obsidian-graph` accurately reads all vault notes, extracts wikilinks `[[target]]`, resolves cross-references, and outputs fully connected nodes & edges.
- [x] **2.2 Frontend: Constellation Graph Core Physics & Rendering (`ObsidianGraph.tsx`)**
  - Implement dynamic force-directed simulation (spring attraction, Coulomb repulsion, central gravity, velocity damping).
  - Constellation visual styling: Rich galaxy background, starfield particles with subtle twinkle, glowing atmospheric halos around star nodes.
  - Edges: Thin starlight lines with glowing photon energy pulses traveling between connected notes.
  - Hub nodes (MOCs, Projects) render with pulsing planetary orbital rings.
  - Interactive dragging: Grab any node to physically stretch the constellation with live spring reaction.
  - Hover highlights: Hovering a node highlights all connected links and adjacent neighbor stars while softly dimming unrelated stars.
  - HUD Card: Sleek glassmorphic card displaying node metadata, category, link count, and quick open action.
  - Click interaction: Clicking any star immediately opens the note in the Vault Explorer file editor.
  - Smooth pan & zoom with bounding box auto-fit on load and reset button.
  - Search & category filter pills with instant star glowing/focus.

## Phase 3: Spatial Memory Canvas Rectification (`SpatialMemoryCanvas.tsx`)
- [x] **3.1 Fix Offset & Coordinate Bugs**
  - Remove the `-2000px` SVG offset bug that disconnected wires from cards.
  - Recalculate wire ports (source right -> target left, top -> bottom) based on actual card bounds.
- [x] **3.2 Layout & Spacing Overhaul**
  - Fix the bunched card positioning by organizing cards into distinct thematic zones (Target & Strategy on Left, Topics & Hubs in Center, Active Projects on Lower Grid, Memory Transcripts in Log Lane).
  - Ensure initial transform centers the content properly in view.
  - Ensure responsive sizing and smooth panning/dragging without jitter.

## Phase 4: Leftover Integrations & AI Action Wiring
- [x] **4.1 Wiring AI Actions**
  - Verify chat session persistence, automatic context injection via `context_router.py`.
  - Verify free model round-robin fallback works reliably under load across OpenRouter / Groq.
- [x] **4.2 Diagnostics & Health Sync**
  - Ensure all system services, agent harnesses, and vault sync endpoints report green.

## Phase 5: Build, Test & Final Verification
- [x] **5.1 Compile & Type-Check**
  - Run `npm run build` and ensure zero TypeScript errors.
- [x] **5.2 Restart & Test Backend**
  - Restart `aegis-backend` service and test `/api/chat`, `/api/obsidian-graph`, `/api/models`.
- [x] **5.3 End-to-End Verification**
  - Verify Vault Explorer graph view renders beautifully without any offset or clustering bugs.

## Phase 6: Professional Obsidian Harmonization & Spatial Canvas Vault Grounding
- [ ] **6.1 Spatial Cards Grounded 100% in Real Obsidian Vault Notes (`SpatialMemoryCanvas.tsx`)**
  - Replace all hardcoded/synthetic cards (`Forward-Deployed Engineering`, `Bay Area`) with real notes from Obsidian vault (`MOCs`, `1-Projects`, `2-Areas`, `3-Resources`, `4-Archives`).
  - Restyle cards to match the exact dark glassmorphic dashboard palette (`#0e0e11`, `#141418`, dark translucent gradients, clean monospace headers, emerald/cyan/violet tags). No white paper cards!
  - Real metadata: Note word count, file size, actual markdown snippets, real wikilinks and backlinks.
  - Clicking "Open Note" opens the real note in the Vault Explorer editor.
- [ ] **6.2 Professional Knowledge Graph Architecture (`ObsidianGraph.tsx`)**
  - Remove all "toy-like" elements: remove artificial sinusoidal oscillation jitter, cartoonish pulsing ripples, and wobbly physics.
  - Implement clean, professional Obsidian force physics with stable energy dissipation (simulates and settles firmly like Obsidian / Gephi).
  - Crisp, elegant typography and minimalist node pinpoints with hierarchy: MOC hubs (clean crisp rings), project roots (solid emerald pins), content notes (hairline celestial nodes).
  - Real-time Obsidian controls: Node Size slider, Link Distance, Force Repulsion, Label Mode (Hubs, All, Hover).
  - Rich Obsidian backlink inspector: Hovering or selecting a node shows exact inbound and outbound wikilinks with direct clickable jumps.
- [ ] **6.3 Phase 6 Documentation Sync**
  - Update `AGENTS.md` and `README.md` to reflect the 100% Obsidian-grounded spatial canvas and professional graph engine.

## Phase 7: agies Knowledge Pack Grounding (seeded 2026-09-27, surfacing pending)
- [x] **7.1 Seed every project + knowledge into TurboQuant + mem0 (`scripts/seed_agies_knowledge.py`)**
  - 20 project entries + 5 knowledge entries (dark-psychology-defense, dark-rom-knowledge, installed-apps, apps-index, about-me). 25 TurboQuant sources, mem0 total 27. Retrieval verified.
- [x] **7.2 `AGIES.md` boot file (mirrored vault ↔ dashboard ↔ temp-aegis) + `docs/AGIES_KNOWLEDGE_PACK.md`**
- [x] **7.3 `backend/config.py` PROJECTS includes non-git roots (Amruthpaan, artemis, SkillOpt, school-netops, Work, netops-backups, qwen-audio-agent, pinokio)**
- [ ] **7.4 Surface pack in UI: Knowledge shortcut row in VaultExplorer + `/knowledge` chat slash command**


