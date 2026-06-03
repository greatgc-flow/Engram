# launch-wsbtest.ps1 — Run sandbox-test.bat inside Windows Sandbox (WSB)
# Usage: powershell -ExecutionPolicy Bypass -File launch-wsbtest.ps1
# Requires: Windows Sandbox feature enabled (optional feature on Win11 Pro/Enterprise)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SysDir    = Split-Path -Parent $ScriptDir
$BaseDir   = Split-Path -Parent $SysDir
$ResultsDir = Join-Path $ScriptDir "results"

if (-not (Test-Path $ResultsDir)) {
    New-Item -ItemType Directory -Path $ResultsDir -Force | Out-Null
}

# Resolve physical path (handles SUBST drives)
$PhysicalBaseDir = $BaseDir
$Drive = ($BaseDir -replace '^([A-Za-z]):.*', '$1').ToUpper()
$SubstLines = subst 2>&1
foreach ($line in $SubstLines) {
    if ($line -match "^${Drive}:\\:\s+=>\s+(.+)$") {
        $PhysicalBase = $Matches[1].Trim().TrimEnd('\')
        $Relative = $BaseDir.Substring(2)   # strip "P:"
        if ($Relative -ne "" -and $Relative[0] -ne '\') { $Relative = "\" + $Relative }
        $PhysicalBaseDir = $PhysicalBase + $Relative
        break
    }
}
$PhysicalBaseDir = $PhysicalBaseDir.TrimEnd('\')

$PhysicalResultsDir = Join-Path $PhysicalBaseDir "_sys\test\results"

Write-Host "[WSB Test] Host base path  : $PhysicalBaseDir"
Write-Host "[WSB Test] Results folder  : $PhysicalResultsDir"

# Generate temp WSB config with physical paths
$Timestamp = Get-Date -Format "yyyyMMddHHmmss"
$TempWsb = Join-Path $env:TEMP "porta-wsbtest-$Timestamp.wsb"

$WsbXml = @"
<Configuration>
  <VGpu>Disable</VGpu>
  <Networking>Disable</Networking>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>$PhysicalBaseDir</HostFolder>
      <SandboxFolder>C:\PortableDev</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>$PhysicalResultsDir</HostFolder>
      <SandboxFolder>C:\TestResults</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>cmd /c "C:\PortableDev\_sys\test\sandbox-test.bat &amp; echo WSB_DONE > C:\TestResults\result.txt &amp; shutdown /s /t 5"</Command>
  </LogonCommand>
</Configuration>
"@

Set-Content -Path $TempWsb -Value $WsbXml -Encoding utf8
Write-Host "[WSB Test] Launching Windows Sandbox..."
Write-Host "[WSB Test] Sandbox will auto-shutdown when tests finish."
Write-Host "[WSB Test] Waiting for results in: $ResultsDir"

$ResultFile = Join-Path $ResultsDir "result.txt"
if (Test-Path $ResultFile) { Remove-Item $ResultFile -Force }

Start-Process $TempWsb
Write-Host "[WSB Test] Waiting for result file (timeout 3 min)..."

$Deadline = (Get-Date).AddMinutes(3)
while (-not (Test-Path $ResultFile) -and (Get-Date) -lt $Deadline) {
    Start-Sleep -Seconds 5
    Write-Host "  ...waiting"
}

if (Test-Path $ResultFile) {
    # Find the detailed report written by sandbox-test.bat
    $ReportFile = Get-ChildItem $ResultsDir -Filter "test_*.txt" |
                  Sort-Object LastWriteTime -Descending |
                  Select-Object -First 1
    Write-Host "`n========== WSB TEST RESULTS =========="
    if ($ReportFile) {
        Get-Content $ReportFile.FullName | Write-Host
    } else {
        Write-Host "(no detailed report found)"
    }
    Remove-Item $TempWsb -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "[WSB Test] TIMEOUT — no result file received."
    Write-Host "           Check if Windows Sandbox feature is enabled."
    Write-Host "           Enable via: optionalfeatures.exe -> Windows Sandbox"
}
