# Technical Runbook: FACTS_MD (Fact Markdown Synchronizer)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `facts_md.py` |
| **Script Path** | `tools/ops/facts_md.py` |
| **Version** | `1.0.1+build.20260922.1` |
| **Test Suite** | `tests/integration/test_facts_md.py` |
| **Log Output** | `logs/facts_md-[YYYYMMDD_HHMMSS].log` |
| **Target Document** | `data/archival_records/facts.md` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
`facts_md.py` renders the master JSON fact registry (`data/entities/facts.json`) into human-readable Markdown (`data/archival_records/facts.md`). It sorts facts chronologically by individual, generates cross-reference tables, and creates pre-write Safe Backups.

### CLI Syntax
```powershell
python tools/ops/facts_md.py [--dry-run] [-v] [--debug]
```

### Options & Parameter Reference
* `--dry-run`: Runs generation in memory and prints preview statistics without writing to disk.
* `-v, --verbose`: Logs detailed synchronization traces to `logs/facts_md-[timestamp].log`.
* `--debug`: Outputs live execution traces directly to stderr.

### Quick Runbook
Synchronize master facts to Markdown:
```powershell
python tools/ops/facts_md.py
```
Perform dry-run inspection:
```powershell
python tools/ops/facts_md.py --dry-run -v
```

---

## 2. Technical Architecture & Data Lifecycle

### Pipeline Execution Stages
1. **Registry Extraction:** Loads `facts.json` and `people.json`. Resolves primary subject names and vital dates.
2. **Chronological Grouping & Sort:** Groups assertions by `person_id` and sorts chronologically from earliest to latest.
3. **Markdown Rendering:** Formats standardized document headers and emits individual tables containing Date, Fact Type, Description, Location, and Source URN.
4. **Safe Backup & Atomic Output:** Creates `backups/facts.md.[timestamp].bk` before writing the updated document with UTF-8 encoding.

### Framework Integration
* `tools.lib.gda_core.GDAConfig.CONFIG`: Resolves paths to facts, people, records, backups, and logs.
* `tools.lib.gda_core.GDALogger.setup_logger`: Configures `[SYS]` event-aware logging.
* `tools.lib.gda_core.GDAUtil.GDAUtil`: Coordinates safe backups and atomic document writing.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/integration/test_facts_md.py`
* **Execution:**
```powershell
pytest tests/integration/test_facts_md.py -v
```

### Diagnostic Matrix
* **Facts Missing in Output:** Verify that facts in `facts.json` possess valid `person_id` references matching entries in `people.json`.
* **Markdown Table Formatting Corrupted:** Ensure raw description text does not contain unescaped pipe characters (`|`).
