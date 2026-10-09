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

:: Help for any verb is a static file: print it before any setup/Python check (works on a fresh folder)
set "_HELPVERB="
for %%V in (open update doctor menu tidy snapshots repair relocate uninstall backup restore reset version) do if /i "%SUBCMD%"=="%%V" set "_HELPVERB=%%V"
if not defined _HELPVERB goto :verb_help_done
if /i "%~2"=="-h" goto :verb_help_out
if /i "%~2"=="--help" goto :verb_help_out
if /i "%~2"=="/?" goto :verb_help_out
if /i "%~2"=="help" goto :verb_help_out
if /i "%_HELPVERB%"=="menu" (
    if /i "%~3"=="-h" goto :verb_help_out
    if /i "%~3"=="--help" goto :verb_help_out
    if /i "%~3"=="/?" goto :verb_help_out
    if /i "%~3"=="help" goto :verb_help_out
)
goto :verb_help_done
:verb_help_out
call :print_help_file %_HELPVERB%
exit /b 0
:verb_help_done

:: --- Interrupted environment operation gate (design section 9) ---
:: A non-terminal env-op journal means a Python/venv swap or relocation was interrupted. Only recovery,
:: read-only and help verbs may run; everything else (including the first-run bootstrap path, i.e. plain
:: `engram`) is refused.
call :journal_active
if not "%_JOURNAL_ACTIVE%"=="1" goto :journal_gate_pass
for %%V in (help --help -h /? version --version -v doctor repair relocate snapshots) do if /i "%SUBCMD%"=="%%V" goto :journal_gate_pass
goto :journal_blocked
:journal_gate_pass

if "%SUBCMD%"=="" goto :cmd_open

if /i "%SUBCMD%"=="help" (
    if "%~2"=="" goto :show_help
    goto :help_topic
)
if /i "%SUBCMD%"=="--help" goto :show_help
if /i "%SUBCMD%"=="-h" goto :show_help
if /i "%SUBCMD%"=="/?" goto :show_help

if /i "%SUBCMD%"=="version" (
    if "%~2"=="/?" goto :show_version_help
    if "%~2"=="-h" goto :show_version_help
    if "%~2"=="--help" goto :show_version_help
    if /i "%~2"=="help" goto :show_version_help
    goto :show_version
)
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
if /i "%SUBCMD%"=="snapshots" goto :cmd_snapshots
if /i "%SUBCMD%"=="repair" goto :cmd_repair
if /i "%SUBCMD%"=="relocate" goto :cmd_relocate
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
set "ENGRAM_UNKNOWN_VERB=%SUBCMD%"
call :say_unknown "Unknown command"
call :suggest_verb
echo Run 'engram help' for available commands.
exit /b 2

:: 'engram help <verb>' prints the same file as '<verb> --help' (core\help\<verb>.txt)
:help_topic
set "_HV_FILE="
if /i "%~2"=="help" goto :show_help
if /i "%~2"=="--help" goto :show_help
if /i "%~2"=="-h" goto :show_help
if /i "%~2"=="/?" goto :show_help
for %%F in ("%SYS_PATH%\core\help\*.txt") do if /i "%%~nF"=="%~2" if /i not "%%~nF"=="index" set "_HV_FILE=%%~fF"
if defined _HV_FILE (
    type "%_HV_FILE%"
    exit /b 0
)
set "ENGRAM_UNKNOWN_VERB=%~2"
call :say_unknown "Unknown command"
call :suggest_verb
echo Run 'engram help' for available commands.
exit /b 2

:: Echo user-supplied text safely: delayed expansion expands AFTER parsing, so & | < > ^ % and quotes stay literal
:say_unknown
setlocal EnableDelayedExpansion
echo [Error] %~1: !ENGRAM_UNKNOWN_VERB!
endlocal
exit /b 0

:: Prints "Did you mean ..." for ENGRAM_UNKNOWN_VERB when Python is available (silent otherwise)
:suggest_verb
if not exist "%SYS_PATH%\env\python\python.exe" exit /b 0
"%SYS_PATH%\env\python\python.exe" "%SYS_PATH%\core\cli_help.py" suggest-verb 2>nul
exit /b 0

:: Prints core\help\<name>.txt (name passed as %1): the single source of every verb's help text
:print_help_file
if exist "%SYS_PATH%\core\help\%~1.txt" (
    type "%SYS_PATH%\core\help\%~1.txt"
) else (
    echo Usage: engram %~1 [options]
    echo Help file missing: _sys\core\help\%~1.txt
)
exit /b 0

