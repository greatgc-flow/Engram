@echo off
setlocal EnableDelayedExpansion
:: ================================================================
:: local-test.bat  -  Run unit tests in current environment (no sandbox)
::
:: Adapts sandbox-test.bat for local P:\ execution.
:: Results: _archive\test-results\local_YYYYMMDD_HHMMSS.txt
::
:: Usage: local-test.bat        (from sandbox terminal, after start.bat)
:: ================================================================

:: --- Resolve BASE_DIR ---
if defined BASE_DIR (set "_BASE=%BASE_DIR%") else (for %%I in ("%~dp0..\..") do set "_BASE=%%~fI")

set "PD=%_BASE%"
set "TW=%TEMP%\PortaFlowTest_%RANDOM%"
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "_DT=%%T"
set "TR=%_BASE%\_archive\test-results"
if not exist "%TR%" mkdir "%TR%"
set "_REPORT=%TR%\local_!_DT!.txt"
set "_TMP=%TW%\_tmp.txt"

set "_PASS=0" & set "_FAIL=0" & set "_TOTAL=0"

mkdir "%TW%" > nul 2>&1
mkdir "%TW%\_archive\collab-log" > nul 2>&1
mkdir "%TW%\_archive\raw-log" > nul 2>&1
mkdir "%TW%\_archive\sessions" > nul 2>&1
mkdir "%TW%\_sys\gemini" > nul 2>&1
mkdir "%TW%\_sys\claude\config\projects\P--" > nul 2>&1
mkdir "%TW%\project" > nul 2>&1
xcopy "%PD%\_sys\context\*.bat" "%TW%\context\" /Q /Y > nul 2>&1
(echo {"mode":"OFF","reason":"manual_override","installed":false,"authenticated":false,"last_check":"!_DT!","last_error":null}) > "%TW%\_sys\gemini\status.json"
(
  echo # Test Project
  echo ## Current State
  echo Baseline
  echo ## Architecture Decisions
  echo - none
  echo ## Next Steps
  echo - none
) > "%TW%\project\CLAUDE.md"

set "BASE_DIR=%TW%"
set "GEMINI_DIR=%TW%\_sys\gemini"
set "CLAUDE_CONFIG_DIR=%TW%\_sys\claude\config"
set "SESSION_DIR=%TR%\sessions"
if not exist "%TR%\sessions" mkdir "%TR%\sessions"

echo ============================================================= >> "!_REPORT!"
echo   Porta-Flow Local Unit Test Report                           >> "!_REPORT!"
echo   Base: %PD%                                                  >> "!_REPORT!"
echo   Run:  !_DT!                                                 >> "!_REPORT!"
echo ============================================================= >> "!_REPORT!"

echo [local-test] Report: !_REPORT!
echo [local-test] Workspace: %TW%

echo. >> "!_REPORT!"
echo [GROUP 1] File Presence >> "!_REPORT!"
echo ---- >> "!_REPORT!"
call :F "ctx-save.bat"            "%PD%\_sys\context\ctx-save.bat"
call :F "ctx-end.bat"             "%PD%\_sys\context\ctx-end.bat"
call :F "version-check.bat"       "%PD%\_sys\context\version-check.bat"
call :F "agent-audit.bat"         "%PD%\_sys\context\agent-audit.bat"
call :F "risk-scan.bat"           "%PD%\_sys\context\risk-scan.bat"
call :F "script-deps.bat"         "%PD%\_sys\context\script-deps.bat"
call :F "git-draft.bat"           "%PD%\_sys\context\git-draft.bat"
call :F "context-health.bat"      "%PD%\_sys\context\context-health.bat"
call :F "collab-log-append.bat"   "%PD%\_sys\context\collab-log-append.bat"
call :F "raw-log.bat"             "%PD%\_sys\context\raw-log.bat"
call :F "gemini-session-read.bat" "%PD%\_sys\context\gemini-session-read.bat"
call :F "gemini-status.bat"       "%PD%\_sys\gemini\gemini-status.bat"
call :F "start.bat"               "%PD%\_sys\start.bat"
call :F "rg.exe"                  "%PD%\_sys\tools\ripgrep\rg.exe"
call :F "fd.exe"                  "%PD%\_sys\tools\fd\fd.exe"
call :F "jq.exe"                  "%PD%\_sys\tools\jq\jq.exe"
call :F "bat.exe"                 "%PD%\_sys\tools\bat\bat.exe"
call :F "fzf.exe"                 "%PD%\_sys\tools\fzf\fzf.exe"
call :F "delta.exe"               "%PD%\_sys\tools\delta\delta.exe"
call :F "oh-my-posh.exe"          "%PD%\_sys\tools\oh-my-posh\oh-my-posh.exe"
call :F "CLAUDE.md"               "%PD%\CLAUDE.md"
call :F "CONVENTION.md"           "%PD%\CONVENTION.md"
call :F "GEMINI.md"               "%PD%\GEMINI.md"
call :F "settings.json"           "%PD%\.claude\settings.json"
call :F ".claude/agents dir"      "%PD%\.claude\agents"
call :F "sandbox-test.bat"        "%PD%\_sys\test\sandbox-test.bat"
call :F "run-sandbox-test.bat"    "%PD%\_sys\test\run-sandbox-test.bat"
call :F "sandbox-unit-test.wsb"   "%PD%\_sys\test\sandbox-unit-test.wsb"

