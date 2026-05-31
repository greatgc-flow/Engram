@echo off
setlocal DisableDelayedExpansion
:: collab-log-append.bat [AXIS] [SCRIPT] [STATUS] [DETAIL]
::
:: Appends one structured entry to _archive/collab-log/YYYY-MM-DD.md
:: Called by all Axis scripts after each Gemini invocation.
::
:: Parameters:
::   %1  Axis label   e.g. "Axis-B"
::   %2  Script name  e.g. "version-check.bat"
::   %3  Status       OK | FAIL | REFUSED | ESCALATED
::   %4  Detail       e.g. "Output: _archive\version-check.json"

if defined BASE_DIR (set "_B=%BASE_DIR%") else (for %%I in ("%~dp0..\..") do set "_B=%%~fI")
set "_LOGDIR=%_B%\_archive\collab-log"

for /f "delims=" %%D in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "_LD=%%D"
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format HH:mm:ss"') do set "_LT=%%T"

powershell -NoProfile -Command "$nl=[System.Environment]::NewLine; $d='%_LOGDIR%'; if(!(Test-Path $d)){[void](New-Item $d -ItemType Directory -Force)}; $f=$d+'\%_LD%.md'; $e=$nl+'## [%_LT%] %~1 | %~2'+$nl+'Status: %~3'+$nl+'%~4'+$nl+'---'; [System.IO.File]::AppendAllText($f,$e,(New-Object System.Text.UTF8Encoding($false)))" > nul 2>&1

:: Update gemini_metrics in status.json
if defined GEMINI_DIR (
    powershell -NoProfile -Command "$gf='%GEMINI_DIR%\status.json'; if(!(Test-Path $gf)){exit}; $j=Get-Content $gf -Raw|ConvertFrom-Json; $td=Get-Date -Format yyyyMMdd; $ts=Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'; if(!$j.PSObject.Properties['gemini_metrics'] -or $j.gemini_metrics.calls_today_date -ne $td){$m=[pscustomobject]@{calls_today=0;calls_today_date=$td;last_call_ts=$null;last_axis=$null;consecutive_failures=0;last_failure_reason=$null};$j|Add-Member -NotePropertyName gemini_metrics -NotePropertyValue $m -Force}; $m=$j.gemini_metrics; if('%~3' -eq 'OK' -or '%~3' -eq 'REFUSED'){$m.calls_today++;$m.last_axis='%~1';$m.last_call_ts=$ts}; if('%~3' -eq 'OK'){$m.consecutive_failures=0;$m.last_failure_reason=$null}elseif('%~3' -eq 'REFUSED'){$m.consecutive_failures++;$m.last_failure_reason='REFUSED: %~4'}else{$m.consecutive_failures++;$m.last_failure_reason='%~4'}; if($m.consecutive_failures -ge 3){$j.mode='OFF';$j.reason='api_error';$j.last_error='consecutive_failures_'+$td}; [System.IO.File]::WriteAllText($gf,($j|ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))" > nul 2>&1
)
