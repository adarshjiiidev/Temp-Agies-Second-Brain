# AEGIS RESEARCH_LAB Profile (P3.1–P3.4)

Defensive / educational scope only. No exploit delivery, no credential
attacks, no external attack traffic. Secrets are never printed
(`research_lab.redact_token()` for any token display).

Implementation: `backend/research_lab.py` (new module — `backend/server.py`
is NOT modified by this change).

## 1. Profile table

| Profile | temp | max_turns | max_concurrency | tool allowlist | requires_lab_target |
|---|---|---|---|---|---|
| STANDARD | 0.3 | 8 | 2 | read-vault, run-readonly-eval, write-experiment | no |
| RESEARCH_LAB | 0.7 | 20 | 4 | + dry-run-harness, log-test-case | yes |
| RED_TEAM_LAB | 0.9 | 30 | 2 (tighter review) | + classify-refusal (local heuristic only) | yes |

`get_profile(name)` returns the dataclass; unknown names raise `ValueError("NOT_CONFIGURED …")`.

## 2. Session-auth flow

1. Registry `~/.temporary-aegis/config/lab_targets.json` seeds `localhost`
   (loopback dry-runs) and `owned-repos` (read-only static analysis), both `ACTIVE`.
2. Client calls `authorize_session(target_id, capabilities, ttl_min)` (1–480 min).
   Unknown target → `NOT_CONFIGURED`; inactive → `TARGET_OUTSIDE_SCOPE`;
   capability outside target scopes → `CAPABILITY_NOT_AUTHORIZED`.
3. Granted sessions persist to `lab_sessions.json` (same dir) with expiry;
   display via `public_session()` (token redacted, never printed).
4. Each capability use goes through `check(target_id, capability)` →
   `AUTHORIZED` or exactly one of `BLOCKED:TARGET_OUTSIDE_SCOPE`,
   `BLOCKED:CAPABILITY_NOT_AUTHORIZED`, `BLOCKED:PERMISSION_EXPIRED`,
   `BLOCKED:NOT_CONFIGURED`.

## 3. Endpoint spec for wiring (server.py, not yet wired)

- `GET /api/lab/profile?name=RESEARCH_LAB` → `get_profile()` →
  `{name, temperature, max_turns, max_concurrency, tool_allowlist, requires_lab_target}`.
- `POST /api/lab/authorize` body `{target_id, capabilities[], ttl_min?}` →
  `authorize_session()` → `{session_id, token_ref (redacted), target_id,
  capabilities, issued_at, expires_at, status}`. Raw token returned once
  to caller, never logged.
- `POST /api/lab/experiment` body `{exp_id, goal, hypothesis, model, config,
  scope, inputs, outputs, evaluation, lesson}` → `write_experiment()` →
  `{path}` under `~/ObsidianVault/agies/research/<YYYY-MM-DD>_<expid>.md`.
- Jailbreak-eval hook `eval_variant(prompt_variant, target_model, exp_id?)`
  classifies LOCALLY (`self-refusal-pattern | empty-or-trivial |
  needs-human-review`) and appends the test case + classification to the
  experiment file. No network calls, no model calls.

## 4. Dashboard exposure note

Expose under a gated "Lab" tab visible only with an ACTIVE lab session:
profile picker (table above), Authorize button (shows `token_ref` only),
per-capability `check()` status chips, experiment-file viewer, and the
`eval_variant` log tail. All lab UI actions stay read-only / log-only until
server.py wiring lands; no lab controls on the default STANDARD view.