echo. >> "!_REPORT!"
echo [GROUP 2] Tool CLI Execution >> "!_REPORT!"
echo ---- >> "!_REPORT!"
"%PD%\_sys\tools\ripgrep\rg.exe" --version > "!_TMP!" 2>&1 & call :E "rg --version" 0 !ERRORLEVEL!
"%PD%\_sys\tools\fd\fd.exe" --version > "!_TMP!" 2>&1 & call :E "fd --version" 0 !ERRORLEVEL!
"%PD%\_sys\tools\jq\jq.exe" --version > "!_TMP!" 2>&1 & call :E "jq --version" 0 !ERRORLEVEL!
"%PD%\_sys\tools\bat\bat.exe" --version > "!_TMP!" 2>&1 & call :E "bat --version" 0 !ERRORLEVEL!
"%PD%\_sys\tools\fzf\fzf.exe" --version > "!_TMP!" 2>&1 & call :E "fzf --version" 0 !ERRORLEVEL!
"%PD%\_sys\tools\delta\delta.exe" --version > "!_TMP!" 2>&1 & call :E "delta --version" 0 !ERRORLEVEL!
"%PD%\_sys\env\git\cmd\git.exe" --version > "!_TMP!" 2>&1 & call :E "git --version" 0 !ERRORLEVEL!
"%PD%\_sys\env\nodejs\node.exe" --version > "!_TMP!" 2>&1 & call :E "node --version" 0 !ERRORLEVEL!
"%PD%\_sys\tools\sqlite\sqlite3.exe" --version > "!_TMP!" 2>&1 & call :E "sqlite3 --version" 0 !ERRORLEVEL!
"%PD%\_sys\tools\gh\gh.exe" --version > "!_TMP!" 2>&1 & call :E "gh --version portable" 0 !ERRORLEVEL!
"%PD%\_sys\env\pwsh\pwsh.exe" --version > "!_TMP!" 2>&1 & call :E "pwsh --version" 0 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 3] raw-log.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
call "%TW%\context\raw-log.bat" "Axis-T" > "!_TMP!" 2>&1 & call :E "raw-log: no file ??? graceful" 0 !ERRORLEVEL!
call "%TW%\context\raw-log.bat" "Axis-T" "%TW%\nofile.txt" > "!_TMP!" 2>&1 & call :E "raw-log: missing file ??? silent" 0 !ERRORLEVEL!
echo fake > "%TW%\rsp.txt"
call "%TW%\context\raw-log.bat" "Axis-T" "%TW%\rsp.txt" > "!_TMP!" 2>&1 & call :E "raw-log: valid file ??? exit 0" 0 !ERRORLEVEL!
dir /b "%TW%\_archive\raw-log\*response*" > "!_TMP!" 2>&1 & call :E "raw-log: response.txt created" 0 !ERRORLEVEL!
echo dir > "%TW%\drv.txt"
call "%TW%\context\raw-log.bat" "Axis-T2" "%TW%\rsp.txt" "%TW%\drv.txt" > "!_TMP!" 2>&1
dir /b "%TW%\_archive\raw-log\*directive*" > "!_TMP!" 2>&1 & call :E "raw-log: directive.txt created" 0 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 4] collab-log-append.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
call "%TW%\context\collab-log-append.bat" "Axis-T" "local-test.bat" "OK" "detail" > "!_TMP!" 2>&1
for /f %%D in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "_TD=%%D"
call :F "collab-log-append: MD created" "%TW%\_archive\collab-log\!_TD!.md"
call "%TW%\context\collab-log-append.bat" "Axis-T" "local-test.bat" "FAIL" "err" > "!_TMP!" 2>&1
findstr /c:"Axis-T" "%TW%\_archive\collab-log\!_TD!.md" > nul 2>&1 & call :E "collab-log-append: content" 0 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 5] risk-scan.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
set "NO_GEMINI=1" & set "GEMINI_MODE="
call "%TW%\context\risk-scan.bat" > "!_TMP!" 2>&1 & call :E "risk-scan: no args ??? exit 0" 0 !ERRORLEVEL!
call :F "risk-scan: JSON created" "%TW%\_archive\risk-scan.json"
findstr /c:"UNKNOWN" "%TW%\_archive\risk-scan.json" > nul 2>&1 & call :E "risk-scan: UNKNOWN in output" 0 !ERRORLEVEL!
powershell -NoProfile -Command "try{Get-Content '%TW%\_archive\risk-scan.json' -Raw|ConvertFrom-Json|Out-Null;exit 0}catch{exit 1}" & call :E "risk-scan: valid JSON" 0 !ERRORLEVEL!
call "%TW%\context\risk-scan.bat" "my task" > "!_TMP!" 2>&1 & call :E "risk-scan: with task ??? exit 0" 0 !ERRORLEVEL!
call "%TW%\context\risk-scan.bat" "my task" "a.bat,b.ps1" > "!_TMP!" 2>&1 & call :E "risk-scan: task+files ??? exit 0" 0 !ERRORLEVEL!
powershell -NoProfile -Command "try{$j=Get-Content '%TW%\_archive\risk-scan.json' -Raw|ConvertFrom-Json;if($j.proceed -eq $true){exit 0}else{exit 1}}catch{exit 1}" & call :E "risk-scan: proceed=true" 0 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 6] context-health.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
set "NO_GEMINI=1" & set "GEMINI_MODE="
call "%TW%\context\context-health.bat" > "!_TMP!" 2>&1 & call :E "context-health: no JSONL ??? exit 0" 0 !ERRORLEVEL!
findstr /c:"No JSONL" "!_TMP!" > nul 2>&1 & call :E "context-health: no JSONL message" 0 !ERRORLEVEL!
call "%TW%\context\context-health.bat" --force > "!_TMP!" 2>&1 & call :E "context-health: --force no JSONL ??? exit 0" 0 !ERRORLEVEL!
powershell -NoProfile -Command "$f='%TW%\_sys\claude\config\projects\P--\s.jsonl'; $s=New-Object System.IO.FileStream($f,'Create'); $s.SetLength(102400); $s.Close()"
call "%TW%\context\context-health.bat" > "!_TMP!" 2>&1 & call :E "context-health: 100KB JSONL ??? exit 0" 0 !ERRORLEVEL!
findstr /c:"GREEN" "!_TMP!" > nul 2>&1 & call :E "context-health: GREEN reported" 0 !ERRORLEVEL!
powershell -NoProfile -Command "$f='%TW%\_sys\claude\config\projects\P--\s.jsonl'; $s=New-Object System.IO.FileStream($f,'Create'); $s.SetLength(716800); $s.Close()"
call "%TW%\context\context-health.bat" > "!_TMP!" 2>&1
findstr /c:"YELLOW" "!_TMP!" > nul 2>&1 & call :E "context-health: YELLOW reported" 0 !ERRORLEVEL!
powershell -NoProfile -Command "$f='%TW%\_sys\claude\config\projects\P--\s.jsonl'; $s=New-Object System.IO.FileStream($f,'Create'); $s.SetLength(1572864); $s.Close()"
call "%TW%\context\context-health.bat" > "!_TMP!" 2>&1 & call :E "context-health: RED JSONL ??? exit 0" 0 !ERRORLEVEL!
findstr /c:"RED" "!_TMP!" > nul 2>&1 & call :E "context-health: RED reported" 0 !ERRORLEVEL!
call "%TW%\context\context-health.bat" --force > "!_TMP!" 2>&1 & call :E "context-health: --force RED ??? exit 0" 0 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 7] gemini-status.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
set "NO_GEMINI=1" & set "GEMINI_MODE=" & set "GEMINI_OFF_REASON="
call "%PD%\_sys\gemini\gemini-status.bat"
if "!GEMINI_MODE!"=="OFF" (call :OK "gemini-status: NO_GEMINI=1 ??? OFF") else (call :NG "gemini-status: NO_GEMINI=1 ??? OFF" "was !GEMINI_MODE!")
if "!GEMINI_OFF_REASON!"=="manual_override" (call :OK "gemini-status: reason=manual_override") else (call :NG "gemini-status: reason=manual_override" "was !GEMINI_OFF_REASON!")
call :F "gemini-status: status.json written" "%TW%\_sys\gemini\status.json"
powershell -NoProfile -Command "try{$j=Get-Content '%TW%\_sys\gemini\status.json' -Raw|ConvertFrom-Json;if($j.mode -eq 'OFF'){exit 0}else{exit 1}}catch{exit 1}" & call :E "gemini-status: JSON mode=OFF" 0 !ERRORLEVEL!
set "NO_GEMINI=" & set "GEMINI_MODE=" & set "GEMINI_OFF_REASON="
call "%PD%\_sys\gemini\gemini-status.bat"
if "!GEMINI_MODE!"=="OFF" (call :OK "gemini-status: no auth ??? OFF") else (call :OK "gemini-status: with auth ??? ON (OK)")

