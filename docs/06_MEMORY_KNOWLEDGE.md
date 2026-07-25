# PROJECT AEGIS — MEMORY ARCHITECTURE, KNOWLEDGE GRAPH, AND OBSIDIAN STRATEGY

**Document ID:** AEGIS-DOC-007
**Version:** 0.1.0 (Prompt 01 Foundation)
**Status:** DRAFT — Architecture Phase Only
**Last Updated:** 2026-07-24

---

## 1. MEMORY LANDSCAPE — WHY NINE TIERS

AEGIS treats memory like a human does: not one big bucket, but distinct systems with different persistence, confidence, access patterns, and forgetting curves. The wrong memory architecture will either (a) leak privacy by remembering things the user never wanted stored, or (b) be useless by forgetting everything important, or (c) hallucinate by conflating observations with facts.

All nine tiers share a **common write path** and **common provenance model** but diverge in retention, access, and validation.

---

## 2. THE NINE-TIER MEMORY HIERARCHY

### Logical Tier Diagram (volatility ↑ durability →)

```
WORKING (0)  ─────────────────────────────────────── Most volatile
  │
SESSION (1)
  │
EPISODIC (2)   SEMANTIC (3)   PROCEDURAL (4)
  │               │               │
  └───────────────┼───────────────┘
                  │
          PERSONAL (5)     ENVIRONMENTAL (6)     PROJECT (7)     SKILL (8)
                  │               │                  │               │
                  └───────────────┴──────────────────┴───────────────┘
                                                                  │
                                                     Most durable / validated
META-MEMORY: parallel index across ALL tiers (confidence, staleness, provenance)
```

### 2.1 Tier-by-Tier Specification

| # | Tier Name | Scope | Retention Default | Auto-written? | User-validated? | Purpose |
|---|---|---|---|---|---|---|
| T0 | **Working** | Single LLM call / current turn context | TTL = max(5 min, end of turn) | YES | No | In-context scratchpad; never persisted to disk; bound by LLM context window |
| T1 | **Session** | One user session (boot → shutdown) | 30 days after session end; auto-archive after | YES | Optional confirm-on-session-end | Everything that happened during this session: goals, plans, outcomes, raw interaction log |
| T2 | **Episodic** | Cross-session "what happened when" | 2 years default; user configurable TTL | YES | Partial — flagged highlights promoted; rest auto-curated | Timestamped events with provenance; "On 2026-07-24, AEGIS implemented Prompt 01 docs" |
| T3 | **Semantic** | Facts, knowledge, world model | Forever unless stale or user deletes | YES → after confidence check | YES promotion required before high-confidence | Decontextualized facts; "Python 3.12 supports type parameter syntax"; supports citation graph |
| T4 | **Procedural** | Learned workflows and recipes | Forever unless deprecated | YES → after auto-harness passes | YES to promote from draft to active | "How user likes to start a new Python project" — typed workflow recipe; used by cognitive planner |
| T5 | **Personal** | User preferences, goals, styles, people models | Forever unless user deletes; never auto-forget | Candidate → YES candidate written with DRAFT flag | **REQUIRED** — nothing auto-promotes to Personal without explicit user confirm | User's communication preference, long-term goals, coding style rules, explicitly enrolled person models |
| T6 | **Environmental** | Observations about user's digital environment | 90 days default; freshness tracking; auto-rescan | YES via environment scanners | User can override / blacklist / correct | "Python 3.12.4 installed at C:\\Python312", "Obsidian vault at D:\\Notes\\Vault", "User has 12 Git repos in ~/Projects" |
| T7 | **Project** | Scoped to one project / repository | Travels with the project; can embed `.aegis/` dir inside repo | YES when scanner detects project | User approves cross-project sharing | "Repo AGIES uses Python + uv, targets 3.12, has 11 docs in docs/"; planner reads this to adapt to each project automatically |
| T8 | **Skill** | Registered capability with auto-harness history | Versioned; retained until explicitly deprecated | YES after auto-harness score ≥ threshold | Optional approval before first-production-use | Generated tools, MCP wrappers, learned skills — with confidence, success rate, last tested date, limitations |