:: ----------------------------------------------------------------------------
:: Subcommand Handlers
:: ----------------------------------------------------------------------------

:cmd_open
if "%~1"=="/?" goto :show_open_help
if "%~1"=="-h" goto :show_open_help
if "%~1"=="--help" goto :show_open_help
if /i "%~1"=="help" goto :show_open_help
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
    if exist "%SYS_PATH%\env\venv\" (
        call :managed_python_missing
        if errorlevel 2 exit /b 1
    )
    echo Engram is not set up.
    echo Run 'engram' to initialize the environment.
    exit /b 1
)
exit /b 0

:managed_python_missing
:: Recovery verbs get a precise hint when only the managed Python is gone (venv kept).
for %%V in (repair relocate snapshots doctor) do if /i "%SUBCMD%"=="%%V" (
    echo Managed Python is missing. Run _sys\core\bootstrap.bat to restore it ^(the venv and packages are kept^), then run 'engram repair'.
    exit /b 2
)
exit /b 0

:cmd_doctor
if "%~1"=="/?" goto :dispatch_doctor
if "%~1"=="-h" goto :dispatch_doctor
if "%~1"=="--help" goto :dispatch_doctor
if /i "%~1"=="help" goto :dispatch_doctor
call :check_setup
if errorlevel 1 exit /b 1
:dispatch_doctor
call "%SYS_PATH%\core\dispatch.bat" doctor %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_menu
if "%~1"=="/?" goto :show_menu_help
if "%~1"=="-h" goto :show_menu_help
if "%~1"=="--help" goto :show_menu_help
if /i "%~1"=="help" goto :show_menu_help
if "%~2"=="/?" goto :show_menu_help
if "%~2"=="-h" goto :show_menu_help
if "%~2"=="--help" goto :show_menu_help
if /i "%~2"=="help" goto :show_menu_help
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
set "ENGRAM_UNKNOWN_VERB=%~1"
call :say_unknown "Unknown menu command"
set "ENGRAM_SUGGEST_FROM=status,enable,disable,clean"
call :suggest_verb
echo Run 'engram menu --help' for available commands.
exit /b 2

:show_menu_help
call :print_help_file menu
exit /b 0

