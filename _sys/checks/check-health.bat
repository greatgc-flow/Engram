@echo off
setlocal EnableDelayedExpansion

:: ================================================================
:: context-health.bat  -  Axis-H: Context Health Check
::
:: Usage: context-health           (auto-detects; reports JSONL size)
::        context-health --force   (force handoff generation even if not RED)
::
:: Estimates Claude token load via JSONL conversation file size.
:: Thresholds (JSONL overhead ~3x raw text, so 1.2MB ~ 100k tokens):
::   GREEN  : < 600 KB
::   YELLOW : 600 KB - 1.2 MB  (consider /compact soon)
::   RED    : > 1.2 MB          (recommend /compact or new session)
::
:: If RED or --force: calls Gemini to generate _archive/session-handoff.json
:: for state continuity across context boundary or session split.
::
:: Requires: Gemini CLI (GEMINI_MODE=ON) for handoff generation only.
:: Status update to _sys\gemini\status.json runs regardless of Gemini mode.
:: ================================================================

if defined BASE_DIR (set "_BASE=%BASE_DIR%") else (for %%I in ("%~dp0..\..") do set "_BASE=%%~fI")
if defined GEMINI_DIR (set "_GDIR=%GEMINI_DIR%") else set "_GDIR=%_BASE%\_sys\gemini"

set "_PROJECTS_DIR=%_BASE%\_sys\claude\config\projects\P--"
set "_ARCHIVE_DIR=%_BASE%\_archive"
set "_SESSIONS_DIR=%_ARCHIVE_DIR%\sessions"
set "_STATUS_FILE=%_GDIR%\status.json"
set "_HANDOFF=%_ARCHIVE_DIR%\session-handoff.json"

set "_FORCE=0"
if "%~1"=="--force" set "_FORCE=1"

:: --- Gemini mode check ---
call "%~dp0..\hooks\ai-check.bat"

:: --- Find newest JSONL ---
set "_JSONL="
for /f "delims=" %%F in ('dir /b /od /a-d "%_PROJECTS_DIR%\*.jsonl" 2^>nul') do set "_JSONL=%_PROJECTS_DIR%\%%F"

if not defined _JSONL (
    echo [context-health] No JSONL found in %_PROJECTS_DIR%
    echo [context-health] Session not yet started or wrong project directory.
    endlocal
    exit /b 0
)

:: --- Get file size (KB integer + MB decimal) ---
for /f "delims=" %%K in ('powershell -NoProfile -Command "[int]((Get-Item -LiteralPath '!_JSONL!').Length / 1024)"') do set "_SIZE_KB=%%K"
for /f "delims=" %%M in ('powershell -NoProfile -Command "[math]::Round((Get-Item -LiteralPath '!_JSONL!').Length / 1048576, 2)"') do set "_MB=%%M"

:: --- Determine status ---
set "_STATUS=GREEN"
set "_TRIGGER=0"
if !_SIZE_KB! geq 600 set "_STATUS=YELLOW"
if !_SIZE_KB! geq 1200 (
    set "_STATUS=RED"
    set "_TRIGGER=1"
)
if "!_FORCE!"=="1" set "_TRIGGER=1"

:: --- Console output ---
echo.
echo [context-health] JSONL : !_JSONL!
echo [context-health] Size  : !_MB! MB  ^(!_SIZE_KB! KB^)
echo [context-health] Status: !_STATUS!

if "!_STATUS!"=="YELLOW" (
    echo [context-health] WARNING: Context load elevated. Consider /compact before next heavy task.
)
if "!_STATUS!"=="RED" (
    echo [context-health] ALERT: Context near limit. Run /compact or start a new session.
    echo [context-health] Generating session-handoff.json...
)

:: --- Update status.json context_health field ---
if exist "%_STATUS_FILE%" (
    powershell -NoProfile -Command "$f='%_STATUS_FILE%'; $j=Get-Content $f -Raw | ConvertFrom-Json; $ch=[pscustomobject]@{jsonl_mb=[double]'!_MB!';status='!_STATUS!';checked=(Get-Date -Format yyyyMMddHHmmss)}; $j | Add-Member -NotePropertyName 'context_health' -NotePropertyValue $ch -Force; [System.IO.File]::WriteAllText($f,($j|ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))" > nul 2>&1
)