echo. >> "!_REPORT!"
echo [GROUP 8] version-check.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
set "NO_GEMINI=1" & set "GEMINI_MODE="
call "%TW%\context\version-check.bat" > "!_TMP!" 2>&1 & call :E "version-check: NO_GEMINI ??? exit 1" 1 !ERRORLEVEL!
findstr /c:"ERROR" "!_TMP!" > nul 2>&1 & call :E "version-check: ERROR msg shown" 0 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 9] agent-audit.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
set "NO_GEMINI=1" & set "GEMINI_MODE="
call "%TW%\context\agent-audit.bat" > "!_TMP!" 2>&1 & call :E "agent-audit: NO_GEMINI ??? exit 1" 1 !ERRORLEVEL!
set "_AC=0" & for %%F in ("%PD%\.claude\agents\*.md") do set /a "_AC+=1"
if !_AC! GEQ 9 (call :OK "agent-audit: !_AC! agent files present") else (call :NG "agent-audit: 9+ agents" "found !_AC!")

echo. >> "!_REPORT!"
echo [GROUP 10] script-deps.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
set "NO_GEMINI=1" & set "GEMINI_MODE="
call "%TW%\context\script-deps.bat" > "!_TMP!" 2>&1 & call :E "script-deps: NO_GEMINI ??? exit 1" 1 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 11] git-draft.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
set "NO_GEMINI=1" & set "GEMINI_MODE="
call "%TW%\context\git-draft.bat" > "!_TMP!" 2>&1 & call :E "git-draft: no args ??? exit 1" 1 !ERRORLEVEL!
call "%TW%\context\git-draft.bat" --staged > "!_TMP!" 2>&1 & call :E "git-draft: --staged ??? exit 1" 1 !ERRORLEVEL!
call "%TW%\context\git-draft.bat" --unknownflag > "!_TMP!" 2>&1 & call :E "git-draft: unknown flag ??? exit 1" 1 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 12] ctx-save.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
set "NO_GEMINI=1" & set "GEMINI_MODE="
cd /d "%TW%"
call "%TW%\context\ctx-save.bat" > "!_TMP!" 2>&1 & call :E "ctx-save: no CLAUDE.md ??? exit 1" 1 !ERRORLEVEL!
cd /d "%TW%\project"
call "%TW%\context\ctx-save.bat" > "!_TMP!" 2>&1 & call :E "ctx-save: valid CLAUDE.md ??? exit 0" 0 !ERRORLEVEL!
dir /b "%TR%\sessions\*.md" > "!_TMP!" 2>&1 & call :E "ctx-save: session log created" 0 !ERRORLEVEL!
findstr /c:"ctx-save" "%TW%\project\CLAUDE.md" > nul 2>&1 & call :E "ctx-save: checkpoint marker written" 0 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 13] ctx-end.bat >> "!_REPORT!"
echo ---- >> "!_REPORT!"
set "NO_GEMINI=1" & set "GEMINI_MODE="
cd /d "%TW%\project"
call "%TW%\context\ctx-end.bat" > "!_TMP!" 2>&1
set "_EC=!ERRORLEVEL!"
if !_EC! neq 0 (call :OK "ctx-end: no credentials ??? non-zero exit") else (call :OK "ctx-end: ran (credentials present)")
call "%TW%\context\ctx-end.bat" --global > "!_TMP!" 2>&1
set "_EC=!ERRORLEVEL!"
if !_EC! neq 0 (call :OK "ctx-end --global: expected non-zero") else (call :OK "ctx-end --global: ran ok")

