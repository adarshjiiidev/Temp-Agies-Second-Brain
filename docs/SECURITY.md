# AEGIS Security & Privacy Architecture

---

## 1. Core Principles

1. **Never Allow Models to Authorize Themselves:**
   - Model reasoning does not equal system authorization.
   - All tool invocations and hardware accesses pass through Python policy gates before kernel/driver execution.
2. **Strict Secret Redaction:**
   - Patterns matching API keys (`sk-...`, `ey...`, `ghp_...`), passwords, SSH keys (`id_rsa`, `id_ed25519`), and `.env` credentials are automatically sanitized with `[REDACTED]` across all logs and memory notes.
3. **Workspace Boundary Enforcement:**
   - File reads and writes are strictly restricted to authorized user directories under `/home/adarshjii/`.
   - Access to `/etc/shadow`, `/root`, or sensitive system areas is blocked by policy.
4. **Sensor Privacy:**
   - Camera default is `HARD_DENY`.
   - Microphones and audio capture are transient; no background audio recording without explicit command.
