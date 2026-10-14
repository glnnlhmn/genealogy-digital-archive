# Name: inspect_versions.ps1
# Path: tools/sys/inspect_versions.ps1
# Description: Recursively scans Python files, test files, Markdown specifications, 
#              and pyproject.toml manifests to audit header versions and __version__ tokens.

[CmdletBinding()]
param(
    [string]$TargetDir = ".",
    [switch]$MismatchesOnly
)

$targetPath = Resolve-Path $TargetDir
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " GDA Archive Version Auditor: $targetPath" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

$results = [System.Collections.Generic.List[PSCustomObject]]::new()

# 1. Audit Python source and test files
$pyFiles = Get-ChildItem -Path $targetPath -Filter "*.py" -Recurse -File | 
    Where-Object { $_.FullName -notmatch "(\.venv|site-packages|__pycache__|\.pytest_cache|gtemp)" }

foreach ($file in $pyFiles) {
    $content = Get-Content -Path $file.FullName -TotalCount 25 -ErrorAction SilentlyContinue
    $headerVersion = $null
    $codeVersion = $null

    if ($content) {
        # Check lines 1-15 for "# Version: ..."
        foreach ($line in $content) {
            if ($line -match '^\s*#\s*Version:\s*([^\s]+)') {
                $headerVersion = $matches[1]
                break
            }
        }
    }

    # Search entire file for __version__ = "..."
    $fullContent = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($fullContent -match '__version__\s*=\s*["'']([^"'']+)["'']') {
        $codeVersion = $matches[1]
    }

    $relPath = Resolve-Path -Path $file.FullName -Relative

    $status = if ($headerVersion -and $codeVersion) {
        if ($headerVersion -eq $codeVersion) { "OK" } else { "MISMATCH" }
    } elseif ($headerVersion -or $codeVersion) {
        "PARTIAL"
    } else {
        "MISSING"
    }

    $results.Add([PSCustomObject]@{
        FileType      = "Python"
        RelativePath  = $relPath
        HeaderVersion = if ($headerVersion) { $headerVersion } else { "<none>" }
        CodeVersion   = if ($codeVersion) { $codeVersion } else { "<none>" }
        Status        = $status
    })
}

# 2. Audit Markdown specifications in prompts/ and docs/
$mdFiles = Get-ChildItem -Path $targetPath -Filter "*.md" -Recurse -File |
    Where-Object { $_.FullName -match "(prompts|docs)" -and $_.FullName -notmatch "gtemp" }

foreach ($file in $mdFiles) {
    $content = Get-Content -Path $file.FullName -TotalCount 25 -ErrorAction SilentlyContinue
    $headerVersion = $null

    if ($content) {
        foreach ($line in $content) {
            if ($line -match '<!--\s*Version:\s*([^\s]+)\s*-->') {
                $headerVersion = $matches[1]
                break
            }
            if ($line -match '^\s*#\s*Version:\s*([^\s]+)') {
                $headerVersion = $matches[1]
                break
            }
        }
    }

    $relPath = Resolve-Path -Path $file.FullName -Relative
    $results.Add([PSCustomObject]@{
        FileType      = "Markdown"
        RelativePath  = $relPath
        HeaderVersion = if ($headerVersion) { $headerVersion } else { "<none>" }
        CodeVersion   = "N/A"
        Status        = if ($headerVersion) { "OK" } else { "MISSING" }
    })
}

# 3. Audit pyproject.toml manifests
$tomlFiles = Get-ChildItem -Path $targetPath -Filter "pyproject.toml" -Recurse -File |
    Where-Object { $_.FullName -notmatch "gtemp" }

foreach ($file in $tomlFiles) {
    $fullContent = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
    $projVersion = $null

    if ($fullContent -match 'version\s*=\s*["'']([^"'']+)["'']') {
        $projVersion = $matches[1]
    }

    $relPath = Resolve-Path -Path $file.FullName -Relative
    $results.Add([PSCustomObject]@{
        FileType      = "TOML"
        RelativePath  = $relPath
        HeaderVersion = "N/A"
        CodeVersion   = if ($projVersion) { $projVersion } else { "<none>" }
        Status        = if ($projVersion) { "OK" } else { "MISSING" }
    })
}

# Display output
$filtered = if ($MismatchesOnly) {
    $results | Where-Object { $_.Status -ne "OK" }
} else {
    $results
}

$filtered | Sort-Object FileType, RelativePath | Format-Table -AutoSize -Property `
    @{Label="Type"; Expression={$_.FileType}},
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
    @{Label="File Path"; Expression={$_.RelativePath}}

$total = $results.Count
$ok = ($results | Where-Object { $_.Status -eq "OK" }).Count
$diff = ($results | Where-Object { $_.Status -eq "MISMATCH" }).Count
$missing = ($results | Where-Object { $_.Status -eq "MISSING" }).Count

Write-Host "--------------------------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Summary: Total Audited: $total | Clean (OK): $ok | Mismatches: $diff | Untagged: $missing" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan