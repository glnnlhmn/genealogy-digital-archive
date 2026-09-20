# Genealogy Person Intake Pipeline (GPI) Runbook

## Overview
The Genealogy Person Intake Pipeline (\`tools/ops/gpi.py\`) is an automated 7-stage state machine designed to discover, validate, canonicalize, and commit individual person entities (\`pep-let-*.json\`) into the master person registry (\`data/entities/people.json\`).


## Pipeline Stages

1. **Stage 0: Discovery**
   * Scans the archive root for staged entity fragments matching \`data/entities/pep-let-*.json\`.
2. **Stage 1: Syntax & Schema Validation**
   * Validates each staged JSON record against \`schemas/entities/person.schema.json\` using pre-loaded shared definitions (\`schemas/defs/_shared_definitions.schema.json\`). Invalid records are safely routed to quarantine.
3. **Stage 2: Graph Topology Verification**
   * Ensures every staged entity maintains a connected relationship path back to the primary root node (\`IND-00000\`). Isolated nodes are quarantined.
4. **Stage 3: Deduplication & Drift Detection**
   * Evaluates record fingerprints (\`given | surname | birth_year\`) against the master registry to prevent duplicate ingestion collisions.
5. **Stage 4: Location Canonicalization**
   * Resolves raw birth and death place strings against master location entities (\`data/entities/locations.json\`) and lookup redirects (\`data/indexes/location_index.json\`).
6. **Stage 5: Minting & Reciprocal Linking**
   * Automatically calculates the highest existing master identifier (\`IND-#####\`), assigns permanent canonical IDs to incoming records, and injects reciprocal genealogical links (e.g., \`FATH\` to \`CHIL\`).
7. **Stage 6: Atomic Commit & Cleanup**
   * Generates a pre-execution backup in \`backups/\`, atomically rewrites \`data/entities/people.json\` with updated registry metadata, and unlinks successfully processed staging files.


## Command-Line Interface (CLI)

Execute operations from the archive root via PowerShell using the virtual environment:

### Ingestion Execution (\`--append\`)
Processes all valid staged pep-lets, merges them into the master registry, creates an atomic backup, and cleans up staging files:
```powershell
python tools/ops/gpi.py --append
```

### Verbose Diagnostic Logging (\`--verbose\`)
Emits itemized record-level diagnostic logs to the session output and writes detailed execution traces to \`logs/gpi-[timestamp].log\`:
```powershell
python tools/ops/gpi.py --append --verbose
```

### Quarantine Restoration (\`--restore\`)
Recovers all quarantined files from the quarantine buffer back to \`data/entities/\` for re-evaluation and correction:
```powershell
python tools/ops/gpi.py --restore
```

---

## Error Handling & Quarantine

* **Quarantine Buffer:** Unverified, malformed, or topologically invalid files are safely copied to \`data/entities/Quarantine\` and removed from staging.
* **Cross-Drive Compatibility:** File movements utilize safe copy-and-unlink routines to prevent cross-volume system exceptions (\`WinError 17\`) between temporary environments and virtual drives.

---

## 5. Testing Architecture & Validation Standards
Automated test suites ensure pipeline integrity, schema conformity, and regression safety across all ingestion modules. All unit and integration tests reside in \`tools/tests/\` and are executed via \`pytest\` within the active virtual environment. Test fixtures must mock archive states cleanly without mutating production datasets under \`data/\`. When modifying pipeline logic or staging operations, developers must run the full test suite to verify that syntax validation, topological graph tracing, and deduplication logic pass successfully before committing operational changes.
'''

target = Path("docs/tools/gpi.md")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(content, encoding="utf-8")
print(f"Successfully generated {target}")
"@