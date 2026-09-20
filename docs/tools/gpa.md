# GPA: Genealogy People Auditor (Runbook)

## 1. Overview & Purpose
`gpa.py` is the operational CLI verification engine for the master person database (`data/entities/people.json`). It enforces schema compliance against `schemas/entities/person_registry.schema.json` (v1.0.1), verifies container metadata and counts, validates bidirectional kinship links, enforces biological chronological thresholds, and audits vital-date synchronization.

## 2. Technical Specifications
* **Script Location:** `tools/ops/gpa.py`
* **Target Database:** `data/entities/people.json`
* **Schema Contract:** `schemas/entities/person_registry.schema.json` (v1.0.1)
* **Log Output:** `logs/gpa-[YYYYMMDD_HHMMSS].log`
* **Report Output:** `reports/audit_people_[check_name]_[YYYYMMDD_HHMMSS].txt`
* **Remediation Output:** `reports/remediation_vital_sync_[YYYYMMDD_HHMMSS].csv`

## 3. Operational CLI Flags
GPA can be invoked with specific operational flags for targeted or automated auditing:

| Flag | Purpose |
| :--- | :--- |
| `--container` | Validates root envelope properties, `$schema`, `schema_version`, and `total_persons` match. |
| `--schema` | Verifies individual person record schemas, ID patterns, names, sexes, and date formats. |
| `--reciprocity` | Audits bidirectional kinship relationships (`CHIL` <-> `FATH`/`MOTH`, `SPOU` <-> `SPOU`). |
| `--chronology` | Checks biological limits between parents and children at birth (minimum age 12, maximum age 85). |
| `--vital-sync` | Audits date consistency between `canonical_name` and `vitals` blocks (emits remediation CSV). |
| `--incomplete-dates` | Catalogs missing vital dates and detects partial date patterns (`YYYY`, `YYYY-MM`). |
| `--all` | Non-interactive execution running all audit routines, writing the unified master report and CSV. |
| `-v`, `--verbose` | Emits detailed operational execution logs to `logs/gpa-[timestamp].log`. |
| `--debug` | Directs live diagnostic traces directly to `sys.stderr`. |

If invoked without operational flags (`python tools/ops/gpa.py`), the tool displays an interactive console menu:

```text
========================================================
        GPA: GENEALOGY PEOPLE AUDITOR (v1.0.0)
========================================================
1. Validate Container Schema & Version
2. Validate Entity Schema Requirements
3. Validate Bidirectional Kinship Reciprocity
4. Validate Child/Parent Birth Chronology
5. Validate Birth & Death Cross-Synchronization (TXT + CSV)
6. Audit Incomplete & Partial Vital Dates
7. Run Complete Audit (All Checks + CSV)
Q. Quit
========================================================
```

## 4. Usage Examples

Run a complete audit non-interactively with diagnostic logging:
```powershell
python tools/ops/gpa.py --all -v
```

Audit kinship reciprocity only:
```powershell
python tools/ops/gpa.py --reciprocity
```

Launch interactive menu console:
```powershell
python tools/ops/gpa.py
```

## 5. Test Suite
Automated regression tests are maintained in `tests/test_gpa.py`, utilizing isolated temporary fixtures.

Run the test suite:
```powershell
python -m pytest tests/test_gpa.py -v
```