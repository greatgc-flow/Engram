@echo off
:: run-tests.bat - Test execution entry point
::
:: First time running this? The portable venv does not ship pytest/hypothesis
:: by design (dev-only, not part of the runtime install) -- run this once:
::   _sys\env\venv\Scripts\python.exe -m pip install -r ..\..\requirements-dev.txt
::
:: Usage:
:: run-tests [--unit]        pytest unit tests (fast, ~5s)
:: run-tests [--lifecycle]   system lifecycle/portability tests
:: run-tests [--scenario]    MECE scenario tests (Korean path + SUBST + lifecycle)
:: run-tests [--scenarios]   alias of --scenario (kept for backward compatibility)
:: run-tests [--all]         all tests (unit+lifecycle, ~20s)
:: run-tests [--full]        alias of --all (kept for backward compatibility)
:: run-tests [--no-stress]   alias of --all (kept for backward compatibility)
::
:: --unit-edge, --unit-consensus, --unit-stress, and --integration were removed
:: 2026-09-07: their underlying test files (test_hub_edge.py, test_hub_consensus.py,
:: test_hub_stress.py, test_locking_stress.py, test_integration_py.py) were all
:: deleted in 482ab76 (Engram/peerhub separation, peer-governance layer removed)
:: but this runner kept referencing them, silently making --all/--full/--no-stress
:: always report FAIL and --unit-edge/--unit-consensus/--unit-stress/--integration
:: always report "no tests ran" -- found via direct execution, not by reading this
:: script. If a peer-governance-equivalent test class is ever needed again for a
:: different reason, it belongs in a new file, not a restoration of these.

for %%I in ("%~dp0..\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHONUTF8=1"
set "SYS_DIR=%PORTABLE_ROOT%\_sys"
set "PATH=%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PATH%"

set "_MODE=unit"
if "%~1"=="--unit"        set "_MODE=unit"
if "%~1"=="--lifecycle"   set "_MODE=lifecycle"
if "%~1"=="--scenario"    set "_MODE=scenario"
if "%~1"=="--scenarios"   set "_MODE=scenario"
if "%~1"=="--all"         set "_MODE=all"
if "%~1"=="--full"        set "_MODE=all"
if "%~1"=="--no-stress"   set "_MODE=all"

set "_FAIL=0"

echo [tests] Mode: %_MODE%
echo [tests] ============================================

:: Jump to the starting point for the selected mode
if "%_MODE%"=="unit"      goto :run_unit_all
if "%_MODE%"=="lifecycle" goto :run_lifecycle
if "%_MODE%"=="scenario"  goto :run_scenario
if "%_MODE%"=="all"       goto :run_unit_all
goto :done

:run_unit_all
echo [tests] --- Unit All (Core, Doc, Status, Path, Lifecycle) ---
python -m pytest "%~dp0unit" -v --tb=short
if errorlevel 1 set "_FAIL=1"
if "%_MODE%"=="unit" goto :done
goto :run_lifecycle

:run_lifecycle
echo [tests] --- System Lifecycle and Portability ---
python -m pytest "%~dp0unit\test_system_lifecycle.py" "%~dp0unit\test_path_scenarios.py" -v --tb=short
if errorlevel 1 set "_FAIL=1"
goto :done

:run_scenario
echo [tests] --- MECE Scenario (Korean path + SUBST + Lifecycle) ---
python -m pytest "%~dp0unit\test_path_scenarios.py" "%~dp0unit\test_system_lifecycle.py" -v --tb=short
if errorlevel 1 set "_FAIL=1"
goto :done

:done
echo.
echo [tests] ============================================
if "%_FAIL%"=="1" (
    echo [tests] RESULT: FAIL
    exit /b 1
) else (
    echo [tests] RESULT: PASS
    exit /b 0
)
