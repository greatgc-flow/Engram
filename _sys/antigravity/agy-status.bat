:: ================================================================
:: agy-status.bat  -  Antigravity (agy) installation check
::
:: Engram scope: is the vendor CLI installed, and what version.
:: Peer coordination status (health, quota, routing) belongs to the
:: separately-installed peerhub package: `peerhub status --peer ag`.
:: ================================================================
@echo off

set "_AGY_EXE=%~dp0..\tools\agy\agy.exe"

if exist "%_AGY_EXE%" (
    echo [Antigravity] installed=true
    "%_AGY_EXE%" --version 2>&1
) else (
    echo [Antigravity] installed=false
    echo   Expected at: %_AGY_EXE%
    echo   Run INSTALL.bat to provision it.
)

set "_AGY_EXE="