:: --- Update ai_health dashboard field ---
if exist "%_STATUS_FILE%" (
    powershell -NoProfile -Command "$f='%_STATUS_FILE%'; $j=Get-Content $f -Raw|ConvertFrom-Json; $gm=if($j.mode -eq 'ON'){if($j.PSObject.Properties['gemini_metrics'] -and $j.gemini_metrics.consecutive_failures -ge 3){'ERROR'}else{'ON'}}else{'OFF'}; $ts=Get-Date -Format yyyyMMddHHmmss; $ah=[pscustomobject]@{claude_status='!_STATUS!';gemini_status=$gm;last_session_transition_recommended=$null;dashboard_updated=$ts}; $j|Add-Member -NotePropertyName ai_health -NotePropertyValue $ah -Force; [System.IO.File]::WriteAllText($f,($j|ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))" > nul 2>&1
)

:: --- Gemini handoff generation (RED or --force only) ---
if "!_TRIGGER!"=="0" (
    endlocal
    exit /b 0
)

if not "%GEMINI_MODE%"=="ON" (
    echo [context-health] Gemini not available ^(%GEMINI_OFF_REASON%^). Skipping handoff generation.
    echo [context-health] Run start.bat first, or check _sys\gemini\status.json
    endlocal
    exit /b 0
)

:: Find newest session log
set "_SESSION_LOG="
for /f "delims=" %%F in ('dir /b /od /a-d "%_SESSIONS_DIR%\*.md" 2^>nul') do set "_SESSION_LOG=%_SESSIONS_DIR%\%%F"

if not defined _SESSION_LOG (
    echo [context-health] No session log found in %_SESSIONS_DIR%
    echo [context-health] Run ctx-save first to create a session checkpoint.
    echo [context-health] Skipping handoff generation.
    endlocal
    exit /b 0
)

echo [context-health] Session log: !_SESSION_LOG!
echo [context-health] Writing handoff to: %_HANDOFF%

set "_PROMPT=Read this session log and output ONLY a valid JSON object with no extra text, matching this exact schema: {\"version\":\"1.0\",\"generated_at\":\"ISO8601_timestamp\",\"session_context\":{\"project_id\":\"P--\",\"active_axis\":\"last_axis_mentioned_or_none\",\"model_used\":\"claude-sonnet-4-6\"},\"executive_summary\":{\"narrative\":\"dense 3-5 sentence summary of what was accomplished\",\"milestones_reached\":[\"item1\"],\"lessons_learned\":[\"item1\"]},\"technical_state\":{\"modified_files\":[\"path1\"],\"critical_constants\":{\"KEY\":\"VALUE\"},\"pending_changes\":[\"item1\"],\"unresolved_bugs\":[]},\"strategy_for_next_session\":{\"immediate_priority\":\"top 1 next action\",\"risks\":[\"risk1\"],\"suggested_entry_point\":\"first thing to do on next session\"}}. Be factual and dense. Output ONLY the JSON object, nothing else."

for /f "delims=" %%U in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString()"') do set "_EPHEMERAL_SID=%%U"
type "!_SESSION_LOG!" | gemini --session-id !_EPHEMERAL_SID! -p "!_PROMPT!" -o text -y > "%_HANDOFF%" 2>nul

if errorlevel 1 (
    echo [context-health] ERROR: Handoff generation failed. Check Gemini auth.
    call "%~dp0..\hooks\collab-log.bat" "Axis-H" "context-health.bat" "FAIL" "Error: handoff generation failed"
    for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_ERR_DT=%%T"
    if exist "%_STATUS_FILE%" (
        powershell -NoProfile -Command "$f='%_STATUS_FILE%'; $j=Get-Content $f -Raw | ConvertFrom-Json; $j.last_error='context_health_failed_!_ERR_DT!'; [System.IO.File]::WriteAllText($f,($j|ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))" > nul 2>&1
    )
    endlocal
    exit /b 1
)

:: Check for Gemini refusal in output
findstr /i "\[REFUSAL:" "%_HANDOFF%" > nul 2>&1
if not errorlevel 1 (
    del "%_HANDOFF%" > nul 2>&1
    echo [context-health] Gemini refused handoff generation.
    call "%~dp0..\hooks\collab-log.bat" "Axis-H" "context-health.bat" "REFUSED" "Gemini refused request"
    endlocal
    exit /b 1
)

echo [context-health] Handoff written: %_HANDOFF%
call "%~dp0..\hooks\collab-log.bat" "Axis-H" "context-health.bat" "OK" "Handoff: %_HANDOFF%"
echo [context-health] Recommended actions:
echo [context-health]   1. /compact  - compress current context (loses detail)
echo [context-health]   2. New session - read _archive\session-handoff.json to resume

call "%~dp0..\hooks\archive-data.bat" --name scan-health --file "%_ARCHIVE_DIR%\session-handoff.json" || echo [WARN] Archive failed (non-blocking)

endlocal
exit /b 0
