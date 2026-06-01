@echo off
setlocal EnableDelayedExpansion
:: ================================================================
:: gemini-consult.bat (Axis-Q) - Synchronous Gemini consultation
::
:: Usage:
::   gemini-consult.bat [query-file]
::
::   [query-file]  optional path to query file.
::                 If omitted, falls back to _sys\gemini\consult-query.txt
::
:: Recommended (parallel-safe): pass a unique per-call filename
::   e.g. cq-20260601185504-a3f2.txt
::
:: Step 1: Write query to unique file (TASK/CONTEXT/QUESTION format)
:: Step 2: PowerShell tool (timeout 180000):
::           $env:PATH += ";P:\_sys\env\nodejs\npm-global"
::           cmd /c "P:\_sys\context\gemini-consult.bat P:\_sys\gemini\cq-{TS}-{RND}.txt" 2>&1
:: ================================================================

:: --- Resolve paths ---
if defined GEMINI_DIR (set "_GD=%GEMINI_DIR%") else (for %%I in ("%~dp0..\gemini") do set "_GD=%%~fI")
if defined BASE_DIR (set "_ROOT=%BASE_DIR%") else (for %%I in ("%~dp0..\..") do set "_ROOT=%%~fI")

:: --- Ensure npm-global (gemini.cmd) is in PATH ---
if exist "%_ROOT%\_sys\env\nodejs\npm-global\gemini.cmd" (
    set "PATH=%_ROOT%\_sys\env\nodejs\npm-global;%PATH%"
)

:: --- Query file: use argument if provided, else default ---
if not "%~1"=="" (
    set "_QFILE=%~1"
) else (
    set "_QFILE=%_GD%\consult-query.txt"
)

:: --- Check query file ---
if not exist "%_QFILE%" (
    echo [Axis-Q] ERROR: query file not found: %_QFILE%
    exit /b 1
)
for %%Z in ("%_QFILE%") do if %%~zZ==0 (
    echo [Axis-Q] ERROR: query file is empty
    exit /b 1
)

:: --- Gemini availability ---
call "%~dp0gemini-mode-check.bat"
if not "%GEMINI_MODE%"=="ON" (
    echo [Axis-Q] ERROR: Gemini not available ^(%GEMINI_OFF_REASON%^)
    exit /b 1
)

:: --- Ratio gate (>= 5 required) ---
call "%_GD%\gemini-gate.bat" 5
if errorlevel 1 (
    echo [Axis-Q] SKIP: GEMINI_RATIO ^< 5
    exit /b 0
)

:: --- Call Gemini ---
echo [Axis-Q] Consulting Gemini...
type "%_QFILE%" | gemini -p "Respond to the task or question below." -o text
set "_EC=!errorlevel!"

if !_EC! neq 0 (
    echo [Axis-Q] ERROR: Gemini exited !_EC!
    call "%~dp0collab-log-append.bat" "Axis-Q" "gemini-consult.bat" "FAIL" "Error: exit !_EC!"
    exit /b !_EC!
)

call "%~dp0collab-log-append.bat" "Axis-Q" "gemini-consult.bat" "OK" "Consult completed"
del "%_QFILE%" >nul 2>&1

set "_GD=" & set "_ROOT=" & set "_QFILE=" & set "_EC="
endlocal
exit /b 0
