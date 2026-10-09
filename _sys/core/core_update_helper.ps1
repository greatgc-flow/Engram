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
    if (-not ($Plan.PSObject.Properties['skip_process_wait'] -and $Plan.skip_process_wait -eq $true)) {
        $parent = Get-Process -Id $ParentPID -ErrorAction SilentlyContinue
        if ($parent) {
            $parent.WaitForExit()
        }
    }
} catch {
}

function Get-Sha256 {
    param([string]$FilePath)
    $stream = [System.IO.File]::OpenRead($FilePath)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha.ComputeHash($stream))
    } finally {
        $stream.Dispose()
        $sha.Dispose()
    }
}

function Write-Journal {
    param([string]$Status)
    $journal = @{ status = $Status; created_files = @($CreatedFiles) }
    $journal | ConvertTo-Json | Set-Content -Path $JournalPath -Encoding UTF8
}

$CreatedFiles = @()
$OriginalHashes = @{}
$BackedUpFiles = @()
$ExeRenamed = $false
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
        if (Test-Path -LiteralPath $TargetPath -PathType Container) {
            throw "Candidate file conflicts with directory: $TargetRelPath"
        }
        if (Test-Path -LiteralPath $TargetPath -PathType Leaf) {
            $OriginalHashes[$TargetRelPath] = (Get-Sha256 $TargetPath)
            $BackupFilePath = Join-Path $BackupDir $TargetRelPath
            $BackupFileDir = Split-Path $BackupFilePath
            if (-not (Test-Path $BackupFileDir)) {
                New-Item -ItemType Directory -Force -Path $BackupFileDir | Out-Null
            }
            Copy-Item -LiteralPath $TargetPath -Destination $BackupFilePath -Force
            $BackedUpFiles += $TargetRelPath
        } else {
            $CreatedFiles += $TargetRelPath
        }
    }
    
    Write-Journal "IN_PROGRESS"
    $EngramExe = Join-Path $TargetDir "Engram.exe"
    if (Test-Path $EngramExe) {
        Rename-Item -Path $EngramExe -NewName "Engram.exe.old" -Force
        $ExeRenamed = $true
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
    Write-Journal "ROLLBACK_IN_PROGRESS"
    try {
        foreach ($RelPath in $CreatedFiles) {
            $CreatedPath = Join-Path $TargetDir $RelPath
            if (Test-Path -LiteralPath $CreatedPath -PathType Leaf) {
                Remove-Item -LiteralPath $CreatedPath -Force
            }
        }
        if ($ExeRenamed) {
            Move-Item -LiteralPath (Join-Path $TargetDir "Engram.exe.old") -Destination (Join-Path $TargetDir "Engram.exe") -Force
        }
        foreach ($RelPath in $BackedUpFiles) {
            Copy-Item -LiteralPath (Join-Path $BackupDir $RelPath) -Destination (Join-Path $TargetDir $RelPath) -Force
        }
        foreach ($RelPath in $OriginalHashes.Keys) {
            $Restored = Join-Path $TargetDir $RelPath
            if (-not (Test-Path -LiteralPath $Restored -PathType Leaf) -or
                (Get-Sha256 $Restored) -ne $OriginalHashes[$RelPath]) {
                throw "Rollback verification failed: $RelPath"
            }
        }
        foreach ($RelPath in $CreatedFiles) {
            if (Test-Path -LiteralPath (Join-Path $TargetDir $RelPath)) {
                throw "Rollback left candidate file: $RelPath"
            }
        }
        Write-Journal "FAILED_ROLLED_BACK"
    } catch {
        Write-Journal "FAILED_ROLLBACK_FAILED"
    }
    exit 1
}
exit 0
