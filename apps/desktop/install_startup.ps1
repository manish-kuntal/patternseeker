$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $project ".venv\Scripts\python.exe"
$script = Join-Path $project "main.py"

if (!(Test-Path $python)) {
    Write-Host "Virtual environment not found."
    Write-Host "Run:"
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "PATTERN Collector.lnk"

$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $python
$shortcut.Arguments = "`"$script`""
$shortcut.WorkingDirectory = $project
$shortcut.WindowStyle = 7
$shortcut.Save()

Write-Host "PATTERN collector startup shortcut installed."
Write-Host $shortcutPath
