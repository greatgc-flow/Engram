@echo off
setlocal DisableDelayedExpansion

:: Minimal Bootstrap environment
set "SYS_DIR=%~dp0.."
set "PY=%SYS_DIR%\env\python\python.exe"

:: If Python is missing, only allow 'install'
if not exist "%PY%" (
    if /i "%~1"=="install" (
        echo [i] Bootstrapping environment...
        :: _sys/core/bootstrap.bat logic will be triggered if we just call it
        :: but we want to avoid infinite loops.
        :: For now, we'll let the root _sys/core/bootstrap.bat handle the initial bootstrap.
        exit /b 0
    )
    :: An interrupted Python swap can leave env\python missing: only `repair` may run on the
    :: first working alternate interpreter so it can resume or roll the operation back.
    if exist "%SYS_DIR%\data\state\env-op.journal.jsonl" (
        if /i "%~1"=="repair" goto :alt_python
    )
    echo [Error] Portable environment not initialized.
    echo Please run _sys/core/bootstrap.bat first.
    exit /b 1
)

:: Execute via dispatcher.py
set "PYTHONUTF8=1"
"%PY%" "%SYS_DIR%\core\dispatcher.py" %*
set "_RC=%errorlevel%"
if not "%_RC%"=="75" exit /b %_RC%

:: Exit 75 = runner handoff (python swap). The engine process ran ON env\python, so it cannot rename it: it
:: prepared a runner copy and exited. Re-run the same command line on that runner (design 6.1).
if "%ENGRAM_IN_RUNNER%"=="1" exit /b 75
if not exist "%SYS_DIR%\data\state\env-op\handoff.txt" (
    echo [Error] A runner handoff was requested but no handoff file was written.
    exit /b 1
)
set "_REL="
set "_YES="
set /p _REL=<"%SYS_DIR%\data\state\env-op\handoff.txt"
for /f "usebackq skip=1 delims=" %%Y in ("%SYS_DIR%\data\state\env-op\handoff.txt") do set "_YES=%%Y"
del /q "%SYS_DIR%\data\state\env-op\handoff.txt" >nul 2>&1
:: The handoff names the runner RELATIVE to the sys dir (ASCII): immune to console code pages. Refuse traversal.
if not defined _REL (
    echo [Error] The runner handoff file is empty.
    exit /b 1
)
if not "%_REL:..=%"=="%_REL%" (
    echo [Error] The runner handoff path is not allowed.
    exit /b 1
)
set "_RUNNER=%SYS_DIR%\%_REL%"
if not exist "%_RUNNER%" (
    echo [Error] The runner interpreter named by the handoff file does not exist.
    exit /b 1
)
set "ENGRAM_IN_RUNNER=1"
if "%_YES%"=="1" set "ENGRAM_ASSUME_YES=1"
echo [i] Continuing on the runner interpreter so the Python tree can be replaced.
"%_RUNNER%" "%SYS_DIR%\core\dispatcher.py" %*
exit /b %errorlevel%

:alt_python
set "PYTHONUTF8=1"
set "PY="
set "_KIND="

:: 1) newest runner copy
if exist "%SYS_DIR%\data\temp\env-op\" (
    for /f "usebackq delims=" %%D in (`dir /b /ad /o-d "%SYS_DIR%\data\temp\env-op" 2^>nul`) do call :check_runner "%%D"
)
if defined PY goto :alt_found

:: 2) backup payload
if exist "%SYS_DIR%\data\backups\env\python\" (
    for /f "usebackq delims=" %%D in (`dir /b /ad /o-d "%SYS_DIR%\data\backups\env\python" 2^>nul`) do call :check_backup "%%D"
)
if defined PY goto :alt_found

:: 3) python.new
if exist "%SYS_DIR%\env\python.new\python.exe" (
    set "PY=%SYS_DIR%\env\python.new\python.exe"
    set "_KIND=python.new"
    goto :alt_found
)

:alt_found
if not defined PY (
    echo [Error] No usable Python interpreter was found to recover the interrupted operation.
    exit /b 1
)
echo [i] Recovering an interrupted environment operation with an alternate interpreter: %_KIND%
:: an alternate interpreter is already outside the swap targets: never hand off again
set "ENGRAM_IN_RUNNER=1"
"%PY%" "%SYS_DIR%\core\dispatcher.py" %*
exit /b %errorlevel%

:check_runner
if defined PY exit /b 0
if exist "%SYS_DIR%\data\temp\env-op\%~1\runner\python.exe" (
    set "PY=%SYS_DIR%\data\temp\env-op\%~1\runner\python.exe"
    set "_KIND=runner"
)
exit /b 0

:check_backup
if defined PY exit /b 0
if exist "%SYS_DIR%\data\backups\env\python\%~1\payload\python.exe" (
    set "PY=%SYS_DIR%\data\backups\env\python\%~1\payload\python.exe"
    set "_KIND=backup"
)
exit /b 0
