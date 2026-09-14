# TEMPORARY AEGIS — Ingestion Pipeline

**Date:** 2026-09-12
**Status:** Manual ingestion (automated pipeline pending)

## How Ingestion Works

### 1. Capture (Inbox)
- Raw notes go to `./memory/0-Inbox/`
- Include: date, source, type, confidence

### 2. Triage (Weekly)
- Review inbox
- Move to appropriate PARA folder
- Link to existing notes via [[wikilinks]]
- Create MOC entries if needed

### 3. Distill
- Extract key points
- Create[[...[truncated]