@echo off
setlocal EnableDelayedExpansion

:: ================================================================
:: ctx-save.bat  -  Mid-session checkpoint (session stays alive)
::
:: Usage: type  ctx-save  in VS Code integrated terminal
::        OR open a split terminal and run from project root
::
:: Two ways to checkpoint:
::   1. Inside claude session: "checkpoint - update CLAUDE.md now"
::   2. From separate terminal: ctx-save  (this script)
::      -> spawns new claude call, original session unaffected
:: ================================================================

set "CLAUDE_MD=%CD%\CLAUDE.md"
if not exist "%CLAUDE_MD%" (
    echo [ctx-save] No CLAUDE.md in: %CD%
    echo            Run from project root.
    exit /b 1
)

echo [ctx-save] Checkpointing: %CD%

:: Write minimal checkpoint marker to CLAUDE.md (no AI subprocess — token efficient)
powershell -NoProfile -Command "$f='%CLAUDE_MD%'; $ts=Get-Date -Format 'yyyy-MM-dd HH:mm'; $c=(Get-Content $f -Raw); $c=$c -replace '(?<=## Current State\r?\n)[^\r\n]*', ('Last ctx-save: '+$ts+' -- see _archive/sessions/ for snapshot'); [System.IO.File]::WriteAllText($f,$c,(New-Object System.Text.UTF8Encoding($false)))" > nul 2>&1
echo [ctx-save] CLAUDE.md checkpoint marker updated (no AI subprocess)

:: Save checkpoint to local session log
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_DT=%%I"
set "SES_DATE=%_DT:~0,4%-%_DT:~4,2%-%_DT:~6,2%"
set "SES_TIME=%_DT:~8,2%:%_DT:~10,2%"
if defined SESSION_DIR (set "SES_DIR=%SESSION_DIR%") else (for %%I in ("%~dp0..\..") do set "SES_DIR=%%~fI\_archive\sessions")
for %%I in ("%CD%") do set "_PROJ=%%~nxI"
set "SES_FILE=!SES_DIR!\!SES_DATE!_!_PROJ!.md"
if not exist "!SES_DIR!" mkdir "!SES_DIR!"
if not exist "!SES_FILE!" >> "!SES_FILE!" echo # Sessions !SES_DATE!
>> "!SES_FILE!" echo.
>> "!SES_FILE!" echo ## [ctx-save] !SES_DATE! !SES_TIME! - %CD%
>> "!SES_FILE!" echo.
type "%CLAUDE_MD%" >> "!SES_FILE!"
echo [ctx-save] Session log: !SES_FILE!


echo [ctx-save] Done. Session is still active.

:: Optional: Gemini mid-session summary (skipped if Gemini unavailable)
for %%I in ("%~dp0..\..") do set "_PORTABLE_ROOT=%%~fI"
set "PYTHONUTF8=1"
set "PATH=!_PORTABLE_ROOT!\_sys\env\venv\Scripts;%PATH%"
call "%~dp0ai-check.bat" >nul 2>&1
if errorlevel 1 goto :SKIP_GEMINI_SUM
set "_SUM=!SES_FILE!.midsummary.md"
set "_QF=%TEMP%\ctx-save-query-%RANDOM%.txt"
echo Read the checkpoint log below and write a 3-bullet summary: 1) What was done since last checkpoint 2) Current state 3) Immediate next steps. > "!_QF!"
echo. >> "!_QF!"
type "!SES_FILE!" >> "!_QF!" 2>nul
echo [ctx-save] Generating Gemini mid-session summary...
cmd /c "!_PORTABLE_ROOT!\_sys\cli\msg.bat" ask --to gc --query-file "!_QF!" > "!_SUM!" 2>&1
if not exist "!_SUM!" goto :CTX_SAVE_GEMINI_FAIL
for /f "delims=" %%Z in ('powershell -NoProfile -Command "(Get-Item -LiteralPath '!_SUM!').Length"') do set "_SZ=%%Z"
if "!_SZ!"=="0" goto :CTX_SAVE_GEMINI_FAIL
echo [ctx-save] Mid-summary: !_SUM!
call "%~dp0collab-log.bat" "Axis-D+" "ctx-save.bat" "OK" "Summary: !_SUM!"
goto :SKIP_GEMINI_SUM
:CTX_SAVE_GEMINI_FAIL
del "!_SUM!" > nul 2>&1
echo [ctx-save] Gemini mid-summary skipped (auth or network issue).
call "%~dp0collab-log.bat" "Axis-D+" "ctx-save.bat" "FAIL" "Error: api_error"
:SKIP_GEMINI_SUM
endlocal
