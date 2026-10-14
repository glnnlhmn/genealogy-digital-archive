# Name: inspect_gdacore_versions.ps1
# Path: tools/sys/inspect_gdacore_versions.ps1
# Description: Scans tools/lib/gdacore source files, test suites, and pyproject.toml 
#              to audit lines 1-15 header versions, module __version__, and manifest versions.

[CmdletBinding()]
param(
    [string]$CorePath = "tools/lib/gdacore"
)

$resolvedPath = Resolve-Path $CorePath -ErrorAction Stop

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " GDA Core Library Version Auditor: $resolvedPath" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

$results = [System.Collections.Generic.List[PSCustomObject]]::new()

# 1. Inspect Python source and test files in tools/lib/gdacore
$pyFiles = Get-ChildItem -Path $resolvedPath -Filter "*.py" -Recurse -File | 
    Where-Object { $_.FullName -notmatch "(\.venv|__pycache__|\.pytest_cache)" }

foreach ($file in $pyFiles) {
    $headerLines = Get-Content -Path $file.FullName -TotalCount 15 -ErrorAction SilentlyContinue
    $headerVersion = $null
    $codeVersion = $null

    if ($headerLines) {
        foreach ($line in $headerLines) {
            if ($line -match '^\s*#\s*Version:\s*([^\s]+)') {
                $headerVersion = $matches[1]
                break
            }
        }
    }

    $rawContent = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($rawContent -match '__version__\s*=\s*["'']([^"'']+)["'']') {
        $codeVersion = $matches[1]
    }

    $relPath = Resolve-Path -Path $file.FullName -Relative

    $status = if ($headerVersion -and $codeVersion) {
        if ($headerVersion -eq $codeVersion) { "OK" } else { "MISMATCH" }
    } elseif ($headerVersion -or $codeVersion) {
        # Tests legitimately omit module-level __version__ but require header versions
        if ($relPath -match "tests" -and $headerVersion) { "OK" } else { "PARTIAL" }
    } else {
        "MISSING"
    }

    $results.Add([PSCustomObject]@{
        Component     = if ($relPath -match "tests") { "Test Suite" } else { "Source Module" }
        HeaderVersion = if ($headerVersion) { $headerVersion } else { "<none>" }
        CodeVersion   = if ($codeVersion) { $codeVersion } else { "<none>" }
        Status        = $status
        RelativePath  = $relPath
    })
}

# 2. Inspect tools/lib/gdacore/pyproject.toml
$tomlFile = Join-Path $resolvedPath "pyproject.toml"
if (Test-Path $tomlFile) {
    $tomlContent = Get-Content -Path $tomlFile -Raw -ErrorAction SilentlyContinue
    $projVersion = $null
    if ($tomlContent -match '(?m)^\s*version\s*=\s*["'']([^"'']+)["'']') {
        $projVersion = $matches[1]
    }
    
    $headerTomlVer = $null
    $tomlHeaderLines = Get-Content -Path $tomlFile -TotalCount 10 -ErrorAction SilentlyContinue
    foreach ($line in $tomlHeaderLines) {
        if ($line -match '^\s*#\s*Version:\s*([^\s]+)') {
            $headerTomlVer = $matches[1]
            break
        }
    }

    $results.Add([PSCustomObject]@{
        Component     = "Package Manifest"
        HeaderVersion = if ($headerTomlVer) { $headerTomlVer } else { "<none>" }
        CodeVersion   = if ($projVersion) { $projVersion } else { "<none>" }
        Status        = if ($projVersion) { "OK" } else { "MISSING" }
        RelativePath  = Resolve-Path -Path $tomlFile -Relative
    })
}

# Output report table
$results | Sort-Object Component, RelativePath | Format-Table -AutoSize -Property `
    @{Label="Component"; Expression={$_.Component}},
    @{Label="Status"; Expression={
        switch ($_.Status) {
            "OK"       { "  OK  " }
            "MISMATCH" { "! DIFF !" }
            "PARTIAL"  { "? PART ?" }
            "MISSING"  { "- NONE -" }
        }
    }},
    @{Label="Header Version"; Expression={$_.HeaderVersion}},
    @{Label="Code / Manifest"; Expression={$_.CodeVersion}},
    @{Label="Path"; Expression={$_.RelativePath}}

$total = $results.Count
$clean = ($results | Where-Object { $_.Status -eq "OK" }).Count
$issues = ($results | Where-Object { $_.Status -ne "OK" }).Count

Write-Host "--------------------------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Summary for gdacore: $total items audited | Clean: $clean | Warnings/Issues: $issues" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan