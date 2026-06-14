@echo off
:: ================================================================
:: collab-rate-gate.bat THRESHOLD
::
:: Reads _sys\ai\protocol.json, exits 0 if collab_rate >= THRESHOLD.
::
:: Usage: call collab-rate-gate.bat 7
:: ================================================================
if "%~1"=="" exit /b 0

for %%I in ("%~dp0..\ai\protocol.json") do set "_PROTO=%%~fI"

powershell -NoProfile -Command "try { $r=[int](Get-Content '%_PROTO:\=\\%' -Raw | ConvertFrom-Json).collab_rate.current; if($r -ge [int]'%~1'){exit 0}else{exit 1} } catch { exit 1 }"
set _exit=%errorlevel%
set "_PROTO="
exit /b %_exit%
