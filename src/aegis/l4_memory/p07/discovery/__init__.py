"""P07 Discovery — Consent Gate and Scanning Coordinator.

Sub-modules:
    consent    — ConsentGate: tracks opt-in/opt-out; discovery blocked without consent
    coordinator — ScanningCoordinator: orchestrates scanners under consent + privacy zone

Architectural invariants:
    - Discovery is EXPLICITLY OPT-IN. Scanning never happens without consent.
    - Privacy zone filter applied BEFORE any data reaches EnvironmentStore.
    - All operations are bounded (max_seconds, max_results) per scanner.
    - Import safety: l4_memory.p07.* + stdlib ONLY.
"""

from aegis.l4_memory.p07.discovery.consent import ConsentGate, ConsentRecord, ConsentScope
from aegis.l4_memory.p07.discovery.coordinator import ScanningCoordinator, DiscoveryResult

__all__ = [
    "ConsentGate",
    "ConsentRecord",
    "ConsentScope",
    "ScanningCoordinator",
    "DiscoveryResult",
]