### 2.2 The Promotion Pathway — No Silent Leaps

Data can only move **upward** in durability through explicit gates. Data never automatically jumps from T1 Session to T5 Personal.

```
Observed → T1 Session (auto)
              │
              │  Extract event + tag   → T2 Episodic (auto; DRAFT_CONFIDENCE)
              │  Extract fact + cite   → T3 Semantic (candidate; DRAFT)
              │  Extract workflow      → T4 Procedural (candidate; DRAFT)
              │  Extract preference    → T5 Personal (CANDIDATE ONLY, DRAFT)
              │  Scanner result        → T6 Environmental (auto; freshness tagged)
              │  Project context       → T7 Project (auto; repo-scoped)
              │  Tool + Harness ≥Q     → T8 Skill (auto_register or user_approve)
              ▼
     META-MEMORY reconciles confidence, staleness, provenance per write
```

Rules:
- **T5 Personal promotion requires explicit user confirmation.** No exceptions. Not silent.
- **T4 Procedural promotion requires user confirmation OR 3 consecutive successful invocations with user not correcting the workflow.**
- **T3 Semantic promotion requires either (a) ≥2 corroborating observations, (b) a citation, or (c) user confirmation.**
- **T8 Skill promotion requires auto-harness score ≥ threshold AND approval gate if skill requires HIGH/CRITICAL permissions.**

### 2.3 Common Write Model (Applies to All Tiers)

```python
class MemoryWrite:
    tier: MemoryTier
    key: str                         # stable identifier; same key = version update
    content: Any                     # typed payload per tier
    embedding: Vector | None         # vector for retrieval
    privacy_tier: PrivacyTier        # P0 / P1 / P2 / P3 (from 05_SECURITY_PRIVACY)
    confidence: float                # 0.0..1.0 — starts low, promotes via rules above
    provenance: ProvenanceChain      # where this came from (user input? web? scanner? LLM-generated?)
    scope: Scope                     # global? project_id? session_id?
    citations: list[Citation] | None # for T3 Semantic; sources supporting the fact
    ttl: Duration | None             # explicit TTL; None = tier default applies
    is_draft: bool                   # DRAFT flag; promotion gates clear this
    revision: int                    # monotonically increasing per key
    parent_revision: int | None      # for diffs and corrections
```

**Provenance is non-negotiable.** Every memory record has a chain answering:
1. Who/what wrote this? (subject)
2. From what source? (user utterance id · web URL · scanner id · LLM completion id + model)
3. When? (timestamp + clock-skew flag)
4. Via what promotion rule? (T1→T2 extract · T1→T5 candidate · user confirmed · auto-harness id)
5. Corroborated by? (citations or prior memory ids)

---

## 3. RETRIEVAL PIPELINE — HOW MEMORY IS RECALLED

Memory retrieval is **tier-aware** and **context-aware**. The system does NOT dump everything from every tier at the LLM.

### 3.1 Recall Pipeline Stages

```
Incoming Query / Context Window
        │
        ▼
STAGE 1: Query Decomposition — what kinds of memory does this need?
  (semantic facts? recent episodes? user preferences? project context? skills?)
        │
        ▼
STAGE 2: Per-Tier Retrieval — per required tier, pull candidates:
  a. T0 Working: in-context, no query needed
  b. T1 Session: time-window lookup + topic filter
  c. T2 Episodic: hybrid vector + FTS5 keyword + time range
  d. T3 Semantic: vector search + citation graph traversal + confidence filter
  e. T4 Procedural: capability-matching via graph + success-rate threshold
  f. T5 Personal: scope filter + preference category keys (explicit, never fuzzy)
  g. T6 Environmental: freshness-aware lookup (< 90d default)
  h. T7 Project: repo-scoped exact + fuzzy
  i. T8 Skill: capability registry lookup (confidence ≥ threshold, compatible with required permissions)
        │
        ▼
STAGE 3: Rerank — cross-tier reranker with:
  · Confidence weight
  · Privacy tier compliance (P0 only goes to local models; never to cloud prompt)
  · Staleness penalty for T3/T6
  · Provenance quality (user-written > corroborated > single observation > LLM guessed)
        │
        ▼
STAGE 4: Context Window Budget — pack LLM context with bounded tokens per tier:
  T5 max 512 tok | T7 max 512 tok | T4 max 1024 tok | T3/T2/T1 remaining budget
        │
        ▼
STAGE 5: Assemble Typed Context Package — structured sections injected into LLM prompt
  with clear BEGIN/END blocks per tier, labeled sources, labeled confidence.
        │
        ▼
LLM consumes labeled memory. LLM output never touches memory directly; writes go through the promotion gates in §2.2.
```