echo. >> "!_REPORT!"
echo [GROUP 14] settings.json >> "!_REPORT!"
echo ---- >> "!_REPORT!"
call :F "settings.json exists" "%PD%\.claude\settings.json"
powershell -NoProfile -Command "try{Get-Content '%PD%\.claude\settings.json' -Raw|ConvertFrom-Json|Out-Null;exit 0}catch{exit 1}" & call :E "settings.json: valid JSON" 0 !ERRORLEVEL!
powershell -NoProfile -Command "try{$j=Get-Content '%PD%\.claude\settings.json' -Raw|ConvertFrom-Json;if($j.defaultShell -eq 'powershell'){exit 0}else{exit 1}}catch{exit 1}" & call :E "settings.json: defaultShell=powershell" 0 !ERRORLEVEL!
powershell -NoProfile -Command "try{$j=Get-Content '%PD%\.claude\settings.json' -Raw|ConvertFrom-Json;if($j.env.CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE -eq 'false'){exit 0}else{exit 1}}catch{exit 1}" & call :E "settings.json: auto-update disabled" 0 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 15] start.bat integrity >> "!_REPORT!"
echo ---- >> "!_REPORT!"
findstr /c:"TOOLS_DIR" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: TOOLS_DIR PATH" 0 !ERRORLEVEL!
findstr /c:"ripgrep" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: ripgrep entry" 0 !ERRORLEVEL!
findstr /c:"gemini-status.bat" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: gemini-status call" 0 !ERRORLEVEL!
findstr /c:"NPM_CONFIG_PREFIX" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: NPM_CONFIG_PREFIX" 0 !ERRORLEVEL!
findstr /c:"SUBST_DRIVE_LETTER" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: SUBST portability" 0 !ERRORLEVEL!
findstr /c:"sqlite" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: sqlite PATH entry" 0 !ERRORLEVEL!
findstr /c:"\gh" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: gh PATH entry" 0 !ERRORLEVEL!

