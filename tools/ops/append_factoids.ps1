# Name: append_factoids.ps1
# Path: auto\op_tools\append_factoids.ps1

[CmdletBinding()]
param (
    [Parameter(Mandatory = $false)]
    [switch]$help
)

if ($help) {
    Write-Host @"
NAME:
    append_factoids.ps1

SYNOPSIS:
    Merges incoming factoids into the master archive facts entity dataset.

SYNTAX:
    .\append_factoids.ps1 [-help] [-Debug] [-Verbose]

DESCRIPTION:
    Processes data\entities\factoids.json, validates that it contains records,
    reads data\entities\facts.json, de-duplicates incoming records by fact_id,
    and writes the consolidated payload to data\entities\facts-combined.json.
    Prompts for confirmation if the destination file already exists.

PARAMETERS:
    -help       Displays syntax and usage information, then exits.
    -Debug      Built-in switch: outputs runtime diagnostics directly to the console.
    -Verbose    Built-in switch: writes structured execution traces to gtemp\append_factoids-[timestamp].log.
"@
    exit 0
}

$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = Split-Path -Parent $scriptPath
$projectRoot = (Resolve-Path (Join-Path -Path $scriptDir -ChildPath "..\..")).Path

$entitiesDir = Join-Path -Path $projectRoot -ChildPath "data\entities"
$gtempDir = Join-Path -Path $projectRoot -ChildPath "gtemp"

$incomingFactsFile = Join-Path -Path $entitiesDir -ChildPath "factoids.json"
$masterFactsFile = Join-Path -Path $entitiesDir -ChildPath "facts.json"
$outputFile = Join-Path -Path $entitiesDir -ChildPath "facts-combined.json"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path -Path $gtempDir -ChildPath "append_factoids-$timestamp.log"

$isDebug   = $PSBoundParameters.ContainsKey('Debug') -or ($DebugPreference -ne 'SilentlyContinue')
$isVerbose = $PSBoundParameters.ContainsKey('Verbose') -or ($VerbosePreference -ne 'SilentlyContinue')

function Write-TraceLog {
    param ([string]$Message, [string]$Level = "INFO")
    $logEntry = "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] [$Level] $Message"
    if ($isDebug) {
        Write-Host $logEntry -ForegroundColor Cyan
    }
    if ($isVerbose) {
        if (-not (Test-Path -LiteralPath $gtempDir)) {
            New-Item -ItemType Directory -Path $gtempDir -Force | Out-Null
        }
        $logEntry | Out-File -LiteralPath $logFile -Append -Encoding UTF8
    }
}

Write-TraceLog "Starting append_factoids execution." "INFO"
Write-Host "=== Archive Tool: Append Factoids ===" -ForegroundColor Cyan

# 1. Resolve & Process Incoming Facts First
if (-not (Test-Path -LiteralPath $incomingFactsFile)) {
    Write-Error "[CRITICAL ERROR] Incoming facts file not found at: $incomingFactsFile"
    Write-TraceLog "Incoming facts file missing: $incomingFactsFile" "CRITICAL"
    exit 1
}

Write-TraceLog "Reading incoming facts from: $incomingFactsFile" "INFO"
$incomingData = Get-Content -LiteralPath $incomingFactsFile -Raw -Encoding UTF8 | ConvertFrom-Json
$incomingFacts = if ($incomingData.facts) { @($incomingData.facts) } else { @() }

if ($incomingFacts.Count -eq 0) {
    Write-Warning "[STOP] The incoming facts file ($incomingFactsFile) is empty. Processing halted."
    Write-TraceLog "Incoming facts count is 0. Halting process." "WARN"
    exit 0
}

$incomingTotal = $incomingFacts.Count
Write-Host "Incoming Facts : $incomingFactsFile ($incomingTotal records)" -ForegroundColor Yellow
Write-TraceLog "Incoming facts loaded: $incomingTotal records." "INFO"

