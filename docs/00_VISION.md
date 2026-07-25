# PROJECT AEGIS — MASTER VISION

**Document ID:** AEGIS-DOC-001
**Version:** 0.1.0 (Prompt 01 Foundation)
**Status:** DRAFT — Architecture Phase Only
**Last Updated:** 2026-07-24

---

## 1. EXECUTIVE VISION

AEGIS is a **personal adaptive AI operating system** designed for one primary user. It is not a chatbot, not a collection of hardcoded API integrations, and not a simple autonomous agent.

AEGIS aspires to become:

- A deeply personalized AI companion
- A continuously evolving second brain
- A safe software operator and workflow executor
- A research partner and coding collaborator
- An intelligent interface between the user and their digital/authorized physical environment
- A system that discovers and learns capabilities instead of requiring every feature to be hand-coded

The target experience: the user should eventually be able to say, *"AEGIS, handle this,"* and the system autonomously determines context, capabilities, plan, execution, verification, learning, and improvement.

---

## 2. THE AEGIS PROMISE

### What AEGIS Should Feel Like

> "A continuously learning personal intelligence that lives alongside the user."

### What AEGIS Must Never Feel Like

> "A collection of APIs connected to an LLM."

### The Capability Discovery Imperative

When the user asks for something, AEGIS does **not** hardcode branches like:

```
if user asks Obsidian → call Obsidian API
if user asks GitHub   → call GitHub API
if user asks Browser  → call Browser API
```

Instead, AEGIS follows a discovery and learning pipeline:

```
User Goal
   ↓
Capability Required
   ↓
Search Existing Capability → Search Available Tools → Search MCP Servers
   ↓
Search APIs → Search CLI → Inspect Software → Study Documentation
   ↓
Study Web → Observe UI → Learn Workflow
   ↓
Create or Acquire Capability → Generate Tool / MCP if necessary
   ↓
Test in Sandbox → Auto-Harness → Evaluate → Register Capability
   ↓
Remember How It Works → Use Capability → Reflect → Improve
```

---

## 3. PRIMARY USER MODEL

AEGIS is built for **one user** and learns deeply about that individual:

| Category | Examples |
|---|---|
| Communication | Style, tone, formality, channel preferences |
| Coding | Language preferences, architecture biases, test attitudes, review style |
| Research | Source preferences, depth vs. breadth, citation habits |
| Projects | Organization structure, naming, branching, deployment |
| Software | Preferred apps, keyboard shortcuts, UI layout, plugin choices |
| Workflows | Task decomposition, scheduling, interrupt handling, review cadence |
| Decisions | Risk tolerance, approval style, trade-off preferences |
| Learning | Reading order, note-taking, spaced repetition preferences |
| Goals | Long-term objectives, active projects, milestone tracking |
| People | Important contacts, relationships, collaboration patterns |
| Knowledge | Domain expertise, known concepts, learning gaps |

### Memory Classification — Non-Negotiable

AEGIS **must** classify information into distinct retention tiers and never silently promote observations to permanent memory:

```
Temporary Context ← Session Information ← Important Memories
         ↓                ↓                     ↓
   Ephemeral           Session-scoped        User-validated
   < 1 hour            < session lifetime    Long-term / durable
```

Additional categories with independent retention policies:
- User preferences
- Learned workflows
- Sensitive information (encrypted-at-rest, stricter access)
- Environmental observations
- Project memory (scoped to repository/project)

### User Rights Over Memory

The user must always be able to:
- **Inspect** any memory item with full provenance
- **Correct** memories the system got wrong
- **Delete** any memory or entire categories
- **Export** memory in open, portable formats (JSONL, Markdown, Obsidian Vault)
- **Disable** memory categories or the entire memory system
- **Control retention** (TTL, max items, auto-archive rules)
- **Control what is learned** (allow/deny lists for learning topics)

---

## 4. CORE DESIGN PRINCIPLES

These are architectural laws. They apply to every subsystem and every milestone.

### P1 — One Subsystem at a Time
Fully design, implement, test, and verify a subsystem before moving to the next. Clean milestones. No scope creep across phase boundaries.

### P2 — Clean Boundaries
Every module exposes a stable interface. No internal details leak. Subsystems communicate through the Event Bus or typed interfaces only.

### P3 — Provider Neutrality
Never hardcode one AI provider. The AI Kernel speaks to an abstract LLM interface; providers are plugins. Same for databases, vector stores, browsers, automation.

### P4 — Capability Neutrality
Never hardcode a specific software integration when a generic *capability abstraction* is the correct layer. "Manipulate notes" instead of "call Obsidian." "Interact with Git repo" instead of "run GitHub CLI."

### P5 — Interface First
Define the stable interface (protocol / trait / ABC) before writing a single implementation. Code to the interface, not the concrete class.

### P6 — Security First — Non-Negotiable Pipeline
**Every** action must eventually traverse:

