@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Method Post http://127.0.0.1:8000/api/system/shutdown ^| Out-Null; Write-Host 'LegalDesk stop requested.' } catch { Write-Host 'LegalDesk is not running.' }"
endlocal
