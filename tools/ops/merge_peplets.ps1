# Name: merge_peplets.ps1
# Path: auto\op_tools\merge_peplets.ps1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [switch]$run,

    [Parameter(Mandatory = $false)]
    [switch]$help
)

#Requires -Version 7.0
$ErrorActionPreference = "Stop"

if ($help) {
    Write-Host @"
NAME:
    merge_peplets.ps1

SYNOPSIS:
    Reconciles and aggregates staged pep-let files into a combined staging container.

SYNTAX:
    .\merge_peplets.ps1 [-run] [-help] [-Debug] [-Verbose]

DESCRIPTION:
    Reads canonical ID baselines from data\entities\people.json strictly as read-only context.
    Collects all staged data\entities\pep-let-*.json files, maps temporary identifiers to
    sequential canonical IND-##### IDs, translates internal relationship pointers, and
    compiles records into data\entities\peplets.json. Prompts for confirmation if the
    output file exists, and purges source pep-lets only when -run is supplied.

PARAMETERS:
    -run        Executes the commit to peplets.json and purges staged pep-lets. Defaults to dry-run.
    -help       Displays this usage menu and exits.
    -Debug      Outputs real-time diagnostics and execution traces directly to the console.
    -Verbose    Writes timestamped execution telemetry to gtemp\merge_peplets-[timestamp].log.
"@
    exit 0
}

$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = Split-Path -Parent $scriptPath
$projectRoot = (Resolve-Path (Join-Path -Path $scriptDir -ChildPath "..\..")).Path

$entitiesDir = Join-Path -Path $projectRoot -ChildPath "data\entities"
$gtempDir = Join-Path -Path $projectRoot -ChildPath "gtemp"

$peopleFilePath = Join-Path -Path $entitiesDir -ChildPath "people.json"
$outputFilePath = Join-Path -Path $entitiesDir -ChildPath "peplets.json"
$stagingPattern = "pep-let-*.json"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path -Path $gtempDir -ChildPath "merge_peplets-$timestamp.log"

$isDebug   = $PSBoundParameters.ContainsKey('Debug') -or ($DebugPreference -ne 'SilentlyContinue')
$isVerbose = $PSBoundParameters.ContainsKey('Verbose') -or ($VerbosePreference -ne 'SilentlyContinue')

function Write-TraceLog {
    param([string]$Message, [string]$Level = "INFO")
    $logEntry = "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] [$Level] $Message"

    if ($isDebug -or $Level -in @("ERROR", "WARNING", "SUCCESS")) {
        switch ($Level) {
            "ERROR"   { Write-Host $logEntry -ForegroundColor Red }
            "WARNING" { Write-Host $logEntry -ForegroundColor Yellow }
            "SUCCESS" { Write-Host $logEntry -ForegroundColor Green }
            "DEBUG"   { Write-Host $logEntry -ForegroundColor Cyan }
            default   { Write-Host $logEntry -ForegroundColor DarkGray }
        }
    }

    if ($isVerbose) {
        if (-not (Test-Path -LiteralPath $gtempDir)) {
            New-Item -ItemType Directory -Path $gtempDir -Force | Out-Null
        }
        $logEntry | Out-File -LiteralPath $logFile -Append -Encoding UTF8
    }
}

Write-TraceLog "Starting pep-let aggregation process." "INFO"
Write-Host "=== Archive Tool: Merge Pep-lets ===" -ForegroundColor Cyan

# 1. Inspect Master Registry (Read-Only Baseline)
if (-not (Test-Path -LiteralPath $peopleFilePath)) {
    Write-Error "[CRITICAL ERROR] Canonical people registry not found at: $peopleFilePath"
    Write-TraceLog "Canonical people registry missing: $peopleFilePath" "ERROR"
    exit 1
}

