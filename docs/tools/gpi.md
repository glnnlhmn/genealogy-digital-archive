# Technical Runbook: GPI (Genealogy Person Intake)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `gpi.py` |
| **Script Path** | `tools/ops/gpi.py` |
| **Version** | `1.0.4+build.20260922.2` |
| **Test Suite** | `tests/integration/test_gpi.py` |
| **Log Output** | `logs/gpi-[YYYYMMDD_HHMMSS].log` |
| **Target Registry** | `data/entities/people.json` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
GPI processes staged person entity fragments (`data/entities/pep-let-*.json`) into the master registry (`data/entities/people.json`). It enforces schema validation, verifies graph traversal to root ancestor `IND-00000`, mints sequential IDs, injects reciprocal kinship links, and cleans staging workspaces.

### CLI Syntax
```powershell
python tools/ops/gpi.py [-a] [-r] [-v] [--debug]
```

### Options & Parameter Reference
* `-a, --append`: Executes the full 7-stage intake pipeline, committing valid staged files to `people.json`.
* `-r, --restore`: Recovers all quarantined person files from `data/entities/quarantine/` back to `data/entities/`.
* `-v, --verbose`: Logs detailed record-level diagnostic traces.
* `--debug`: Outputs live execution traces directly to stderr.

### Quick Runbook
Execute intake and commit staged fragments:
```powershell
python tools/ops/gpi.py --append
```
Restore quarantined person fragments for review:
```powershell
python tools/ops/gpi.py --restore
```

---

## 2. Technical Architecture & Data Lifecycle

### Pipeline Execution Stages
1. **Discovery:** Identifies `data/entities/pep-let-*.json` staging fragments.
2. **Schema Conformance:** Validates each fragment against `person.schema.json`. Malformed records route to `data/entities/quarantine/`.
3. **Graph Topology Verification:** Confirms that each candidate entity maintains a traversal path back to root ancestor `IND-00000`. Isolated nodes route to quarantine.
4. **Deduplication:** Evaluates `given | surname | birth_year` fingerprints against `people.json` to prevent duplicate ingestion.
5. **Location Canonicalization:** Normalizes place names against master indexes (`data/entities/locations.json`, `data/indexes/location_index.json`).
6. **Minting & Reciprocal Linking:** Allocates the next sequential `IND-#####` ID and generates reciprocal kinship relations (e.g., `FATH` -> `CHIL`).
7. **Atomic Commit & Cleanup:** Creates an atomic Safe Backup of `people.json` in `backups/`, writes the updated registry, and deletes processed staging files.

### Framework Integration
* `tools.lib.gda_core.GDAConfig.CONFIG`: Resolves registry paths (`CONFIG.people`, `CONFIG.quarantine`, `CONFIG.backups`).
* `tools.lib.gda_core.GDALogger.setup_logger`: Configures `[SYS]` event-aware logging.
* `tools.lib.gda_core.GDAUtil.GDAUtil`: Coordinates safe backups, atomic JSON persistence, and quarantine isolation.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/integration/test_gpi.py`
* **Execution:**
```powershell
pytest tests/integration/test_gpi.py -v
```

### Diagnostic Matrix
* **Quarantined (`Schema violation`):** Check syntax and required fields against `schemas/entities/person.schema.json`.
* **Quarantined (`Topology failure`):** The person has no valid parent or spouse path connecting back to progenitor `IND-00000`.
