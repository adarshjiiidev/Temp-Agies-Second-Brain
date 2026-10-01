"""L3 AI Kernel — Credential Resolution & Provisioner Extension Points (P07.5).

This module provides:

1. CredentialResolver — resolves ProviderKey.vault_ref strings to live API key
   values without storing the raw secret.  Supports:
     env:VAR_NAME         -> os.environ["VAR_NAME"]
     file:/path/to/file   -> first non-empty line of file (no trailing newline)
     aegis-keyring:scope/id -> L2 crypto vault hook (NotImplementedError by default)

2. CredentialProvisioner (ABC) — extension point for future credential
   acquisition mechanisms (§17 of the P07.5 directive).
   Concrete implementations:
     ManualProvisioner      — noop; user configures credentials themselves.
     EnvironmentProvisioner — scans env vars matching "{PROVIDER}_API_KEY" pattern.
     BrowserProvisioner     — NOT IMPLEMENTED (stub; raises NotImplementedError
                              with an explicit message; never auto-creates accounts).

Security invariants enforced throughout:
  - Raw API key strings NEVER appear in log output, exception messages,
    repr() output, or serialised model state.
  - Only the non-secret key_id is exposed externally.
  - vault_ref values are treated as opaque references, not secrets.

Layer: L3 (imports stdlib + L1 errors + L3 keys only; no L4+).
"""

from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Optional

from aegis.l3_intelligence.ai_kernel.keys import KeyManager, ProviderKey

logger = logging.getLogger(__name__)

