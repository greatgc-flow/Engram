@echo off
setlocal enabledelayedexpansion

:: ======================================================================
:: UPDATE.bat  -  Discover tool/runtime updates and propose a diff
:: Read-only w.r.t. runtimes.json - never auto-applies anything. Review
:: the generated artifact under _archive\tool-updates\<UTC>\ and manually
:: apply the diff to _sys\runtimes.json as the next step.
:: ======================================================================

set "PY_EXE=%~dp0_sys\env\python\python.exe"
if not exist "%PY_EXE%" (
    echo [Error] Python runtime not found at _sys\env\python\python.exe.
    echo Please run INSTALL.bat first to bootstrap the environment.
    exit /b 1
)

echo ^>^>^> Checking for tool and runtime updates...
"%PY_EXE%" "%~dp0_sys\checks\check_tool_updates.py" --propose-diff
if errorlevel 1 (
    echo [Error] Update discovery failed.
    exit /b 1
)

set "LATEST_DIR="
if exist "%~dp0_archive\tool-updates" (
    for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "Get-ChildItem '%~dp0_archive\tool-updates' -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty Name"`) do set "LATEST_DIR=%%D"
)

echo ======================================================================
if not "!LATEST_DIR!"=="" (
    echo Proposal artifacts generated under:
    echo   _archive\tool-updates\!LATEST_DIR!\
) else (
    echo Proposal artifacts generated under _archive\tool-updates\.
)
echo.
echo Please review the proposed changes and manually apply the diff to
echo _sys\runtimes.json as the next step.
echo ======================================================================

endlocal
exit /b 0
