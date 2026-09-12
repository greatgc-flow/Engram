param(
    [Parameter(Mandatory=$true)]
    [string]$PlanPath
)

$ErrorActionPreference = "Continue"

if (-not (Test-Path -LiteralPath $PlanPath)) {
    Write-Error "Plan file not found: $PlanPath"
    exit 1
}

$plan = Get-Content -LiteralPath $PlanPath -Raw -Encoding utf8 | ConvertFrom-Json
$journalPath = $plan.journal_path
$parentPid = $plan.parent_pid
$targets = $plan.targets
$baseDir = $plan.base_dir
$sysDir = $plan.sys_dir

function Update-Journal {
    param(
        [string]$Status,
        [string]$Step,
        [bool]$ErrorRecoverable = $false,
        [string[]]$Remaining = @()
    )
    if (Test-Path -LiteralPath $journalPath) {
        try {
            $j = Get-Content -LiteralPath $journalPath -Raw -Encoding utf8 | ConvertFrom-Json
            $j.status = $Status
            if ($Step -and ($j.steps -notcontains $Step)) {
                $j.steps += $Step
            }
            if ($ErrorRecoverable) {
                $j.error_recoverable = $true
            }
            if ($Remaining.Count -gt 0) {
                $j | Add-Member -NotePropertyName "remaining_targets" -NotePropertyValue $Remaining -Force
            }
            $jsonStr = $j | ConvertTo-Json -Depth 10
            $utf8NoBom = New-Object System.Text.UTF8Encoding $false
            [System.IO.File]::WriteAllText($journalPath, $jsonStr, $utf8NoBom)
        } catch {
            Write-Warning "Failed to update journal: $_"
        }
    }
}

# 1. Wait for parent process (30s timeout -> FAILED_FATAL)
if ($parentPid) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt 30) {
        $p = Get-Process -Id $parentPid -ErrorAction SilentlyContinue
        if (-not $p) { break }
        Start-Sleep -Milliseconds 500
    }
    $p = Get-Process -Id $parentPid -ErrorAction SilentlyContinue
    if ($p) {
        Update-Journal -Status "FAILED_FATAL" -Step "directory_purge_timeout"
        exit 1
    }
}

# 2. Re-run link guard and remove targets
$skippedTargets = @()
foreach ($target in $targets) {
    if (-not (Test-Path -LiteralPath $target)) {
        continue
    }

    # Check if target itself or anything under it is a ReparsePoint
    $hasReparse = $false
    try {
        $item = Get-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
        if ($item -and ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            $hasReparse = $true
        } elseif (Test-Path -LiteralPath $target -PathType Container) {
            $reparseItems = Get-ChildItem -LiteralPath $target -Recurse -Force -Attributes ReparsePoint -ErrorAction SilentlyContinue
            if ($reparseItems) {
                $hasReparse = $true
            }
        }
    } catch {
        # Ignore access or inspection errors
    }

    if ($hasReparse) {
        Write-Warning "Skipping target containing reparse point: $target"
        $skippedTargets += $target
        continue
    }

    try {
        Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Warning "Failed to remove target $target : $_"
    }
}

# 3. Prune empty directories under sys_dir bottom-up
if ($sysDir -and (Test-Path -LiteralPath $sysDir -PathType Container)) {
    Get-ChildItem -LiteralPath $sysDir -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Sort-Object -Property { $_.FullName.Length } -Descending |
        ForEach-Object {
            $sub = $_.FullName
            if ((Get-ChildItem -LiteralPath $sub -Force -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
                Remove-Item -LiteralPath $sub -Force -ErrorAction SilentlyContinue
            }
        }
    if ((Get-ChildItem -LiteralPath $sysDir -Force -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
        Remove-Item -LiteralPath $sysDir -Force -ErrorAction SilentlyContinue
    }
}

# 4. Remove base_dir only if it is completely empty
if ($baseDir -and (Test-Path -LiteralPath $baseDir -PathType Container)) {
    if ((Get-ChildItem -LiteralPath $baseDir -Force -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
        Remove-Item -LiteralPath $baseDir -Force -ErrorAction SilentlyContinue
    }
}

# 5. Check remaining targets and update journal
$remaining = @()
foreach ($target in $targets) {
    if (Test-Path -LiteralPath $target) {
        $remaining += $target
    }
}

if ($remaining.Count -eq 0 -and $skippedTargets.Count -eq 0) {
    Update-Journal -Status "COMPLETED" -Step "directory_purge"
    exit 0
} else {
    $allRemaining = @($remaining) + @($skippedTargets)
    Update-Journal -Status "FAILED_RECOVERABLE" -Step "directory_purge" -ErrorRecoverable $true -Remaining $allRemaining
    exit 1
}
