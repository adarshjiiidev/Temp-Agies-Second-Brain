# AEGIS Org Cameras (P6.5) — BLOCKED on credentials

Status: `AWAITING_CREDENTIALS`. Scaffolding only; no live connections.

## 1. What you must provide (no passwords in chat)
- Target list: `[{id, host, port, protocol}]`, e.g.
  `[{"id": "venue-cam-01", "host": "192.0.2.10", "port": 554, "protocol": "rtsp"}]`
- Admin username + password per camera ID, delivered OUT-OF-BAND into the vault (never chat/logs).

## 2. Where creds go
- Vault file: `~/.temporary-aegis/config/org_cameras.json`, mode `0600`, created ONLY via explicit
  `hub.install_vault_entry(id, username, password)` or manual `chmod 600` creation. Code never
  creates it with dummy passwords; `configure()` rejects any password keys.
- Format example (placeholder values only, never real secrets):
  `{"cameras": {"venue-cam-01": {"username": "YOUR_ADMIN_ID", "password": "YOUR_ADMIN_PASS"}}}`
- Runtime alternative (no file): env `ORG_CAM_PASS_<ID>` (e.g. `ORG_CAM_PASS_VENUE_CAM_01`).

## 3. Scope limits
- Explicit hosts only. No subnet scanning, no nmap, no range expansion.
- Defaults: `DISCOVERED` → unauthorized, `HARD_DENY` snapshots until `authorize()` + `enable_vision()`.
- All logs/returns redact credential values (`[REDACTED]`); `status()` shows `PRESENT`/`ABSENT` only.

## 4. What unlocks once provided
- `configure(targets)` → `authorize(id)` (needs vault/env cred) → `enable_vision(id)` → `snapshot(id)`
  permitted for `AUTHORIZED` + vision-enabled cameras via `vision_engine` (transient analysis only).

## Unblock line (send targets only, never the password)
`P6.5 UNBLOCK targets=[{"id":"<CAM_ID>","host":"<IP/HOST>","port":554,"protocol":"rtsp"}] vault=~/.temporary-aegis/config/org_cameras.json:0600`
