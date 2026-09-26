# Technical Runbook: GPI (Genealogy Person Intake)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `gpi.py` |
| **Script Path** | `tools/ops/gpi.py` |
| **Version** | `1.2.0+build.20260926.07` |
| **Test Suites** | `tests/unit/test_gpi_unit.py`, `tests/integration/test_gpi.py` |
| **Coverage Benchmark** | 96.77% branch/statement coverage (51 tests passed) |
| **Log Output** | `logs/gpi-[YYYYMMDD_HHMMSS].log` |
| **Target Registry** | `data/entities/people.json` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
GPI automates discovery, syntactic verification, topological reachability, biological chronology enforcement, deduplication drift control, location canonicalization, sequential identifier allocation, reciprocal edge synchronization, and atomic commit operations for staged person entity fragments (`data/entities/pep-let-*.json`) merging into the master person registry (`data/entities/people.json`).

### CLI Syntax
```powershell

python tools/ops/gpi.py [-a] [-r] [-v] [--debug]
```

### Options & Parameter Reference
* `-a, --append`: Executes the full 7-stage state machine, committing valid staged files to `people.json`.
* `-r, --restore`: Recovers all quarantined person files from `data/entities/quarantine/` back to `data/entities/` for re-evaluation.
* `-v, --verbose`: Logs itemized record-level diagnostic traces and reciprocal link mutations.
* `--debug`: Routes runtime traces and detailed exception stacks to `sys.stderr`.

### Quick Execution
Execute complete intake and append valid staged fragments:
```powershell

python tools/ops/gpi.py --append --verbose
```

Restore quarantined fragments back to staging:
```powershell

python tools/ops/gpi.py --restore
```

---

## 2. Technical Architecture & State Machine

### 7-Stage State Machine Lifecycle
1. **Stage 0: Discovery:** Scans `data/entities/` for files matching pattern `pep-let-*.json`. Returns a sorted list of candidate paths.
2. **Stage 1: Syntax & Intra-Record Audit:** 
   * Validates structure against `schemas/entities/person.schema.json` and referenced `_shared_defs.schema.json`.
   * Enforces structural union requirements (`spouse_id` presence, valid `status`).
   * Executes in-memory `RegistryAuditor` intra-record checks (`audit_vital_synchronization`, `audit_locations`, `audit_biological_chronology`).
   * Quarantines syntax errors, death-before-birth anomalies, and malformed location structures.
3. **Stage 2: Topological Graph Reachability:**
   * Constructs an in-memory bi-directional adjacency graph combining existing registry persons and staged candidates.
   * Traverses outward from progenitor `IND-00000`. Quarantines self-referential loops or disconnected components lacking reachability to root.
4. **Stage 2b: Inter-Record Relational Chronology:**
   * Evaluates the merged pool against `RegistryAuditor.audit_biological_chronology()`.
   * Isolates inter-generational biological plausibility violations (e.g., `CHRONO_PARENT_TOO_YOUNG`, `CHRONO_MOTHER_TOO_OLD`, `CHRONO_BORN_AFTER_PARENT_DEATH`).
   * Direct and message-referenced staged candidate IDs are isolated and quarantined.
5. **Stage 3: Deduplication & Drift Control:**
   * Calculates identity fingerprints (`given|surname|birth_year`).
   * Evaluates incoming records against existing registry entries to prevent duplicate ingestion.
   * Tracks intra-batch collisions (`seen_batch_fingerprints`), admitting the first instance while quarantining subsequent intra-batch duplicates.
6. **Stage 4: Location Canonicalization:**
   * Resolves birth and death place objects against `data/indexes/location_index.json` redirects and `data/entities/locations.json`.
   * Normalizes shorthand aliases to canonical standardized strings and enriches records with jurisdictional metadata hierarchy.
   * Quarantines records referencing unregistered or unresolvable place names.
7. **Stage 5: Identifier Minting & Graph Rewriting:**
   * Scans existing master IDs for maximum sequence number (`IND-#####`).
   * Assigns sequential master IDs to staged records.
   * Rewrites internal intra-batch temporary ID cross-references (`TMP-XXXXX` -> `IND-XXXXX`).
   * Injects deduplicated inverse reciprocal links on referenced entities (e.g., `FATH` -> `CHIL`, `SPOU` -> `SPOU`).
8. **Stage 6: Atomic Commit & Physical Cleanup:**
   * Generates a pre-execution rollback snapshot in `backups/` (`people.json.[timestamp].bk`) adhering to the Safe Backup Protocol.
   * Commits the updated master payload to `data/entities/people.json` with updated `total_persons` and `last_modified` ISO timestamps.
   * Deletes processed `pep-let-*.json` files from staging upon verified write completion. Aborts deletion if disk errors occur.

---

## 3. Operational Protocols & Guardrails

### Safe Backup Protocol Integration
Prior to executing modifications to `people.json`, `stage_6_atomic_commit` calls `GDAUtil.create_safe_backup()`. In the event of an `OSError` or write failure:
* The transaction is aborted immediately.
* No staging intake files are deleted.
* Staging artifacts remain fully intact for forensic remediation.

### Quarantine Recovery Subsystem
Entities failing any validation or graph criteria are moved via `GDAUtil.quarantine_file` into `data/entities/quarantine/` with diagnostic logging. The `--restore` (`-r`) CLI flag recovers all isolated `pep-let-*.json` files from quarantine back to the intake workspace (`data/entities/`).

---

## 4. Verification Harness & Diagnostics

### Test Harness Matrix
* **Unit Suite:** `tests/unit/test_gpi_unit.py` (Functional stage checks, non-reciprocal role passthrough, invalid location branches).
* **Integration Suite:** `tests/integration/test_gpi.py` (Multi-stage pipeline, atomic commit, rollback snapshots, CLI flags, 10-peplet golden batch regression).

### Verification Commands
Execute complete test suite across unit and integration targets:
```powershell

pytest tests/unit/test_gpi_unit.py tests/integration/test_gpi.py -v
```

Execute branch and statement coverage analysis:
```powershell

pytest tests/unit/test_gpi_unit.py tests/integration/test_gpi.py --cov=tools.ops.gpi --cov-branch --cov-report=term-missing
```

### Diagnostic Resolution Matrix
| Diagnostic Failure | Underlying Cause | Corrective Action |
| :--- | :--- | :--- |
| `Schema validation error` | Unevaluated properties, invalid enum, or missing required attributes. | Align entity JSON against `schemas/entities/person.schema.json`. |
| `GPA audit violation` | Intra-record vital date desynchronization or death before birth. | Ensure `vitals.birth.date` and `vitals.death.date` match canonical ranges. |
| `Graph topology error` | Entity has no traversal path connecting back to `IND-00000`. | Add ancestral kinship pointer to an existing root-connected person. |
| `Biological chronology violation` | Parentage age < 12 or post-mortem birth beyond allowable gestational window. | Re-evaluate source citations and correct vital dates. |
| `Collision: Candidate duplicate` | Exact match on given name, surname, and birth year in registry or batch. | Verify if entity represents persona drift or a distinct historical individual. |
| `Location resolution failure` | Birth or death place string missing from canonical authority tables. | Register place in `data/entities/locations.json` or alias in `location_index.json`. |