### 3.2 Retrieval Access Controls

- **P0 DEVICE_LOCAL_ONLY memory**: Never included in any prompt routed to a cloud LLM. The router blocks the call with error if no local model is available. Enforced in L3 ai_kernel.router BEFORE the prompt is assembled.
- **Blacklisted user data**: Memory records the user has tagged `hide_from_llm` are excluded from recall entirely, regardless of other filters.
- **Scope enforcement**: T7 Project memory only retrieves records for the active project id. Never bleed project context across unrelated work.

---

## 4. META-MEMORY — WHAT THE SYSTEM KNOWS ABOUT WHAT IT KNOWS

Meta-Memory is a parallel index covering every record in every tier. Cognitive Planner, Model Router, and Retrieval Pipeline all consult Meta-Memory *before* doing real work.

### Meta-Memory Fields

```python
class MetaMemoryIndex:
    # Coverage
    total_records_by_tier: dict[MemoryTier, int]
    estimated_coverage_by_domain: dict[str, tuple[float, float]]  # (coverage_estimate, confidence)
    # Confidence
    records_by_confidence_bucket: dict[tuple[float,float], int]
    well_calibrated: bool           # has calibration test been run recently and passed?
    # Staleness
    stale_records_by_tier: dict[MemoryTier, int]
    last_full_refresh_by_source: dict[str, DateTime]
    # Provenance
    records_by_source: dict[str, int]
    user_validated_ratio: float     # T3+T4+T5 records that passed user validation
    # Capabilities
    skills_with_recent_harness: dict[SkillId, DateTime]  # last tested < 30d
    skills_failing: dict[SkillId, int]                   # consecutive failures
    # Gaps
    known_unknowns: list[KnowledgeGap]                   # things AEGIS knows it doesn't know
    # Calibration
    calibration_curve: dict[float, float]                # predicted_conf → actual_true_ratio
```

### Meta-Memory In Action

**Example 1 — Planner asks "Can I do X?"**
- Meta-Memory: `skill:git.create_pr exists? success_rate? last tested? required permissions available?`
- If missing → capability discovery pipeline engaged.

**Example 2 — User asks "How confident are you in this answer?"**
- Meta-Memory: aggregate staleness, provenance quality, corroboration count, confidence bucket for the T3 facts cited.

**Example 3 — Self-improvement loop**
- Meta-Memory: identify `skills_failing > 2` and queue auto-harness re-evaluation.
- Meta-Memory: identify `stale_records > threshold` in T6 Environmental and queue scanner refresh.

---

## 5. KNOWLEDGE GRAPH — TYPED ENTITIES AND RELATIONS

The Knowledge Graph (KG) is the *relationship* layer. Semantic memory (T3) stores facts as documents; the KG stores entities (nodes) and typed edges (relations) so the system can answer "How is AEGIS related to its AI Kernel?" with a traversal, not just keyword search.

### 5.1 Core Entity Types (Type System is Extensible)

| Entity Kind | Examples | Extensible? |
|---|---|---|
| `project` | AEGIS, Website_Redesign, Research_QA_Paper | YES |
| `repository` | git@github.com:user/agies.git, file:///c:/Users/adars/Projects/AGIES | YES |
| `document` | doc_001_prompt_01_spec, research_paper_attention | YES |
| `person` | user_primary, alice_colleague (EXPLICIT ENROLLMENT ONLY) | YES — only with user consent |
| `tool` | cli_git, mcp_obsidian, generated_openapi_client | YES |
| `skill` | skill_start_python_project, skill_research_topic | YES |
| `technology` | python_3_12, sqlite, qdrant, ollama, playwright | YES |
| `concept` | adversarial_machine_learning, zkp, rbac | YES |
| `software` | obsidian_v1_6, firefox_128, docker_27 | YES |
| `decision` | dec_2026_07_24_001_sqlite_as_default_kv | YES |
| `experiment` | exp_sandbox_tier2_escape_2026_08 | YES |
| `api` | api_openrouter_v1, api_groq_chat | YES |

