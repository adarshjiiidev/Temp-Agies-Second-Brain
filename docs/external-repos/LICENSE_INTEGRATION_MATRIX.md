# License Integration Matrix

This matrix governs how AEGIS consumes external systems to remain compliant.

| Project | License | Integration Strategy | Restriction Notes |
|---------|---------|----------------------|-------------------|
| **Multica** | Apache 2.0 (Custom conditions) | Direct API/Adapter | Can use concepts and run daemon. Must observe custom conditions in Part I of license. |
| **ECC** | MIT | Native Import / Fusion | Safe for direct source integration and modification inside AEGIS core. Extract skills, rules, and hooks directly. |
| **VoiceStudio** | AGPL-3.0 | Process Boundary / Local API | **DO NOT** embed source into AEGIS Python backend. Must run as an isolated service. Communicate strictly via HTTP/MCP APIs to prevent viral AGPL contamination. |
| **FrontierAgent** | Apache 2.0 | Native Import / Python Adapter | Safe for library usage. Can import Python modules (`frontier_agent.*`) directly into AEGIS workers. Must preserve license notices. |

## Compliance Rules:
1. **AGPL Isolation**: All AGPL applications must remain separated by a network/process boundary. AEGIS core cannot link directly to AGPL code.
2. **Attribution**: Preserve Apache 2.0 and MIT copyright notices when migrating source (e.g., ECC skills).
3. **Product Cohesion**: Regardless of the integration boundary (API vs. native import), the UX remains 100% unified under the AEGIS dashboard.