# 2. Resolve Master Facts File
if (-not (Test-Path -LiteralPath $masterFactsFile)) {
    Write-Error "[CRITICAL ERROR] Master facts file not found at: $masterFactsFile"
    Write-TraceLog "Master facts file missing: $masterFactsFile" "CRITICAL"
    exit 1
}

Write-TraceLog "Reading master facts from: $masterFactsFile" "INFO"
$masterData = Get-Content -LiteralPath $masterFactsFile -Raw -Encoding UTF8 | ConvertFrom-Json
$masterFacts = if ($masterData.facts) { @($masterData.facts) } else { @() }
$masterTotal = $masterFacts.Count
Write-Host "Master Facts   : $masterFactsFile ($masterTotal records)" -ForegroundColor Yellow
Write-TraceLog "Master facts loaded: $masterTotal records." "INFO"

# 3. Check Existing Output Destination
if (Test-Path -LiteralPath $outputFile) {
    Write-Host "`nTarget file already exists: $outputFile" -ForegroundColor Magenta
    $promptChoice = Read-Host "Do you want to replace it or cancel? (Enter 'Y' to replace, 'N' to cancel)"
    if ($promptChoice -notmatch '^[Yy]$') {
        Write-Host "Operation cancelled by user. Existing file was not modified." -ForegroundColor Yellow
        Write-TraceLog "Operation cancelled by user at overwrite prompt." "WARN"
        exit 0
    }
    Write-TraceLog "User confirmed overwrite of existing destination file." "INFO"
}

# 4. Ingest Master Records & De-duplicate
$existingFactIds = @{}
$combinedFactList = @()

foreach ($fact in $masterFacts) {
    if (-not $existingFactIds.ContainsKey($fact.fact_id)) {
        $existingFactIds[$fact.fact_id] = $true
        $combinedFactList += $fact
    }
}
Write-TraceLog "Ingested $($combinedFactList.Count) master records into lookup table." "INFO"

# 5. Evaluate Incoming Facts
$appendedCount = 0
$duplicateCount = 0

foreach ($newFact in $incomingFacts) {
    if (-not $existingFactIds.ContainsKey($newFact.fact_id)) {
        $existingFactIds[$newFact.fact_id] = $true
        $combinedFactList += $newFact
        $appendedCount++
    } else {
        $duplicateCount++
    }
}

Write-TraceLog "Merge complete. Clean appended: $appendedCount, Duplicates skipped: $duplicateCount" "INFO"

# 6. Package Entity Container
$combinedContainer = [ordered]@{
    '$schema' = "schemas\entities\fact.schema.json"
    schema_version = "1.0.0"
    generated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    total_facts = $combinedFactList.Count
    facts = $combinedFactList
}

# 7. Write to Destination
$outputDir = Split-Path -Parent $outputFile
if (-not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$combinedContainer | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $outputFile -Encoding UTF8

if (-not (Test-Path -LiteralPath $outputFile)) {
    Write-Error "[CRITICAL ERROR] Failed to verify created output file at: $outputFile"
    Write-TraceLog "Verification failed for: $outputFile" "CRITICAL"
    exit 1
}

# 8. Output Results Summary
Write-Host "`n=== Operation Results Summary ===" -ForegroundColor Green
Write-Host "  Initial Master Facts : $masterTotal" -ForegroundColor Cyan
Write-Host "  Incoming Evaluated   : $incomingTotal" -ForegroundColor Cyan
Write-Host "  Clean Facts Appended : $appendedCount" -ForegroundColor Cyan
Write-Host "  Duplicates Skipped   : $duplicateCount" -ForegroundColor Yellow
Write-Host "  Total Output Records : $($combinedFactList.Count)" -ForegroundColor Green
Write-Host "  Written to           : $outputFile" -ForegroundColor Green

Write-TraceLog "append_factoids execution completed successfully. Output count: $($combinedFactList.Count)" "INFO"