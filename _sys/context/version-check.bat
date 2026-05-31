@echo off
setlocal

:: ================================================================
:: version-check.bat  -  Check latest tool versions via Gemini
::
:: Usage: version-check        (run from sandbox terminal)
::
:: Requires: gemini CLI in PATH (installed via npm-global)
:: Output:   _archive\version-check.json
:: ================================================================

:: --- Resolve BASE_DIR ---
if defined BASE_DIR (
    set "_BASE=%BASE_DIR%"
) else (
    for %%I in ("%~dp0..\..") do set "_BASE=%%~fI"
)

set "OUT_DIR=%_BASE%\_archive"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
set "OUT_FILE=%OUT_DIR%\version-check.json"

:: --- Timestamp for log ---
for /f "delims=" %%I in (
    'powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"'
) do set "_DT=%%I"

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
        if not errorlevel 1 (
            set "GEMINI_MODE=ON"
        ) else (
            set "GEMINI_MODE=OFF"
            set "GEMINI_OFF_REASON=not_installed"
        )
    )
)
set "_GM_RECHECK="
if not "%GEMINI_MODE%"=="ON" (
    echo [version-check] ERROR: Gemini not available.
    echo                 Reason: %GEMINI_OFF_REASON%
    echo                 Run start.bat first, or check _sys\gemini\status.json
    exit /b 1
)

:: --- Run Gemini version search ---
echo [version-check] Querying latest tool versions via Gemini...
echo [version-check] Date: %_DT:~0,8%

gemini -p "Search for the latest stable release versions of these tools as of today. Return ONLY valid JSON, no markdown, no explanation. Format: {\"ripgrep\": \"VERSION\", \"fd\": \"VERSION\", \"jq\": \"VERSION\", \"bat\": \"VERSION\", \"delta\": \"VERSION\", \"fzf\": \"VERSION\", \"oh-my-posh\": \"VERSION\", \"nodejs-lts\": \"VERSION\"} where VERSION is just the version string like 1.2.3. Sources: GitHub releases for BurntSushi/ripgrep, sharkdp/fd, stedolan/jq, sharkdp/bat, dandavison/delta, junegunn/fzf, JanDeDobbeleer/oh-my-posh, and nodejs.org LTS." -o text -y > "%OUT_FILE%" 2>&1

if errorlevel 1 (
    echo [version-check] ERROR: gemini returned non-zero. Check auth or network.
    echo                 Run 'gemini' interactively to re-authenticate.
    del "%OUT_FILE%" > nul 2>&1
    call "%~dp0collab-log-append.bat" "Axis-B" "version-check.bat" "FAIL" "Error: api_error"
    if defined GEMINI_DIR (
        powershell -NoProfile -Command "$f='%GEMINI_DIR%\status.json'; if (Test-Path $f) { $j=Get-Content $f -Raw | ConvertFrom-Json; $j.last_error='version_check_failed_%_DT%'; $j.mode='OFF'; $j.reason='api_error'; [System.IO.File]::WriteAllText($f, ($j | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false))) }"
    )
    exit /b 1
)

:: Check for Gemini refusal in output
findstr /i "\[REFUSAL:" "%OUT_FILE%" > nul 2>&1
if not errorlevel 1 (
    call "%~dp0collab-log-append.bat" "Axis-B" "version-check.bat" "REFUSED" "Gemini refused request"
    del "%OUT_FILE%" > nul 2>&1
    exit /b 1
)

echo [version-check] Done: %OUT_FILE%
echo [version-check] Compare with setup.ps1 version section to find updates.
call "%~dp0collab-log-append.bat" "Axis-B" "version-check.bat" "OK" "Output: %OUT_FILE%"
endlocal