### 5.2 Core Relation Types (Extensible)

All relations are directed and typed: `(subject --[relation {metadata}]--> object)`.

| Relation | Domain Example |
|---|---|
| `uses` | AEGIS --uses→ AI_Kernel |
| `depends_on` | AI_Kernel --depends_on→ Model_Router |
| `implemented_by` | Cognitive_Planner --implemented_by→ l6_cognitive/planner/cognitive.py |
| `researched` | AEGIS --researched→ Local_Models |
| `implemented` | AEGIS --implemented→ Planning_Engine |
| `related_to` | Memory_Engine --related_to→ Self_Learning |
| `contains` | Repo_AGIES --contains→ docs/02_ARCHITECTURE.md |
| `authored_by` | Decision_001 --authored_by→ user_primary |
| `cites` | Document_X --cites→ Research_Paper_Y |
| `conflicts_with` | Fact_A --conflicts_with→ Fact_B |
| `confirms` | Observation_42 --confirms→ Semantic_Fact_17 |
| `learned_from` | Skill_12 --learned_from→ Obsidian_Docs_Study |
| `version_of` | Skill_12_v2 --version_of→ Skill_12_v1 |
| `assigned_to` | Task_B --assigned_to→ Worker_Role_Planner |
| `works_on` | person:alice --works_on→ project:project_x |

### 5.3 Architecture Pattern — SQLite Edges + NetworkX Hybrid

```
WRITE PATH:
  Memory Write Promotion
    │
    ▼
  Entity/Relation Extractor (LLM-assisted + typed extraction + schema validate)
    │
    ▼
  SQLite edges table: id | src_id | dst_id | rel_type | created | attrs_json
  SQLite nodes table: id | kind | key | attrs_json | label
    │
    ▼
  Node embeddings written to vector store for entity similarity search
    │
    ▼
  KG write is idempotent + audited; duplicate edge = bump revision

READ PATH:
  Query (graph traversal / path / neighborhood / pattern match)
    │
    ▼
  Load relevant subgraph from SQLite into NetworkX (in-memory)
    │
    ▼
  NetworkX algorithms: shortest path, centrality, link prediction, community detection
    │
    ▼
  Result back to caller; hot subgraphs cached with TTL
```

Why this hybrid?
- **SQLite** gives durability, ACID, ad-hoc SQL filter queries, no extra process, easy backup.
- **NetworkX** gives 100+ graph algorithms out of the box without writing them ourselves.
- **Subgraph loading** keeps memory bounded even for 1M-node graphs (only load what the query needs).

### 5.4 Auto-Linking (Suggestion, Not Auto-Commit)

When a new entity or fact is written, the KG suggests candidate edges based on:
1. Vector similarity to existing nodes
2. Co-occurrence in episodic context
3. Known patterns (if kind=technology and kind=project AND co-occur in single T2 episode → suggest uses or researched)

**Auto-suggested edges are written with `is_draft=true`. They are NOT traversed in queries by default. They require user confirmation OR ≥ 2 corroborating episodes.**

No silent relationship promotion.

---

## 6. OBSIDIAN STRATEGY — HUMAN-READABLE PROJECTION LAYER

The Knowledge Graph and memory engine are AEGIS-native (SQLite+Qdrant+NetworkX), but the user thinks in markdown, wikilinks, and an Obsidian vault. AEGIS must therefore maintain a **bidirectional, loss-minimizing projection** between its internal structured knowledge and the user's Obsidian vault.

### 6.1 Design Goals