echo. >> "!_REPORT!"
echo [GROUP 16] 2026-06-03 hub.py IPC + 3TCP v1 >> "!_REPORT!"
echo ---- >> "!_REPORT!"

:: gemini-consult.bat removed (replaced by msg.bat ask --to gemini)
call :SK "gemini-consult.bat: CRLF endings"          "deleted: replaced by msg.bat"
call :SK "gemini-consult.bat: --approval-mode plan"  "deleted"
call :SK "gemini-consult.bat: _SID_FILE before gate" "deleted"
call :SK "gemini-consult.bat: _GUSAGE var"           "deleted"
call :SK "gemini-consult.bat: ripgrep in PATH"       "deleted"
call :SK "gemini-consult.bat: session-map update"    "deleted"
call :SK "gemini-consult.bat: usage auto-update"     "deleted"

:: ctx-end.bat: CRLF + check-gate (replaces session-map)
powershell -NoProfile -Command "if([IO.File]::ReadAllText('%PD%\_sys\hooks\ctx-end.bat').Contains([char]13)){exit 0}else{exit 1}" > nul 2>&1
call :E "ctx-end.bat: CRLF endings" 0 !ERRORLEVEL!
findstr /c:"check-gate" "%PD%\_sys\hooks\ctx-end.bat" > nul 2>&1 & call :E "ctx-end.bat: check-gate.bat used" 0 !ERRORLEVEL!

:: gemini-usage.bat: Axis-Q tracking
findstr /c:"Q=0" "%PD%\_sys\gemini\gemini-usage.bat" > nul 2>&1 & call :E "gemini-usage.bat: Q=0 key" 0 !ERRORLEVEL!
findstr /c:"A-HQ" "%PD%\_sys\gemini\gemini-usage.bat" > nul 2>&1 & call :E "gemini-usage.bat: [A-HQ] regex" 0 !ERRORLEVEL!

