@echo off
cd /d "%~dp0"
setlocal DisableDelayedExpansion

:: ============================================================================
:: Engram Portable CLI Entrypoint
:: https://github.com/greatgc-flow/Engram
::
:: Provides unified CLI access to Engram portable runtime commands & PeerHub.
:: ============================================================================

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
:: No parenthesized block here on purpose -- %ERRORLEVEL% inside an
:: `if (...) ( ... exit /b %ERRORLEVEL% )` block is expanded ONCE at
:: parse time (before the block runs), so it would report the exit
:: code from BEFORE the call, not the dispatcher's real result. The
:: fix isn't delayed expansion (!ERRORLEVEL!) -- that would work too,
:: but requires enabling delayed expansion for the whole file, which
:: then silently corrupts a literal "!" in any user-supplied CLI
:: argument forwarded via %1-%9 below. Using `goto` instead of `( )`
:: avoids the parenthesized-block problem entirely, so %ERRORLEVEL%
:: on its own line (freshly re-evaluated, not batch-expanded) is
:: already correct with no expansion-mode trade-off either way.
if not exist "_sys\core\dispatch.bat" goto :cmd_unknown
call "_sys\core\dispatch.bat" %SUBCMD% %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_unknown
echo [Error] Unknown command: %SUBCMD%
echo Run 'engram --help' for available commands.
exit /b 1

:: ----------------------------------------------------------------------------
:: Subcommand Handlers
:: ----------------------------------------------------------------------------
:cmd_install
call ".\INSTALL.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_status
call ".\STATUS.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_register
call ".\register.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_unregister
call ".\unregister.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_update
call ".\UPDATE.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_cleanup
call ".\CLEANUP.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_tidy
call ".\TIDY.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%



:cmd_launch
call ".\_sys\cli\launch.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%




:: ----------------------------------------------------------------------------
:: Info Handlers
:: ----------------------------------------------------------------------------
:cmd_uninstall
call ".\_sys\env\venv\Scripts\python.exe" "_sys\cli\manage.py" uninstall
exit /b %ERRORLEVEL%

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

