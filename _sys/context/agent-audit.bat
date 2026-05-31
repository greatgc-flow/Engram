@echo off
setlocal

:: ================================================================
:: agent-audit.bat  -  Analyze agent consistency via Gemini
::
:: Usage: agent-audit        (run from sandbox terminal)
::
:: Requires: gemini CLI (GEMINI_MODE=ON)
:: Output:   _archive\agent-audit.json
::
:: Note: --include-files was removed in newer Gemini CLI builds.
::       Agent files are merged into a single temp file via PowerShell
::       and piped to gemini via stdin (type file | gemini -p ...).
:: ================================================================

:: --- Resolve BASE_DIR ---
if defined BASE_DIR (
    set "_BASE=%BASE_DIR%"
) else (
    for %%I in ("%~dp0..\..") do set "_BASE=%%~fI"
)

set "AGENTS_DIR=%_BASE%\.claude\agents"
set "OUT_DIR=%_BASE%\_archive"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
set "OUT_FILE=%OUT_DIR%\agent-audit.json"
set "TEMP_MERGED=%TEMP%\agent_audit_merged_%RANDOM%.txt"

:: --- Timestamp ---
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
    echo [agent-audit] ERROR: Gemini not available. Reason: %GEMINI_OFF_REASON%
    echo               Run start.bat first, or check _sys\gemini\status.json
    exit /b 1
)

:: --- Check agents dir exists ---
if not exist "%AGENTS_DIR%" (
    echo [agent-audit] ERROR: Agents directory not found: %AGENTS_DIR%
    exit /b 1
)

:: --- Merge all agent .md files into single temp file (--include-dir not supported) ---
echo [agent-audit] Merging agent definitions from: %AGENTS_DIR%
powershell -NoProfile -Command "$out='%TEMP_MERGED:\=\\%'; $dir='%AGENTS_DIR:\=\\%'; $files=Get-ChildItem $dir -Filter '*.md' -File; if ($files.Count -eq 0) { exit 1 }; $merged = foreach ($f in $files) { '=== ' + $f.Name + ' ==='; Get-Content $f.FullName -Raw }; [System.IO.File]::WriteAllText($out, ($merged -join \"`n\"), (New-Object System.Text.UTF8Encoding($false))); Write-Host ('[agent-audit] Merged ' + $files.Count + ' agent files.')"
if errorlevel 1 (
    echo [agent-audit] ERROR: No agent .md files found in %AGENTS_DIR%
    exit /b 1
)

:: --- Run Gemini agent consistency analysis ---
echo [agent-audit] Analyzing agent definitions via Gemini...

type "%TEMP_MERGED%" | gemini -p "Analyze ALL agent markdown files provided. Find: 1) Role overlaps (two agents doing the same thing), 2) Coverage gaps (tasks no agent handles), 3) Inconsistencies with CONVENTION.md. Return ONLY valid JSON: {\"scan_ts\":\"%_DT%\",\"overlaps\":[{\"agents\":[],\"issue\":\"\"}],\"gaps\":[{\"task\":\"\",\"suggested_owner\":\"\"}],\"inconsistencies\":[{\"agent\":\"\",\"issue\":\"\",\"severity\":\"High or Medium or Low\"}],\"ok_count\":0}" -o text -y > "%OUT_FILE%" 2>&1

if errorlevel 1 (
    echo [agent-audit] ERROR: gemini returned non-zero. Check auth or network.
    del "%OUT_FILE%" > nul 2>&1
    del "%TEMP_MERGED%" > nul 2>&1
    call "%~dp0collab-log-append.bat" "Axis-E" "agent-audit.bat" "FAIL" "Error: api_error"
    if defined GEMINI_DIR (
        powershell -NoProfile -Command "$f='%GEMINI_DIR%\status.json'; if (Test-Path $f) { $j=Get-Content $f -Raw | ConvertFrom-Json; $j.last_error='agent_audit_failed_%_DT%'; $j.mode='OFF'; $j.reason='api_error'; [System.IO.File]::WriteAllText($f, ($j | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false))) }"
    )
    exit /b 1
)

:: Check for Gemini refusal in output
findstr /i "\[REFUSAL:" "%OUT_FILE%" > nul 2>&1
if not errorlevel 1 (
    call "%~dp0collab-log-append.bat" "Axis-E" "agent-audit.bat" "REFUSED" "Gemini refused request"
    del "%OUT_FILE%" > nul 2>&1
    del "%TEMP_MERGED%" > nul 2>&1
    exit /b 1
)

del "%TEMP_MERGED%" > nul 2>&1

:: Clean output: extract JSON block (strip YOLO messages, routing errors, code fences)
powershell -NoProfile -Command "$f='%OUT_FILE%'; $raw=Get-Content $f -Raw; $idx=$raw.IndexOf('{'); if($idx -ge 0){$end=$raw.LastIndexOf('}'); $json=$raw.Substring($idx,$end-$idx+1); [System.IO.File]::WriteAllText($f,$json,(New-Object System.Text.UTF8Encoding($false))); Write-Host '[agent-audit] JSON extracted cleanly.'}else{Write-Host '[agent-audit] WARNING: No JSON found in output.'}"

echo [agent-audit] Done: %OUT_FILE%
echo [agent-audit] Review overlaps and gaps before adding new agents.
call "%~dp0collab-log-append.bat" "Axis-E" "agent-audit.bat" "OK" "Output: %OUT_FILE%"
endlocal
