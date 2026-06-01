@echo off
setlocal EnableDelayedExpansion
:: ================================================================
:: gemini-consult.bat (Axis-Q) - Synchronous Gemini consultation
::
:: Usage:
::   gemini-consult.bat [query-file]
::
::   [query-file]  optional path to query file.
::                 If omitted, falls back to _sys\gemini\consult-query.txt
::
:: Recommended (parallel-safe): pass a unique per-call filename
::   e.g. cq-20260601185504-a3f2.txt
::
:: Step 1: Write query to unique file (TASK/CONTEXT/QUESTION format)
:: Step 2: PowerShell tool (timeout 180000):
::           $env:PATH += ";P:\_sys\env\nodejs\npm-global"
::           cmd /c "P:\_sys\context\gemini-consult.bat P:\_sys\gemini\cq-{TS}-{RND}.txt" 2>&1
:: ================================================================

:: --- Resolve paths ---
if defined GEMINI_DIR (set "_GD=%GEMINI_DIR%") else (for %%I in ("%~dp0..\gemini") do set "_GD=%%~fI")
if defined BASE_DIR (set "_ROOT=%BASE_DIR%") else (for %%I in ("%~dp0..\..") do set "_ROOT=%%~fI")
:: _SID_FILE and _GUSAGE must be set here — gemini-gate.bat clears _GD after use
set "_SID_FILE=%_GD%\session-id.txt"
set "_GUSAGE=%_GD%\gemini-usage.bat"

:: --- Ensure npm-global (gemini.cmd) and tools are in PATH ---
if exist "%_ROOT%\_sys\env\nodejs\npm-global\gemini.cmd" (
    set "PATH=%_ROOT%\_sys\env\nodejs\npm-global;%PATH%"
)
if exist "%_ROOT%\_sys\tools\ripgrep\rg.exe" (
    set "PATH=%_ROOT%\_sys\tools\ripgrep;%PATH%"
)

:: --- Query file: use argument if provided, else default ---
if not "%~1"=="" (
    set "_QFILE=%~1"
) else (
    set "_QFILE=%_GD%\consult-query.txt"
)

:: --- Check query file ---
if not exist "%_QFILE%" (
    echo [Axis-Q] ERROR: query file not found: %_QFILE%
    exit /b 1
)
for %%Z in ("%_QFILE%") do if %%~zZ==0 (
    echo [Axis-Q] ERROR: query file is empty
    exit /b 1
)

:: --- Gemini availability ---
call "%~dp0gemini-mode-check.bat"
if not "%GEMINI_MODE%"=="ON" (
    echo [Axis-Q] ERROR: Gemini not available ^(%GEMINI_OFF_REASON%^)
    exit /b 1
)

:: --- Ratio gate (>= 5 required) ---
call "%_GD%\gemini-gate.bat" 5
if errorlevel 1 (
    echo [Axis-Q] SKIP: GEMINI_RATIO ^< 5
    exit /b 0
)

:: --- Session management ---
set "_SESSION_FLAG="
set "_SMAP=%_SID_FILE:session-id.txt=session-map.json%"
if exist "%_SID_FILE%" (
    set /p "_SID=" < "%_SID_FILE%"
    set "_SESSION_FLAG=--resume !_SID!"
    :: session-map: last_used + call_count 갱신
    powershell -NoProfile -Command "$f='!_SMAP:\=\\!'; if(Test-Path $f){try{$m=Get-Content $f -Raw|ConvertFrom-Json; if($m.active){$m.active.last_used=(Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'); $m.active.call_count=[int]$m.active.call_count+1; [IO.File]::WriteAllText($f,($m|ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))}}catch{}}" >nul 2>&1
) else (
    for /f "delims=" %%U in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString()"') do set "_NEW_SID=%%U"
    > "%_SID_FILE%" echo !_NEW_SID!
    set "_SESSION_FLAG=--session-id !_NEW_SID!"
    :: session-map: 신규 active 항목 기록
    powershell -NoProfile -Command "$f='!_SMAP:\=\\!'; $now=(Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'); $hist=@(); if(Test-Path $f){try{$old=Get-Content $f -Raw|ConvertFrom-Json; if($old.history){$hist=[array]$old.history}}catch{}}; $m=[ordered]@{active=[ordered]@{gemini_session_id='!_NEW_SID!';started_at=$now;last_used=$now;call_count=1};history=$hist}; [IO.File]::WriteAllText($f,($m|ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))" >nul 2>&1
)

:: --- Call Gemini ---
echo [Axis-Q] Consulting Gemini...
type "%_QFILE%" | gemini !_SESSION_FLAG! --approval-mode plan -p "Respond to the task or question below." -o text
set "_EC=!errorlevel!"

if !_EC! neq 0 (
    :: 세션 오류 시 새 세션으로 재시도
    if exist "%_SID_FILE%" (
        echo [Axis-Q] Session error, retrying with new session...
        del "%_SID_FILE%" >nul 2>&1
        for /f "delims=" %%U in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString()"') do set "_NEW_SID=%%U"
        > "%_SID_FILE%" echo !_NEW_SID!
        type "%_QFILE%" | gemini --session-id !_NEW_SID! --approval-mode plan -p "Respond to the task or question below." -o text
        set "_EC=!errorlevel!"
    )
)

if !_EC! neq 0 (
    echo [Axis-Q] ERROR: Gemini exited !_EC!
    call "%~dp0collab-log-append.bat" "Axis-Q" "gemini-consult.bat" "FAIL" "Error: exit !_EC!"
    exit /b !_EC!
)

call "%~dp0collab-log-append.bat" "Axis-Q" "gemini-consult.bat" "OK" "Consult completed"
del "%_QFILE%" >nul 2>&1

:: usage.json 자동 갱신
call "%_GUSAGE%" >nul 2>&1

set "_GD=" & set "_ROOT=" & set "_QFILE=" & set "_EC="
endlocal
exit /b 0
