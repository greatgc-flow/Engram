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
if not defined BASE_DIR for %%I in ("%~dp0..\..") do set "BASE_DIR=%%~fI"
set "_BASE=%BASE_DIR%"

set "PD=%_BASE%"
set "TW=%TEMP%\EngramTest_%RANDOM%"
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "_DT=%%T"
set "TR=%_BASE%\_archive\test-results"
if not exist "%TR%" mkdir "%TR%"
set "_REPORT=%TR%\local_!_DT!.txt"
set "_TMP=%TW%\_tmp.txt"

set "_PASS=0" & set "_FAIL=0" & set "_TOTAL=0"

mkdir "%TW%" > nul 2>&1
mkdir "%TW%\_archive\collab-log" > nul 2>&1
mkdir "%TW%\_archive\raw-log" > nul 2>&1
xcopy "%PD%\_sys\context\*.bat" "%TW%\context\" /Q /Y > nul 2>&1

set "BASE_DIR=%TW%"

echo ============================================================= >> "!_REPORT!"
echo   Engram Local Unit Test Report                           >> "!_REPORT!"
echo   Base: %PD%                                                  >> "!_REPORT!"
echo   Run:  !_DT!                                                 >> "!_REPORT!"
echo ============================================================= >> "!_REPORT!"

echo [local-test] Report: !_REPORT!
echo [local-test] Workspace: %TW%

echo. >> "!_REPORT!"
echo [GROUP 1] File Presence >> "!_REPORT!"
echo ---- >> "!_REPORT!"
call :F "start.bat"               "%PD%\_sys\start.bat"
call :F "rg.exe"                  "%PD%\_sys\tools\ripgrep\rg.exe"
call :F "fd.exe"                  "%PD%\_sys\tools\fd\fd.exe"
call :F "jq.exe"                  "%PD%\_sys\tools\jq\jq.exe"
call :F "bat.exe"                 "%PD%\_sys\tools\bat\bat.exe"
call :F "fzf.exe"                 "%PD%\_sys\tools\fzf\fzf.exe"
call :F "delta.exe"               "%PD%\_sys\tools\delta\delta.exe"
call :F "oh-my-posh.exe"          "%PD%\_sys\tools\oh-my-posh\oh-my-posh.exe"
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
echo [GROUP 15] start.bat integrity >> "!_REPORT!"
echo ---- >> "!_REPORT!"
findstr /c:"TOOLS_DIR" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: TOOLS_DIR PATH" 0 !ERRORLEVEL!
findstr /c:"ripgrep" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: ripgrep entry" 0 !ERRORLEVEL!
findstr /c:"NPM_CONFIG_PREFIX" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: NPM_CONFIG_PREFIX" 0 !ERRORLEVEL!
findstr /c:"SUBST_DRIVE_LETTER" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: SUBST portability" 0 !ERRORLEVEL!
findstr /c:"sqlite" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: sqlite PATH entry" 0 !ERRORLEVEL!
findstr /c:"\gh" "%PD%\_sys\start.bat" > nul 2>&1 & call :E "start.bat: gh PATH entry" 0 !ERRORLEVEL!

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
