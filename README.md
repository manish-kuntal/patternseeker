# PatternSeeker v2.1 — Adaptive Local Intelligence

PatternSeeker is a privacy-first personal behavior intelligence system. v2.0 adds normalized Windows process telemetry and adaptive local screen intelligence.

## v2.0 focus
- Whole-machine normalized process CPU (no `System Idle Process` pollution)
- Explicit collector runtime impact metrics
- Screen capture stays in memory
- Tesseract OCR is local and raw OCR is not persisted
- Optional Qwen2.5-VL local inference with resource guardrails
- Vision inference is cooldown/context-change aware to protect an RTX 4050 6GB laptop
- Screenshots are never sent to the PatternSeeker API
- Sensitive-window detection pauses screen analysis

## Local vision safeguards
Qwen vision runs only when system CPU and memory are below configured thresholds, after a cooldown, and (by default) when the active context changes. OCR/rule-based classification remains the fallback.

## Privacy
PatternSeeker intentionally does not collect keystrokes, passwords, clipboard contents, browser cookies, microphone/camera streams, or raw file contents.

## v2.1 Intelligence Layers

The previously locked intelligence layers are now functional and local-first:

- **Behavior Graph** — builds weighted relationships between observed applications, projects and screen activity.
- **Focus Analysis** — derives session length, deep-session time, context switching and a transparent focus score from foreground activity.
- **Predictions** — estimates recurring weekday/hour activity from historical observations; it is explicitly descriptive, not certainty.
- **Anomaly Detection** — compares daily event volume against a robust median/MAD baseline and surfaces strong deviations.

All four are exposed through `/api/intelligence/*` and rendered from live database data.


## v2.3 Advanced Intelligence
- Daily Brief
- Recurring Routine Detection
- Project Lifecycle Intelligence
- Context-switch analytics API
- Data Quality / Coverage
- Local metadata search
- Adaptive local intelligence remains privacy-first
