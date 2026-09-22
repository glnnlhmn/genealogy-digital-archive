# Technical Runbook: GPA (Genealogy People Auditor)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `gpa.py` |
| **Script Path** | `tools/ops/gpa.py` |
| **Version** | `1.0.1+build.20260922.2` |
| **Test Suite** | `tests/integration/test_gpa.py` |
| **Log Output** | `logs/gpa-[YYYYMMDD_HHMMSS].log` |
| **Report Output** | `reports/audit_people_[check]_[timestamp].txt` |
| **Remediation Output** | `reports/remediation_vital_sync_[timestamp].csv` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
GPA audits `data/entities/people.json` to verify envelope structure, schema requirements, kinship reciprocity, biological chronology plausibility, and date consistency between canonical name summaries and detailed vitals blocks.

### CLI Syntax
```powershell
python tools/ops/gpa.py [--container] [--schema] [--reciprocity] [--chronology] [--vital-sync] [--incomplete-dates] [--all] [-v] [--debug]
```

### Options & Parameter Reference
* `--container`: Verifies container envelope properties, schema version, and entity count accuracy.
* `--schema`: Audits individual entity records against schema constraints and enum values.
* `--reciprocity`: Validates bidirectional kinship linkages (`FATH`/`MOTH` <-> `CHIL`, `SPOU` <-> `SPOU`).
* `--chronology`: Enforces biological plausibility limits between parent and child birth years (12–85 years).
* `--vital-sync`: Audits concordance between summary canonical years and vitals blocks, emitting a remediation CSV.
* `--incomplete-dates`: Catalogs missing vital dates and identifies partial date formats (`YYYY`, `YYYY-MM`).
* `--all`: Executes all audit routines non-interactively and generates tiered reports and CSV ledgers.
* `-v, --verbose`: Enables diagnostic logging to the session log.
* `--debug`: Routes runtime traces directly to standard error.

### Quick Runbook
Execute complete audit non-interactively:
```powershell
python tools/ops/gpa.py --all -v
```
Audit vital date synchronization and generate remediation ledger:
```powershell
python tools/ops/gpa.py --vital-sync
```

---

## 2. Technical Architecture & Data Lifecycle

### Audit Capabilities & Finding Tiers
GPA classifies validation results into three distinct severity levels via `TieredFindings`:
* **Errors:** Critical schema violations, invalid enum tokens, broken kinship reciprocity, biological age anomalies (<12 or >85 years), and direct birth/death year conflicts.
* **Warnings:** Data gaps, unreciprocated spouse assertions, modifier discordances (`EXACT` vs. `ABT`), and unrecorded vital dates.
* **Notes:** Observational notes, incomplete/partial date representations, and skipped checks due to absent parent/child dates.

### Remediation Ledger Generation
When running `--vital-sync` or `--all`, discrepancies between `canonical_name.birth_year` / `canonical_name.death_year` and `vitals` blocks are evaluated against evidentiary arbitration rules:
* If vitals contains day-level precision while canonical contains only year, vitals is presumed authoritative.
* Actionable fixes are written to `reports/remediation_vital_sync_[timestamp].csv` containing target JSON paths, current values, proposed values, and rule rationales.

### Framework Integration
* `tools.lib.gda_core.GDAConfig.CONFIG`: Resolves registry path (`CONFIG.people`) and reports directory (`CONFIG.reports`).
* `tools.lib.gda_core.GDALogger.setup_logger`: Configures `[SYS]` event-aware logging.
* `tools.lib.gda_core.GDAUtil.GDAUtil`: Handles UTF-8 JSON I/O.
* `tools.lib.gda_core.registry.SchemaEnums`: Validates sex, date modifier, and association role enums against `_enums.schema.json`.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/integration/test_gpa.py`
* **Execution:**
```powershell
pytest tests/integration/test_gpa.py -v
```

### Diagnostic Matrix
* **Reciprocity Error (`Links parent, but target does not link back`):** Target individual's `associated_people` array is missing a reciprocal `CHIL` link.
* **Chronology Error (`Biological impossibility`):** Parent was under 12 or over 85 at child birth. Verify source documents for misattributed individuals.
