@echo off
set "ENGRAM_CALLER_CWD=%CD%"
cd /d "%~dp0"
setlocal DisableDelayedExpansion

:: ============================================================================
:: Discovery Hierarchy for Engram System Directory
:: ============================================================================
set "ENGRAM_SYS_DIR_NAME="

:: Tier 1: Explicit caller override via environment variable
if defined ENGRAM_SYS_DIR (
    if exist "%~dp0%ENGRAM_SYS_DIR%\core\dispatch.bat" (
        set "ENGRAM_SYS_DIR_NAME=%ENGRAM_SYS_DIR%"
        goto :sys_dir_resolved
    )
    if exist "%ENGRAM_SYS_DIR%\core\dispatch.bat" (
        set "ENGRAM_SYS_DIR_NAME=%ENGRAM_SYS_DIR%"
        goto :sys_dir_resolved
    )
    if exist "%~dp0%ENGRAM_SYS_DIR%\" (
        set "ENGRAM_SYS_DIR_NAME=%ENGRAM_SYS_DIR%"
        goto :sys_dir_resolved
    )
)

:: Tier 2: Zero-cost fast path for standard installations
if exist "%~dp0_sys\core\dispatch.bat" (
    set "ENGRAM_SYS_DIR_NAME=_sys"
    goto :sys_dir_resolved
)
if exist "%~dp0_sys\" (
    set "ENGRAM_SYS_DIR_NAME=_sys"
    goto :sys_dir_resolved
)

:: Tier 3: Probe immediate subdirectories for the core dispatch anchor
for /d %%D in ("%~dp0*") do (
    if exist "%%D\core\dispatch.bat" (
        set "ENGRAM_SYS_DIR_NAME=%%~nxD"
        goto :sys_dir_resolved
    )
)

:: Failure fallback: Anchor missing
echo [Error] Engram system directory not found under "%~dp0".
echo         Expected a directory containing core\dispatch.bat.
exit /b 1

:sys_dir_resolved
set "ENGRAM_SYS_DIR=%ENGRAM_SYS_DIR_NAME%"
set "SYS_PATH=%~dp0%ENGRAM_SYS_DIR%"

:: ============================================================================
:: Engram Portable CLI Entrypoint
:: https://github.com/greatgc-flow/Engram
::
:: Provides unified CLI access to Engram portable runtime commands.
:: ============================================================================

:: ----------------------------------------------------------------------------
:: Route commands
:: ----------------------------------------------------------------------------
set "SUBCMD=%~1"

if "%SUBCMD%"=="" goto :cmd_open
if /i "%SUBCMD%"=="help" goto :show_help
if /i "%SUBCMD%"=="--help" goto :show_help
if /i "%SUBCMD%"=="-h" goto :show_help
if /i "%SUBCMD%"=="/?" goto :show_help

if /i "%SUBCMD%"=="version" goto :show_version
if /i "%SUBCMD%"=="--version" goto :show_version
if /i "%SUBCMD%"=="-v" goto :show_version

:: --- Layout Migration Auto-Trigger ---
set "_MIGRATE_LAYOUT=0"
if exist "%SYS_PATH%\env\python\python.exe" (
    if not exist "%SYS_PATH%\data\state\layout.json" (
        set "_MIGRATE_LAYOUT=1"
    ) else (
        "%SYS_PATH%\env\python\python.exe" -c "import json, sys; l=json.load(open(r'%SYS_PATH%\data\state\layout.json', encoding='utf-8')); v=json.load(open(r'%SYS_PATH%\core\version.json', encoding='utf-8')).get('version', 'unknown'); sys.exit(0 if l.get('layout_version', 0) < 2 or l.get('engram_version', 'unknown') != v else 1)" 2>nul
        if not errorlevel 1 set "_MIGRATE_LAYOUT=1"
    )
)
if "%_MIGRATE_LAYOUT%"=="1" (
    call "%SYS_PATH%\core\dispatch.bat" migrate-layout
    if not exist "%SYS_PATH%\data\state\layout.json" exit /b 1
)
:: -------------------------------------

:: Shift first argument so %1-%9 in sub-scripts receives remaining arguments
shift

