# Technical Runbook: GPA (Genealogy People Auditor)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `gpa.py` |
| **Script Path** | `tools/ops/gpa.py` |
| **Version** | `1.1.0+build.20260926.01` |
| **Test Suites** | `tests/integration/test_gpa.py`, `tests/unit/test_gpa_units.py` |
| **Log Output** | `logs/gpa-[YYYYMMDD_HHMMSS].log` |
| **Report Output** | `reports/audit_people_[check]_[timestamp].txt` |
| **Remediation Output** | `reports/remediation_vital_sync_[timestamp].csv` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
GPA audits person registries (`data/entities/people.json` or target test files) to enforce schema compliance, envelope integrity, reciprocal kinship linkages, graph reachability and topology, biological chronology limits, location structure standardization, and synchronicity between canonical summary dates and detailed vital event blocks.

### CLI Syntax
```powershell
python tools/ops/gpa.py [--file <path>] [--container] [--schema] [--reciprocity] [--chronology] [--vital-sync] [--locations] [--unions] [--all] [-v] [--debug]
```

### Options & Parameter Reference
* `--file <path>`: Specifies custom registry path to audit (defaults to `CONFIG.people` -> `data/entities/people.json`).
* `--container`: Verifies container envelope properties (`$schema`, `schema_version`, `total_persons`), detecting `ENV_REQ` and `COUNT_MISMATCH`.
* `--schema`: Audits individual entity records against schema constraints and enum definitions.
* `--reciprocity`: Validates bidirectional kinship linkages (`FATH`/`MOTH` <-> `CHIL`, `SPOU` <-> `SPOU`), detecting `ASYM_ASSOC`.
* `--chronology`: Enforces biological plausibility limits between parent and child birth years (parent minimum 12 years old, mother upper threshold 55 years old, lifespan maximum 115 years unless documented by exemption notes).
* `--vital-sync`: Audits concordance between canonical year summaries and vitals date blocks, detecting `VITAL_SYNC_BIRTH_YEAR` and `VITAL_SYNC_DEATH_YEAR`. Emits a remediation CSV when discrepancies are discovered.
* `--locations`: Verifies place objects within birth and death blocks for dictionary structure (`LOCATION_MALFORMED`) and standard keys (`LOCATION_MISSING_STANDARD`).
* `--unions`: Verifies union definitions for valid spouse IDs (`UNION_NO_SPOUSE`), legal marital statuses (`UNION_INVALID_STATUS`), and synchronized marriage dates across spouses (`UNION_DATE_MISMATCH`).
* `--all`: Executes all audit routines non-interactively, emitting diagnostic logs and returning exit code `0` on success or `1` if critical violations exist.
* `-v, --verbose`: Enables diagnostic logging to the console and session log.
* `--debug`: Routes runtime traces directly to standard error.

### Quick Runbook Commands
Audit production registry with complete ruleset:
```powershell
python tools/ops/gpa.py --all -v
```

Audit specific fixture file for vital date synchronization:
```powershell
python tools/ops/gpa.py --file tests/fixtures/failures/failed_vital_sync_death.json --vital-sync
```

---

## 2. Technical Architecture & Data Lifecycle

### Audit Capabilities & Finding Tiers
GPA classifies validation results into two primary operational tiers via `TieredFindings`:
* **Critical Errors (Exit Code 1):** Fatal schema violations, container property omissions (`ENV_REQ`), count desynchronizations (`COUNT_MISMATCH`), duplicate identifiers (`DUPLICATE_PERSON_ID`), dangling associations (`DANGLING_ASSOC`), isolated components (`TOPOLOGY_ISLAND`), impossible lifespans (`CHRONO_DEATH_BEFORE_BIRTH`, `CHRONO_PARENT_TOO_YOUNG`, `CHRONO_BORN_AFTER_PARENT_DEATH`), and vital year desynchronizations (`VITAL_SYNC_BIRTH_YEAR`, `VITAL_SYNC_DEATH_YEAR`).
* **Warnings (Exit Code 0 if no Criticals):** Reciprocal linkage omissions (`ASYM_ASSOC`), identity fingerprint collisions (`DEDUP_COLLISION`), union date discrepancies (`UNION_DATE_MISMATCH`), union status or identifier anomalies (`UNION_NO_SPOUSE`, `UNION_INVALID_STATUS`), unverified extreme lifespans (`CHRONO_IMPLAUSIBLE_LIFESPAN`), mature maternal delivery (`CHRONO_MOTHER_TOO_OLD`), and malformed location objects (`LOCATION_MALFORMED`, `LOCATION_MISSING_STANDARD`).

### Biological Chronology & Exemption Protocols
GPA implements historical research exemption rules to suppress false warnings for documented archival exceptions:
* **Longevity Exemption:** When calculated lifespan exceeds 115 years, GPA searches the individual's `notes` array for `"longevity"`. If found, `CHRONO_IMPLAUSIBLE_LIFESPAN` is suppressed.
* **Late Maternal Birth Exemption:** When maternal age at delivery exceeds 55 years, GPA evaluates `notes` on the child and mother records for `"late"`. If found, `CHRONO_MOTHER_TOO_OLD` is suppressed.

