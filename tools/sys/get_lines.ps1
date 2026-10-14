# Name: get_lines.ps1
# Path: tools/sys/get_lines.ps1
# Version: 1.0.0+build.rc1

<#
.SYNOPSIS
    Outputs numbered source code lines from a target file.
.DESCRIPTION
    Utility to display line-numbered slices of any repository file on disk.
    Enables immediate diagnosis of branch coverage gaps and line-specific defects.
.PARAMETER FilePath
    Path to the file to inspect.
.PARAMETER StartLine
    1-based starting line number (default: 1).
.PARAMETER EndLine
    1-based ending line number (default: StartLine + 25).
.PARAMETER Context
    Optional line number to center around with +/- 10 lines of context.
.EXAMPLE
    .\tools\sys\get_lines.ps1 -FilePath "tools/lib/gdaschema/src/gdaschema/schema_util.py" -StartLine 90 -EndLine 115
.EXAMPLE
    .\tools\sys\get_lines.ps1 -FilePath "tools/lib/gdaschema/src/gdaschema/schema_util.py" -Context 102
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$FilePath,

    [Parameter(Position = 1)]
    [int]$StartLine = 1,

    [Parameter(Position = 2)]
    [int]$EndLine = 0,

    [Parameter()]
    [int]$Context = 0
)

$targetPath = Resolve-Path -Path $FilePath -ErrorAction SilentlyContinue
if (-not $targetPath -or -not (Test-Path $targetPath)) {
    Write-Error "Target file not found: $FilePath"
    exit 1
}

$allLines = Get-Content -Path $targetPath -Encoding UTF8
$totalLines = $allLines.Count

if ($Context -gt 0) {
    $StartLine = [Math]::Max(1, $Context - 10)
    $EndLine = [Math]::Min($totalLines, $Context + 10)
} else {
    if ($EndLine -le 0) {
        $EndLine = [Math]::Min($totalLines, $StartLine + 25)
    }
}

$StartLine = [Math]::Max(1, $StartLine)
$EndLine = [Math]::Min($totalLines, $EndLine)

Write-Host "--- File: $FilePath (Lines $StartLine to $EndLine of $totalLines) ---" -ForegroundColor Cyan

for ($idx = $StartLine; $idx -le $EndLine; $idx++) {
    $lineContent = $allLines[$idx - 1]
    if ($Context -gt 0 -and $idx -eq $Context) {
        Write-Host ("{0,5}: {1}" -f $idx, $lineContent) -ForegroundColor Yellow
    } else {
        Write-Host ("{0,5}: {1}" -f $idx, $lineContent)
    }
}