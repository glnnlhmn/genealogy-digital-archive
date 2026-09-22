# Technical Runbook: GFI (Genealogy Fact Intake)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `gfi.py` |
| **Script Path** | `tools/ops/gfi.py` |
| **Version** | `1.0.1+build.20260922.1` |
| **Test Suite** | `tests/integration/test_gfi.py` |
| **Log Output** | `logs/gfi-[YYYYMMDD_HHMMSS].log` |
| **Target Registry** | `data/entities/facts.json` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
GFI manages the intake, semantic validation, auto-chunking, and master appending of staged fact assertions (`data/entities/factoid-*.json`). It protects production by isolating malformed records in quarantine, creating paired rollback snapshots, and merging into `facts.json`.

### CLI Syntax
```powershell
python tools/ops/gfi.py [-b {75,150,300}] [-i] [-a] [-r] [-v] [--debug]
```

### Options & Parameter Reference
* `-b, --batch-size {75,150,300}`: Number of factoids packed per batch container (Default: `75`).
* `-i, --intake`: Validates staged assertions, isolates malformed records into quarantine, and builds batch containers.
* `-a, --append`: Performs end-to-end ingestion: batches pending files, merges to `facts.json`, creates dual backups, and purges `fact-new/`.
* `-r, --restore`: Recovers all quarantined files from `data/entities/quarantine/` back to `data/entities/`.
* `-v, --verbose`: Emits detailed record-level diagnostic traces to session logs.
* `--debug`: Directs live runtime traces directly to stderr.

### Quick Runbook
Execute full intake, batching, master merge, and staging cleanup:
```powershell
python tools/ops/gfi.py --append
```
Restore quarantined fact assertions for re-evaluation:
```powershell
python tools/ops/gfi.py --restore
```

---

## 2. Technical Architecture & Data Lifecycle

### Pipeline Execution Stages
1. **Validation & Semantic Normalization:** Verifies subject and associate person IDs against `people.json`. Normalizes fields (`place` -> `location`, formats standard `source_urn`). Detects self-referential loops. Quarantines invalid records via `GDAUtil.quarantine_file()`.
2. **Batch Container Packaging:** Groups valid records into slices of `batch_size` (default: 75). Creates sequential batch folders (`fact-new/batch-XXXX/`) and envelopes (`fact-new/factoids-XXXX.json`).
3. **Master Sync, Dual Backups & Purge:** Deduplicates incoming `fact_id` values against existing records in `facts.json`. Generates paired synchronized rollback backups in `backups/`:
   * Master facts snapshot: `facts.json.[timestamp].bk`
   * Ingested batch snapshot: `factoids_ingested_[timestamp].bk`
   Persists master facts atomically and removes `data/entities/fact-new/`.

### Framework Integration
* `tools.lib.gda_core.GDAConfig.CONFIG`: Resolves entities, people, facts, quarantine, backups, and logs directories.
* `tools.lib.gda_core.GDALogger.setup_logger`: Configures `[SYS]` event-aware logging.
* `tools.lib.gda_core.GDAUtil.GDAUtil`: Coordinates safe backups, quarantine moves, and atomic JSON I/O.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/integration/test_gfi.py`
* **Execution:**
```powershell
pytest tests/integration/test_gfi.py -v
```

### Diagnostic Matrix
* **Quarantined (`person_id does not exist`):** Ingest the individual using `gpi.py` first before ingesting their associated facts.
* **Quarantined (`Self-referencing loop`):** The fact asserts an associated person with the same ID as the primary subject under a conflicting relationship role.
