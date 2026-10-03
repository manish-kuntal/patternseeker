# PATTERN Architecture

## Core rule

Collectors produce metadata-only events.

The backend stores normalized events.

The analytics engine creates measurable evidence.

The optional LLM explains validated evidence.

```text
Windows Agent ─┐
               ├─> Event API ─> Database ─> Pattern Engine ─> Dashboard
Android App ───┘                                  │
                                                  └─> Ollama (optional)
```

## Why this design

The LLM is not responsible for discovering facts from raw personal telemetry. Deterministic analytics produce the evidence first.

This prevents the system from turning guesses into "patterns".

## Future modules

- Android UsageStats opt-in collector
- Google Calendar connector
- GitHub connector
- browser metadata connector
- encrypted remote sync
- account authentication
- PostgreSQL production database
- background workers
- anomaly detection
- behavioral graph
