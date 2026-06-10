@echo off
:: ================================================================
:: gemini-set-ratio.bat [0-10]
::
:: Sets COLLAB_RATE in _sys\ai\config.json (PROTOCOL v3.1 Mixed-Model)
::
:: Anchor Definitions:
::   [0] Solo         (100%% Autonomy - No consensus)
::   [3] System Guard (75%% Autonomy - PROPOSE for _sys/ and docs)
::   [5] Partner      (50%% Autonomy - Milestone consensus - DEFAULT)
::   [8] Strict       (25%% Autonomy - Logic change consensus)
::   [10] Brain Sync  (0%% Autonomy - ABSOLUTE ZERO EXCEPTIONS)
:: ================================================================

for %%I in ("%~dp0..\ai\config.json") do set "_CFG=%%~fI"

if "%~1"=="" (
    echo Usage: gemini-set-ratio.bat [0-10]
    echo.
    echo Anchor Levels:
    echo   [0] Solo         (Autonomy: 100%%)
    echo   [3] System Guard (Autonomy: 75%%)
    echo   [5] Partner      (Autonomy: 50%%)
    echo   [8] Strict       (Autonomy: 25%%)
    echo   [10] Brain Sync  (Autonomy: 0%%)
    echo.
    echo Current config:
    type "%_CFG%"
    exit /b 0
)

set "_N=%~1"
if %_N% LSS 0 set "_N=0"
if %_N% GTR 10 set "_N=10"

powershell -NoProfile -Command "$n=[int]'%_N%'; try { $cfg=Get-Content '%_CFG:\=\\%' -Raw|ConvertFrom-Json } catch { $cfg=[pscustomobject]@{ratio=5;review_interval_min=5;last_review_ts=$null} }; $cfg|Add-Member -NotePropertyName ratio -NotePropertyValue $n -Force; [System.IO.File]::WriteAllText('%_CFG:\=\\%',($cfg|ConvertTo-Json -Depth 3),(New-Object System.Text.UTF8Encoding($false)))"

echo [gemini-set-ratio] COLLAB_RATE set to %_N%
if "%_N%"=="0"  echo   [Solo Mode - All autonomous]
if "%_N%"=="3"  echo   [System Guard - PROPOSE for _sys/ and docs]
if "%_N%"=="5"  echo   [Partner Mode - Milestone consensus]
if "%_N%"=="8"  echo   [Strict Mode - Logic change consensus]
if "%_N%"=="10" echo   [Brain Sync - ABSOLUTE ZERO EXCEPTIONS]

type "%_CFG%"

set "_CFG=" & set "_N="
