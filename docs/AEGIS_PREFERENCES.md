# AEGIS Preferences (P2.11/P5.1)

Store: `~/.temporary-aegis/config/preferences.json` (i.e. `cfg.CONFIG_DIR / "preferences.json"`).
Module: `backend/preferences.py` (new module only; `backend/server.py` untouched — main agent wires routes).

## 1. Schema

```json
{
  "<section>": {
    "<key>": {"value": <any>, "source": "<string>", "confidence": 0.0, "updated": "<iso-8601 UTC>"}
  }
}
```

- Sections: `identity`, `dev`, `ui_style`, `product`, `workflow`, `research`.
- `source`: `user` (authoritative) | `vault:<file>` (explicit seed) | `vault-inferred:<file>` (inferred seed) | `task-spec(P2.11)`.
- `confidence`: explicit vault/task statements `1.0`; inferred values `<= 0.6`. Confirming a pref sets `1.0`.
- `ui_style` canonical values: bg `#0e0e11` / `#050608`, accent orange/amber, glassmorphic dark surfaces with subtle glow, density high, minimal sidebar, mono headers.
- `product` keys per category: `developer-tool`, `dashboard`, `chat`.
- NEVER log or print raw values (may evolve to include secrets); log counts/status only.

## 2. Precedence

`resolve(key, context)` — winner is the highest present level:

1. `project_rule` 2. `task_instruction` 3. `user_pref` (falls back to store lookup across all sections) 4. `global` 5. `default`

Returns `{"key", "value", "winner"}` where `winner` is the level name or `"none"`.

## 3. Endpoint spec (main-agent wiring, FastAPI)

| Method & path | Body / query | Behavior |
|---|---|---|
| `GET /api/preferences` | — | `get_profile()` → full `{section: {key: record}}` |
| `GET /api/preferences/<section>` | section ∈ 6 names, else 404 | `get_section(section)` |
| `POST /api/preferences/set` | `{section, key, value, source="user"}` | `set_pref(...)` → record; `user` source forces confidence 1.0 |
| `POST /api/preferences/confirm` | `{section, key}` | `confirm_pref(...)` → confidence 1.0 |
| `DELETE /api/preferences/<section>/<key>` | — | `delete_pref(...)` → `{ok: bool}`; 404 if absent |

Mutating routes must sit behind the existing auth middleware (X-AEGIS-Token / chat-session + same-origin), same as other `POST/DELETE` endpoints. Validate `section` against `get_sections()`.

## 4. Dashboard panel spec — PENDING-UI

Preferences panel (not yet built): section tabs (6); per-key rows showing value + source badge + confidence bar; swatch previews for `ui_style` colors (`#0e0e11`, `#050608`, orange/amber accent) with live theme preview; per-row Confirm / Edit / Delete buttons mapped to the endpoints above; read-only provenance line (`source`, `updated`). Status: **PENDING-UI**.
