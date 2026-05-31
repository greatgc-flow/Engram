:: ================================================================
:: gemini-status.bat  -  Single source of truth for Gemini mode
::
:: IMPORTANT: Do NOT add setlocal/endlocal - env vars must propagate.
:: ================================================================

if defined GEMINI_DIR (
    set "_STATUS_FILE=%GEMINI_DIR%\status.json"
) else (
    set "_STATUS_FILE=%~dp0status.json"
)

for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_DT=%%I"

if "%NO_GEMINI%"=="1" (
    set "GEMINI_MODE=OFF"
    set "GEMINI_OFF_REASON=manual_override"
    goto :WRITE_STATUS
)

where gemini > nul 2>&1
if errorlevel 1 (
    set "GEMINI_MODE=OFF"
    set "GEMINI_OFF_REASON=not_installed"
    goto :WRITE_STATUS
)

set "_GEMINI_AUTH_DIR=%USERPROFILE%\.gemini"
if not exist "%_GEMINI_AUTH_DIR%\" (
    set "GEMINI_MODE=OFF"
    set "GEMINI_OFF_REASON=not_authenticated"
    goto :WRITE_STATUS
)
:: Check auth dir contains actual credential files (empty dir = not authenticated)
if not exist "%_GEMINI_AUTH_DIR%\*" (
    set "GEMINI_MODE=OFF"
    set "GEMINI_OFF_REASON=not_authenticated"
    goto :WRITE_STATUS
)

set "GEMINI_MODE=ON"
set "GEMINI_OFF_REASON="

:: Optional: live auth ping (set GEMINI_PING_TEST=1 in local.config.bat to enable)
if "%GEMINI_PING_TEST%"=="1" (
    gemini -p "ok" -y -o text > nul 2>&1
    if errorlevel 1 (
        set "GEMINI_MODE=OFF"
        set "GEMINI_OFF_REASON=api_error"
        for /f "delims=" %%P in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_PING_ERR=ping_failed_%%P"
        goto :WRITE_STATUS
    )
)

:WRITE_STATUS
set "_INSTALLED=false"
where gemini > nul 2>&1
if not errorlevel 1 set "_INSTALLED=true"
set "_AUTHED=false"
if "%GEMINI_MODE%"=="ON" set "_AUTHED=true"

set "_REASON=%GEMINI_OFF_REASON%"
if "%GEMINI_MODE%"=="ON" set "_REASON=ready"

:: Preserve last_error from previous status.json if mode is now ON (clear only on successful ON)
:: If mode=OFF due to ping failure, use _PING_ERR; otherwise keep previous last_error
powershell -NoProfile -Command "$f='%_STATUS_FILE:\=\\%'; $prev=$null; if (Test-Path $f) { try { $prev=(Get-Content $f -Raw | ConvertFrom-Json).last_error } catch {} }; $ping='%_PING_ERR%'; $le=if('%GEMINI_MODE%' -eq 'ON') { $null } elseif ($ping -ne '') { $ping } else { $prev }; $json=[ordered]@{ mode='%GEMINI_MODE%'; reason='%_REASON%'; installed=[bool]::Parse('%_INSTALLED%'); authenticated=[bool]::Parse('%_AUTHED%'); last_check='%_DT%'; last_error=$le }; [System.IO.File]::WriteAllText($f, ($json | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false)))"

set "_STATUS_FILE="
set "_DT="
set "_GEMINI_AUTH_DIR="
set "_INSTALLED="
set "_AUTHED="
set "_REASON="
set "_PING_ERR="
