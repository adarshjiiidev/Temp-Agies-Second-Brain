# PROJECT AEGIS — P07 ARCHITECTURE PLAN

**Milestone:** P07 — Adaptive Intelligence & Personal Environment Learning
**Document type:** Architecture plan ONLY. No implementation code will be written in this session.
**Status:** PLAN — awaiting authorization before implementation.
**Date:** 2026-08-07

> ⚠️ Read this entire document before doing anything. This is the **plan for P07**, not the implementation.
> It is addressed to the next architect/build agent. If a § is marked **DECISION REQUESTED**, do not
> proceed past it without an explicit choice from the project director.

---

## 1. SITUATION SUMMARY (verified)

- AEGIS is a 7-layer, downward-only dependency architecture (L1 → L7).
- L1–L6 are implemented and pass tests. P01–P06 milestones are complete (L1 Core, L2 Foundation, L3 AI
  Kernel, L4 Memory/Knowledge, L5 Execution, L6 Planning).
- L7 HCI/UI is NOT started.
- P07 is the next milestone and touches L4 (memory) and L6 (planning), and introduces new personal
  environment-learning capabilities. It does NOT own L7.
- Verified test state: full suite **793 passed** (system `python`, pytest 8.3.3); **782 passed** (`.venv`,
  pytest 9.1.1 + pytest-anyio). The difference is purely L1/L2 anyio-parametrized collection (57 vs 46);
  layer counts are otherwise identical (L3=256, L4=130, L5=103).
- L5 execution-suite hang was fixed (STAB-01, verified). Full suite terminates in ~8–11s.

---

## 2. P07 SCOPE (from master directive §16)

P07 = **Adaptive Intelligence & Personal Environment Learning**.

### 2.1 Planned capability areas
- Environment model graph
- Environment scanners (bounded, safe, opt-in)
- Application discovery
- Project discovery
- CLI discovery
- Environment relationships
- Optional behavior observers
- Workflow inference
- Preference learning (CANDIDATE only — no automatic T5 promotion)
- Privacy zones
- Freshness tracking

### 2.2 Success criteria (target)
- **95%** application discovery against ground truth.
- **≥ 8 / 10** synthetic workflows detected.
- Preference **candidate** creation WITHOUT automatic promotion to T5 (memory tier).
- **Zero** privacy-zone leakage.
- **Zero** records remaining after observer shutdown.

### 2.3 Hard exclusions (do NOT do in P07)
- Do NOT implement the full agent swarm / subagents (§11, §24).
- Do NOT implement self-modification beyond explicit, gated, reversible changes (§12).
- Do NOT replace L4 memory architecture (§13) — extend it, do not create a parallel memory system.
- Do NOT build the HCI (L7) UI.
- Do NOT blindly rewrite existing hardcoded intelligence; document + migration-plan instead (§5, §9).

---

## 3. ARCHITECTURAL PRINCIPLE FOR P07 (from §3, §15)

> **AI decides what should happen; deterministic infrastructure guarantees what is allowed to happen.**

- **Privacy = deterministic invariant.** Never delegated to AI.
- **Observation is opt-in, pausable, privacy-zone aware, retention-limited, locally controlled.**
- Scanner + observer writes insurance walked.

### 3.1 Deterministic (guaranteed) in P07
- Permissions, consent, privacy zones
- Observer start/pause/stop lifecycle
- Retention limits + expiry
- Audit log of all observations
- Scanner bounds (depth, size, paths)
- Data tiering (P0…) before any model is invoked
- Candidate editing is NEVER auto-promoted without explicit action

### 3.2 AI / learned in P07 (open-ended, gated)
- Workflow inference (label patterns over observed sequences)
- Preference candidate generation (from raw observation)
- Environment relationship suggestion
- Ambiguity detection / intent classification (reuse L6)

---

## 4. LAYER PLACEMENT

P07 lives in L4 (memory/knowledge) and coordinates with L6 (planning) and L5 (execution). It must NOT
add upward dependencies (L7 must never import P07).

```text
        L6  Planning ────────────────────────► (consumes environment/knowledge)
              ▲
              │
        L4  Memory / Knowledge ◄── P07 used tier:
              │          ▲
              │          │ proposed, opt-in scans
        L3  AI Kernel ◄──┘ provider-neutral
              ▲
              │
       L2/L1   deterministic sandbox + permission primitive (bounded subprocess)
```

Key placements:
- New packages under `src/aegis/l4_memory/knowledge/…` or a new distinct package, respecting existing L4
  structure (see §4.5 of `02_ARCHITECTURE.md` + `04_repo structure`). CONFIRM existing paths before deciding.
- Observers that execute OS-level stuff must marshal through **L5 execution sandbox primitives**, never
  unbounded work, and obey `max_seconds`/resource caps (recent precedent: lazy FS search fix + `max_seconds=10`).

---

## 5. COMPONENT PROPOSAL — BUILDING BLOCKS

> Mark = **[N]** required, **[M]** optional, **[DEFER P08+]**.

### 5.1 Environment model graph
- Type: layered, typed node graph (JSON-persisted, versioned).
- Nuclei: `hardware`, `os`, `applications`, `projects`, `repositories`, `files`, `workspaces`, `devices`,
  `tools`, `accounts`, `dev_environments`.
- Relationships (typed edges): `uses`, `contains`, `deploys_through`, `runs_on`, etc.
- Provenance + freshness timestamp per node/edge.
- Persisted in the existing L4 memory store, NOT a new parallel DB. **[DECISION REQUESTED]** confirm
  whether to reuse the memory registry vs a sibling store (see §13 confidentiality note; do not diverge
  from canon).