:: 1. Public verbs (checked before the existing-path fallback: a folder that
:: happens to be named like a verb is opened only via the explicit
:: 'engram open <name>', per the ratified command-surface rule ordering)
if /i "%SUBCMD%"=="open" goto :cmd_open
if /i "%SUBCMD%"=="update" goto :cmd_update
if /i "%SUBCMD%"=="doctor" goto :cmd_doctor
if /i "%SUBCMD%"=="menu" goto :cmd_menu
if /i "%SUBCMD%"=="tidy" goto :cmd_tidy
if /i "%SUBCMD%"=="uninstall" goto :cmd_uninstall
if /i "%SUBCMD%"=="backup" goto :cmd_backup
if /i "%SUBCMD%"=="restore" goto :cmd_restore
if /i "%SUBCMD%"=="reset" goto :cmd_reset

:: 2. Retired verbs
if /i "%SUBCMD%"=="install" goto :retired_install
if /i "%SUBCMD%"=="setup" goto :retired_install
if /i "%SUBCMD%"=="status" goto :retired_status
if /i "%SUBCMD%"=="register" goto :retired_register
if /i "%SUBCMD%"=="unregister" goto :retired_unregister
if /i "%SUBCMD%"=="menu-cleanup" goto :retired_menu_cleanup
if /i "%SUBCMD%"=="cleanup" goto :retired_cleanup
if /i "%SUBCMD%"=="launch" goto :retired_launch
if /i "%SUBCMD%"=="start" goto :retired_launch

:: 3. Existing path routes to open (only reached once SUBCMD matched no verb)
if exist "%SUBCMD%\" goto :cmd_open_implicit

goto :cmd_unknown

:cmd_unknown
echo [Error] Unknown command: %SUBCMD%
echo Run 'engram help' for available commands.
exit /b 2

:: ----------------------------------------------------------------------------
:: Subcommand Handlers
:: ----------------------------------------------------------------------------

:cmd_open
if not exist "%SYS_PATH%\env\python\python.exe" (
    call :do_first_run
    if errorlevel 1 exit /b 1
)
call "%SYS_PATH%\core\dispatch.bat" start %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_open_implicit
if not exist "%SYS_PATH%\env\python\python.exe" (
    call :do_first_run
    if errorlevel 1 exit /b 1
)
call "%SYS_PATH%\core\dispatch.bat" start "%SUBCMD%" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:do_first_run
echo This will set up Engram's portable Python, tools, and runtimes in "%CD%"
set "SETUP_CHOICE="
set /p "SETUP_CHOICE=Set up Engram here now? [Y/n] "
if /i "%SETUP_CHOICE%"=="n" exit /b 1
call "%SYS_PATH%\core\bootstrap.bat"
if errorlevel 1 exit /b 1
if not exist "workspace\" mkdir "workspace"
if exist "%SYS_PATH%\data\state\register.state.json" exit /b 0
set "MENU_CHOICE=y"
set /p MENU_CHOICE=Add "Open in Engram" to the Explorer right-click menu? [Y/n] 
if /i not "%MENU_CHOICE%"=="n" call "%SYS_PATH%\core\dispatch.bat" menu-enable
exit /b 0

:check_setup
if not exist "%SYS_PATH%\env\python\python.exe" (
    echo Engram is not set up.
    echo Run 'engram' to initialize the environment.
    exit /b 1
)
exit /b 0

