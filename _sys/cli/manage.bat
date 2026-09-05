@echo off
cd /d "%~dp0..\.."
setlocal DisableDelayedExpansion
:: manage.bat - Wrapper for manage.py
:: Unified Sandbox Environment Manager

set "PY=_sys\env\python\python.exe"

if not exist "%PY%" echo [Error] Portable Python not found at: "%PY%" && exit /b 1

"%PY%" "_sys\cli\manage.py" %*
endlocal
