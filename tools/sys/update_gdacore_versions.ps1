# Name: update_gdacore_versions.ps1
# Path: tools/sys/update_gdacore_versions.ps1
# Version: 1.0.0+build.20261013.1
# Description: Batch synchronizes lines 1-15 file headers, in-module __version__ assignments,
#              and pyproject.toml manifests across tools/lib/gdacore to a target version.

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Position = 0)]
    [string]$TargetVersion = "1.0.0+build.rc1",

    [Parameter(Position = 1)]
    [string]$CorePath = "tools/lib/gdacore",

    [switch]$DryRun
)

$resolvedPath = Resolve-Path$CorePath -ErrorAction Stop

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " GDA Core Library Version Updater: $resolvedPath" -ForegroundColor Cyan
Write-Host " Target Version: $TargetVersion" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host " Mode: DRY RUN (No files will be modified)" -ForegroundColor Yellow
}
Write-Host "================================================================================" -ForegroundColor Cyan

$pyFiles = Get-ChildItem -Path$resolvedPath -Filter "*.py" -Recurse -File | 
    Where-Object { $_.FullName -notmatch "(\.venv|__pycache__|\.pytest_cache)" }

$updatedCount = 0$matchedCount = 0

foreach ($file in$pyFiles) {
    $rawContent = Get-Content -Path$file.FullName -Raw -Encoding utf8 -ErrorAction Stop
    $originalContent =$rawContent
    $relPath = Resolve-Path -Path$file.FullName -Relative

    # 1. Update lines 1-15 top metadata comment '# Version: ...'
    $rawContent = $rawContent -replace '(?m)^#\s*Version:\s*[^\r\n]+', "# Version: $TargetVersion"

    # 2. Update code __version__ assignment if present
    if ($rawContent -match '(?m)^__version__\s*=\s*["''][^"'']+["'']') {
        $rawContent =$rawContent -replace '(?m)^__version__\s*=\s*["''][^"'']+["'']', "__version__ = `"$TargetVersion`""
    }

    if ($rawContent -ne $originalContent) {$matchedCount++
        if (-not $DryRun) {
            Set-Content -Path $file.FullName -Value$rawContent -Encoding utf8 -NoNewline
            Write-Host " [UPDATED] $relPath" -ForegroundColor Green
            $updatedCount++
        } else {
            Write-Host " [WOULD UPDATE] $relPath" -ForegroundColor Yellow
        }
    } else {
        Write-Host " [UNCHANGED] $relPath" -ForegroundColor DarkGray
    }
}

# 3. Synchronize tools/lib/gdacore/pyproject.toml manifest
$tomlFile = Join-Path$resolvedPath "pyproject.toml"
if (Test-Path $tomlFile) {
    $tomlContent = Get-Content -Path$tomlFile -Raw -Encoding utf8 -ErrorAction Stop
    $originalToml =$tomlContent
    $relToml = Resolve-Path -Path$tomlFile -Relative

    # Update top comment header version if present
    $tomlContent = $tomlContent -replace '(?m)^#\s*Version:\s*[^\r\n]+', "# Version: $TargetVersion"

    # Extract base version without PEP 440 local build tag for package metadata
    $manifestVersion = ($TargetVersion -split '\+')[0]
    $tomlContent =$tomlContent -replace '(?m)^\s*version\s*=\s*["''][^"'']+["'']', "version = `"$manifestVersion`""

    if ($tomlContent -ne $originalToml) {$matchedCount++
        if (-not $DryRun) {
            Set-Content -Path $tomlFile -Value$tomlContent -Encoding utf8 -NoNewline
            Write-Host " [UPDATED] $relToml (version = `"$manifestVersion`")" -ForegroundColor Green
            $updatedCount++
        } else {
            Write-Host " [WOULD UPDATE] $relToml" -ForegroundColor Yellow
        }
    } else {
        Write-Host " [UNCHANGED] $relToml" -ForegroundColor DarkGray
    }
}

Write-Host "--------------------------------------------------------------------------------" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "Dry run complete: $matchedCount items would be synchronized to '$TargetVersion'." -ForegroundColor Yellow
} else {
    Write-Host "Completed: $updatedCount of$matchedCount modified files written successfully." -ForegroundColor Green
}
Write-Host "================================================================================" -ForegroundColor Cyan