@echo off
setlocal EnableExtensions
title PatternSeeker - Full Launcher
color 0B

set "ROOT=C:\Users\manis\PatternSeeker"
set "BACKEND=%ROOT%\backend"
set "DESKTOP=%ROOT%\apps\desktop"
set "WEB=%ROOT%\web"
set "OLLAMA_URL=http://127.0.0.1:11434"
set "API_URL=http://127.0.0.1:8000"
set "WEB_URL=http://localhost:5173"
set "TESSERACT=C:\Program Files\Tesseract-OCR"
set "MODEL=qwen2.5vl:7b"

cd /d "%ROOT%"

echo.
echo ============================================================
echo                 PATTERNSEEKER
echo          FULL LOCAL INTELLIGENCE LAUNCHER
echo ============================================================
echo.

REM ------------------------------------------------------------
REM 0. Basic checks
REM ------------------------------------------------------------
echo [1/7] Checking PatternSeeker files...

if not exist "%BACKEND%\app\main.py" (
    echo [ERROR] Backend not found: %BACKEND%\app\main.py
    goto FAIL
)

if not exist "%DESKTOP%\main.py" (
    echo [ERROR] Desktop collector not found: %DESKTOP%\main.py
    goto FAIL
)

if not exist "%WEB%\package.json" (
    echo [ERROR] Web dashboard not found: %WEB%\package.json
    goto FAIL
)

echo       PatternSeeker files OK.

REM ------------------------------------------------------------
REM 1. Tesseract
REM ------------------------------------------------------------
echo.
echo [2/7] Checking Tesseract OCR...

if exist "%TESSERACT%\tesseract.exe" (
    set "PATH=%PATH%;%TESSERACT%"
    echo       Tesseract found.
) else (
    echo [WARNING] Tesseract not found at:
    echo           %TESSERACT%
    echo       Screen OCR may not work.
)

REM ------------------------------------------------------------
REM 2. Ollama
REM ------------------------------------------------------------
echo.
echo [3/7] Starting / checking Ollama...

where ollama >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama command was not found in PATH.
    echo         Install Ollama or restart Windows after installation.
    goto FAIL
)

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%OLLAMA_URL%/api/tags' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"

if errorlevel 1 (
    echo       Ollama API is not running. Starting Ollama...
    start "" "ollama"
    timeout /t 5 /nobreak >nul
)

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%OLLAMA_URL%/api/tags' -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"

if errorlevel 1 (
    echo [ERROR] Ollama API did not become available.
    echo         Try running: ollama serve
    goto FAIL
)

echo       Ollama API is READY.

echo       Checking Qwen Vision model: %MODEL%
ollama list | findstr /I /C:"%MODEL%" >nul 2>&1
if errorlevel 1 (
    echo       Qwen Vision model is missing.
    echo       Pulling %MODEL% now...
    ollama pull %MODEL%
    if errorlevel 1 (
        echo [ERROR] Failed to pull %MODEL%.
        goto FAIL
    )
) else (
    echo       %MODEL% is installed.
)

REM ------------------------------------------------------------
REM 3. Backend
REM ------------------------------------------------------------
echo.
echo [4/7] Starting Backend API...

powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri '%API_URL%/api/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"

if errorlevel 1 (
    if exist "%BACKEND%\.venv\Scripts\python.exe" (
        echo       Using backend virtual environment.
        "%BACKEND%\.venv\Scripts\python.exe" -m pip install -q -r "%BACKEND%\requirements.txt"
        start "PatternSeeker - Backend" cmd /k "cd /d %BACKEND% && call .venv\Scripts\activate && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
    ) else (
        echo       Backend .venv not found. Using system Python.
        start "PatternSeeker - Backend" cmd /k "cd /d %BACKEND% && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
    )
) else (
    echo       Backend is already running.
)

echo       Waiting for Backend API...

set /a COUNT=0
:BACKEND_CHECK
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri '%API_URL%/api/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 goto BACKEND_READY

set /a COUNT+=1
if %COUNT% GEQ 30 (
    echo [ERROR] Backend did not become ready.
    goto FAIL
)
timeout /t 2 /nobreak >nul
goto BACKEND_CHECK

:BACKEND_READY
echo       Backend API is READY.

REM ------------------------------------------------------------
REM 4. Desktop collector
REM ------------------------------------------------------------
echo.
echo [5/7] Starting Desktop Collector...

if exist "%DESKTOP%\.venv\Scripts\python.exe" (
    "%DESKTOP%\.venv\Scripts\python.exe" -m pip install -q -r "%DESKTOP%\requirements.txt"
    start "PatternSeeker - Collector" cmd /k "cd /d %DESKTOP% && set PATH=%PATH%;C:\Program Files\Tesseract-OCR && call .venv\Scripts\activate && python main.py"
) else (
    start "PatternSeeker - Collector" cmd /k "cd /d %DESKTOP% && set PATH=%PATH%;C:\Program Files\Tesseract-OCR && python main.py"
)

timeout /t 5 /nobreak >nul

REM ------------------------------------------------------------
REM 5. Web dashboard
REM ------------------------------------------------------------
echo.
echo [6/7] Starting Web Dashboard...

start "PatternSeeker - Dashboard" cmd /k "cd /d %WEB% && npm run dev"

echo       Waiting for Dashboard...

set /a COUNT=0
:DASHBOARD_CHECK
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri '%WEB_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 goto DASHBOARD_READY

set /a COUNT+=1
if %COUNT% GEQ 30 (
    echo [ERROR] Dashboard did not become ready.
    goto FAIL
)
timeout /t 2 /nobreak >nul
goto DASHBOARD_CHECK

:DASHBOARD_READY
echo       Dashboard is READY.

REM ------------------------------------------------------------
REM 6. Final
REM ------------------------------------------------------------
echo.
echo [7/7] Launching PatternSeeker...
timeout /t 2 /nobreak >nul
start "" "%WEB_URL%"

echo.
echo ============================================================
echo              PATTERNSEEKER IS READY
echo ============================================================
echo.
echo Backend    : %API_URL%
echo API Docs   : %API_URL%/docs
echo Ollama     : %OLLAMA_URL%
echo Qwen Vision: %MODEL%
echo Dashboard  : %WEB_URL%
echo OCR        : Tesseract
echo Screen AI  : Enabled through PatternSeeker .env
echo.
echo Backend, Collector and Dashboard windows will stay open.
echo You may close this launcher window.
echo.
pause
exit /b 0

:FAIL
echo.
echo ============================================================
echo                    STARTUP FAILED
echo ============================================================
echo.
echo Check the error above.
echo.
pause
exit /b 1
