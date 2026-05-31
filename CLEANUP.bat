@echo off
setlocal
cd /d "%~dp0"

echo =====================================================
echo  Portable Dev — Cleanup Utility
echo =====================================================
echo  1. Light (Safe) - Temp files, caches, old logs
echo  2. Hard        - Tier 1 + Setup archives + venv
echo  3. Reset       - Tier 2 + Portable Runtimes/Tools
echo  4. ZeroBase    - Tier 3 + Workspace + All data (WIPE)
echo =====================================================
set /p CHOICE="Choose cleanup level (1-4, Default=1): "

if "%CHOICE%"=="2" (
    set "FLAGS=-Hard"
) else if "%CHOICE%"=="3" (
    set "FLAGS=-Reset"
) else if "%CHOICE%"=="4" (
    set "FLAGS=-ZeroBase"
) else (
    set "FLAGS="
)

powershell -NoProfile -ExecutionPolicy Bypass -File "_sys\cleanup.ps1" %FLAGS%

endlocal
pause
