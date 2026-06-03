@echo off
:: run-tests.bat — 테스트 실행 진입점
:: Usage:
::   run-tests [--unit]          pytest 단위 테스트 (빠름, ~5s)
::   run-tests [--unit-edge]     경계값/에러핸들링 단위 테스트
::   run-tests [--unit-stress]   병렬 스트레스 단위 테스트 (~30s)
::   run-tests [--integration]   PowerShell 통합 테스트 (~30s)
::   run-tests [--scenarios]     사용자 시나리오 E2E 테스트 (~20s)
::   run-tests [--all]           전체 (unit+integration+scenarios, ~90s)
::   run-tests [--full]          전체+스트레스 (모든 테스트, ~120s)

for %%I in ("%~dp0..\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHONUTF8=1"
set "PATH=%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PATH%"

set "_MODE=unit"
if "%~1"=="--unit"         set "_MODE=unit"
if "%~1"=="--unit-edge"    set "_MODE=unit-edge"
if "%~1"=="--unit-stress"  set "_MODE=unit-stress"
if "%~1"=="--integration"  set "_MODE=integration"
if "%~1"=="--scenarios"    set "_MODE=scenarios"
if "%~1"=="--all"          set "_MODE=all"
if "%~1"=="--full"         set "_MODE=full"

set "_FAIL=0"
set "_TOTAL=0"

echo [tests] Mode: %_MODE%
echo [tests] ============================================

if "%_MODE%"=="unit"        goto :run_unit_core
if "%_MODE%"=="unit-edge"   goto :run_unit_edge
if "%_MODE%"=="unit-stress" goto :run_unit_stress
if "%_MODE%"=="integration" goto :run_integration
if "%_MODE%"=="scenarios"   goto :run_scenarios
if "%_MODE%"=="all"         goto :run_unit_core
if "%_MODE%"=="full"        goto :run_unit_core
goto :done

:run_unit_core
echo [tests] --- Unit Core (test_hub.py) ---
python -m pytest "%~dp0unit\test_hub.py" -v --tb=short
if errorlevel 1 set "_FAIL=1"
if "%_MODE%"=="unit" goto :done
if "%_MODE%"=="unit-edge" goto :done

:run_unit_edge
echo [tests] --- Unit Edge (test_hub_edge.py) ---
python -m pytest "%~dp0unit\test_hub_edge.py" -v --tb=short
if errorlevel 1 set "_FAIL=1"
if "%_MODE%"=="unit-edge" goto :done
if "%_MODE%"=="all"       goto :run_integration
if "%_MODE%"=="full"      goto :run_unit_stress
goto :run_integration

:run_unit_stress
echo [tests] --- Unit Stress (test_hub_stress.py) ---
python -m pytest "%~dp0unit\test_hub_stress.py" -v --tb=short -x
if errorlevel 1 set "_FAIL=1"
if "%_MODE%"=="unit-stress" goto :done
goto :run_integration

:run_integration
echo [tests] --- Integration (PS1) ---
powershell -ExecutionPolicy Bypass -File "%~dp0integration\test_tools_path.ps1"
if errorlevel 1 set "_FAIL=1"
powershell -ExecutionPolicy Bypass -File "%~dp0integration\test_session_flow.ps1"
if errorlevel 1 set "_FAIL=1"
powershell -ExecutionPolicy Bypass -File "%~dp0integration\test_ipc.ps1"
if errorlevel 1 set "_FAIL=1"
if "%_MODE%"=="integration" goto :done
goto :run_scenarios

:run_scenarios
echo [tests] --- User Scenarios (test_scenarios.ps1) ---
powershell -ExecutionPolicy Bypass -File "%~dp0integration\test_scenarios.ps1"
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
