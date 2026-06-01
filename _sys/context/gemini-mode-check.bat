:: gemini-mode-check.bat - Sets GEMINI_MODE if not defined or stale.
:: IMPORTANT: No setlocal/endlocal - env vars must propagate to caller.
:: Usage: call "%~dp0gemini-mode-check.bat"
set "_GMC=0"
if not defined GEMINI_MODE set "_GMC=1"
if defined GEMINI_MODE if /i "%GEMINI_MODE%"=="OFF" if /i not "%GEMINI_OFF_REASON%"=="manual_override" set "_GMC=1"
if not "%_GMC%"=="1" goto :GMC_DONE
if "%NO_GEMINI%"=="1" (
    set "GEMINI_MODE=OFF"
    set "GEMINI_OFF_REASON=manual_override"
    goto :GMC_DONE
)
where gemini > nul 2>&1
if not errorlevel 1 (set "GEMINI_MODE=ON") else (
    set "GEMINI_MODE=OFF"
    set "GEMINI_OFF_REASON=not_installed"
)
:GMC_DONE
set "_GMC="
