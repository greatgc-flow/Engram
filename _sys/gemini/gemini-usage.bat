@echo off
:: ================================================================
:: gemini-usage.bat  -  Gemini usage stats (zero tokens, local files only)
::
:: Read-only - no API calls
:: Source 1: _sys\gemini\config\tmp\*\logs.json  (direct CLI sessions)
:: Source 2: _sys\gemini\status.json             (Axis metrics, gemini_metrics)
:: Source 3: _archive\collab-log\YYYY-MM-DD.md  (Axis detail log)
:: Output  : _sys\gemini\usage.json
:: ================================================================

if defined GEMINI_DIR (set "_GD=%GEMINI_DIR%") else (set "_GD=%~dp0")
if defined BASE_DIR (set "_ROOT=%BASE_DIR%") else (for %%I in ("%~dp0..\..") do set "_ROOT=%%~fI")

for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_DT=%%I"

powershell -NoProfile -Command "$gd='%_GD:\=\\%'; $root='%_ROOT:\=\\%'; $today=Get-Date -Format 'yyyy-MM-dd'; $todayYMD=Get-Date -Format 'yyyyMMdd'; $gd=$gd.TrimEnd('\')+'\'; $root=$root.TrimEnd('\')+'\'; $tmpBase=$gd+'config\tmp'; $statusFile=$gd+'status.json'; $collabLog=$root+'_archive\collab-log\'+$today+'.md'; $outFile=$gd+'usage.json'; $sessions=@{}; $msgCount=0; $lastMsgTs=$null; if (Test-Path $tmpBase) { Get-ChildItem $tmpBase -Directory -ErrorAction SilentlyContinue | ForEach-Object { $lf=$_.FullName+'\logs.json'; if (Test-Path $lf) { try { $logs=Get-Content $lf -Raw | ConvertFrom-Json } catch { $logs=@() }; foreach ($e in $logs) { if ($e.timestamp -and $e.timestamp.StartsWith($today) -and $e.type -eq 'user') { $sessions[$e.sessionId]=1; $msgCount++; if (-not $lastMsgTs -or $e.timestamp -gt $lastMsgTs) { $lastMsgTs=$e.timestamp } } } } } }; $cfails=0; if (Test-Path $statusFile) { try { $s=Get-Content $statusFile -Raw | ConvertFrom-Json; if ($s.PSObject.Properties['gemini_metrics'] -and $s.gemini_metrics.calls_today_date -eq $todayYMD) { $cfails=[int]$s.gemini_metrics.consecutive_failures } } catch {} }; $axisBreakdown=[ordered]@{A=0;B=0;C=0;'D+'=0;D=0;E=0;F=0;G=0;H=0;Q=0}; $lastAxisName=$null; $lastAxisTime=$null; if (Test-Path $collabLog) { Get-Content $collabLog | ForEach-Object { if ($_ -match '^## \[(\d{2}:\d{2}:\d{2})\] (Axis-[A-HQ+]+)') { $ax=$Matches[2] -replace 'Axis-',''; if ($axisBreakdown.Contains($ax)) { $axisBreakdown[$ax]++ }; $lastAxisName=$Matches[2]; $lastAxisTime=$today+'T'+$Matches[1] } } }; $axisCalls=[int](($axisBreakdown.Values | Measure-Object -Sum).Sum); $result=[ordered]@{date=$today;generated_at='%_DT%';gemini_cli_direct=[ordered]@{sessions_today=$sessions.Count;messages_today=$msgCount;last_message_ts=if($lastMsgTs){$lastMsgTs}else{$null}};axis_calls=[ordered]@{calls_today=$axisCalls;last_axis=if($lastAxisName){$lastAxisName}else{$null};last_call_ts=if($lastAxisTime){$lastAxisTime}else{$null};consecutive_failures=$cfails;by_axis=$axisBreakdown};total_interactions_today=($sessions.Count+$axisCalls)}; [System.IO.File]::WriteAllText($outFile,($result | ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false))); Write-Host 'OK: Usage written to' $outFile"

set "_GD="
set "_ROOT="
set "_DT="
