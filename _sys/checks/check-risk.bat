@echo off
setlocal EnableDelayedExpansion

:: ================================================================
:: risk-scan.bat  -  Axis-I: Pre-flight Risk Assessment
::
:: Usage: risk-scan.bat "task description" "file1,file2,..."
::
:: Calls Gemini to detect scope conflicts, MECE gaps, requirement
:: ambiguity, and known failure patterns from collab-log history.
:: Outputs: _archive/risk-scan.json
::
:: GEMINI_MODE=OFF -> writes UNKNOWN result, exits 0 (non-blocking).
:: ================================================================

if defined BASE_DIR (set "_BASE=%BASE_DIR%") else (for %%I in ("%~dp0..\..") do set "_BASE=%%~fI")
if defined GEMINI_DIR (set "_GDIR=%GEMINI_DIR%") else set "_GDIR=%_BASE%\_sys\gemini"

set "_ARCHIVE_DIR=%_BASE%\_archive"
set "_COLLAB_LOG_DIR=%_ARCHIVE_DIR%\collab-log"
set "_OUTPUT=%_ARCHIVE_DIR%\risk-scan.json"
set "_CONV_DIR=%_BASE%\CONVENTION.md"

set "_TASK=%~1"
set "_FILES=%~2"

:: --- Gemini mode check ---
call "%~dp0..\hooks\ai-check.bat"

:: --- Gemini OFF: write UNKNOWN result, exit 0 (non-blocking) ---
if not "%GEMINI_MODE%"=="ON" (
    echo [risk-scan] Gemini not available. Skipping risk assessment.
    powershell -NoProfile -Command ^
        "$ts=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'); $out=[pscustomobject]@{agent='risk-scanner';timestamp=$ts;task_summary='%_TASK%';risks=@();overall_risk='UNKNOWN';proceed=$true;note='Gemini unavailable - proceeding without risk scan'}; [System.IO.File]::WriteAllText('%_OUTPUT%',($out | ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))" > nul 2>&1
    echo [risk-scan] Output: %_OUTPUT% (overall_risk=UNKNOWN)
    endlocal
    exit /b 0
)

:: --- Find today's collab-log (last 20 lines) ---
set "_COLLAB_SNIPPET="
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "_TODAY=%%T"
set "_COLLOG=%_COLLAB_LOG_DIR%\%_TODAY%.md"
set "_COLLOG_LINES="
if exist "%_COLLOG%" (
    for /f "delims=" %%L in ('powershell -NoProfile -Command "Get-Content '%_COLLOG%' | Select-Object -Last 20 | Out-String"') do set "_COLLOG_LINES=%%L"
)

:: --- Build prompt ---
set "_PROMPT=You are a pre-flight risk scanner. Analyze the task below and output ONLY a valid JSON object with NO extra text or markdown fences. Schema: {\"agent\":\"risk-scanner\",\"timestamp\":\"ISO8601\",\"task_summary\":\"string\",\"risks\":[{\"level\":\"HIGH|MED|LOW\",\"category\":\"scope|mece|convention|requirement|dependency|known_failure\",\"description\":\"string\",\"affected_files\":[],\"recommendation\":\"ask_user|proceed_with_caution|proceed\"}],\"overall_risk\":\"HIGH|MED|LOW\",\"proceed\":true}. Use overall_risk=HIGH only if there is a critical scope conflict, MECE violation, or a known failure pattern that directly matches this task. TASK: %_TASK%. FILES: %_FILES%."

if defined _COLLOG_LINES (
    set "_PROMPT=%_PROMPT% RECENT COLLAB LOG (last 20 lines - check for known failures): !_COLLOG_LINES!"
)

:: --- Call Gemini ---
echo [risk-scan] Calling Axis-I (Gemini risk assessment)...
for /f "delims=" %%U in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString()"') do set "_EPHEMERAL_SID=%%U"
gemini --session-id !_EPHEMERAL_SID! -p "!_PROMPT!" -o text -y > "%_OUTPUT%" 2>nul

if errorlevel 1 (
    echo [risk-scan] ERROR: Gemini call failed.
    call "%~dp0..\hooks\collab-log.bat" "Axis-I" "risk-scan.bat" "FAIL" "Error: Gemini call failed"
    powershell -NoProfile -Command ^
        "$ts=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'); $out=[pscustomobject]@{agent='risk-scanner';timestamp=$ts;task_summary='%_TASK%';risks=@();overall_risk='UNKNOWN';proceed=$true;note='Gemini call failed'}; [System.IO.File]::WriteAllText('%_OUTPUT%',($out | ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))" > nul 2>&1
    endlocal
    exit /b 1
)

:: Check for Gemini refusal in output (non-blocking: write UNKNOWN result)
findstr /i "\[REFUSAL:" "%_OUTPUT%" > nul 2>&1
if not errorlevel 1 (
    call "%~dp0..\hooks\collab-log.bat" "Axis-I" "risk-scan.bat" "REFUSED" "Gemini refused risk scan - proceeding with UNKNOWN"
    powershell -NoProfile -Command ^
        "$ts=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'); $out=[pscustomobject]@{agent='risk-scanner';timestamp=$ts;task_summary='%_TASK%';risks=@();overall_risk='UNKNOWN';proceed=$true;note='Gemini refused - proceeding without risk scan'}; [System.IO.File]::WriteAllText('%_OUTPUT%',($out | ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))" > nul 2>&1
    echo [risk-scan] Gemini refused. UNKNOWN result written ^(non-blocking^).
    endlocal
    exit /b 0
)

call "%~dp0..\hooks\raw-log.bat" "Axis-I" "%_OUTPUT%"
:: --- Validate JSON output ---
powershell -NoProfile -Command ^
    "$f='%_OUTPUT%'; try { $j=Get-Content $f -Raw | ConvertFrom-Json; $risk=$j.overall_risk; Write-Host \"[risk-scan] overall_risk=$risk\" } catch { Write-Host '[risk-scan] WARNING: Output is not valid JSON - check %_OUTPUT%' }"

call "%~dp0..\hooks\collab-log.bat" "Axis-I" "risk-scan.bat" "OK" "Output: %_OUTPUT%"
echo [risk-scan] Done. Output: %_OUTPUT%

call "%~dp0..\hooks\archive-data.bat" --name scan-risk --file "%_OUTPUT%" || echo [WARN] Archive failed (non-blocking)

endlocal
exit /b 0