try {
    $peopleRaw = Get-Content -LiteralPath $peopleFilePath -Raw -Encoding UTF8
    $peopleData = ConvertFrom-Json -InputObject $peopleRaw -Depth 100
} catch {
    Write-Error "[CRITICAL ERROR] Failed to parse JSON in $peopleFilePath : $_"
    Write-TraceLog "Registry parse failure: $_" "ERROR"
    exit 1
}

$maxId = -1
foreach ($person in $peopleData.persons) {
    if ($person.person_id -match '^IND-(\d+)$') {
        $idNum = [int]$matches[1]
        if ($idNum -gt $maxId) {
            $maxId = $idNum
        }
    }
}
Write-TraceLog "Established highest canonical ID index from master: $maxId" "DEBUG"

# 2. Discover Staged pep-let Files
$stagingFiles = Get-ChildItem -LiteralPath $entitiesDir -Filter $stagingPattern | Sort-Object Name
if ($null -eq $stagingFiles -or $stagingFiles.Count -eq 0) {
    Write-Warning "[STOP] No staged pep-let files found in $entitiesDir matching $stagingPattern."
    Write-TraceLog "No staging files found. Halting execution." "WARNING"
    exit 0
}

Write-TraceLog "Found $($stagingFiles.Count) staged pep-let file(s) for aggregation." "INFO"

# 3. Interactive Overwrite Guard
if (Test-Path -LiteralPath $outputFilePath) {
    Write-Host "`nTarget file already exists: $outputFilePath" -ForegroundColor Magenta
    $promptChoice = Read-Host "Do you want to replace it or cancel? (Enter 'Y' to replace, 'N' to cancel)"
    if ($promptChoice -notmatch '^[Yy]$') {
        Write-Host "Operation cancelled by user. Existing file was not modified." -ForegroundColor Yellow
        Write-TraceLog "Operation cancelled by user at overwrite prompt." "WARN"
        exit 0
    }
    Write-TraceLog "User confirmed overwrite of existing destination file: $outputFilePath" "INFO"
}

# 4. Map Staged Records to Sequential Canonical IDs
$stagedRecords = [System.Collections.Generic.List[psobject]]::new()
$tempToCanonical = @{}
$nextIdNum = $maxId + 1

foreach ($file in $stagingFiles) {
    try {
        $rawContent = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
        $parsed = ConvertFrom-Json -InputObject $rawContent -Depth 100

        $tempId = $parsed.temporary_person_id
        if ([string]::IsNullOrWhiteSpace($tempId)) {
            $tempId = $parsed.staging_id
        }
        if ([string]::IsNullOrWhiteSpace($tempId)) {
            $tempId = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
        }

        $canonicalId = "IND-{0:D5}" -f $nextIdNum
        $tempToCanonical[$tempId] = $canonicalId
        $nextIdNum++

        $parsed | Add-Member -NotePropertyName "_target_canonical_id" -NotePropertyValue $canonicalId -Force
        $parsed | Add-Member -NotePropertyName "_filepath" -NotePropertyValue $file.FullName -Force
        $stagedRecords.Add($parsed)

        Write-TraceLog "Mapped [$tempId] ($($parsed.canonical_name)) -> $canonicalId" "DEBUG"
    } catch {
        Write-Error "[CRITICAL ERROR] Error reading staging file $($file.FullName): $_"
        Write-TraceLog "Failed reading $($file.FullName): $_" "ERROR"
        exit 1
    }
}

# 5. Translate Relationship Pointers
$newCanonicalPersons = [System.Collections.Generic.List[psobject]]::new()