__all__ = [
    "CredentialResolver",
    "CredentialProvisioner",
    "ManualProvisioner",
    "EnvironmentProvisioner",
    "BrowserProvisioner",
    "CredentialResolutionError",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CredentialResolutionError(Exception):
    """Raised when a vault_ref cannot be resolved to a credential value.

    IMPORTANT: The exception message MUST NOT contain the raw credential value
    or the full vault_ref if it could leak path-encoded secrets.
    """


# ---------------------------------------------------------------------------
# CredentialResolver
# ---------------------------------------------------------------------------


class CredentialResolver:
    """Resolves ProviderKey.vault_ref strings to live credential values.

    Supported schemes
    -----------------
    ``env:VAR_NAME``
        Read the value of the environment variable ``VAR_NAME``.
        Raises ``CredentialResolutionError`` if the variable is not set or empty.

    ``file:/absolute/path/to/file``
        Read the first non-empty, stripped line of the file.
        Raises ``CredentialResolutionError`` if the file is missing or unreadable.

    ``aegis-keyring:scope/id``
        Hook for the L2 encrypted credential vault.
        Raises ``NotImplementedError`` by default (wire at application startup).

    Bare strings (no scheme prefix)
        Treated as an environment-variable name for backward compatibility
        (equivalent to ``env:NAME``).

    Security
    --------
    - Resolved values are returned as plain strings and MUST be used immediately
      (passed to an HTTP header, not stored).
    - The resolver never logs the resolved value.
    - Exception messages never include the resolved credential.
    """

    # Regex for env: scheme
    _ENV_PATTERN = re.compile(r"^env:(.+)$")
    # Regex for file: scheme
    _FILE_PATTERN = re.compile(r"^file:(.+)$")
    # Regex for aegis-keyring: scheme
    _KEYRING_PATTERN = re.compile(r"^aegis-keyring:(.+)$")

    def resolve(self, vault_ref: str) -> str:
        """Resolve a vault_ref to its credential value.

        Args:
            vault_ref: The opaque reference string from ProviderKey.vault_ref.

        Returns:
            The resolved credential string (never empty).

        Raises:
            CredentialResolutionError: If resolution fails.
            NotImplementedError: For unimplemented schemes (aegis-keyring).
        """
        if not vault_ref:
            raise CredentialResolutionError(
                "vault_ref is empty — no credential configured for this key."
            )

        m_env = self._ENV_PATTERN.match(vault_ref)
        if m_env:
            return self._resolve_env(m_env.group(1))

        m_file = self._FILE_PATTERN.match(vault_ref)
        if m_file:
            return self._resolve_file(m_file.group(1))

        m_kr = self._KEYRING_PATTERN.match(vault_ref)
        if m_kr:
            return self._resolve_keyring(m_kr.group(1))

        # Bare string — treat as env var name (backward compat)
        return self._resolve_env(vault_ref)

    def _resolve_env(self, var_name: str) -> str:
        value = os.environ.get(var_name, "")
        if not value:
            raise CredentialResolutionError(
                f"Environment variable '{var_name}' is not set or empty. "
                f"Configure the credential before starting AEGIS."
            )
        return value

    def _resolve_file(self, path: str) -> str:
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped:
                        return stripped
            raise CredentialResolutionError(
                f"Credential file at path contains no non-empty lines."
            )
        except FileNotFoundError:
            raise CredentialResolutionError(
                f"Credential file not found. Check the file path in your configuration."
            ) from None
        except OSError as exc:
            raise CredentialResolutionError(
                f"Could not read credential file: {exc.strerror}"
            ) from exc

    def _resolve_keyring(self, ref: str) -> str:
        # Future: wire to L2 crypto vault / OS keyring.
        raise NotImplementedError(
            "aegis-keyring credential resolution is not yet implemented. "
            f"Use 'env:' or 'file:' schemes instead. ref_scheme=aegis-keyring"
        )


# ---------------------------------------------------------------------------
# CredentialProvisioner — extension point ABC
# ---------------------------------------------------------------------------


class CredentialProvisioner(ABC):
    """Abstract extension point for credential acquisition (P07.5 §17).

    Implementations populate a KeyManager with ProviderKey entries.
    They MUST NOT:
      - Store raw API keys anywhere persistent without encryption.
      - Bypass provider authentication or CAPTCHA.
      - Create accounts to evade provider quotas.
      - Automate any action requiring explicit user consent.
    """

    @abstractmethod
    def provision(
        self,
        key_manager: KeyManager,
        provider_id: str,
    ) -> list[str]:
        """Discover and register credentials for the given provider.

        Args:
            key_manager: The KeyManager to register found keys into.
            provider_id: The target provider identifier (e.g. 'groq').

        Returns:
            List of registered key_ids (non-secret stable identifiers).
        """


# ---------------------------------------------------------------------------
# ManualProvisioner
# ---------------------------------------------------------------------------


class ManualProvisioner(CredentialProvisioner):
    """Noop provisioner — credentials are configured manually by the operator.

    Use this (the default) when credentials are already registered in
    KeyManager by application startup code. Calling provision() is a no-op.
    """

    def provision(
        self,
        key_manager: KeyManager,
        provider_id: str,
    ) -> list[str]:
        """No-op: return the list of already-registered key_ids."""
        return [k.key_id for k in key_manager.list_keys(provider_id)]


# ---------------------------------------------------------------------------
# EnvironmentProvisioner
# ---------------------------------------------------------------------------


class EnvironmentProvisioner(CredentialProvisioner):
    """Scans environment variables matching known patterns and auto-registers keys.

    Pattern: ``{PROVIDER_UPPER}_API_KEY`` or ``{PROVIDER_UPPER}_API_KEY_N``
    where N is 1, 2, 3, ...

    Examples for provider_id='groq':
        GROQ_API_KEY        -> key_id 'env-groq-0'  vault_ref 'env:GROQ_API_KEY'
        GROQ_API_KEY_1      -> key_id 'env-groq-1'  vault_ref 'env:GROQ_API_KEY_1'
        GROQ_API_KEY_2      -> key_id 'env-groq-2'  vault_ref 'env:GROQ_API_KEY_2'

    Security: Only the env var NAME (not its value) is stored in vault_ref.
    """

    def __init__(self, scopes: set[str] | None = None) -> None:
        self._scopes = scopes or {"chat"}

    def provision(
        self,
        key_manager: KeyManager,
        provider_id: str,
    ) -> list[str]:
        prefix = provider_id.upper().replace("-", "_")
        registered: list[str] = []

        # Primary key: PROVIDER_API_KEY
        primary_var = f"{prefix}_API_KEY"
        if os.environ.get(primary_var, ""):
            key_id = f"env-{provider_id}-0"
            if not self._is_registered(key_manager, provider_id, key_id):
                key_manager.register(
                    ProviderKey(
                        key_id=key_id,
                        provider_id=provider_id,
                        vault_ref=f"env:{primary_var}",
                        scopes=self._scopes,
                        priority=0,
                        enabled=True,
                    )
                )
                logger.debug(
                    "EnvironmentProvisioner: registered key '%s' from env var '%s'.",
                    key_id, primary_var,
                )
            registered.append(key_id)

        # Numbered keys: PROVIDER_API_KEY_1, PROVIDER_API_KEY_2, ...
        for n in range(1, 21):   # Support up to 20 numbered keys
            var = f"{prefix}_API_KEY_{n}"
            if not os.environ.get(var, ""):
                break
            key_id = f"env-{provider_id}-{n}"
            if not self._is_registered(key_manager, provider_id, key_id):
                key_manager.register(
                    ProviderKey(
                        key_id=key_id,
                        provider_id=provider_id,
                        vault_ref=f"env:{var}",
                        scopes=self._scopes,
                        priority=n,
                        enabled=True,
                    )
                )
                logger.debug(
                    "EnvironmentProvisioner: registered key '%s' from env var '%s'.",
                    key_id, var,
                )
            registered.append(key_id)

        return registered

    @staticmethod
    def _is_registered(km: KeyManager, provider_id: str, key_id: str) -> bool:
        return any(k.key_id == key_id for k in km.list_keys(provider_id))


# ---------------------------------------------------------------------------
# BrowserProvisioner — NOT IMPLEMENTED (design stub only)
# ---------------------------------------------------------------------------


class BrowserProvisioner(CredentialProvisioner):
    """Future browser-based credential acquisition stub (P07.5 §17).

    THIS IMPLEMENTATION IS INTENTIONALLY DISABLED.

    The BrowserProvisioner is designed as an extension point for future
    legitimate credential setup workflows (e.g. guiding the user through
    an API key creation page in a controlled browser session, with explicit
    user consent at every step).

    It MUST NEVER:
      - Bypass CAPTCHA or identity verification.
      - Create accounts to circumvent provider quotas.
      - Automate any action without explicit, step-by-step user authorization.
      - Evade provider rate limits or terms of service.

    Implementation is deferred to a future milestone (P10+ Browser OS).
    """

    def provision(
        self,
        key_manager: KeyManager,
        provider_id: str,
    ) -> list[str]:
        raise NotImplementedError(
            "BrowserProvisioner is not yet implemented. "
            "This feature is planned for a future milestone (P10+ Browser OS). "
            "Use ManualProvisioner or EnvironmentProvisioner instead. "
            f"provider_id={provider_id!r}"
        )