```
Plan → Permission Check → Policy Gate → Execution → Audit → Verification
```

No shortcuts. No "trusted internal paths."

### P7 — Never Trust LLM Output Directly
LLMs produce *suggestions* and *structured requests*. The system validates. Schema validation. Type checks. Permission checks. Sandbox. Audit.

### P8 — Approval Gates for Dangerous Actions
Silent execution of destructive, irreversible, or external-facing actions is forbidden. Approvals are explicit, auditable, and revocable.

### P9 — Never Silently Rewrite the Core
All changes to critical core systems are:
- Versioned
- Tested (automated harness)
- Auditable (change log + diff)
- Reversible (rollback path defined before deploy)
- Optionally user-approved (default: user approval for core mutations)

### P10 — Every Important Action Is Observable
Logs → Events → Metrics → Audit Records. If an action matters, it leaves a trace.

---

## 5. LONG-TERM CAPABILITY DOMAINS

The following domains define the *eventual* scope of AEGIS. **None are implemented in Prompt 01.** They are listed here to ensure the architecture can accommodate them.

| # | Domain | Description |
|---|---|---|
| C1 | Computer Use | File system, terminals, processes, Git, Docker, apps, desktop automation, screen understanding |
| C2 | Browser Use | Web search, research, forms, uploads/downloads, unfamiliar websites, workflow memory |
| C3 | Software Familiarization | Detect software → study docs/CLI/UI → experiment safely → model → tool → test → remember |
| C4 | Coding Intelligence | Repo understanding, code generation/refactor/debug, tests, PRs, delegation to coding agents |
| C5 | Local + Cloud AI | Groq, OpenRouter, Ollama, vLLM, local models, multi-key routing, cost/latency/privacy-aware selection |
| C6 | Second Brain | Projects, docs, PDFs, research, notes, conversations, decisions, experiments, skills, workflows |
| C7 | Knowledge Graph + Obsidian | Entity graph, automatic linking, project pages, daily logs, human-readable Obsidian projection |
| C8 | Continuous Learning | Observe → Understand → Attempt → Evaluate → Remember (or Analyze Failure → Research → Repair → Retry) |
| C9 | Auto-Harness | Generated capability → generated test cases → sandboxed execution → scoring → repair → register |
| C10 | Self-Repair | Tool fails → analyze → research → generate fix → sandbox test → evaluate → versioned deploy |
| C11 | Adaptive Environment Model | Hardware, OS, apps, projects, repos, files, workspaces, devices, tools, accounts, and their relationships |
| C12 | Vision / Perception | Camera discovery, OCR, scene/object/person detection, anomaly/event detection (explicit authorization only) |
| C13 | Personal & Social Intelligence | Models of explicitly enrolled people, probabilistic behavior predictions, evidence-based, correctable |
| C14 | Social Media | Trust ladder: Read → Draft → User Approval → Trusted Workflow → Limited Autonomy |
| C15 | Finance (Indian Markets) | NSE/BSE, fundamentals, news, TA, QA, backtesting, paper trading; live trading gated as high-risk |
| C16 | Cybersecurity Learning | Education, CTFs, defensive security, labs, vuln analysis — offensive only in authorized sandboxed labs |

---

## 6. DEFINITION OF DONE — PROMPT 01

This document is part of Prompt 01. Prompt 01 is **documentation and architecture only**.

### Explicitly NOT Implemented in Prompt 01
- No agents, no chatbots
- No browser automation
- No desktop automation
- No voice
- No vision / cameras
- No finance / trading
- No cybersecurity labs
- No social media integrations
- No MCP servers
- No self-modifying code
- No real provider integrations
- No actual assistant runtime

### What Prompt 01 Must Deliver
A truthful, technically rigorous foundation that answers:

1. What are we building?
2. Why this architecture?
3. What technologies, compared against what alternatives?
4. How do the modules connect? (dependency graph)
5. Where are the security and privacy boundaries?
6. How will each future subsystem plug in? (extension points)
7. What is the ordered roadmap, and why?
8. What are the known risks and how will we mitigate them?

---

## 7. THE ANTI-CHATBOT MANIFESTO

To reinforce the vision, AEGIS is explicitly *not*:

| ❌ AEGIS is NOT | ✅ AEGIS IS |
|---|---|
| A chatbot with a text box | A system that lives alongside and observes the user's environment |
| A toolbox of hardcoded integrations | A capability discoverer and learner |
| A prompt-in → text-out pipeline | A plan-do-check-act learning loop with memory |
| Stateless | Continuously learning and personalized |
| An opaque executor | An auditable, permission-gated, reversible operator |
| Something the user types *at* | Something the user *works with* |
| Fixed capabilities | Growing capabilities through learning and auto-harness |
| Cloud-only | Local-first with cloud augmentation where privacy permits |

This manifesto is the North Star for every architectural and product decision.

---

*End of Document 00_VISION.md*
