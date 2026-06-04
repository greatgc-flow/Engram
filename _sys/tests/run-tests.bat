@echo off
:: run-tests.bat - Test execution entry point
:: Usage:
:: run-tests [--unit]          pytest unit tests (fast, ~5s)
:: run-tests [--unit-edge]     boundary/error-handling unit tests
:: run-tests [--unit-consensus] N-Node consensus deep tests
:: run-tests [--unit-stress]   parallel stress unit tests (~30s, high memory)
:: run-tests [--lifecycle]     system lifecycle/portability tests
:: run-tests [--integration]   PowerShell integration tests (~30s)
:: run-tests [--scenario]      MECE scenario tests (Korean path + SUBST + lifecycle)
:: run-tests [--scenarios]     user scenario E2E tests (~20s)
:: run-tests [--all]           all tests (unit+lifecycle+integration+scenarios, ~90s)
:: run-tests [--full]          all+stress (every test, ~120s, needs ~1.5GB RAM)
:: run-tests [--no-stress]     same as --full but skips stress tests

for %%I in ("%~dp0..\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHONUTF8=1"
set "GEMINI_DIR=%PORTABLE_ROOT%\_sys\gemini"
set "SYS_DIR=%PORTABLE_ROOT%\_sys"
set "PATH=%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PATH%"

set "_MODE=unit"
set "_NO_STRESS=0"
if "%~1"=="--unit"            set "_MODE=unit"
if "%~1"=="--unit-edge"       set "_MODE=unit-edge"
if "%~1"=="--unit-consensus"  set "_MODE=unit-consensus"
if "%~1"=="--unit-stress"     set "_MODE=unit-stress"
if "%~1"=="--lifecycle"       set "_MODE=lifecycle"
if "%~1"=="--integration"     set "_MODE=integration"
if "%~1"=="--scenario"        set "_MODE=scenario"
if "%~1"=="--scenarios"       set "_MODE=scenarios"
if "%~1"=="--all"             set "_MODE=all"
if "%~1"=="--full"            set "_MODE=full"
if "%~1"=="--no-stress"       set "_MODE=full" & set "_NO_STRESS=1"

set "_FAIL=0"
set "_TOTAL=0"

echo [tests] Mode: %_MODE%
echo [tests] ============================================

:: Force Gemini mode ON for testing consistency
python -c "import json; from pathlib import Path; p = Path(r'%~dp0..\gemini\status.json'); d = json.loads(p.read_text('utf-8-sig')) if p.exists() else {}; d['mode']='ON'; d['consecutive_failures']=0; p.write_text(json.dumps(d, indent=2), 'utf-8')"

:: Jump to the starting point for the selected mode
if "%_MODE%"=="unit"           goto :run_unit_all
if "%_MODE%"=="unit-edge"      goto :run_unit_edge
if "%_MODE%"=="unit-consensus" goto :run_unit_consensus
if "%_MODE%"=="unit-stress"    goto :run_unit_stress
if "%_MODE%"=="lifecycle"      goto :run_lifecycle
if "%_MODE%"=="integration"    goto :run_integration
if "%_MODE%"=="scenario"       goto :run_scenario
if "%_MODE%"=="scenarios"      goto :run_scenarios
if "%_MODE%"=="all"            goto :run_unit_all
if "%_MODE%"=="full"           goto :run_unit_all
goto :done

:run_unit_all
echo [tests] --- Unit All (Core, Edge, Consensus, Doc, Status, Path, Lifecycle) ---
python -m pytest "%~dp0unit" --ignore="%~dp0unit\test_hub_stress.py" --ignore="%~dp0unit\test_locking_stress.py" --ignore="%~dp0unit\test_integration_py.py" -v --tb=short
if errorlevel 1 set "_FAIL=1"
if "%_MODE%"=="unit" goto :done
if "%_MODE%"=="all" goto :run_integration
if "%_NO_STRESS%"=="1" goto :run_integration
if "%_MODE%"=="full" goto :run_unit_stress
goto :run_integration

:run_unit_consensus
echo [tests] --- Unit Consensus (test_hub_consensus.py) ---
python -m pytest "%~dp0unit\test_hub_consensus.py" -v --tb=short
if errorlevel 1 set "_FAIL=1"
goto :done

:run_unit_edge
echo [tests] --- Unit Edge (test_hub_edge.py) ---
python -m pytest "%~dp0unit\test_hub_edge.py" -v --tb=short
if errorlevel 1 set "_FAIL=1"
goto :done

:run_unit_stress
echo [tests] --- Unit Stress (test_hub_stress.py + test_locking_stress.py, needs 2GB+ RAM) ---
python -m pytest "%~dp0unit\test_hub_stress.py" "%~dp0unit\test_locking_stress.py" -v --tb=short -x
if errorlevel 1 set "_FAIL=1"
if "%_MODE%"=="unit-stress" goto :done
goto :run_integration

:run_lifecycle
echo [tests] --- System Lifecycle and Portability ---
python -m pytest "%~dp0unit\test_system_lifecycle.py" "%~dp0unit\test_path_scenarios.py" -v --tb=short
if errorlevel 1 set "_FAIL=1"
if "%_MODE%"=="lifecycle" goto :done
goto :run_integration

:run_integration
echo [tests] --- Integration (test_integration_py.py) ---
python -m pytest "%~dp0unit\test_integration_py.py" -v --tb=short
if errorlevel 1 set "_FAIL=1"
goto :done

:run_scenario
echo [tests] --- MECE Scenario (Korean path + SUBST + Lifecycle) ---
python -m pytest "%~dp0unit\test_path_scenarios.py" "%~dp0unit\test_system_lifecycle.py" -v --tb=short
if errorlevel 1 set "_FAIL=1"
goto :done

:run_scenarios
echo [tests] --- User Scenarios E2E (integration + path + lifecycle) ---
python -m pytest "%~dp0unit\test_integration_py.py" "%~dp0unit\test_path_scenarios.py" "%~dp0unit\test_system_lifecycle.py" -v --tb=short
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
