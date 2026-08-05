"""Reasoning subsystem — public API.

Exports the key types callers need:
  - ReasoningProvider    (ABC to depend on)
  - ReasoningUnavailableError  (sentinel to catch)
  - MockReasoningProvider (for tests)
  - KernelReasoningProvider (for production)
  - PromptId             (constant strings)
  - ReasoningRequest / ReasoningResponse (data contracts)
"""

from aegis.reasoning.provider import ReasoningProvider, ReasoningUnavailableError
from aegis.reasoning.mock_provider import MockReasoningProvider
from aegis.reasoning.kernel_provider import KernelReasoningProvider
from aegis.reasoning.types import PromptId, ReasoningRequest, ReasoningResponse

__all__ = [
    "ReasoningProvider",
    "ReasoningUnavailableError",
    "MockReasoningProvider",
    "KernelReasoningProvider",
    "PromptId",
    "ReasoningRequest",
    "ReasoningResponse",
]
