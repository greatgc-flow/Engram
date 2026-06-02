@echo off
:: ================================================================
:: gemini-session-read.bat  -  Read current Gemini session flag
::
:: Sets _GEMINI_SESSION_FLAG in caller's environment:
::   "--resume <uuid>"  if valid session-id.txt exists (< 12h)
::   ""                 if no session or session is stale
::
:: Uses 9> OS-level lock to prevent read/write race with gemini-consult.bat
::
:: Usage: call gemini-session-read.bat
:: Then:  gemini %_GEMINI_SESSION_FLAG% -p "..." -o text
::
:: NOTE: parallel Axis scripts (background tasks) should NOT share this session.
::       They should generate their own ephemeral --session-id to avoid SQLite
::       concurrent-write conflicts. Session sharing is reserved for interactive,
::       user-facing conversational continuity only.
:: ================================================================
setlocal EnableDelayedExpansion

if defined GEMINI_DIR (set "_GD=%GEMINI_DIR%") else (for %%I in ("%~dp0..\gemini") do set "_GD=%%~fI")
set "_SID=%_GD%\session-id.txt"
set "_LOCK=%_GD%\session.lock"
set "_SF="
set "_WAIT=0"

:READ_LOCK
2>nul (9>"%_LOCK%" (
    if exist "%_SID%" (
        powershell -NoProfile -Command "if((Get-Date)-(Get-Item '%_SID%').LastWriteTime -le [TimeSpan]::FromHours(12)){exit 0}else{exit 1}" >nul 2>&1
        if not errorlevel 1 (
            for /f "usebackq delims=" %%S in ("%_SID%") do set "_SF=--resume %%S"
        )
    )
)) || (
    set /a "_WAIT+=1"
    if !_WAIT! geq 30 (goto :READ_DONE)
    timeout /t 1 /nobreak >nul 2>&1
    goto :READ_LOCK
)
:READ_DONE

endlocal & set "_GEMINI_SESSION_FLAG=%_SF%"
