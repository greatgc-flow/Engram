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
if /i "%SUBCMD%"=="launch" goto :cmd_launch
if /i "%SUBCMD%"=="uninstall" goto :cmd_uninstall
if /i "%SUBCMD%"=="start" goto :cmd_launch

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



:cmd_launch
call "%ENGRAM_ROOT%\_sys\cli\launch.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b !ERRORLEVEL!




:: ----------------------------------------------------------------------------
:: Info Handlers
:: ----------------------------------------------------------------------------
:cmd_uninstall
call "%ENGRAM_ROOT%\_sys\env\venv\Scripts\python.exe" "%ENGRAM_ROOT%\_sys\cli\manage.py" uninstall
exit /b !ERRORLEVEL!

:show_version
echo Engram v2.1.0 (Portable Dev Runtime)
exit /b 0

:show_help
echo ===============================================================================
echo   Engram v2.1.0 - Portable Dev Runtime
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
echo Options:
echo   --version, -v         Display Engram version information
echo   --help, -h            Display this help message
echo.
exit /b 0