:: Gemini CLI bundle: rg-win32-x64.exe
call :F "Gemini bundle: rg-win32-x64.exe" "%PD%\_sys\env\nodejs\npm-global\node_modules\@google\gemini-cli\bundle\rg-win32-x64.exe"

:: hub.py IPC core files
call :F "hub.py: core IPC script"   "%PD%\_sys\core\hub.py"
call :F "msg.bat: IPC channel"      "%PD%\_sys\cli\msg.bat"
findstr /c:"PYTHONUTF8" "%PD%\_sys\cli\msg.bat" > nul 2>&1 & call :E "msg.bat: PYTHONUTF8=1 present" 0 !ERRORLEVEL!
findstr /c:"hub.py" "%PD%\_sys\cli\msg.bat" > nul 2>&1 & call :E "msg.bat: calls hub.py" 0 !ERRORLEVEL!

:: parallel Axis scripts: ephemeral session (new _sys\scans\ paths)
for %%S in (scan-risk scan-audit scan-deps scan-env scan-health) do (
    powershell -NoProfile -Command "if((Get-Content '%PD%\_sys\scans\%%S.bat' -Raw) -match 'EPHEMERAL_SID'){exit 0}else{exit 1}" > nul 2>&1
    call :E "%%S.bat: ephemeral session used" 0 !ERRORLEVEL!
    powershell -NoProfile -Command "if((Get-Content '%PD%\_sys\scans\%%S.bat' -Raw) -notmatch 'gemini-session-read'){exit 0}else{exit 1}" > nul 2>&1
    call :E "%%S.bat: no session-read call" 0 !ERRORLEVEL!
)

:: interactive scripts use check-gate.bat (replaces _GEMINI_SESSION_FLAG)
powershell -NoProfile -Command "if((Get-Content '%PD%\_sys\hooks\ctx-save.bat' -Raw) -match 'check-gate'){exit 0}else{exit 1}" > nul 2>&1
call :E "ctx-save.bat: check-gate.bat used" 0 !ERRORLEVEL!
powershell -NoProfile -Command "if((Get-Content '%PD%\_sys\tools\git-draft.bat' -Raw) -match 'check-gate'){exit 0}else{exit 1}" > nul 2>&1
call :E "git-draft.bat: check-gate.bat used" 0 !ERRORLEVEL!

:: gemini-session-read.bat removed (replaced by hub.py)
call :SK "gemini-session-read.bat: CRLF endings"          "deleted: replaced by hub.py"
call :SK "gemini-session-read: no session -> flag empty"   "deleted"
call :SK "gemini-session-read: serial 2nd call succeeds"   "deleted"
call :SK "gemini-session-read: active session -> flag set" "deleted"

:: --- Cleanup ---
cd /d "P:\"
if exist "%TW%" rmdir /s /q "%TW%" > nul 2>&1

echo. >> "!_REPORT!"
echo ============================================================= >> "!_REPORT!"
echo   RESULT: PASS=!_PASS!  FAIL=!_FAIL!  TOTAL=!_TOTAL!          >> "!_REPORT!"
echo ============================================================= >> "!_REPORT!"

echo.
echo ================================================
if !_FAIL! gtr 0 type "!_REPORT!" | findstr /c:"[FAIL]"
echo ================================================
echo   TOTAL: !_TOTAL!   PASS: !_PASS!   FAIL: !_FAIL!
echo ================================================
echo [local-test] Report saved: !_REPORT!
endlocal
exit /b 0

:F
set /a "_TOTAL+=1"
if exist "%~2" (set /a "_PASS+=1" & echo   [PASS] %~1 >> "!_REPORT!") else (set /a "_FAIL+=1" & echo   [FAIL] %~1 [missing: %~2] >> "!_REPORT!")
exit /b 0

:E
set /a "_TOTAL+=1"
if "%~2"=="%~3" (set /a "_PASS+=1" & echo   [PASS] %~1 >> "!_REPORT!") else (set /a "_FAIL+=1" & echo   [FAIL] %~1 [expected=%~2 got=%~3] >> "!_REPORT!")
exit /b 0

:OK
set /a "_TOTAL+=1" & set /a "_PASS+=1"
echo   [PASS] %~1 >> "!_REPORT!"
exit /b 0

:NG
set /a "_TOTAL+=1" & set /a "_FAIL+=1"
echo   [FAIL] %~1 [%~2] >> "!_REPORT!"
exit /b 0
