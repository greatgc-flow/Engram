@echo off
setlocal EnableDelayedExpansion
:: ================================================================
:: gemini-batch-review.bat  (Axis-R) - Batch review of uncommitted changes
::
:: Called by: Stop hook (via gemini-review-trigger.bat) or manually
:: Requires:  GEMINI_RATIO >= 7, time gate, git changes present
:: Output:    _archive\gemini-reviews\YYYYMMDD_HHMMSS.md + latest.md
:: ================================================================

if defined GEMINI_DIR (set "_GD=%GEMINI_DIR%") else (for %%I in ("%~dp0..\gemini") do set "_GD=%%~fI")
if defined BASE_DIR (set "_ROOT=%BASE_DIR%") else (for %%I in ("%~dp0..\..") do set "_ROOT=%%~fI")
set "_CFG=%_GD%\config.json"

:: --- Ratio check (requires >= 7) ---
call "%_GD%\gemini-gate.bat" 7
if errorlevel 1 (
    echo [Axis-R] SKIP: ratio ^< 7
    goto :END
)

:: --- Gemini availability check ---
call "%~dp0gemini-mode-check.bat"
if not "%GEMINI_MODE%"=="ON" (
    echo [Axis-R] SKIP: Gemini not available ^(%GEMINI_OFF_REASON%^)
    goto :END
)

:: --- Time gate ---
powershell -NoProfile -Command "$ok='SKIP'; try { $cfg=Get-Content '%_CFG:\=\\%' -Raw|ConvertFrom-Json; $iv=[int]$cfg.review_interval_min; $last=$cfg.last_review_ts; if(-not $last -or $last -eq 'null'){$ok='RUN'}elseif((New-TimeSpan (Get-Date $last) (Get-Date)).TotalMinutes -ge $iv){$ok='RUN'} } catch { $ok='RUN' }; Write-Host $ok" > "%TEMP%\_axisR_gate.txt" 2>&1
set /p _GATE=<"%TEMP%\_axisR_gate.txt"
del "%TEMP%\_axisR_gate.txt" >nul 2>&1
if not "!_GATE!"=="RUN" (
    echo [Axis-R] SKIP: review interval not elapsed
    goto :END
)

:: --- Check for uncommitted changes ---
set "_HAS_DIFF="
for /f "delims=" %%L in ('git -C "%_ROOT%" diff HEAD --name-only 2^>nul') do set "_HAS_DIFF=1"
if not defined _HAS_DIFF (
    echo [Axis-R] SKIP: no uncommitted changes
    goto :END
)

:: --- Build diff content (limited to ~8000 chars) ---
set "_TMPD=%TEMP%\_axisR_diff_%RANDOM%.txt"
set "_TMPP=%TEMP%\_axisR_prompt_%RANDOM%.txt"

git -C "%_ROOT%" diff HEAD --stat > "%_TMPD%" 2>&1
git -C "%_ROOT%" diff HEAD >> "%_TMPD%" 2>&1

powershell -NoProfile -Command "$d=Get-Content '%_TMPD:\=\\%' -Raw; if($d.Length -gt 8000){$d=$d.Substring(0,8000)+'`n...(truncated)'}; $p='Review the following uncommitted git diff. Report in Korean:`n1) Bugs or risky patterns`n2) Improvements or simplification opportunities`n3) One-line summary of changes`nBe concise (max 400 words).`n`n--- git diff ---`n'+$d; [System.IO.File]::WriteAllText('%_TMPP:\=\\%',$p,(New-Object System.Text.UTF8Encoding($false)))"

:: --- Setup output paths ---
set "_OUTDIR=%_ROOT%\_archive\gemini-reviews"
if not exist "%_OUTDIR%" mkdir "%_OUTDIR%"

for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "_TS=%%T"
set "_OUT=%_OUTDIR%\!_TS!.md"

:: --- Call Gemini ---
echo [Axis-R] Requesting Gemini review...
call "%~dp0gemini-session-read.bat"
type "%_TMPP%" | gemini %_GEMINI_SESSION_FLAG% -p "" -y -o text > "%_OUT%" 2>&1
if errorlevel 1 (
    echo [Axis-R] ERROR: Gemini call failed
    del "%_OUT%" >nul 2>&1
    call "%~dp0collab-log-append.bat" "Axis-R" "gemini-batch-review.bat" "FAIL" "Error: gemini call failed"
    goto :CLEANUP
)

:: --- Check for refusal ---
findstr /i "\[REFUSAL:" "%_OUT%" >nul 2>&1
if not errorlevel 1 (
    echo [Axis-R] Gemini refused request
    del "%_OUT%" >nul 2>&1
    call "%~dp0collab-log-append.bat" "Axis-R" "gemini-batch-review.bat" "REFUSED" "Gemini refused review"
    goto :CLEANUP
)

:: --- Write latest.md and update timestamp ---
copy /Y "%_OUT%" "%_OUTDIR%\latest.md" >nul

powershell -NoProfile -Command "$ts=Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'; $f='%_CFG:\=\\%'; try{$cfg=Get-Content $f -Raw|ConvertFrom-Json}catch{$cfg=[pscustomobject]@{ratio=7;review_interval_min=5}}; $cfg|Add-Member -NotePropertyName last_review_ts -NotePropertyValue $ts -Force; [System.IO.File]::WriteAllText($f,($cfg|ConvertTo-Json -Depth 3),(New-Object System.Text.UTF8Encoding($false)))" >nul 2>&1

call "%~dp0collab-log-append.bat" "Axis-R" "gemini-batch-review.bat" "OK" "Review: %_OUT%"
echo [Axis-R] Review complete: %_OUT%

:CLEANUP
del "%_TMPD%" >nul 2>&1
del "%_TMPP%" >nul 2>&1

:END
set "_GD="
set "_ROOT="
set "_CFG="
set "_HAS_DIFF="
set "_GATE="
set "_TMPD="
set "_TMPP="
set "_OUTDIR="
set "_TS="
set "_OUT="
endlocal
