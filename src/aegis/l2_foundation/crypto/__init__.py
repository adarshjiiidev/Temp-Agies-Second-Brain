"""L2 Crypto + Secrets Vault.
In Prompt 02:
  - Pattern-based automatic redactor for logs/traces
  - Pure-Python secrets vault (AES-GCM via optional `cryptography` package)
  - Optional FFI bridge: Rust aegis_cffi built with pyo3 if cargo is installed
Prompt 05+ adds full TCB hash-chained audit integrity chain via Rust aegis_audit_chain crate."""

from aegis.l2_foundation.crypto.redact import (
    Redactor,
    redact_value,
    secret_ref,
)
from aegis.l2_foundation.crypto.vault import FileSecretVault, Hasher

__all__ = ["FileSecretVault", "Hasher", "Redactor", "redact_value", "secret_ref"]
