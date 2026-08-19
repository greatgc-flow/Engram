:: ================================================================
:: codex-status.bat  -  Codex installation check
::
:: Engram scope: is the vendor CLI installed, and what version.
:: Peer coordination status (health, quota, routing) belongs to the
:: separately-installed peerhub package: `peerhub status --peer cx`.
:: ================================================================
@echo off

set "_CODEX_CMD=%~dp0..\env\nodejs\npm-global\codex.cmd"

if exist "%_CODEX_CMD%" (
    echo [Codex] installed=true
    call "%_CODEX_CMD%" --version 2>&1
) else (
    echo [Codex] installed=false
    echo   Expected at: %_CODEX_CMD%
    echo   Run INSTALL.bat to provision it.
)

set "_CODEX_CMD="
