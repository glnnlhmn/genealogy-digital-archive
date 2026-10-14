# Name: inspect_gaps.ps1
# Path: tools/sys/inspect_gaps.ps1

$targetPath = "tools/lib/gdadomain/src/gdadomain/facts.py"

if (-not (Test-Path $targetPath)) {
    Write-Error "Target file not found at: $targetPath"
    exit 1
}

$lines = Get-Content -Path $targetPath

$gaps = @(
    @{ Name = "Gap 1: resolve_id RecursionError"; Start = 184; End = 193 },
    @{ Name = "Gap 2: validate_fact_schema assoc is None"; Start = 225; End = 234 },
    @{ Name = "Gap 3: _rebuild_indices apid check"; Start = 241; End = 249 },
    @{ Name = "Gap 4: verify_reciprocal_facts non-dict skip"; Start = 425; End = 432 },
    @{ Name = "Gap 5: add_reciprocal_facts is_recip guard"; Start = 477; End = 484 },
    @{ Name = "Gap 6/7: save clean/dirty guard exit"; Start = 508; End = 518 },
    @{ Name = "Gap 7 alternative: Line 593 area"; Start = 588; End = 598 }
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Inspecting: $targetPath (Total lines: $($lines.Count))" -ForegroundColor Cyan
Write-Host "Header Line 3: $($lines[2])" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

foreach ($g in $gaps) {
    Write-Host "`n--- $($g.Name) (Lines $($g.Start) to $($g.End)) ---" -ForegroundColor Green
    for ($i = $g.Start; $i -le $g.End; $i++) {
        if ($i -le $lines.Count -and $i -ge 1) {
            $lineContent = $lines[$i - 1]
            Write-Host ("{0,4}: {1}" -f $i, $lineContent)
        }
    }
}