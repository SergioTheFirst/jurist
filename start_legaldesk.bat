@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8000"
set "BASE_URL=http://%HOST%:%PORT%"
set "HEALTH_URL=%BASE_URL%/health"
set "PYTHON_EXE="

for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$candidates = @('%~dp0.venv\Scripts\python.exe', ($env:LOCALAPPDATA + '\Programs\Python\Python313\python.exe'), ($env:LOCALAPPDATA + '\Programs\Python\Python312\python.exe'), ($env:LOCALAPPDATA + '\Programs\Python\Python311\python.exe'), ($env:LOCALAPPDATA + '\Programs\Python\Python310\python.exe'), ($env:USERPROFILE + '\AppData\Local\Programs\Python\Python313\python.exe'), ($env:USERPROFILE + '\AppData\Local\Programs\Python\Python312\python.exe'), ($env:USERPROFILE + '\AppData\Local\Programs\Python\Python311\python.exe'), ($env:USERPROFILE + '\AppData\Local\Programs\Python\Python310\python.exe')); $path = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1; if (-not $path) { $cmd = Get-Command python -ErrorAction SilentlyContinue; if ($cmd) { $path = $cmd.Source } }; if ($path) { Write-Output $path; exit 0 } else { exit 1 }"` ) do set "PYTHON_EXE=%%P"

if not defined PYTHON_EXE (
    echo [ERROR] Python 3 not found.
    echo Install Python or create .venv in the project root.
    exit /b 1
)

call :check_health
if not errorlevel 1 (
    echo LegalDesk is already running. Opening browser...
    start "" "%BASE_URL%"
    exit /b 0
)

echo Using Python: %PYTHON_EXE%
echo Starting LegalDesk server in this window...
echo Browser will open automatically after /health becomes available.

start "LegalDesk Browser Waiter" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i = 0; $i -lt 40; $i++) { try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%HEALTH_URL%' -TimeoutSec 2; if ($response.StatusCode -eq 200) { Start-Process '%BASE_URL%'; exit 0 } } catch { } Start-Sleep -Seconds 1 } exit 1"

"%PYTHON_EXE%" -m uvicorn backend.main:app --host %HOST% --port %PORT%
exit /b %errorlevel%

:check_health
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%HEALTH_URL%' -TimeoutSec 2; if ($response.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
exit /b %errorlevel%
