# AEGIS Documentation Index

**Location:** /home/adarshjii/Projects/Aegis/docs/
**Total:** 20+ documents

---

## Core Documents

### Vision & Requirements
- [[AEGIS_DOCS/00_VISION]] — Project vision, guiding constraints
- [[AEGIS_DOCS/01_REQUIREMENTS]] — Requirements specification

### Architecture
- [[AEGIS_DOCS/02_ARCHITECTURE]] — Layer architecture, component maps, flow diagrams
- [[AEGIS_DOCS/03_TECH_STACK]] — Technology choices and rationale
- [[AEGIS_DOCS/04_REPOSITORY_STRUCTURE]] — Repository layout, conventions

### Security & Privacy
- [[AEGIS_DOCS/05_SECURITY]] — Security model, privacy boundaries, risk register (9+ risks)

### Memory & Intelligence
- [[AEGIS_DOCS/06_MEMORY]] — Memory and knowledge architecture (9 tiers)
- [[AEGIS_DOCS/07_AI_STRATEGY]] — AI strategy, model selection approach

### Operations
- [[AEGIS_DOCS/08_CAPABILITY_DISCOVERY]] — Capability discovery process
- [[AEGIS_DOCS/09_ROADMAP]] — 23-prompt milestone roadmap
- [[AEGIS_DOCS/10_RISKS]] — Risk register with mitigations

### Prompt Completions
- [[AEGIS_DOCS/11_PROMPT_02]] — Prompt 02 (L1+L2) completion details

### Audit & State
- [[AEGIS_DOCS/AEGIS_MASTER_AUDIT]] — Master audit report (authoritative, 2026-08-07)
- [[AEGIS_DOCS/PROJECT_AEGIS_CURRENT_STATE]] — Current state (partially outdated)
- [[AEGIS_DOCS/P07_ARCHITECTURE]] — P07 memory scanner architecture plan

---

## Key Findings from Master Audit

1. **L1-L6 implemented + redesign packages present** — far ahead of documentation
2. **Full test suite hangs at L5** — STAB-01 fix applied 2026-08-07
3. **Redesign packages broken** — KernelReasoningProvider calls non-existent methods
4. **Rust crates don't compile** — missing deps, syntax errors
5. **Import-linter contracts stale** — reference old package names
6. **8 commits, all "Initial Commit"** — no commit message narrative

---

*See also: [[Aegis]], [[Aegis Architecture]]*