### 5.2 Scanners (all bounded, opt-in)
- Application discovery — scan known dirs + OS app sources (PATH). **95% ground-truth** target.
- Project discovery — scan configured roots for VCS/manifest markers.
- CLI/tool discovery — inspect shell rc + installed bins.
- Environment relationship inference — version matcher (e.g., project → py env / db).
- Freshness tracker — schedule + last-scan per target, bounded frequency.

Each scanner = interface with deterministic caps and a dry-run/no-op default in offline/denied state.

### 5.3 Optional behavior observer
- Records coarse typed events (start app, open file, run task) — **opt-in, privacy zones filter first**.
- Locally stored, retention-limited, audit-logged, expirable.
- Feeds workflow inference (offline, local model or heuristic) and preference **candidate** generator.
- Shutdown = guaranteed removal of transient/candidate records (per §2.2: zero leftover).

### 5.4 Workflow + preference inference (AI-gated)
- Workflow inference: sequence → label → template. Deterministic **fallback** exists and is explicitly marked
  fallback (do not present heuristic as the primary intelligence).
- Preference inference: raw → candidate. **STOPS at candidate.** No T5 promotion without explicit action.

### 5.5 Privacy zone
- Declarative zones (paths, apps, P0/P1 tiers) enforced **before** data touches memory.
- Filter applied in scanners + observer at ingestion boundary only.

---

## 6. ARCHITECTURAL MAP (repo-context for L4/L6)

> Fill after `04_REPOSITORY_STRUCTURE.md` + `src/aegis/l4_memory/**` inspection. Do not fabricate modules by
> name from docs; verify each with a file read.

```
src/aegis/
  l4_memory/
   (existing registry/knowledge store)        <= hook P07 entities here
   p07/
     model/        types + graph + relations
     scanners/     app*, project*, cli*, relation*, freshness
     observer/     events, lifecycle, expiry, audit
     inference/    workflow*, preference candidates (L-math), deterministic fallback
     privacy/       zones, redaction, retention policy
     persistence/   graph + candidate storage via L4 API
     discovery/     opt-in consent, offline switch, env // bounded-command runner
   l6.../          planning consumes relations (read-only)
```

> Refine to REAL tree before deciding component boundaries (§7 THE CROWD)
> Do not create parallel memory systems (section 13 master directive).

---

## 7. DEPENDENCY + PRIVACY CHECKLIST

### 7.1 Dependency rules
- No upward import from P07 to L7.
- P07 imports L4 APIs + L5 sandbox executor (bounded) + L3 provider-neutral interface only.
- New packages must be added to import-linter contracts (see docs).

### 7.2 Privacy/intent gate — apply to every P07 component:
1. opt-in flag present
2. consent recorded + revocable
3. privacy-zone filter first
4. retention + freshness set
5. audit log entry
6. offline/denied → no-op deterministic exit

---

## 8. KNOWN RISKS / DECISIONS NEEDED

| # | Item | Recommendation | Ask |
|----|------|---------------|-----|
| R1 | Scanner safety (bounded exec) | reuse L5 sandbox with caps | approve |
| R2 | Offline cap/fallback behavior | degrade gracefully; explicit fallback label | approve |
| R3 | Graph persistence location | reuse L4 store (no parallel) | DECISION REQUIRED |
| R4 | Preference promotion scope | candidate only; no auto-T5 | approve |
| R5 | Observer storage collapse point | ephemeral local, expiring | approve |
| R6 | Volume/retention default | bounded default caps | approve |
| R7 | New deps (env scan libs) | prefer stdlib; no new heavy scan | DECISION REQUIRED |

---

## 8. SUCCESS TEST PLAN (target)

- **Discovery correctness:** build ground truth fixture; app discovery ≥ 95%.
- **Workflow:** run 10 synthetic workflow transcripts; detector ≥ 8/10.
- **Preference:** inject raw logs → candidates only; assert none auto-promoted.
- **Privacy:** set P2 zone; verify ≤ leaks (0) across discovery+observer.
- **Observer shutdown:** start→stop observer; assert zero retained transient records.
- **Offline:** full run with no network/local-model → graceful bounded behavior.
- **Audit:** all observations produce + auditable records.

Tests belong to layer L4 (and L6 for planning integration). Each subsystem tested:

---

## 8. EXECUTION/SHIP PLAN (for build agent when authorized)

1. Read this doc + `docs/09_ROADMAP.md` + `docs/AEGIS_MASTER_AUDIT.md` + inspect real `src/aegis` tree.
2. Produce the concrete inventory/maps for §5 components against the REAL tree; do not invent names.
3. Present architecture + dependencies for approval (find `03_TECH_STACK`, `05_SECURITY`, `06_MEM`).
4. On approval: implement in order — privacy boundary first → shape → scanners → observer → inference candidates
   → audit/expiry → close tests.
5. Update `.agents/AGENTS.md`, ADR for P07, roadmap status. Verify: full suite (say 793 sys / 782 venv) still
   passes; no upward dependency; no parallel memory.

---

## 9. REPORT TEMPLATE (return after plan — not code)

Fill A–O from §26 of the master directive:

## A. What I verified
## B. Complete
## C. Partial
## D. Broken
## E. Hardcoded
## F. AI-driven
## G. Deterministic-by-design
## H. Missing
## I. Tests
## J. Architecture violations
## K. Technical debt
## L. Files modified
## M. Docs updated
## N. Remaining roadmap
## O. Exact next action

---
*PRINCIPAL SYSTEM ARCHITECT — P07 PLAN. Implementation happens only after explicit director authorization.*