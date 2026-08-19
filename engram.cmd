@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: Engram Portable CLI Entrypoint
:: https://github.com/greatgc-flow/Engram
::
:: Provides unified CLI access to Engram portable runtime commands & PeerHub.
:: ============================================================================

set "ENGRAM_ROOT=%~dp0"
if "%ENGRAM_ROOT:~-1%"=="\" set "ENGRAM_ROOT=%ENGRAM_ROOT:~0,-1%"

:: ----------------------------------------------------------------------------
:: Route commands
:: ----------------------------------------------------------------------------
set "SUBCMD=%~1"

if "%SUBCMD%"=="" goto :show_help
if /i "%SUBCMD%"=="help" goto :show_help
if /i "%SUBCMD%"=="--help" goto :show_help
if /i "%SUBCMD%"=="-h" goto :show_help
if /i "%SUBCMD%"=="/?" goto :show_help

if /i "%SUBCMD%"=="version" goto :show_version
if /i "%SUBCMD%"=="--version" goto :show_version
if /i "%SUBCMD%"=="-v" goto :show_version

:: Shift first argument so %* in sub-scripts receives remaining arguments
shift

if /i "%SUBCMD%"=="install" goto :cmd_install
if /i "%SUBCMD%"=="setup" goto :cmd_install
if /i "%SUBCMD%"=="status" goto :cmd_status
if /i "%SUBCMD%"=="doctor" goto :cmd_status
if /i "%SUBCMD%"=="register" goto :cmd_register
if /i "%SUBCMD%"=="unregister" goto :cmd_unregister
if /i "%SUBCMD%"=="update" goto :cmd_update
if /i "%SUBCMD%"=="cleanup" goto :cmd_cleanup
if /i "%SUBCMD%"=="tidy" goto :cmd_tidy
if /i "%SUBCMD%"=="diag" goto :cmd_diag
if /i "%SUBCMD%"=="peerhub" goto :cmd_hub
if /i "%SUBCMD%"=="launch" goto :cmd_launch
if /i "%SUBCMD%"=="start" goto :cmd_launch
if /i "%SUBCMD%"=="agy" goto :cmd_agy
if /i "%SUBCMD%"=="claude" goto :cmd_claude
if /i "%SUBCMD%"=="codex" goto :cmd_codex

:: Fallback: Try dispatch pipeline directly
if exist "%ENGRAM_ROOT%\_sys\core\dispatch.bat" (
    call "%ENGRAM_ROOT%\_sys\core\dispatch.bat" %SUBCMD% %1 %2 %3 %4 %5 %6 %7 %8 %9
    exit /b !ERRORLEVEL!
)

echo [Error] Unknown command: %SUBCMD%
echo Run 'engram --help' for available commands.
exit /b 1

:: ----------------------------------------------------------------------------
:: Subcommand Handlers
:: ----------------------------------------------------------------------------
:cmd_install
call "%ENGRAM_ROOT%\INSTALL.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_status
call "%ENGRAM_ROOT%\STATUS.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_register
call "%ENGRAM_ROOT%\register.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_unregister
call "%ENGRAM_ROOT%\unregister.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_update
call "%ENGRAM_ROOT%\UPDATE.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_cleanup
call "%ENGRAM_ROOT%\CLEANUP.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_tidy
call "%ENGRAM_ROOT%\TIDY.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_diag
call "%ENGRAM_ROOT%\_sys\cli\diag.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_hub
:: Thin passthrough to the separately-installed peerhub package.
call "%ENGRAM_ROOT%\_sys\cli\peerhub.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_launch
call "%ENGRAM_ROOT%\_sys\cli\launch.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_agy
call "%ENGRAM_ROOT%\_sys\cli\agy.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_claude
call "%ENGRAM_ROOT%\_sys\cli\claude.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:cmd_codex
call "%ENGRAM_ROOT%\_sys\cli\codex.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!

:: ----------------------------------------------------------------------------
:: Info Handlers
:: ----------------------------------------------------------------------------
:show_version
echo Engram v2.1.0 (Portable Multi-Agent Dev Runtime)
echo PeerHub v0.1.0 Engine Integration
exit /b 0

:show_help
echo ===============================================================================
echo   Engram v2.1.0 - Portable Multi-Agent Dev Runtime ^& PeerHub Engine
echo   Repository: https://github.com/greatgc-flow/Engram
echo ===============================================================================
echo.
echo Usage:
echo   engram ^<command^> [options...]
echo.
echo Lifecycle ^& Environment:
echo   install               Bootstrap portable Python and deploy all toolchains
echo   status / doctor       Check runtime health, virtual drives, and tool status
echo   register              Mount virtual dev drive (P:) and register context menu
echo   unregister            Unmount virtual dev drive and deregister context menu
echo   update                Check and apply latest stable runtime and tool updates
echo   cleanup / tidy        Clean temporary logs, caches, and orphaned files
echo.
echo Multi-Agent ^& PeerHub Operations:
echo   diag                  Run live multi-peer latency ^& health diagnostics
echo   peerhub ^<args...^>     Passthrough to the installed peerhub package
echo                         (peer dispatch/diagnostics; see `peerhub --help`)
echo   launch [agent]        Launch interactive shell session for agent
echo   agy / claude / codex  Run CLI entrypoint for specific AI agent
echo.
echo Options:
echo   --version, -v         Display Engram version information
echo   --help, -h            Display this help message
echo.
exit /b 0
