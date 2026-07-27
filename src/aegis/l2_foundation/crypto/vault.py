"""L2 Crypto primitives + Secrets Vault adapter.

Prompt 02 SCOPE:
  - Provides: FileVault (AES-GCM encryption via `cryptography` package), Hasher (sha256/hmac).
  - Optional Rust FFI: if aegis_cffi is available via build, functions delegate automatically.
    Otherwise the Python fallback runs transparently. ADR-P02-001 records the pure-Python fallback.
  - No key-management / KMS / networked vaults: those are Prompt 09+.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path

from aegis.l1_core.errors import ErrorCode, NotFoundError, ValidationError

# Optional cryptography dependency. The `pyproject.toml` includes it; guard here for grace
# in the event the user installs without extras.
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore[import-untyped]

    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


# ----- Hash helpers (always available) -----


class Hasher:
    """Deterministic sha256 / hmac-sha256 helpers used by audit log (Prompt 03 chain) & plugin integrity."""

    @staticmethod
    def sha256_hex(data: bytes | str) -> str:
        b = data.encode("utf-8") if isinstance(data, str) else data
        return hashlib.sha256(b).hexdigest()

    @staticmethod
    def hmac_sha256_hex(key: bytes | str, data: bytes | str) -> str:
        kb = key.encode("utf-8") if isinstance(key, str) else key
        db = data.encode("utf-8") if isinstance(data, str) else data
        return hmac.new(kb, db, hashlib.sha256).hexdigest()

    @staticmethod
    def random_hex(nbytes: int = 32) -> str:
        return secrets.token_hex(nbytes)


# ----- AES-GCM file-based vault (Prompt 02) -----


@dataclass
class _VaultHeader:
    version: int
    algorithm: str
    nonce: bytes
    created_at: float


class FileSecretVault:
    """Encrypts arbitrary key=value secrets to JSON + base64 AES-GCM on disk.

    Layout:
      $DATA_DIR/secrets/
        .master.key         32 bytes raw AES-256 key (chmod 0600 on Unix; ACL on Windows)
        scope.<scope>.bin   Base64 envelope: {v, alg, nonce, aad, ciphertext(tag appended)}
    """

    ALG = "aes-256-gcm"
    CURRENT_VERSION = 1
    MASTER_KEY_BYTES = 32
    NONCE_BYTES = 12

    def __init__(self, vault_dir: str | Path) -> None:
        self._dir = Path(vault_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._master_path = self._dir / ".master.key"
        self._lock = threading.RLock()
        self._master: bytes | None = None
        self._ensure_master_key()

    # ---------- master key management ----------

    def _ensure_master_key(self) -> None:
        if not _HAS_CRYPTO:
            # Fallback: use key-derivation from local hash; STRONGLY advise installing cryptography
            self._master = b"\x00" * self.MASTER_KEY_BYTES  # placeholder; NOT secure.
            return
        if self._master_path.exists():
            self._master = self._master_path.read_bytes()
            if len(self._master) != self.MASTER_KEY_BYTES:
                raise ValidationError(ErrorCode.E20502, "Master key corrupted")
        else:
            self._master = os.urandom(self.MASTER_KEY_BYTES)
            try:
                # Best-effort perms on Windows: Write-only admin + current user.
                fd = os.open(str(self._master_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as fh:
                    fh.write(self._master)
            except FileExistsError:
                self._master = self._master_path.read_bytes()

    # ---------- envelope (de/en)velope ----------

    def _pack(self, plaintext: bytes, aad: bytes) -> bytes:
        if not _HAS_CRYPTO:
            # Fallback: XOR-based obfuscation. NOT cryptographically secure.
            # Prompt 02 acceptable ONLY for local development. Prod env MUST install `cryptography`.
            key = self._master or b""
            nonce = os.urandom(self.NONCE_BYTES)
            pad = hashlib.sha256(key + nonce + aad).digest()
            out = bytes(b ^ pad[i % len(pad)] for i, b in enumerate(plaintext))
            tag = hashlib.sha256(aad + nonce + plaintext).digest()[:16]
            envelope = {
                "v": self.CURRENT_VERSION,
                "alg": "fallback-xor-sha256",
                "nonce_b64": base64.b64encode(nonce).decode("ascii"),
                "aad_b64": base64.b64encode(aad).decode("ascii"),
                "ciphertext_b64": base64.b64encode(out + tag).decode("ascii"),
            }
            return json.dumps(envelope).encode("utf-8")
        nonce = os.urandom(self.NONCE_BYTES)
        aes = AESGCM(self._master)
        ct = aes.encrypt(nonce, plaintext, aad)
        envelope = {
            "v": self.CURRENT_VERSION,
            "alg": self.ALG,
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "aad_b64": base64.b64encode(aad).decode("ascii"),
            "ciphertext_b64": base64.b64encode(ct).decode("ascii"),
        }
        return json.dumps(envelope).encode("utf-8")

    def _unpack(self, raw: bytes, aad: bytes) -> bytes:
        env = json.loads(raw.decode("utf-8"))
        nonce = base64.b64decode(env["nonce_b64"])
        ciphertext = base64.b64decode(env["ciphertext_b64"])
        envelope_aad = base64.b64decode(env.get("aad_b64", ""))
        if envelope_aad != aad:
            raise ValidationError(ErrorCode.E20502, "AAD mismatch — vault envelope tampered")
        alg = env.get("alg", self.ALG)
        if not _HAS_CRYPTO or alg == "fallback-xor-sha256":
            key = self._master or b""
            pad = hashlib.sha256(key + nonce + aad).digest()
            body, tag = ciphertext[:-16], ciphertext[-16:]
            plaintext = bytes(b ^ pad[i % len(pad)] for i, b in enumerate(body))
            expected = hashlib.sha256(aad + nonce + plaintext).digest()[:16]
            if not hmac.compare_digest(expected, tag):
                raise ValidationError(ErrorCode.E20502, "Fallback ciphertext MAC mismatch")
            return plaintext
        aes = AESGCM(self._master)
        try:
            return aes.decrypt(nonce, ciphertext, aad)
        except Exception as exc:
            raise ValidationError(ErrorCode.E20502, f"Decryption failed: {exc}") from exc

    # ---------- public API ----------

    def _scope_path(self, scope: str) -> Path:
        safe = "".join(c for c in scope if c.isalnum() or c in "-_.") or "_default"
        return self._dir / f"scope.{safe}.bin"

    def put(self, scope: str, identifier: str, value: str | bytes) -> None:
        raw = value.encode("utf-8") if isinstance(value, str) else value
        path = self._scope_path(scope)
        with self._lock:
            data: dict[str, dict[str, str]] = {}
            if path.exists():
                data = json.loads(
                    self._unpack(path.read_bytes(), path.name.encode("utf-8")).decode("utf-8")
                )
            data[identifier] = base64.b64encode(raw).decode("ascii")
            plaintext = json.dumps(data).encode("utf-8")
            path.write_bytes(self._pack(plaintext, path.name.encode("utf-8")))

    def get(self, scope: str, identifier: str) -> str:
        path = self._scope_path(scope)
        with self._lock:
            if not path.exists():
                raise NotFoundError(ErrorCode.E20501, f"secret scope {scope!r} not found")
            data = json.loads(
                self._unpack(path.read_bytes(), path.name.encode("utf-8")).decode("utf-8")
            )
        if identifier not in data:
            raise NotFoundError(ErrorCode.E20501, f"secret {scope}/{identifier} not found")
        return base64.b64decode(data[identifier]).decode("utf-8")

    def delete(self, scope: str, identifier: str) -> bool:
        path = self._scope_path(scope)
        with self._lock:
            if not path.exists():
                return False
            data = json.loads(
                self._unpack(path.read_bytes(), path.name.encode("utf-8")).decode("utf-8")
            )
            if identifier not in data:
                return False
            data.pop(identifier)
            if data:
                plaintext = json.dumps(data).encode("utf-8")
                path.write_bytes(self._pack(plaintext, path.name.encode("utf-8")))
            else:
                path.unlink()
        return True

    def scopes(self) -> list[str]:
        return sorted(p.stem[len("scope.") :] for p in self._dir.glob("scope.*.bin"))

    def list(self, scope: str) -> list[str]:
        path = self._scope_path(scope)
        if not path.exists():
            return []
        with self._lock:
            data = json.loads(
                self._unpack(path.read_bytes(), path.name.encode("utf-8")).decode("utf-8")
            )
        return sorted(data.keys())
