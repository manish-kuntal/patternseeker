# Privacy

PATTERN is intended for personal use.

The current collectors intentionally do not capture:
- passwords
- keystrokes
- clipboard
- screenshots
- message contents
- full file contents

Desktop events contain metadata such as:
- timestamp
- application name
- project name
- code-file extension
- limited relative file path
- Git commit identifier and message length

Android base collector currently sends only a heartbeat.

Any future sensitive collector should be:
1. opt-in
2. permission-gated
3. independently switchable
4. documented before activation


## Screen Intelligence

Screen Intelligence is designed to observe high-level activity context without becoming a screen recorder. Frames are captured only at the configured interval, processed in memory, and discarded. Raw screenshot pixels and raw OCR text are not persisted in the PatternSeeker database. The collector emits structured categories such as coding, research, learning, communication, design, entertainment, and file management. Optional vision analysis uses a local Ollama vision endpoint only.

Sensitive-window detection can pause analysis for configured terms such as banking, password managers, OTP/authenticator, payment apps, private browsing, and login screens.
