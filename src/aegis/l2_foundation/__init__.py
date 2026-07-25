"""L2 Foundation Services per Prompt 02:
event_bus, config, crypto, persistence, plugin_loader, telemetry, scheduler.

L2 MAY import only from L1. Must NOT import from L3-L7.
We avoid eager submodule imports at package __init__ time so that individual modules
can be imported without bringing up the entire foundation (avoids accidental cycles).
"""
