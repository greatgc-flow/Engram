@echo off
setlocal EnableDelayedExpansion

:: ================================================================
:: git-draft.bat  -  Generate conventional commit message draft
::
:: Usage: git-draft           (run from project git root)
::        git-draft --staged  (staged changes only)
::
:: Requires: gemini CLI (GEMINI_MODE=ON), git in PATH
:: Output:   console (draft commit message)
:: ================================================================

if defined BASE_DIR (set "_BASE=%BASE_DIR%") else (for %%I in ("%~dp0..\..") do set "_BASE=%%~fI")

set "DIFF_MODE=HEAD"
if "%~1"=="--staged" set "DIFF_MODE=--staged"

set "TEMP_DIFF=%TEMP%\git_diff_%RANDOM%.txt"

for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_DT=%%I"

:: --- Check Gemini mode (undefined OR stale OFF from previous session start) ---
set "_GM_RECHECK=0"
if not defined GEMINI_MODE set "_GM_RECHECK=1"
if defined GEMINI_MODE if /i "%GEMINI_MODE%"=="OFF" if /i not "%GEMINI_OFF_REASON%"=="manual_override" set "_GM_RECHECK=1"
if "%_GM_RECHECK%"=="1" (
    if "%NO_GEMINI%"=="1" (
        set "GEMINI_MODE=OFF"
        set "GEMINI_OFF_REASON=manual_override"
    ) else (
        where gemini > nul 2>&1
        if not errorlevel 1 (set "GEMINI_MODE=ON") else (
            set "GEMINI_MODE=OFF"
            set "GEMINI_OFF_REASON=not_installed"
        )
    )
)
set "_GM_RECHECK="
if not "%GEMINI_MODE%"=="ON" (
    echo [git-draft] ERROR: Gemini not available. Reason: %GEMINI_OFF_REASON%
    echo             Run start.bat first, or check _sys\gemini\status.json
    exit /b 1
)

:: --- Check git ---
where git > nul 2>&1
if errorlevel 1 (
    echo [git-draft] ERROR: git not found in PATH. Run from sandbox terminal.
    exit /b 1
)

:: --- Get diff ---
git diff %DIFF_MODE% > "%TEMP_DIFF%" 2>&1
if errorlevel 1 (
    echo [git-draft] ERROR: git diff failed.
    del "%TEMP_DIFF%" > nul 2>&1
    exit /b 1
)

for %%A in ("%TEMP_DIFF%") do if %%~zA==0 (
    echo [git-draft] No changes detected (diff is empty).
    del "%TEMP_DIFF%" > nul 2>&1
    exit /b 0
)

echo [git-draft] Generating commit message draft...

set "TEMP_OUT=%TEMP%\git_draft_out_%RANDOM%.txt"
type "%TEMP_DIFF%" | gemini -p "Read the git diff and write a conventional commit message. Format: type(scope): subject. Body (optional, 1-3 bullets of what/why). Rules: type is feat, fix, docs, refactor, chore, test, or style. Subject max 72 chars. English only, imperative mood. Output ONLY the commit message, nothing else." -o text -y > "!TEMP_OUT!" 2>&1
if errorlevel 1 (
    del "%TEMP_DIFF%" > nul 2>&1
    del "!TEMP_OUT!" > nul 2>&1
    echo [git-draft] ERROR: gemini returned non-zero. Check auth or network.
    call "%~dp0collab-log-append.bat" "Axis-G" "git-draft.bat" "FAIL" "Error: api_error"
    if defined GEMINI_DIR (
        for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_ERR_DT=%%T"
        powershell -NoProfile -Command "$f='%GEMINI_DIR%\status.json'; if (Test-Path $f) { $j=Get-Content $f -Raw | ConvertFrom-Json; $j.last_error='git_draft_failed_!_ERR_DT!'; $j.mode='OFF'; $j.reason='api_error'; [System.IO.File]::WriteAllText($f, ($j | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false))) }"
    )
    exit /b 1
)

:: Check for Gemini refusal in output
findstr /i "\[REFUSAL:" "!TEMP_OUT!" > nul 2>&1
if not errorlevel 1 (
    del "!TEMP_OUT!" > nul 2>&1
    del "%TEMP_DIFF%" > nul 2>&1
    call "%~dp0collab-log-append.bat" "Axis-G" "git-draft.bat" "REFUSED" "Gemini refused request"
    exit /b 1
)

:: Print commit message draft to console
type "!TEMP_OUT!"
del "!TEMP_OUT!" > nul 2>&1

del "%TEMP_DIFF%" > nul 2>&1

call "%~dp0collab-log-append.bat" "Axis-G" "git-draft.bat" "OK" "Output: console (commit draft)"
echo.
echo [git-draft] Review and edit before committing. This is a draft only.
endlocal