1. **Human-readable first.** Every important AEGIS memory that is worth long-term keeping has a markdown representation the user can read, edit, and link with their brain.
2. **AEGIS-native is the system of record.** The vault is the projection, not the source. If AEGIS and vault disagree, AEGIS wins + flags conflict for user review. (User edits to vault ARE ingested back — they become candidate memory with provenance "vault edit".)
3. **No vendor lock-in.** User can walk away at any time with their Obsidian vault and still have their second brain.
4. **Never overwrite user edits.** If user hand-edits a file AEGIS wrote, AEGIS must detect the edit, merge intelligently, and never blindly overwrite.

### 6.2 Vault Layout Proposal (Default; User-Configurable)

```
$OBSIDIAN_VAULT/AEGIS/
├── 00_Index/
│   ├── AEGIS_Dashboard.md                    # auto-generated overview
│   ├── Projects.md                           # list of [[Project:X]]
│   ├── Technologies.md                       # list of [[Tech:Y]]
│   ├── Decisions.md                          # decision log, ADR-style
│   └── Knowledge_Graph_View.md               # embedded graph query results (static render)
│
├── 01_Projects/
│   ├── Project_AEGIS/
│   │   ├── Project_AEGIS.md                  # project home (summary, goals, links)
│   │   ├── Architecture.md                   # auto-synced from docs/02_ARCHITECTURE.md
│   │   ├── Decisions/
│   │   │   └── ADR-001-SQLite-KV-Store.md
│   │   ├── Research/
│   │   │   └── Local-Models-Evaluation.md
│   │   ├── Experiments/
│   │   │   └── EXP-2026-08-01-Sandbox-Tier2.md
│   │   └── Daily/
│   │       └── 2026-07-24.md                 # daily log for this project
│   └── Project_X/...
│
├── 02_Research/
│   ├── Topic-Quantum-Memory-Evaluation.md    # NOT about TurboQuant unless verified
│   ├── Topic-Adaptive-Capability-Discovery.md
│   └── Sources/                              # imported web pages + citations
│
├── 03_Learned/
│   ├── Skills/
│   │   └── Skill-Create-Python-Project.md    # generated human-readable skill
│   ├── Workflows/
│   │   └── WF-Start-New-Research-Topic.md
│   └── Software-Models/
│       └── SW-Obsidian-V1.6-Familiarity.md   # what AEGIS learned about SW
│
├── 04_Personal/                              # P0/P1 — encrypted at sync
│   ├── Preferences.md
│   ├── Goals.md
│   ├── People/
│   │   └── Person-Alice.md                   # EXPLICIT ENROLL ONLY, NEVER AUTO
│   └── Styles/
│       ├── Writing.md
│       └── Coding.md
│
├── 05_Environment/
│   ├── Hardware.md
│   ├── Software-Installed.md
│   └── Repositories.md
│
├── 06_Daily/
│   └── 2026/
│       └── 07/
│           └── 2026-07-24.md                 # global daily log (all projects + personal)
│
└── Templates/                                 # user-customizable templates
    ├── Project-Template.md
    ├── Decision-Template.md
    ├── Research-Topic-Template.md
    ├── Skill-Template.md
    └── Daily-Template.md
```

### 6.3 Bidirectional Sync Protocol

```
┌──────────────────────────────────────────────────────────────────┐
│                    SYNC STATE MACHINE                            │
│                                                                  │
│   AEGIS Internal Store              Obsidian Vault              │
│                                                                  │
│   WRITE (AEGIS → Vault):                                          │
│   1. AEGIS write commits + emits event with revision hash        │
│   2. Vault projection renders markdown + writes with frontmatter │
│      `aegis_revision: {rev_hash}` + `aegis_last_written: ts`     │
│   3. Save last-synced revision in AEGIS per vault path           │
│                                                                  │
│   INGEST (Vault → AEGIS):                                        │
│   1. FS watcher on vault (with user-allowlisted paths only)      │
│   2. On file change: read frontmatter + compare revision         │
│      a. revision matches last AEGIS wrote → user likely edited   │
│         → diff the markdown → candidate memory provenance=vault  │
│         → write to appropriate tier as DRAFT (needs promotion)   │
│      b. revision differs (newer) → AEGIS wrote but vault drifted │
│         → 3-way merge + conflict file if non-trivial diff        │
│   3. Wikilinks in vault file → candidate KG edges (DRAFT)        │
│                                                                  │
│   CONFLICT RESOLUTION:                                           │
│   - Auto-merge trivial (whitespace, list reorder)                │
│   - Non-trivial: write `.aegis-conflict-<ts>.md` showing both    │
│     versions + base; prompt user approval for next sync cycle    │
│   - Never silently pick a winner                                 │
└──────────────────────────────────────────────────────────────────┘
```