foreach ($rec in $stagedRecords) {
    $cid = $rec._target_canonical_id
    $rel = $rec.relationships

    $fatherId = $rel.father_id
    if ($fatherId -and $tempToCanonical.ContainsKey($fatherId)) {
        $fatherId = $tempToCanonical[$fatherId]
    }

    $motherId = $rel.mother_id
    if ($motherId -and $tempToCanonical.ContainsKey($motherId)) {
        $motherId = $tempToCanonical[$motherId]
    }

    $translatedSpouses = [System.Collections.Generic.List[string]]::new()
    if ($rel.spouse_ids) {
        foreach ($s in $rel.spouse_ids) {
            if ($tempToCanonical.ContainsKey($s)) {
                $translatedSpouses.Add($tempToCanonical[$s])
            } else {
                $translatedSpouses.Add($s)
            }
        }
    }

    $translatedChildren = [System.Collections.Generic.List[string]]::new()
    if ($rel.child_ids) {
        foreach ($c in $rel.child_ids) {
            if ($tempToCanonical.ContainsKey($c)) {
                $translatedChildren.Add($tempToCanonical[$c])
            } else {
                $translatedChildren.Add($c)
            }
        }
    }

    $cleanPerson = [ordered]@{
        person_id      = $cid
        canonical_name = $rec.canonical_name
        sex            = if ($rec.sex) { $rec.sex } else { "U" }
        names          = if ($rec.names) { $rec.names } else { [PSCustomObject]@{ given = ""; middle = $null; maiden_surname = ""; aliases = @() } }
        relationships  = [ordered]@{
            father_id  = $fatherId
            mother_id  = $motherId
            spouse_ids = @($translatedSpouses)
            child_ids  = @($translatedChildren)
        }
        facts          = @()
        vitals         = if ($rec.vitals) { $rec.vitals } else { [PSCustomObject]@{ birth = [PSCustomObject]@{ date = $null; place = $null }; death = [PSCustomObject]@{ date = $null; place = $null } } }
    }

    $newCanonicalPersons.Add([PSCustomObject]$cleanPerson)
}

# 6. Build peplets.json Entity Container
$pepletsContainer = [ordered]@{
    '$schema'        = "schemas\entities\person.schema.json"
    schema_version  = "1.0.0"
    generated_at    = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    total_records   = $newCanonicalPersons.Count
    persons         = $newCanonicalPersons.ToArray()
}

# 7. Commit vs Dry-Run
if ($run) {
    Write-TraceLog "Writing compiled records to $outputFilePath..." "INFO"
    $pepletsContainer | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $outputFilePath -Encoding UTF8

    if (-not (Test-Path -LiteralPath $outputFilePath)) {
        Write-Error "[CRITICAL ERROR] Failed to verify created output file at: $outputFilePath"
        Write-TraceLog "Verification failed for: $outputFilePath" "ERROR"
        exit 1
    }

    Write-TraceLog "Purging processed staging files..." "INFO"
    foreach ($rec in $stagedRecords) {
        if (Test-Path -LiteralPath $rec._filepath) {
            Remove-Item -LiteralPath $rec._filepath -Force
            Write-TraceLog "Removed: $($rec._filepath)" "DEBUG"
        }
    }

    Write-Host "`n=== Operation Results Summary ===" -ForegroundColor Green
    Write-Host "  Master Reference     : $peopleFilePath (Preserved / Unmodified)" -ForegroundColor Cyan
    Write-Host "  Staged Ingested      : $($newCanonicalPersons.Count)" -ForegroundColor Cyan
    Write-Host "  Staged Files Purged  : $($stagedRecords.Count)" -ForegroundColor Yellow
    Write-Host "  Output Written To    : $outputFilePath" -ForegroundColor Green
} else {
    Write-Host "`n[DRY-RUN MODE] Evaluated $($newCanonicalPersons.Count) staged pep-let file(s) without modifying disk." -ForegroundColor Yellow
    Write-Host "Run with -run to write $outputFilePath and purge staging files." -ForegroundColor Yellow
}

Write-Host "`n--- Identifier Translation Matrix ---" -ForegroundColor Cyan
foreach ($tempId in $tempToCanonical.Keys) {
    Write-Host "  $tempId  -->  $($tempToCanonical[$tempId])" -ForegroundColor Green
}
Write-Host "-------------------------------------`n" -ForegroundColor Cyan

Write-TraceLog "merge_peplets execution finished successfully." "INFO"