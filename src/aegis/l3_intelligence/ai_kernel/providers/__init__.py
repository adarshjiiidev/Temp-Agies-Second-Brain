"""Provider adapters package — Prompt 03 §10.

Exports all concrete LLMProvider implementations plus base classes.

Import graph (no circular deps):
    base.py ← (each concrete provider imports from base.py)
    fake.py ← no network, stdlib only
    ollama.py ← httpx
    openrouter.py ← httpx
    groq.py ← httpx
    vllm.py ← httpx
"""

from __future__ import annotations

from aegis.l3_intelligence.ai_kernel.providers.base import BaseProvider, ProviderRegistry
from aegis.l3_intelligence.ai_kernel.providers.fake import FakeProvider, FakeResponse

__all__ = [
    "BaseProvider",
    "ProviderRegistry",
    "FakeProvider",
    "FakeResponse",
]

# Lazy-import concrete HTTP providers so that a missing httpx dep does not
# break the entire import chain. Tests that only use FakeProvider work fine
# even if httpx is absent.

def _get_ollama():
    from aegis.l3_intelligence.ai_kernel.providers.ollama import OllamaProvider
    return OllamaProvider

def _get_openrouter():
    from aegis.l3_intelligence.ai_kernel.providers.openrouter import OpenRouterProvider
    return OpenRouterProvider

def _get_groq():
    from aegis.l3_intelligence.ai_kernel.providers.groq import GroqProvider
    return GroqProvider

def _get_vllm():
    from aegis.l3_intelligence.ai_kernel.providers.vllm import VLLMProvider
    return VLLMProvider
