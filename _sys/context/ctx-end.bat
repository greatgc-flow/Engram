@echo off
setlocal EnableDelayedExpansion

:: ================================================================
:: ctx-end.bat  -  Session end: full summary + Obsidian backup

if defined BASE_DIR (set "_BASE=%BASE_DIR%") else (for %%I in ("%~dp0..\..") do set "_BASE=%%~fI")
::
:: Usage: ctx-end               -> summarize current project
::        ctx-end --global      -> also update global CLAUDE.md
:: ================================================================

:: Check claude CLI is installed
where claude > nul 2>&1
if errorlevel 1 (
    echo [ctx-end] ERROR: 'claude' not found in PATH.
    echo           Run this from a sandbox terminal (via start.bat^).
    echo           Or install: npm install -g @anthropic-ai/claude-code
    exit /b 1
)

:: Check claude is authenticated
if not exist "%CLAUDE_CONFIG_DIR%\.credentials.json" (
    echo [ctx-end] ERROR: Claude credentials not found.
    echo           Run 'claude' in the VS Code terminal to log in first.
    exit /b 1
)

set "GLOBAL_UPDATE=0"
if "%~1"=="--global" set "GLOBAL_UPDATE=1"

set "CLAUDE_MD=%CD%\CLAUDE.md"
if not exist "%CLAUDE_MD%" (
    echo [ctx-end] No CLAUDE.md in: %CD%
    echo           Run from project root, or create from template:
    echo           copy "%~dp0CLAUDE_project.md" "%%CD%%\CLAUDE.md"
    exit /b 1
)

echo [ctx-end] Writing session summary for: %CD%

claude -p "Session end: Update CLAUDE.md fully. 1) Current State: final state. 2) Decisions Made: append any new decisions with rationale. 3) Next Steps: clear prioritized list for next session. 4) Update Last updated date. Be thorough - this is the handoff for the next session."

if errorlevel 1 (
    echo [ctx-end] ERROR: claude returned non-zero.
    pause
    exit /b 1
)

if "%GLOBAL_UPDATE%"=="1" (
    if defined CLAUDE_CONFIG_DIR (
        if exist "%CLAUDE_CONFIG_DIR%\CLAUDE.md" (
            echo [ctx-end] Updating global CLAUDE.md...
            claude -p "Update the global CLAUDE.md at %CLAUDE_CONFIG_DIR%\CLAUDE.md with new preferences or lessons from today. Keep it concise and universal across projects."
        ) else (
            echo [ctx-end] Note: no global CLAUDE.md found at %CLAUDE_CONFIG_DIR%\CLAUDE.md
            echo           Copy _sys\context\CLAUDE_global.md to create one.
        )
    )
)

:: Save full summary to local session log
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_DT=%%I"
set "SES_DATE=%_DT:~0,4%-%_DT:~4,2%-%_DT:~6,2%"
set "SES_TIME=%_DT:~8,2%:%_DT:~10,2%"
if defined SESSION_DIR (set "SES_DIR=%SESSION_DIR%") else (for %%I in ("%~dp0..\..") do set "SES_DIR=%%~fI\_archive\sessions")
for %%I in ("%CD%") do set "_PROJ=%%~nxI"
set "SES_FILE=!SES_DIR!\!SES_DATE!_!_PROJ!.md"
if not exist "!SES_DIR!" mkdir "!SES_DIR!"
if not exist "!SES_FILE!" >> "!SES_FILE!" echo # Sessions !SES_DATE!
>> "!SES_FILE!" echo.
>> "!SES_FILE!" echo ## [ctx-end] !SES_DATE! !SES_TIME! - %CD%
>> "!SES_FILE!" echo.
type "%CLAUDE_MD%" >> "!SES_FILE!"
>> "!SES_FILE!" echo.
>> "!SES_FILE!" echo ---
echo [ctx-end] Session log: !SES_FILE!

echo.
echo [ctx-end] Session saved. Safe to close.
if "%GLOBAL_UPDATE%"=="0" echo         Tip: ctx-end --global  also updates global preferences.

:: Optional: Gemini summary (skipped if GEMINI_MODE is not ON)
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
if "%GEMINI_MODE%"=="ON" (
    set "_SUM=!SES_FILE!.summary.md"
    echo [ctx-end] Generating Gemini summary...
    type "!SES_FILE!" | gemini -p "Read the session log below and write a concise summary with exactly 5 bullet points: 1) What was accomplished 2) Key decisions made 3) Files changed 4) Known issues remaining 5) Next actions. Be specific, not generic." -o text -y > "!_SUM!" 2>&1
    if not errorlevel 1 (
        echo [ctx-end] Summary: !_SUM!
        call "%~dp0collab-log-append.bat" "Axis-C" "ctx-end.bat" "OK" "Summary: !_SUM!"
    ) else (
        del "!_SUM!" > nul 2>&1
        echo [ctx-end] Gemini summary skipped (auth or network issue).
        call "%~dp0collab-log-append.bat" "Axis-C" "ctx-end.bat" "FAIL" "Error: api_error"
        :: Update status.json last_error so gemini-status.bat can surface it
        if defined GEMINI_DIR (
            for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_ERR_DT=%%T"
            powershell -NoProfile -Command "$f='%GEMINI_DIR%\status.json'; if (Test-Path $f) { $j=Get-Content $f -Raw | ConvertFrom-Json; $j.last_error='ctx_end_summary_failed_!_ERR_DT!'; $j.mode='OFF'; $j.reason='api_error'; [System.IO.File]::WriteAllText($f, ($j | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false))) }"
        )
    )
)
:: ── Gemini session JSONL cleanup ─────────────────────────────────
if not defined GEMINI_SESSION_KEEP set "GEMINI_SESSION_KEEP=7"
set "_CHAT_DIR=!_BASE!\_sys\gemini\config\tmp\project\chats"
set "_GS_ARCHIVE=!_BASE!\_archive\gemini-sessions"
if exist "!_CHAT_DIR!" (
    if not exist "!_GS_ARCHIVE!" mkdir "!_GS_ARCHIVE!"
    powershell -NoProfile -Command "$src='!_CHAT_DIR!'; $dst='!_GS_ARCHIVE!'; $keep=[int]'!GEMINI_SESSION_KEEP!'; $cutoff=(Get-Date).AddDays(-$keep); $old=Get-ChildItem $src -Filter '*.jsonl' | Where-Object {$_.LastWriteTime -lt $cutoff}; foreach($f in $old){ Move-Item $f.FullName (Join-Path $dst $f.Name) -Force }; Write-Host ('[ctx-end] Gemini session cleanup: ' + $old.Count + ' files moved to _archive/gemini-sessions/')"
)
:: ─────────────────────────────────────────────────────────────────
endlocal
