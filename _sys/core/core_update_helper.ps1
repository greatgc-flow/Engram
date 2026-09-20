param (
    [string]$PlanPath,
    [string]$SysDirName = ""
)
$ErrorActionPreference = "Stop"

$Plan = Get-Content $PlanPath | ConvertFrom-Json
$JournalPath = $Plan.journal_path
$ParentPID = $Plan.parent_pid
$StagedDir = $Plan.staged_dir
$TargetDir = $Plan.target_dir
$BackupDir = $Plan.backup_dir

if (-not $SysDirName) {
    if ($Plan.PSObject.Properties['sys_dir_name'] -and $Plan.sys_dir_name) {
        $SysDirName = $Plan.sys_dir_name
    } else {
        $SysDirName = "_sys"
    }
}
$SysDirName = $SysDirName.TrimEnd('\', '/')

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
        if ($SysDirName -ne "_sys" -and ($RelPath -like "_sys\*" -or $RelPath -like "_sys/*")) {
            $TargetRelPath = $SysDirName + $RelPath.Substring(4)
        } else {
            $TargetRelPath = $RelPath
        }
        $TargetPath = Join-Path $TargetDir $TargetRelPath
        if (Test-Path $TargetPath) {
            $BackupFilePath = Join-Path $BackupDir $TargetRelPath
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
    
    if ($SysDirName -ne "_sys") {
        Get-ChildItem -Path $StagedDir | Where-Object { $_.Name -ne "_sys" } | ForEach-Object {
            if ($_.PSIsContainer) {
                $destSubDir = Join-Path $TargetDir $_.Name
                if (-not (Test-Path $destSubDir)) {
                    New-Item -ItemType Directory -Force -Path $destSubDir | Out-Null
                }
                Copy-Item -Path (Join-Path $_.FullName "*") -Destination $destSubDir -Recurse -Force
            } else {
                Copy-Item -Path $_.FullName -Destination $TargetDir -Force
            }
        }
        $StagedSys = Join-Path $StagedDir "_sys"
        if (Test-Path $StagedSys) {
            $TargetSys = Join-Path $TargetDir $SysDirName
            if (-not (Test-Path $TargetSys)) {
                New-Item -ItemType Directory -Force -Path $TargetSys | Out-Null
            }
            Copy-Item -Path "$StagedSys\*" -Destination $TargetSys -Recurse -Force
        }
    } else {
        Copy-Item -Path "$StagedDir\*" -Destination $TargetDir -Recurse -Force
    }
    
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
