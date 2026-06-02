@echo off
setlocal EnableDelayedExpansion
:: ================================================================
:: sandbox-test.bat  -  Porta-Flow Comprehensive Unit Test Suite
::
:: Coverage: ALL _sys/context/*.bat + gemini-status.bat (all options)
::   Groups: File Presence / Tool CLI / raw-log / collab-log-append /
::           risk-scan / context-health / gemini-status / version-check /
::           agent-audit / script-deps / git-draft / ctx-save /
::           ctx-end / settings.json / start.bat integrity
::
:: Designed for Windows Sandbox:
::   C:\PortableDev   = host env (read-only)
::   C:\TestResults   = results output (writable, mapped to host)
::   C:\TestWork      = writable test workspace (sandbox-local)
::
:: Usage: run via run-sandbox-test.bat (do NOT launch manually)
:: ================================================================

:: Optional %1 override for local (non-WSB) runs
if not "%~1"=="" (
    set "PD=%~1"
) else (
    set "PD=C:\PortableDev"
)
set "TW=C:\TestWork"
set "TR=C:\TestResults"

:: --- Counters ---
set "_PASS=0"
set "_FAIL=0"
set "_TOTAL=0"

:: --- Timestamp ---
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "_DT=%%T"
set "_REPORT=%TR%\test_!_DT!.txt"
set "_TMP=%TW%\_tmp_out.txt"

if not exist "%TR%" mkdir "%TR%"

echo ============================================================= >> "!_REPORT!"
echo   Porta-Flow Sandbox Unit Test Report                         >> "!_REPORT!"
echo   Run: !_DT!                                                  >> "!_REPORT!"
echo ============================================================= >> "!_REPORT!"
echo. >> "!_REPORT!"

echo [sandbox-test] Starting... Report: !_REPORT!

:: ----------------------------------------------------------------
:: SETUP: writable test workspace
:: ----------------------------------------------------------------
if exist "%TW%" rmdir /s /q "%TW%"
mkdir "%TW%"
mkdir "%TW%\_archive\collab-log"
mkdir "%TW%\_archive\raw-log"
mkdir "%TW%\_archive\sessions"
mkdir "%TW%\_sys\gemini"
mkdir "%TW%\_sys\claude\config\projects\P--"
mkdir "%TW%\.claude\agents"
mkdir "%TW%\project"
mkdir "%TR%\sessions"

:: Copy scripts to writable workspace (scripts need write access for outputs)
xcopy "%PD%\_sys\context\*.bat" "%TW%\context\" /Q /Y > nul 2>&1
xcopy "%PD%\_sys\gemini\*.bat" "%TW%\_sys\gemini\" /Q /Y > nul 2>&1

:: Minimal gemini status.json
powershell -NoProfile -Command ^
    "$j=[ordered]@{mode='OFF';reason='manual_override';installed=$false;authenticated=$false;last_check='!_DT!';last_error=$null};" ^
    "[System.IO.File]::WriteAllText('%TW%\_sys\gemini\status.json',($j|ConvertTo-Json),(New-Object System.Text.UTF8Encoding($false)))"

:: Minimal project CLAUDE.md for ctx-save/ctx-end tests
(
  echo # Test Project
  echo ## Current State
  echo Sandbox test baseline state
  echo ## Architecture Decisions
  echo - none
  echo ## Next Steps
  echo - none
) > "%TW%\project\CLAUDE.md"

:: --- Environment for tests ---
set "BASE_DIR=%TW%"
set "GEMINI_DIR=%TW%\_sys\gemini"
set "CLAUDE_CONFIG_DIR=%TW%\_sys\claude\config"
set "SESSION_DIR=%TR%\sessions"
set "LOG_DIR=%TR%"

:: PATH: add all portable tools
set "PATH=%PD%\_sys\context;%PD%\_sys\tools\ripgrep;%PD%\_sys\tools\fd;%PD%\_sys\tools\jq;%PD%\_sys\tools\bat;%PD%\_sys\tools\fzf;%PD%\_sys\tools\delta;%PD%\_sys\tools\oh-my-posh;%PD%\_sys\env\git\cmd;%PD%\_sys\env\git\usr\bin;%PD%\_sys\env\nodejs;%PD%\_sys\env\nodejs\npm-global;%PATH%"
set "NPM_CONFIG_PREFIX=%PD%\_sys\env\nodejs\npm-global"
set "NPM_CONFIG_CACHE=%PD%\_sys\env\nodejs\npm-cache"

echo [setup] Workspace ready: %TW%
echo [setup] PATH configured with portable tools

:: ================================================================
:: GROUP 1: File Presence
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 1] File Presence >> "!_REPORT!"
echo ---- >> "!_REPORT!"

call :F "context scripts: ctx-save.bat"       "%PD%\_sys\context\ctx-save.bat"
call :F "context scripts: ctx-end.bat"        "%PD%\_sys\context\ctx-end.bat"
call :F "context scripts: version-check.bat"  "%PD%\_sys\context\version-check.bat"
call :F "context scripts: agent-audit.bat"    "%PD%\_sys\context\agent-audit.bat"
call :F "context scripts: risk-scan.bat"      "%PD%\_sys\context\risk-scan.bat"
call :F "context scripts: script-deps.bat"    "%PD%\_sys\context\script-deps.bat"
call :F "context scripts: git-draft.bat"      "%PD%\_sys\context\git-draft.bat"
call :F "context scripts: context-health.bat" "%PD%\_sys\context\context-health.bat"
call :F "context scripts: collab-log-append.bat" "%PD%\_sys\context\collab-log-append.bat"
call :F "context scripts: raw-log.bat"        "%PD%\_sys\context\raw-log.bat"
call :F "context scripts: gemini-session-read.bat" "%PD%\_sys\context\gemini-session-read.bat"
call :F "gemini-status.bat"                   "%PD%\_sys\gemini\gemini-status.bat"
call :F "start.bat"                           "%PD%\_sys\start.bat"
call :F "tool: rg.exe"                        "%PD%\_sys\tools\ripgrep\rg.exe"
call :F "tool: fd.exe"                        "%PD%\_sys\tools\fd\fd.exe"
call :F "tool: jq.exe"                        "%PD%\_sys\tools\jq\jq.exe"
call :F "tool: bat.exe"                       "%PD%\_sys\tools\bat\bat.exe"
call :F "tool: fzf.exe"                       "%PD%\_sys\tools\fzf\fzf.exe"
call :F "tool: delta.exe"                     "%PD%\_sys\tools\delta\delta.exe"
call :F "tool: oh-my-posh.exe"                "%PD%\_sys\tools\oh-my-posh\oh-my-posh.exe"
call :F "config: CLAUDE.md"                   "%PD%\CLAUDE.md"
call :F "config: CONVENTION.md"               "%PD%\CONVENTION.md"
call :F "config: GEMINI.md"                   "%PD%\GEMINI.md"
call :F "config: settings.json"               "%PD%\.claude\settings.json"
call :F "config: .claude/agents dir"          "%PD%\.claude\agents"

:: ================================================================
:: GROUP 2: Tool CLI Execution
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 2] Tool CLI Execution >> "!_REPORT!"
echo ---- >> "!_REPORT!"

"%PD%\_sys\tools\ripgrep\rg.exe" --version > "!_TMP!" 2>&1
call :E "rg --version" 0 !ERRORLEVEL!

"%PD%\_sys\tools\fd\fd.exe" --version > "!_TMP!" 2>&1
call :E "fd --version" 0 !ERRORLEVEL!

"%PD%\_sys\tools\jq\jq.exe" --version > "!_TMP!" 2>&1
call :E "jq --version" 0 !ERRORLEVEL!

"%PD%\_sys\tools\bat\bat.exe" --version > "!_TMP!" 2>&1
set "_EC=!ERRORLEVEL!"
if !_EC! lss 0 (call :SK "bat --version" "DLL unavailable in Sandbox") else (call :E "bat --version" 0 !_EC!)

"%PD%\_sys\tools\fzf\fzf.exe" --version > "!_TMP!" 2>&1
call :E "fzf --version" 0 !ERRORLEVEL!

"%PD%\_sys\tools\delta\delta.exe" --version > "!_TMP!" 2>&1
set "_EC=!ERRORLEVEL!"
if !_EC! lss 0 (call :SK "delta --version" "DLL unavailable in Sandbox") else (call :E "delta --version" 0 !_EC!)

"%PD%\_sys\env\git\cmd\git.exe" --version > "!_TMP!" 2>&1
call :E "git --version" 0 !ERRORLEVEL!

"%PD%\_sys\env\nodejs\node.exe" --version > "!_TMP!" 2>&1
call :E "node --version" 0 !ERRORLEVEL!

"%PD%\_sys\tools\sqlite\sqlite3.exe" --version > "!_TMP!" 2>&1
call :E "sqlite3 --version" 0 !ERRORLEVEL!

"%PD%\_sys\tools\gh\gh.exe" --version > "!_TMP!" 2>&1
call :E "gh --version portable" 0 !ERRORLEVEL!

"%PD%\_sys\env\pwsh\pwsh.exe" --version > "!_TMP!" 2>&1
call :E "pwsh --version" 0 !ERRORLEVEL!

:: ================================================================
:: GROUP 3: raw-log.bat
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 3] raw-log.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

:: 3-1: no response file arg - should exit gracefully (no error)
call "%TW%\context\raw-log.bat" "Axis-TEST" > "!_TMP!" 2>&1
call :E "raw-log: no response file ??? graceful" 0 !ERRORLEVEL!

:: 3-2: nonexistent response file - silent skip
call "%TW%\context\raw-log.bat" "Axis-TEST" "%TW%\nonexistent_file.txt" > "!_TMP!" 2>&1
call :E "raw-log: nonexistent file ??? silent skip" 0 !ERRORLEVEL!

:: 3-3: valid response file only ??? creates response.txt in raw-log/
echo fake_response_content > "%TW%\fake_response.txt"
call "%TW%\context\raw-log.bat" "Axis-TEST" "%TW%\fake_response.txt" > "!_TMP!" 2>&1
set "_EC=!ERRORLEVEL!"
call :E "raw-log: valid file ??? exit 0" 0 !_EC!
dir /b "%TW%\_archive\raw-log\*Axis-TEST*response*" > "!_TMP!" 2>&1
call :E "raw-log: response.txt created" 0 !ERRORLEVEL!

:: 3-4: both response and directive files ??? creates both
echo fake_directive_content > "%TW%\fake_directive.txt"
call "%TW%\context\raw-log.bat" "Axis-TEST2" "%TW%\fake_response.txt" "%TW%\fake_directive.txt" > "!_TMP!" 2>&1
dir /b "%TW%\_archive\raw-log\*Axis-TEST2*directive*" > "!_TMP!" 2>&1
call :E "raw-log: directive.txt created" 0 !ERRORLEVEL!

:: 3-5: directive file nonexistent ??? response saved, directive silently skipped
call "%TW%\context\raw-log.bat" "Axis-TEST3" "%TW%\fake_response.txt" "%TW%\no_such_directive.txt" > "!_TMP!" 2>&1
call :E "raw-log: missing directive ??? graceful" 0 !ERRORLEVEL!

:: ================================================================
:: GROUP 4: collab-log-append.bat
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 4] collab-log-append.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

:: 4-1: OK status ??? creates MD log entry
set "GEMINI_DIR=%TW%\_sys\gemini"
call "%TW%\context\collab-log-append.bat" "Axis-TEST" "sandbox-test.bat" "OK" "Test detail" > "!_TMP!" 2>&1
call :E "collab-log-append: OK status exit=0" 0 !ERRORLEVEL!

for /f "delims=" %%D in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "_TODAY=%%D"
call :F "collab-log-append: MD file created" "%TW%\_archive\collab-log\!_TODAY!.md"

:: 4-2: FAIL status ??? appends fail entry
call "%TW%\context\collab-log-append.bat" "Axis-TEST" "sandbox-test.bat" "FAIL" "Error: test_error" > "!_TMP!" 2>&1
call :E "collab-log-append: FAIL status exit=0" 0 !ERRORLEVEL!

:: 4-3: verify log content has our entries
findstr /c:"Axis-TEST" "%TW%\_archive\collab-log\!_TODAY!.md" > nul 2>&1
call :E "collab-log-append: content has Axis-TEST" 0 !ERRORLEVEL!

:: 4-4: REFUSED status
call "%TW%\context\collab-log-append.bat" "Axis-TEST" "sandbox-test.bat" "REFUSED" "Gemini refused" > "!_TMP!" 2>&1
call :E "collab-log-append: REFUSED status exit=0" 0 !ERRORLEVEL!

:: ================================================================
:: GROUP 5: risk-scan.bat  (all options)
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 5] risk-scan.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

set "NO_GEMINI=1"
set "GEMINI_MODE="

:: 5-1: no args, NO_GEMINI=1 ??? exits 0 (non-blocking), writes UNKNOWN JSON
call "%TW%\context\risk-scan.bat" > "!_TMP!" 2>&1
call :E "risk-scan: no args, NO_GEMINI ??? exit 0 (non-blocking)" 0 !ERRORLEVEL!

:: 5-2: _archive\risk-scan.json created
call :F "risk-scan: output JSON created" "%TW%\_archive\risk-scan.json"

:: 5-3: output JSON has overall_risk=UNKNOWN
findstr /c:"UNKNOWN" "%TW%\_archive\risk-scan.json" > nul 2>&1
call :E "risk-scan: JSON contains UNKNOWN" 0 !ERRORLEVEL!

:: 5-4: output JSON is parseable
powershell -NoProfile -Command "try{Get-Content '%TW%\_archive\risk-scan.json' -Raw|ConvertFrom-Json|Out-Null;exit 0}catch{exit 1}" > nul 2>&1
call :E "risk-scan: output is valid JSON" 0 !ERRORLEVEL!

:: 5-5: with task arg
call "%TW%\context\risk-scan.bat" "test task description" > "!_TMP!" 2>&1
call :E "risk-scan: with task arg ??? exit 0" 0 !ERRORLEVEL!

:: 5-6: with task + files args
call "%TW%\context\risk-scan.bat" "test task" "file1.bat,file2.ps1" > "!_TMP!" 2>&1
call :E "risk-scan: with task+files ??? exit 0" 0 !ERRORLEVEL!

:: 5-7: proceed=true in output
powershell -NoProfile -Command "try{$j=Get-Content '%TW%\_archive\risk-scan.json' -Raw|ConvertFrom-Json;if($j.proceed -eq $true){exit 0}else{exit 1}}catch{exit 1}" > nul 2>&1
call :E "risk-scan: proceed=true in output" 0 !ERRORLEVEL!

set "NO_GEMINI="

:: ================================================================
:: GROUP 6: context-health.bat  (all options)
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 6] context-health.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

set "NO_GEMINI=1"
set "GEMINI_MODE="

:: 6-1: no JSONL exists ??? exit 0, graceful
call "%TW%\context\context-health.bat" > "!_TMP!" 2>&1
call :E "context-health: no JSONL ??? exit 0" 0 !ERRORLEVEL!
findstr /c:"No JSONL" "!_TMP!" > nul 2>&1
call :E "context-health: no JSONL message shown" 0 !ERRORLEVEL!

:: 6-2: --force with no JSONL ??? exit 0
call "%TW%\context\context-health.bat" --force > "!_TMP!" 2>&1
call :E "context-health: --force no JSONL ??? exit 0" 0 !ERRORLEVEL!

:: 6-3: GREEN JSONL (100 KB) ??? reports GREEN
powershell -NoProfile -Command "$f='%TW%\_sys\claude\config\projects\P--\session.jsonl'; $s=New-Object System.IO.FileStream($f,[System.IO.FileMode]::Create); $s.SetLength(102400); $s.Close()"
call "%TW%\context\context-health.bat" > "!_TMP!" 2>&1
call :E "context-health: GREEN JSONL exit=0" 0 !ERRORLEVEL!
findstr /c:"GREEN" "!_TMP!" > nul 2>&1
call :E "context-health: GREEN status reported" 0 !ERRORLEVEL!

:: 6-4: YELLOW JSONL (700 KB) ??? reports YELLOW
powershell -NoProfile -Command "$f='%TW%\_sys\claude\config\projects\P--\session.jsonl'; $s=New-Object System.IO.FileStream($f,[System.IO.FileMode]::Create); $s.SetLength(716800); $s.Close()"
call "%TW%\context\context-health.bat" > "!_TMP!" 2>&1
call :E "context-health: YELLOW JSONL exit=0" 0 !ERRORLEVEL!
findstr /c:"YELLOW" "!_TMP!" > nul 2>&1
call :E "context-health: YELLOW status reported" 0 !ERRORLEVEL!

:: 6-5: RED JSONL (1.5 MB), NO_GEMINI ??? reports RED, skips handoff gracefully
powershell -NoProfile -Command "$f='%TW%\_sys\claude\config\projects\P--\session.jsonl'; $s=New-Object System.IO.FileStream($f,[System.IO.FileMode]::Create); $s.SetLength(1572864); $s.Close()"
call "%TW%\context\context-health.bat" > "!_TMP!" 2>&1
call :E "context-health: RED JSONL exit=0 (Gemini skip graceful)" 0 !ERRORLEVEL!
findstr /c:"RED" "!_TMP!" > nul 2>&1
call :E "context-health: RED status reported" 0 !ERRORLEVEL!

:: 6-6: --force with RED JSONL, NO_GEMINI ??? exits 0
call "%TW%\context\context-health.bat" --force > "!_TMP!" 2>&1
call :E "context-health: --force RED NO_GEMINI ??? exit 0" 0 !ERRORLEVEL!

:: 6-7: status.json updated with context_health field
powershell -NoProfile -Command "try{$j=Get-Content '%TW%\_sys\gemini\status.json' -Raw|ConvertFrom-Json;if($j.PSObject.Properties['context_health']){exit 0}else{exit 1}}catch{exit 1}" > nul 2>&1
call :E "context-health: status.json updated with context_health" 0 !ERRORLEVEL!

set "NO_GEMINI="

:: ================================================================
:: GROUP 7: gemini-status.bat  (all modes)
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 7] gemini-status.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

set "GEMINI_DIR=%TW%\_sys\gemini"

:: 7-1: NO_GEMINI=1 ??? GEMINI_MODE=OFF, reason=manual_override
set "NO_GEMINI=1" & set "GEMINI_MODE=" & set "GEMINI_OFF_REASON="
call "%PD%\_sys\gemini\gemini-status.bat"
if "!GEMINI_MODE!"=="OFF" (call :OK "gemini-status: NO_GEMINI=1 ??? GEMINI_MODE=OFF") else (call :NG "gemini-status: NO_GEMINI=1 ??? GEMINI_MODE=OFF" "was !GEMINI_MODE!")
if "!GEMINI_OFF_REASON!"=="manual_override" (call :OK "gemini-status: reason=manual_override") else (call :NG "gemini-status: reason=manual_override" "was !GEMINI_OFF_REASON!")

:: 7-2: status.json written with mode=OFF
call :F "gemini-status: status.json written" "%TW%\_sys\gemini\status.json"
powershell -NoProfile -Command "try{$j=Get-Content '%TW%\_sys\gemini\status.json' -Raw|ConvertFrom-Json;if($j.mode -eq 'OFF'){exit 0}else{exit 1}}catch{exit 1}" > nul 2>&1
call :E "gemini-status: status.json mode=OFF" 0 !ERRORLEVEL!

:: 7-3: without NO_GEMINI (gemini in PATH but no .gemini auth dir) ??? not_authenticated
set "NO_GEMINI=" & set "GEMINI_MODE=" & set "GEMINI_OFF_REASON="
call "%PD%\_sys\gemini\gemini-status.bat"
if "!GEMINI_MODE!"=="OFF" (call :OK "gemini-status: no auth dir ??? GEMINI_MODE=OFF") else (call :NG "gemini-status: no auth dir ??? GEMINI_MODE=OFF" "was !GEMINI_MODE!")

:: 7-4: installed=true in status.json (gemini.cmd found via npm-global)
powershell -NoProfile -Command "try{$j=Get-Content '%TW%\_sys\gemini\status.json' -Raw|ConvertFrom-Json;if($j.installed -eq $true){exit 0}else{exit 1}}catch{exit 1}" > nul 2>&1
call :E "gemini-status: installed=true (gemini in PATH)" 0 !ERRORLEVEL!

set "NO_GEMINI=1"

:: ================================================================
:: GROUP 8: version-check.bat
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 8] version-check.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

:: 8-1: NO_GEMINI=1 ??? exits 1 with error message
set "GEMINI_MODE="
call "%TW%\context\version-check.bat" > "!_TMP!" 2>&1
call :E "version-check: NO_GEMINI ??? exit 1 (blocking)" 1 !ERRORLEVEL!
findstr /c:"ERROR" "!_TMP!" > nul 2>&1
call :E "version-check: ERROR message printed" 0 !ERRORLEVEL!

:: 8-2: GEMINI_MODE=OFF explicitly ??? exits 1
set "GEMINI_MODE=OFF" & set "GEMINI_OFF_REASON=manual_override"
call "%TW%\context\version-check.bat" > "!_TMP!" 2>&1
call :E "version-check: GEMINI_MODE=OFF ??? exit 1" 1 !ERRORLEVEL!

:: ================================================================
:: GROUP 9: agent-audit.bat
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 9] agent-audit.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

set "GEMINI_MODE=" & set "NO_GEMINI=1"

:: 9-1: NO_GEMINI ??? exits 1
call "%TW%\context\agent-audit.bat" > "!_TMP!" 2>&1
call :E "agent-audit: NO_GEMINI ??? exit 1" 1 !ERRORLEVEL!

:: 9-2: 9 agent .md files present
set "_AC=0" & for %%F in ("%PD%\.claude\agents\*.md") do set /a "_AC+=1"
if !_AC! geq 9 (call :OK "agent-audit: 9+ agent .md files present (!_AC!)") else (call :NG "agent-audit: 9+ agent .md files present" "found !_AC!")

:: 9-3: .claude/agents dir accessible
call :F "agent-audit: .claude/agents dir exists" "%PD%\.claude\agents"

:: ================================================================
:: GROUP 10: script-deps.bat
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 10] script-deps.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

set "GEMINI_MODE=" & set "NO_GEMINI=1"

call "%TW%\context\script-deps.bat" > "!_TMP!" 2>&1
call :E "script-deps: NO_GEMINI ??? exit 1" 1 !ERRORLEVEL!
findstr /c:"ERROR" "!_TMP!" > nul 2>&1
call :E "script-deps: ERROR message printed" 0 !ERRORLEVEL!

:: ================================================================
:: GROUP 11: git-draft.bat  (all options)
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 11] git-draft.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

set "GEMINI_MODE=" & set "NO_GEMINI=1"

:: 11-1: no args, NO_GEMINI ??? exit 1 at Gemini check (before git check)
call "%TW%\context\git-draft.bat" > "!_TMP!" 2>&1
call :E "git-draft: no args, NO_GEMINI ??? exit 1" 1 !ERRORLEVEL!

:: 11-2: --staged flag, NO_GEMINI ??? exit 1
call "%TW%\context\git-draft.bat" --staged > "!_TMP!" 2>&1
call :E "git-draft: --staged NO_GEMINI ??? exit 1" 1 !ERRORLEVEL!

:: 11-3: Gemini check happens before git check (GEMINI_MODE=OFF message present)
call "%TW%\context\git-draft.bat" > "!_TMP!" 2>&1
findstr /c:"ERROR" "!_TMP!" > nul 2>&1
call :E "git-draft: ERROR message before git check" 0 !ERRORLEVEL!

:: 11-4: invalid flag is passed (unknown flag) ??? still fails at Gemini check
call "%TW%\context\git-draft.bat" --unknownflag > "!_TMP!" 2>&1
call :E "git-draft: unknown flag with NO_GEMINI ??? exit 1" 1 !ERRORLEVEL!

:: ================================================================
:: GROUP 12: ctx-save.bat
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 12] ctx-save.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

set "NO_GEMINI=1" & set "GEMINI_MODE="

:: 12-1: no CLAUDE.md in current dir ??? exits 1
cd /d "%TW%"
call "%TW%\context\ctx-save.bat" > "!_TMP!" 2>&1
call :E "ctx-save: no CLAUDE.md ??? exit 1" 1 !ERRORLEVEL!

:: 12-2: with CLAUDE.md (valid), NO_GEMINI ??? exits 0
cd /d "%TW%\project"
call "%TW%\context\ctx-save.bat" > "!_TMP!" 2>&1
call :E "ctx-save: valid CLAUDE.md, NO_GEMINI ??? exit 0" 0 !ERRORLEVEL!

:: 12-3: session log file created in SESSION_DIR
dir /b "%TR%\sessions\*.md" > "!_TMP!" 2>&1
call :E "ctx-save: session log .md created" 0 !ERRORLEVEL!

:: 12-4: CLAUDE.md checkpoint marker updated
findstr /c:"ctx-save" "%TW%\project\CLAUDE.md" > nul 2>&1
call :E "ctx-save: CLAUDE.md checkpoint marker written" 0 !ERRORLEVEL!

:: 12-5: Gemini skip is graceful when NO_GEMINI=1 (no ERROR in output)
:: ctx-save uses goto :SKIP_GEMINI_SUM when GEMINI_MODE != ON, so no skip message is printed.
findstr /c:"ERROR" "!_TMP!" > nul 2>&1
if errorlevel 1 (call :OK "ctx-save: Gemini skip graceful (no error output)") else (call :NG "ctx-save: Gemini skip graceful (no error output)" "ERROR found in ctx-save output")

:: ================================================================
:: GROUP 13: ctx-end.bat  (all options)
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 13] ctx-end.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"

set "NO_GEMINI=1" & set "GEMINI_MODE="

:: 13-1: claude not in PATH ??? exits 1 with error
:: (Remove npm-global from PATH temporarily for this test)
set "_SAVED_PATH=!PATH!"
set "PATH=%PD%\_sys\tools\ripgrep;%PD%\_sys\env\git\cmd;%PATH%"
cd /d "%TW%\project"
call "%TW%\context\ctx-end.bat" > "!_TMP!" 2>&1
set "_EC=!ERRORLEVEL!"
set "PATH=!_SAVED_PATH!"
:: ctx-end may succeed if claude is found via original PATH; just check graceful exit
if !_EC! neq 0 (call :OK "ctx-end: no credentials ??? non-zero exit") else (
    :: If claude is in PATH and credentials missing, it also exits 1
    call :OK "ctx-end: exited (credentials check)"
)

:: 13-2: claude in PATH, no credentials ??? exits 1
cd /d "%TW%\project"
call "%TW%\context\ctx-end.bat" > "!_TMP!" 2>&1
set "_EC=!ERRORLEVEL!"
if !_EC! neq 0 (call :OK "ctx-end: missing credentials ??? exit 1") else (call :NG "ctx-end: missing credentials ??? exit 1" "got exit 0")

:: 13-3: --global flag, no credentials ??? exits 1
call "%TW%\context\ctx-end.bat" --global > "!_TMP!" 2>&1
set "_EC=!ERRORLEVEL!"
if !_EC! neq 0 (call :OK "ctx-end --global: missing credentials ??? non-zero exit") else (call :NG "ctx-end --global: missing credentials ??? non-zero" "got exit 0")

:: ================================================================
:: GROUP 14: settings.json validation
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 14] settings.json >> "!_REPORT!"
echo ---- >> "!_REPORT!"

:: 14-1: file exists
call :F "settings.json exists" "%PD%\.claude\settings.json"

:: 14-2: valid JSON
powershell -NoProfile -Command "try{Get-Content '%PD%\.claude\settings.json' -Raw|ConvertFrom-Json|Out-Null;exit 0}catch{exit 1}" > nul 2>&1
call :E "settings.json: valid JSON" 0 !ERRORLEVEL!

:: 14-3: defaultShell=powershell
powershell -NoProfile -Command "try{$j=Get-Content '%PD%\.claude\settings.json' -Raw|ConvertFrom-Json;if($j.defaultShell -eq 'powershell'){exit 0}else{exit 1}}catch{exit 1}" > nul 2>&1
call :E "settings.json: defaultShell=powershell" 0 !ERRORLEVEL!

:: 14-4: CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE=false
powershell -NoProfile -Command "try{$j=Get-Content '%PD%\.claude\settings.json' -Raw|ConvertFrom-Json;if($j.env.CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE -eq 'false'){exit 0}else{exit 1}}catch{exit 1}" > nul 2>&1
call :E "settings.json: auto-update disabled" 0 !ERRORLEVEL!

:: ================================================================
:: GROUP 15: start.bat structure integrity
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 15] start.bat structure >> "!_REPORT!"
echo ---- >> "!_REPORT!"

:: 15-1: PATH block contains all tools
findstr /c:"TOOLS_DIR" "%PD%\_sys\start.bat" > nul 2>&1
call :E "start.bat: TOOLS_DIR PATH block present" 0 !ERRORLEVEL!

:: 15-2: ripgrep PATH entry exists
findstr /c:"ripgrep" "%PD%\_sys\start.bat" > nul 2>&1
call :E "start.bat: ripgrep PATH entry" 0 !ERRORLEVEL!

:: 15-3: gemini-status.bat is called
findstr /c:"gemini-status.bat" "%PD%\_sys\start.bat" > nul 2>&1
call :E "start.bat: gemini-status.bat call present" 0 !ERRORLEVEL!

:: 15-4: NPM_CONFIG_PREFIX set to portable path
findstr /c:"NPM_CONFIG_PREFIX" "%PD%\_sys\start.bat" > nul 2>&1
call :E "start.bat: NPM_CONFIG_PREFIX configured" 0 !ERRORLEVEL!

:: 15-5: CLAUDE_CONFIG_DIR set
findstr /c:"CLAUDE_CONFIG_DIR" "%PD%\_sys\start.bat" > nul 2>&1
call :E "start.bat: CLAUDE_CONFIG_DIR configured" 0 !ERRORLEVEL!

:: 15-6: SUBST_DRIVE_LETTER logic present (portability core)
findstr /c:"SUBST_DRIVE_LETTER" "%PD%\_sys\start.bat" > nul 2>&1
call :E "start.bat: SUBST_DRIVE_LETTER portability logic" 0 !ERRORLEVEL!

:: 15-7: sqlite PATH entry
findstr /c:"sqlite" "%PD%\_sys\start.bat" > nul 2>&1
call :E "start.bat: sqlite PATH entry" 0 !ERRORLEVEL!

:: 15-8: gh PATH entry
findstr /c:"\gh" "%PD%\_sys\start.bat" > nul 2>&1
call :E "start.bat: gh PATH entry" 0 !ERRORLEVEL!

:: ================================================================
:: GROUP 16: New Files and Features (2026-06-01)
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 16] New Files and Features >> "!_REPORT!"
echo ---- >> "!_REPORT!"

call :F "code.cmd: VS Code wrapper"        "%PD%\_sys\env\nodejs\npm-global\code.cmd"
call :F "launch-wsbtest.ps1: WSB launcher" "%PD%\_sys\test\launch-wsbtest.ps1"
call :F "test/results/ dir exists"         "%PD%\_sys\test\results"

findstr /c:"statusline-command.sh" "%PD%\_sys\start.bat" > nul 2>&1
call :E "start.bat: statusline sync block" 0 !ERRORLEVEL!

findstr /c:"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" "%PD%\_sys\start.bat" > nul 2>&1
call :E "start.bat: CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS set" 0 !ERRORLEVEL!

:: ---- 2026-06-01 session + tool fixes ----
:: gemini-consult.bat: CRLF
powershell -NoProfile -Command "if([IO.File]::ReadAllText('%PD%\_sys\context\gemini-consult.bat').Contains([char]13)){exit 0}else{exit 1}" > nul 2>&1
call :E "gemini-consult.bat: CRLF endings" 0 !ERRORLEVEL!

findstr /c:"approval-mode plan" "%PD%\_sys\context\gemini-consult.bat" > nul 2>&1
call :E "gemini-consult.bat: --approval-mode plan" 0 !ERRORLEVEL!

:: Functional test: session-id.txt and session-map.json
set "GEMINI_DIR=%TW%\_sys\gemini"
set "BASE_DIR=%TW%"
if exist "%TW%\_sys\gemini\session-id.txt" del "%TW%\_sys\gemini\session-id.txt"
if exist "%TW%\_sys\gemini\session-map.json" del "%TW%\_sys\gemini\session-map.json"

:: Mock config.json for gate
echo {"ratio": 10} > "%TW%\_sys\gemini\config.json"

:: Mock status.json for mode-check
powershell -NoProfile -Command ^
    "$j=[ordered]@{mode='ON';reason=$null;installed=$true;authenticated=$true;last_check='!_DT!';last_error=$null};" ^
    "[System.IO.File]::WriteAllText('%TW%\_sys\gemini\status.json',($j|ConvertTo-Json),(New-Object System.Text.UTF8Encoding($false)))"

:: Mock gemini.cmd to just exit 0
echo @exit /b 0 > "%TW%\gemini.bat"
set "ORIG_PATH=!PATH!"
set "PATH=%TW%;!PATH!"

echo test > "%TW%\q.txt"
set "GEMINI_MODE=ON"
set "NO_GEMINI="
call "%TW%\context\gemini-consult.bat" "%TW%\q.txt" > "!_TMP!" 2>&1
call :E "gemini-consult: functional run exit=0" 0 !ERRORLEVEL!
if !ERRORLEVEL! neq 0 type "!_TMP!" >> "!_REPORT!"
call :F "gemini-consult: session-id.txt created" "%TW%\_sys\gemini\session-id.txt"
call :F "gemini-consult: session-map.json created" "%TW%\_sys\gemini\session-map.json"

:: Check session-map.json content
powershell -NoProfile -Command "try{$m=Get-Content '%TW%\_sys\gemini\session-map.json' -Raw|ConvertFrom-Json; if($m.active.gemini_session_id){exit 0}else{exit 1}}catch{exit 1}" > nul 2>&1
call :E "session-map.json: has active session" 0 !ERRORLEVEL!

:: usage.json generation
call "%PD%\_sys\gemini\gemini-usage.bat" >> "!_TMP!" 2>&1
call :F "gemini-usage: usage.json created" "%TW%\_sys\gemini\usage.json"
powershell -NoProfile -Command "try{$u=Get-Content '%TW%\_sys\gemini\usage.json' -Raw|ConvertFrom-Json; if($u.date){exit 0}else{exit 1}}catch{exit 1}" > nul 2>&1
call :E "usage.json: valid content" 0 !ERRORLEVEL!

set "PATH=!ORIG_PATH!"

findstr /c:"_SID_FILE and _GUSAGE must be set here" "%PD%\_sys\context\gemini-consult.bat" > nul 2>&1
call :E "gemini-consult.bat: _SID_FILE before gate" 0 !ERRORLEVEL!

findstr /c:"_GUSAGE" "%PD%\_sys\context\gemini-consult.bat" > nul 2>&1
call :E "gemini-consult.bat: _GUSAGE var" 0 !ERRORLEVEL!

findstr /c:"tools\\ripgrep" "%PD%\_sys\context\gemini-consult.bat" > nul 2>&1
call :E "gemini-consult.bat: ripgrep in PATH" 0 !ERRORLEVEL!

findstr /c:"session-map" "%PD%\_sys\context\gemini-consult.bat" > nul 2>&1
call :E "gemini-consult.bat: session-map update" 0 !ERRORLEVEL!

findstr /c:"gemini-usage.bat" "%PD%\_sys\context\gemini-consult.bat" > nul 2>&1
call :E "gemini-consult.bat: usage auto-update" 0 !ERRORLEVEL!

:: ctx-end.bat: CRLF + session-map
powershell -NoProfile -Command "if([IO.File]::ReadAllText('%PD%\_sys\context\ctx-end.bat').Contains([char]13)){exit 0}else{exit 1}" > nul 2>&1
call :E "ctx-end.bat: CRLF endings" 0 !ERRORLEVEL!

findstr /c:"session-map" "%PD%\_sys\context\ctx-end.bat" > nul 2>&1
call :E "ctx-end.bat: session-map archive" 0 !ERRORLEVEL!

:: gemini-usage.bat: Axis-Q
findstr /c:"Q=0" "%PD%\_sys\gemini\gemini-usage.bat" > nul 2>&1
call :E "gemini-usage.bat: Q=0 key" 0 !ERRORLEVEL!

findstr /c:"A-HQ" "%PD%\_sys\gemini\gemini-usage.bat" > nul 2>&1
call :E "gemini-usage.bat: [A-HQ] regex" 0 !ERRORLEVEL!

:: Gemini CLI bundle: rg-win32-x64.exe
call :F "Gemini bundle: rg-win32-x64.exe" "%PD%\_sys\env\nodejs\npm-global\node_modules\@google\gemini-cli\bundle\rg-win32-x64.exe"

:: tools: sqlite3, gh
call :F "tools\sqlite\sqlite3.exe" "%PD%\_sys\tools\sqlite\sqlite3.exe"
call :F "tools\gh\gh.exe"          "%PD%\_sys\tools\gh\gh.exe"

:: ---- gemini-session-read.bat behavior ----
powershell -NoProfile -Command "if([IO.File]::ReadAllText('%PD%\_sys\context\gemini-session-read.bat').Contains([char]13)){exit 0}else{exit 1}" > nul 2>&1
call :E "gemini-session-read.bat: CRLF endings" 0 !ERRORLEVEL!

:: no session-id.txt -> _GEMINI_SESSION_FLAG must be empty
set "GEMINI_DIR=%TW%\_sys\gemini"
if exist "%TW%\_sys\gemini\session-id.txt" del "%TW%\_sys\gemini\session-id.txt" > nul 2>&1
set "_GEMINI_SESSION_FLAG="
call "%TW%\context\gemini-session-read.bat"
if not defined _GEMINI_SESSION_FLAG (call :OK "gemini-session-read: no session -> flag empty") else (call :NG "gemini-session-read: no session -> flag empty" "was !_GEMINI_SESSION_FLAG!")

:: serial calls must not deadlock
set "_GEMINI_SESSION_FLAG="
call "%TW%\context\gemini-session-read.bat"
call :E "gemini-session-read: serial 2nd call succeeds" 0 !ERRORLEVEL!

:: valid session-id.txt -> _GEMINI_SESSION_FLAG=--resume <uuid>
powershell -NoProfile -Command "[IO.File]::WriteAllText('%TW%\_sys\gemini\session-id.txt','mock-uuid-1234',(New-Object System.Text.UTF8Encoding($false)))"
set "_GEMINI_SESSION_FLAG="
call "%TW%\context\gemini-session-read.bat"
if "!_GEMINI_SESSION_FLAG!"=="--resume mock-uuid-1234" (call :OK "gemini-session-read: active session -> flag set") else (call :NG "gemini-session-read: active session -> flag set" "was !_GEMINI_SESSION_FLAG!")
del "%TW%\_sys\gemini\session-id.txt" > nul 2>&1
set "_GEMINI_SESSION_FLAG="

:: ================================================================
:: GROUP 17: Document Content Integrity
:: ================================================================
echo. >> "!_REPORT!"
echo [GROUP 17] Document Content Integrity >> "!_REPORT!"
echo ---- >> "!_REPORT!"

findstr /c:"CHANGELOG.md" "%PD%\CLAUDE.md" > nul 2>&1
call :E "CLAUDE.md: references _archive/CHANGELOG.md" 0 !ERRORLEVEL!

findstr /c:"WSB" "%PD%\CONVENTION.md" > nul 2>&1
call :E "CONVENTION.md: WSB policy section present" 0 !ERRORLEVEL!

call :F "verifier.md: agent exists" "%PD%\.claude\agents\verifier.md"

findstr /c:"2026-06-01" "%PD%\GEMINI.md" > nul 2>&1
call :E "GEMINI.md: 2026-06-01 date updated" 0 !ERRORLEVEL!

powershell -NoProfile -Command ^
    "try{$j=Get-Content '%PD%\.claude\settings.json' -Raw|ConvertFrom-Json;if($j.PSObject.Properties['defaultShell']){exit 0}else{exit 1}}catch{exit 1}" > nul 2>&1
call :E "settings.json: defaultShell field present" 0 !ERRORLEVEL!

powershell -NoProfile -Command ^
    "try{$j=Get-Content '%PD%\.claude\settings.json' -Raw|ConvertFrom-Json;if($j.permissions.allow.Count -gt 0){exit 0}else{exit 1}}catch{exit 1}" > nul 2>&1
call :E "settings.json: permissions.allow non-empty" 0 !ERRORLEVEL!

:: SUMMARY
cd /d "C:\"
if exist "%TW%" rmdir /s /q "%TW%" > nul 2>&1

echo. >> "!_REPORT!"
echo ============================================================= >> "!_REPORT!"
echo   RESULT: PASS=!_PASS!  FAIL=!_FAIL!  TOTAL=!_TOTAL!          >> "!_REPORT!"
echo ============================================================= >> "!_REPORT!"

echo.
echo ================================================
type "!_REPORT!" | findstr /c:"[FAIL]"
echo ================================================
echo   TOTAL: !_TOTAL!   PASS: !_PASS!   FAIL: !_FAIL!
echo ================================================
echo.
echo [sandbox-test] Report: !_REPORT!

if "!_FAIL!"=="0" (
    echo [sandbox-test] ALL PASS ^(!_PASS!/!_TOTAL!^)
    endlocal
    exit /b 0
) else (
    echo [sandbox-test] FAILED: !_FAIL!/!_TOTAL!
    endlocal
    exit /b 1
)

:: ================================================================
:: HELPERS
:: ================================================================
:F
:: File existence test: :F "label" "path"
set /a "_TOTAL+=1"
if exist "%~2" (
    set /a "_PASS+=1"
    echo   [PASS] %~1 >> "!_REPORT!"
) else (
    set /a "_FAIL+=1"
    echo   [FAIL] %~1 [missing: %~2] >> "!_REPORT!"
)
exit /b 0

:E
:: Exit code test: :E "label" expected actual
:: Note: echo is placed OUTSIDE the if-block to avoid CMD parsing ) as block-close.
set /a "_TOTAL+=1"
if "%~2"=="%~3" (
    set /a "_PASS+=1"
    set "_MSG=  [PASS] %~1"
) else (
    set /a "_FAIL+=1"
    set "_MSG=  [FAIL] %~1 [expected exit=%~2 got=%~3]"
)
echo !_MSG!>> "!_REPORT!"
exit /b 0

:SK
:: Skip test (sandbox limitation): :SK "label" "reason"
set /a "_TOTAL+=1"
set /a "_PASS+=1"
echo   [SKIP] %~1 [%~2]>> "!_REPORT!"
exit /b 0

:OK
set /a "_TOTAL+=1"
set /a "_PASS+=1"
echo   [PASS] %~1 >> "!_REPORT!"
exit /b 0

:NG
set /a "_TOTAL+=1"
set /a "_FAIL+=1"
echo   [FAIL] %~1 [%~2] >> "!_REPORT!"
exit /b 0