### Remediation Ledger Generation
When running `--vital-sync` or `--all`, discrepancies between `canonical_name.birth_year` / `canonical_name.death_year` and `vitals` blocks are evaluated against evidentiary arbitration rules:
* If vitals contains day-level precision (`YYYY-MM-DD`) while canonical contains only year, vitals is presumed authoritative.
* Actionable fixes are written to `reports/remediation_vital_sync_[timestamp].csv` containing target JSON paths, current values, proposed values, and rule rationales.

### Framework Integration
* `tools.lib.gda_core.GDAConfig.CONFIG`: Resolves registry path (`CONFIG.people`) and reports directory (`CONFIG.reports`).
* `tools.lib.gda_core.GDALogger.setup_logger`: Configures `[SYS]` event-aware logging.
* `tools.lib.gda_core.GDAUtil.GDAUtil`: Handles atomic Safe Backups and UTF-8 JSON I/O.
* `tools.lib.gda_core.registry.SchemaEnums`: Validates sex, date modifier, and association role enums against `_enums.schema.json`.

---

## 3. Verification Harness & Diagnostics

### Test Suite Structure
The testing architecture splits GPA verification into two distinct suites comprising 33 test cases:
1. **Master Integration Suite (`tests/integration/test_gpa.py`):** 27 tests validating full-tree graph properties and surgical mutations against `golden_people.json` (62 persons) and failure fixtures in `tests/fixtures/failures/`.
2. **Defensive Unit Suite (`tests/unit/test_gpa_units.py`):** 6 tests validating input guards, null date parsing, unmapped association roles, note exemption suppressions, and CLI warning output formatting.

### Pytest Execution Markers
* **Unit Suite Only:**
```powershell
pytest -m unit -v -o addopts=""
```

* **Baseline Smoke / Golden Tree Integrity:**
```powershell
pytest -m smoke -v -o addopts=""
```

* **Failure Mutation Regressions:**
```powershell
pytest -m regression -v -o addopts=""
```

* **Full Combined Run with GPA Coverage:**
```powershell
pytest tests/integration/test_gpa.py tests/unit/test_gpa_units.py -v --cov=tools.ops.gpa --cov-report=term-missing -o addopts=""
```

### Diagnostic Matrix

| Rule Code | Severity | Cause | Remediation |
| :--- | :--- | :--- | :--- |
| `ENV_REQ` | `CRITICAL` | Missing top-level envelope key (`$schema`, `total_persons`, etc.). | Restore missing envelope properties to person registry root. |
| `COUNT_MISMATCH` | `CRITICAL` | `total_persons` integer disagrees with length of `persons` array. | Update `total_persons` in the registry envelope to match actual count. |
| `DUPLICATE_PERSON_ID` | `CRITICAL` | Duplicate `person_id` identifier exists across multiple records. | Reassign unique identifier to colliding record. |
| `DANGLING_ASSOC` | `CRITICAL` | `person_id` in `associated_people` does not exist in registry. | Correct or remove invalid person reference. |
| `TOPOLOGY_ISLAND` | `CRITICAL` | Person record has no reachable edges connecting to main graph. | Attach person via reciprocal association or union linkage. |
| `CHRONO_DEATH_BEFORE_BIRTH` | `CRITICAL` | Death date occurs prior to birth date. | Verify dates against vital certificates. |
| `CHRONO_PARENT_TOO_YOUNG` | `CRITICAL` | Parent was under 12 years old when child was born. | Check generational attribution or birth years for child and parent. |
| `CHRONO_BORN_AFTER_PARENT_DEATH` | `CRITICAL` | Child birth date occurs after recorded parent death date. | Verify parent death year and child birth year. |
| `VITAL_SYNC_BIRTH_YEAR` | `CRITICAL` | Canonical `birth_year` contradicts `vitals.birth.date.date_start`. | Synchronize canonical summary year with vital date. |
| `VITAL_SYNC_DEATH_YEAR` | `CRITICAL` | Canonical `death_year` contradicts `vitals.death.date.date_start`. | Synchronize canonical summary year with vital date. |
| `ASYM_ASSOC` | `WARNING` | Relationship is missing reciprocal entry on target record. | Add reciprocal `CHIL`/`PARENT`/`SPOU` association to target. |
| `UNION_DATE_MISMATCH` | `WARNING` | Marriage dates disagree between reciprocal spouse records. | Reconcile marriage dates between reciprocal spouse union entries. |
| `UNION_NO_SPOUSE` | `WARNING` | Union entry lacks `spouse_id` field. | Populate valid `spouse_id` in union entry. |
| `UNION_INVALID_STATUS` | `WARNING` | Union `status` not in controlled vocabulary enum. | Update status to valid enum (`MARRIED`, `DIVORCED`, `WIDOWED`, `PARTNER`). |
| `LOCATION_MALFORMED` | `WARNING` | Place property is a string or non-dict type. | Format place as dictionary with `verbatim` and `standardized`. |
| `LOCATION_MISSING_STANDARD` | `WARNING` | Place dict missing both `verbatim` and `standardized`. | Supply at least one standard location string. |
| `CHRONO_IMPLAUSIBLE_LIFESPAN` | `WARNING` | Calculated lifespan >115 years without documented note. | Attach longevity note or correct vital dates. |
| `CHRONO_MOTHER_TOO_OLD` | `WARNING` | Maternal age >55 years at delivery without documented note. | Attach late birth note or correct vital dates. |
