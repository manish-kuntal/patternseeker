Set-Location "$PSScriptRoot\..\apps\desktop"

if (!(Test-Path ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\pip.exe" install -r requirements.txt

if (!(Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

& ".\.venv\Scripts\python.exe" main.py
