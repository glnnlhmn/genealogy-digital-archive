# Name: combine_factoids.ps1
# Path: auto\op_tools\combine_factoids.ps1

[CmdletBinding()]
param (
    [Parameter(Mandatory = $false)]
    [switch]$help
)

if ($help) {
    Write-Host @"
NAME:
    combine_factoids.ps1

SYNOPSIS:
    Aggregates individual factoid staging files into a unified factoids entity container.

SYNTAX:
    .\combine_factoids.ps1 [-help] [-Debug] [-Verbose]

DESCRIPTION:
    Scans data\entities\ for factoid-*.json files, flattens single records or nested fact
    arrays, adds standard entity envelope metadata, and outputs data\entities\factoids.json.
    Prompts for confirmation if the target file already exists.

PARAMETERS:
    -help       Displays syntax and usage information, then exits.
    -Debug      Outputs runtime diagnostics directly to the console.
    -Verbose    Writes structured trace telemetry to gtemp\combine_factoids-[timestamp].log.
"@
    exit 0
}

$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = Split-Path -Parent $scriptPath
$projectRoot = (Resolve-Path (Join-Path -Path $scriptDir -ChildPath "..\..")).Path

$entitiesDir = Join-Path -Path $projectRoot -ChildPath "data\entities"
$gtempDir = Join-Path -Path $projectRoot -ChildPath "gtemp"
$outputFile = Join-Path -Path $entitiesDir -ChildPath "factoids.json"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path -Path $gtempDir -ChildPath "combine_factoids-$timestamp.log"

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

Write-TraceLog "Starting combine_factoids execution." "INFO"
Write-Host "=== Archive Tool: Combine Factoids ===" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $entitiesDir)) {
    Write-Error "[CRITICAL ERROR] Target directory not found: $entitiesDir"
    Write-TraceLog "Target directory missing: $entitiesDir" "CRITICAL"
    exit 1
}

$factoidFiles = Get-ChildItem -LiteralPath $entitiesDir -Filter "factoid-*.json"
Write-TraceLog "Found $($factoidFiles.Count) factoid staging files." "INFO"

if ($factoidFiles.Count -eq 0) {
    Write-Warning "[STOP] No factoid-*.json files found in $entitiesDir."
    Write-TraceLog "No source files found. Halting execution." "WARN"
    exit 0
}

$allFacts = [System.Collections.Generic.List[object]]::new()

foreach ($file in $factoidFiles) {
    try {
        $content = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -ne $content) {
            if ($content.PSObject.Properties['facts']) {
                foreach ($f in @($content.facts)) {
                    $allFacts.Add($f)
                }
            } else {
                $allFacts.Add($content)
            }
            Write-TraceLog "Loaded content from $($file.Name)" "INFO"
        }
    } catch {
        Write-Warning "Failed to parse file: $($file.Name)"
        Write-TraceLog "Failed to parse file: $($file.Name) - $_" "WARN"
    }
}

# Check Existing Output Destination & Prompt
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

# Construct valid entity container adhering to fact.schema.json
$combinedContainer = [ordered]@{
    '$schema'        = "schemas\entities\fact.schema.json"
    schema_version  = "1.0.0"
    generated_at    = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    total_facts     = $allFacts.Count
    facts           = $allFacts.ToArray()
}

$combinedContainer | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $outputFile -Encoding UTF8

if (-not (Test-Path -LiteralPath $outputFile)) {
    Write-Error "[CRITICAL ERROR] Failed to verify combined output file at: $outputFile"
    Write-TraceLog "Verification failed for: $outputFile" "CRITICAL"
    exit 1
}

Write-Host "Successfully combined $($allFacts.Count) factoids from $($factoidFiles.Count) files into: $outputFile" -ForegroundColor Green
Write-TraceLog "combine_factoids execution completed successfully. Output count: $($allFacts.Count)" "INFO"