### 6.4 Important — No Auto-Import from Unvetted Vault Content

AEGIS can **read** any allowlisted file in the vault as candidate memory. It can **write** to the vault projection paths above. It cannot:
- Read user's private, non-AEGIS notes unless user adds the path to allowlist.
- Treat user's handwritten notes as automatically-trusted personal facts; they are candidates and go through the promotion gates in §2.2.

### 6.5 On TurboQuant (and any other proposed memory tech)

The master document mentions "If a specific technology such as TurboQuant is proposed for memory compression or quantization, research it carefully before implementation." This is standing policy.

**Operational Rule:** Any new memory technology (quantization, compression, alternative vector DB, alternative KG — including TurboQuant specifically):
1. Is first added as a technology entity in the KG.
2. A Research Topic note is created in the vault.
3. An `exp_*` experiment record is created in T2 Episodic.
4. The technology is compared in a concrete benchmark: recall@k on AEGIS's actual retrieval workload, memory footprint vs. Qdrant default, error introduction rate on T3 semantic facts, privacy compliance (P0 still local?).
5. Only if benchmark is **strictly superior** with no correctness regressions AND no privacy regressions → added as a plugin. It never replaces the default in the kernel silently.

---

## 7. MEMORY + KNOWLEDGE + OBSIDIAN — FULL DATA FLOW

```
  USER INTERACTION / OBSERVATION
        │
        ▼
  T0 WORKING MEMORY (scratch, in-context, ephemeral)
        │
        ▼
  T1 SESSION (auto; this session's everything)
        │
        ├───────────────┬───────────────┬────────────────┬───────────┐
        ▼               ▼               ▼                ▼           ▼
  Episode extract   Fact extract    WF extract     Preference cand Scanner
  T2 EPISODIC       T3 SEMANTIC     T4 PROCEDURAL   T5 PERSONAL    T6 ENV
  (draft if unconf)  (draft if <2c) (draft if <3ok) (CAND ONLY)   (fresh)
        │               │               │                │           │
        ▼               ▼               ▼                ▼           ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  PROMOTION GATES (section 2.2) — user confirm / corroboration /     │
  │  harness success — clear is_draft flag when promoted                │
  └─────────────────────────────────────────────────────────────────────┘
        │               │               │                │           │
        ▼               ▼               ▼                ▼           ▼
  KNOWLEDGE GRAPH — entities + edges created for all promoted records
        │               │               │                │           │
        ▼               ▼               ▼                ▼           ▼
  OBSIDIAN PROJECTION — bidirectional sync with vault markdown
        │
        ▼
  RECALL PIPELINE (section 3.1) — per-tier retrieval + rerank + budgeted context
        │
        ▼
  LLM (local or cloud, privacy-tier gated) + Cognitive Planner
        │
        ▼
  LOOP BACK: new user interaction / observation above
```

---

## 8. VALIDATION PLAN (M04 — Memory & Knowledge Engine)

Before closing M04:

1. **Write 9-tier microbenchmark**: 100k synthetic writes, 1k retrieval queries; p95 recall time per tier < document 03 targets.
2. **Promotion gate correctness**: 100-sample battery — no T1 observation auto-leaks into T5 Personal (must be 0).
3. **Privacy tier recall correctness**: 50-sample battery — P0 memory never appears in prompt routed to cloud provider (must be 0, router must fail, not silently elide).
4. **Knowledge Graph integrity**: SQLite edge tables + NetworkX traversal return identical results for same subgraph for 50 random queries.
5. **Obsidian sync roundtrip**: Write → read vault → modify vault → re-ingest → conflict-free roundtrip for 20 test files.

---

*End of Document 06_MEMORY_KNOWLEDGE.md*
