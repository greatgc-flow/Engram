param (
    [string]$PlanPath
)
$ErrorActionPreference = "Stop"

$Plan = Get-Content $PlanPath | ConvertFrom-Json
$JournalPath = $Plan.journal_path
$ParentPID = $Plan.parent_pid
$StagedDir = $Plan.staged_dir
$TargetDir = $Plan.target_dir
$BackupDir = $Plan.backup_dir

try {
    $parent = Get-Process -Id $ParentPID -ErrorAction SilentlyContinue
    if ($parent) {
        $parent.WaitForExit()
    }
} catch {
}

function Write-Journal {
    param([string]$Status)
    $journal = @{ status = $Status }
    $journal | ConvertTo-Json | Set-Content -Path $JournalPath -Encoding UTF8
}

Write-Journal "IN_PROGRESS"

try {
    New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
    
    $StagedFiles = Get-ChildItem -Path $StagedDir -Recurse -File
    foreach ($File in $StagedFiles) {
        $RelPath = $File.FullName.Substring($StagedDir.Length + 1)
        $TargetPath = Join-Path $TargetDir $RelPath
        if (Test-Path $TargetPath) {
            $BackupFilePath = Join-Path $BackupDir $RelPath
            $BackupFileDir = Split-Path $BackupFilePath
            if (-not (Test-Path $BackupFileDir)) {
                New-Item -ItemType Directory -Force -Path $BackupFileDir | Out-Null
            }
            Copy-Item -Path $TargetPath -Destination $BackupFilePath -Force
        }
    }
    
    $EngramExe = Join-Path $TargetDir "Engram.exe"
    if (Test-Path $EngramExe) {
        Rename-Item -Path $EngramExe -NewName "Engram.exe.old" -Force
    }
    
    Copy-Item -Path "$StagedDir\*" -Destination $TargetDir -Recurse -Force
    
    Write-Journal "COMPLETED"
} catch {
    Write-Journal "FAILED_ROLLED_BACK"
    
    $EngramExeOld = Join-Path $TargetDir "Engram.exe.old"
    $EngramExe = Join-Path $TargetDir "Engram.exe"
    if (Test-Path $EngramExeOld) {
        Move-Item -Path $EngramExeOld -Destination $EngramExe -Force
    }
    
    if (Test-Path $BackupDir) {
        Copy-Item -Path "$BackupDir\*" -Destination $TargetDir -Recurse -Force
    }
    
    exit 1
}
exit 0