:cmd_tidy
if "%~1"=="/?" goto :dispatch_tidy
if "%~1"=="-h" goto :dispatch_tidy
if "%~1"=="--help" goto :dispatch_tidy
if /i "%~1"=="help" goto :dispatch_tidy
call :check_setup
if errorlevel 1 exit /b 1
:dispatch_tidy
call "%SYS_PATH%\core\dispatch.bat" tidy %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_snapshots
if "%~1"=="/?" goto :dispatch_snapshots
if "%~1"=="-h" goto :dispatch_snapshots
if "%~1"=="--help" goto :dispatch_snapshots
if /i "%~1"=="help" goto :dispatch_snapshots
call :check_setup
if errorlevel 1 exit /b 1
:dispatch_snapshots
call "%SYS_PATH%\core\dispatch.bat" snapshots %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_repair
if "%~1"=="/?" goto :dispatch_repair
if "%~1"=="-h" goto :dispatch_repair
if "%~1"=="--help" goto :dispatch_repair
if /i "%~1"=="help" goto :dispatch_repair
:: an interrupted swap may have removed env\python: dispatch.bat then finds an alternate interpreter
if "%_JOURNAL_ACTIVE%"=="1" goto :dispatch_repair
call :check_setup
if errorlevel 1 exit /b 1
:dispatch_repair
call "%SYS_PATH%\core\dispatch.bat" repair %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_relocate
if "%~1"=="/?" goto :dispatch_relocate
if "%~1"=="-h" goto :dispatch_relocate
if "%~1"=="--help" goto :dispatch_relocate
if /i "%~1"=="help" goto :dispatch_relocate
if "%_JOURNAL_ACTIVE%"=="1" goto :dispatch_relocate
call :check_setup
if errorlevel 1 exit /b 1
:dispatch_relocate
call "%SYS_PATH%\core\dispatch.bat" relocate %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_update
if "%~1"=="/?" goto :dispatch_update
if "%~1"=="-h" goto :dispatch_update
if "%~1"=="--help" goto :dispatch_update
if /i "%~1"=="help" goto :dispatch_update
call :check_setup
if errorlevel 1 exit /b 1
:dispatch_update
call "%SYS_PATH%\core\dispatch.bat" update %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_uninstall
if "%~1"=="/?" goto :dispatch_uninstall
if "%~1"=="-h" goto :dispatch_uninstall
if "%~1"=="--help" goto :dispatch_uninstall
if /i "%~1"=="help" goto :dispatch_uninstall
call :check_setup
if errorlevel 1 exit /b 1
:dispatch_uninstall
call "%SYS_PATH%\core\dispatch.bat" uninstall %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_backup
if "%~1"=="/?" goto :dispatch_backup
if "%~1"=="-h" goto :dispatch_backup
if "%~1"=="--help" goto :dispatch_backup
if /i "%~1"=="help" goto :dispatch_backup
call :check_setup
if errorlevel 1 exit /b 1
:dispatch_backup
call "%SYS_PATH%\core\dispatch.bat" backup %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_restore
if "%~1"=="/?" goto :dispatch_restore
if "%~1"=="-h" goto :dispatch_restore
if "%~1"=="--help" goto :dispatch_restore
if /i "%~1"=="help" goto :dispatch_restore
call :check_setup
if errorlevel 1 exit /b 1
:dispatch_restore
call "%SYS_PATH%\core\dispatch.bat" restore %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:cmd_reset
if "%~1"=="/?" goto :dispatch_reset
if "%~1"=="-h" goto :dispatch_reset
if "%~1"=="--help" goto :dispatch_reset
if /i "%~1"=="help" goto :dispatch_reset
call :check_setup
if errorlevel 1 exit /b 1
:dispatch_reset
call "%SYS_PATH%\core\dispatch.bat" reset %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:: ----------------------------------------------------------------------------
:: Interrupted-operation journal helpers (design section 9)
:: ----------------------------------------------------------------------------
:journal_active
set "_JOURNAL_ACTIVE=0"
set "_LASTN="
set "_TERMN="
if not exist "%ENGRAM_SYS_DIR%\data\state\env-op.journal.jsonl" exit /b 0
for /f "tokens=1 delims=:" %%N in ('findstr /n /l /c:"\"event\":\"PHASE\"" "%ENGRAM_SYS_DIR%\data\state\env-op.journal.jsonl"') do set "_LASTN=%%N"
if not defined _LASTN exit /b 0
for /f "tokens=1 delims=:" %%N in ('findstr /n /l /c:"\"name\":\"COMMITTED\"" /c:"\"name\":\"ROLLED_BACK\"" "%ENGRAM_SYS_DIR%\data\state\env-op.journal.jsonl"') do set "_TERMN=%%N"
if not "%_LASTN%"=="%_TERMN%" set "_JOURNAL_ACTIVE=1"
exit /b 0

:journal_blocked
echo [Error] An environment operation was interrupted; its journal is still open.
echo         Finish or undo it before using Engram:
echo           engram repair --resume      continue where it stopped
echo           engram repair --rollback    undo it
exit /b 14

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
    set "ENGRAM_VERSION_FILE=%SYS_PATH%\core\version.json"
    if exist "%SYS_PATH%\env\python\python.exe" (
        for /f "usebackq delims=" %%v in (`"%SYS_PATH%\env\python\python.exe" -c "import json, os, sys; sys.stdout.write(json.load(open(os.environ['ENGRAM_VERSION_FILE'], encoding='utf-8')).get('version', 'unknown'))" 2^>nul`) do (
            set "_ENGRAM_VER=%%v"
        )
    )
    if "%_ENGRAM_VER%"=="unknown" (
        for /f "usebackq delims=" %%v in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Get-Content $env:ENGRAM_VERSION_FILE -Raw | ConvertFrom-Json).version } catch { 'unknown' }" 2^>nul`) do (
            set "_ENGRAM_VER=%%v"
        )
    )
    set "ENGRAM_VERSION_FILE="
)
if "%_ENGRAM_VER%"=="" set "_ENGRAM_VER=unknown"
exit /b 0

:show_version
call :get_version
echo Engram %_ENGRAM_VER% (Portable Dev Runtime)
exit /b 0

:show_version_help
call :print_help_file version
exit /b 0

:show_open_help
call :print_help_file open
exit /b 0

:show_help
call :get_version
echo ===============================================================================
echo   Engram %_ENGRAM_VER% - Portable Dev Runtime
echo   Repository: https://github.com/greatgc-flow/Engram
echo ===============================================================================
echo.
call :print_help_file index
exit /b 0