:cmd_doctor
call :check_setup
if errorlevel 1 exit /b 1
call "%SYS_PATH%\core\dispatch.bat" doctor %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_menu
if "%~1"=="/?" goto :show_menu_help
if "%~1"=="-h" goto :show_menu_help
if "%~1"=="--help" goto :show_menu_help
if /i "%~1"=="help" goto :show_menu_help
call :check_setup
if errorlevel 1 exit /b 1
:: if no args, default to status
if "%~1"=="" (
    call "%SYS_PATH%\core\dispatch.bat" menu-status
    exit /b %ERRORLEVEL%
)
if /i "%~1"=="status" (
    call "%SYS_PATH%\core\dispatch.bat" menu-status %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
if /i "%~1"=="enable" (
    call "%SYS_PATH%\core\dispatch.bat" menu-enable %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
if /i "%~1"=="disable" (
    call "%SYS_PATH%\core\dispatch.bat" menu-disable %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
if /i "%~1"=="clean" (
    call "%SYS_PATH%\core\dispatch.bat" menu-clean %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
echo [Error] Unknown menu command: %1
echo Run 'engram menu --help' for available commands.
exit /b 2

:show_menu_help
echo Engram Right-Click Context Menu Management
echo.
echo Usage:
echo   engram menu ^<subcommand^>
echo.
echo Subcommands:
echo   status     Display current registration status in Windows Explorer
echo   enable     Add "Open in Engram" to Explorer right-click context menu
echo   disable    Remove "Open in Engram" from Explorer context menu
echo   clean      Clean orphaned registry entries from previous installations
echo.
echo Options:
echo   -h, --help, /?  Display this help message
echo.
exit /b 0

:cmd_tidy
call :check_setup
if errorlevel 1 exit /b 1
call "%SYS_PATH%\core\dispatch.bat" tidy %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_update
call :check_setup
if errorlevel 1 exit /b 1
call "%SYS_PATH%\core\dispatch.bat" update %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_uninstall
call :check_setup
if errorlevel 1 exit /b 1
call "%SYS_PATH%\core\dispatch.bat" uninstall %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_backup
call :check_setup
if errorlevel 1 exit /b 1
call "%SYS_PATH%\core\dispatch.bat" backup %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_restore
call :check_setup
if errorlevel 1 exit /b 1
call "%SYS_PATH%\core\dispatch.bat" restore %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_reset
call :check_setup
if errorlevel 1 exit /b 1
call "%SYS_PATH%\core\dispatch.bat" reset %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:: ----------------------------------------------------------------------------
:: Retired Verbs Handlers
:: ----------------------------------------------------------------------------
:retired_install
echo [Notice] '%SUBCMD%' is retired. Use: engram
exit /b 2

:retired_status
echo [Notice] '%SUBCMD%' is retired. Use: engram doctor
exit /b 2

:retired_register
echo [Notice] '%SUBCMD%' is retired. Use: engram menu enable
exit /b 2

:retired_unregister
echo [Notice] '%SUBCMD%' is retired. Use: engram menu disable
exit /b 2

:retired_menu_cleanup
echo [Notice] '%SUBCMD%' is retired. Use: engram menu clean
exit /b 2

:retired_cleanup
echo [Notice] '%SUBCMD%' is retired. Use: engram tidy
exit /b 2

:retired_launch
echo [Notice] '%SUBCMD%' is retired. Use: engram open
exit /b 2

:: ----------------------------------------------------------------------------
:: Info Handlers
:: ----------------------------------------------------------------------------

:get_version
set "_ENGRAM_VER=unknown"
if exist "%SYS_PATH%\core\version.json" (
    if exist "%SYS_PATH%\env\python\python.exe" (
        for /f "usebackq delims=" %%v in (`"%SYS_PATH%\env\python\python.exe" -c "import json, sys; sys.stdout.write(json.load(open(r'%SYS_PATH%\core\version.json', encoding='utf-8')).get('version', 'unknown'))" 2^>nul`) do (
            set "_ENGRAM_VER=%%v"
        )
    )
    if "%_ENGRAM_VER%"=="unknown" (
        for /f "usebackq delims=" %%v in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Get-Content '%SYS_PATH%\core\version.json' -Raw | ConvertFrom-Json).version } catch { 'unknown' }" 2^>nul`) do (
            set "_ENGRAM_VER=%%v"
        )
    )
)
if "%_ENGRAM_VER%"=="" set "_ENGRAM_VER=unknown"
exit /b 0

:show_version
call :get_version
echo Engram %_ENGRAM_VER% (Portable Dev Runtime)
exit /b 0

:show_help
call :get_version
echo ===============================================================================
echo   Engram %_ENGRAM_VER% - Portable Dev Runtime
echo   Repository: https://github.com/greatgc-flow/Engram
echo ===============================================================================
echo.
echo Usage:
echo   engram ^<command^> [options...]
echo.
echo Lifecycle ^& Environment:
echo   engram open           Open a workspace (default action)
echo   engram update         Check and apply latest stable runtime and tool updates
echo   engram doctor         Report environment health, tool status, and configuration
echo   engram menu           Manage right-click context menu (status, enable, disable, clean)
echo   engram tidy           Clean temporary logs, caches, and orphaned files
echo   engram uninstall      Full removal: registry teardown and folder purge
echo.
echo Backup ^& State:
echo   engram backup         Back up personal AI data to a zip archive
echo   engram restore        Restore personal AI data from a backup archive/bundle
echo   engram reset          Reset personal AI data (.engram/ by default; --all includes workspace/)
echo.
echo Options:
echo   --version, -v         Display Engram version information
echo   --help, -h            Display this help message
echo.
exit /b 0
