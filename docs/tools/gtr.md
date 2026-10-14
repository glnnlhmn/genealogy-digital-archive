# Technical Runbook: GTR (Genealogy Token Registry)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `gtr.py` |
| **Script Path** | `tools/ops/gtr.py` |
| **Version** | `1.0.1+build.20260922.1` |
| **Test Suite** | `tests/integration/test_gtr.py` |
| **Log Output** | `logs/gtr-[YYYYMMDD_HHMMSS].log` |
| **Target Registry** | `schemas/naming/_token_registry.json` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
GTR provides programmatic maintenance for controlled vocabularies, token registries, and jurisdiction alias mappings in `schemas/naming/_token_registry.json`. It guarantees deduplication, alphabetical sorting for clean Git diffs, and automated Safe Backups.

### CLI Syntax
```powershell
python tools/ops/gtr.py <vocabulary> <key> [<value>] [-v] [--debug]
```

### Parameters
* `vocabulary`: Target controlled vocabulary name (`counties`, `conflicts`, `jurisdictions`, `pub_codes`, etc.).
* `key`: Token string, jurisdiction alias, or dictionary key.
* `value` *(Optional)*: Canonical value for dictionary vocabularies. (For `jurisdictions`, defaults to `key` if omitted).
* `-v, --verbose`: Outputs diagnostic logs and session execution details to `logs/gtr-[timestamp].log`.
* `--debug`: Prints live debug traces directly to stderr.

### Quick Runbook
Register a new county (alphabetized automatically):
```powershell
python tools/ops/gtr.py counties "Franklin" -v
```
Register a jurisdiction alias mapping (value defaults to key):
```powershell
python tools/ops/gtr.py jurisdictions "PA_FRA" -v
```
Register or update a publication code:
```powershell
python tools/ops/gtr.py pub_codes "SENTINEL" "The Sentinel" -v
```

---

## 2. Technical Architecture & Data Lifecycle

### Validation & Mutation Flow
1. **Vocabulary Conformance:** Validates requested vocabulary against `LIST_VOCABULARIES` and `DICT_VOCABULARIES`.
2. **Duplicate Detection:**
   * List vocabularies: If token exists, exits cleanly as a no-op without creating redundant backups.
   * Dictionary vocabularies: If key-value matches existing entry, exits cleanly without modifying disk state.
3. **Safe Backup Creation:** When a mutation is confirmed, creates `backups/_token_registry.json.[timestamp].bk`.
4. **Alphabetical Sorting & Atomic Persistence:** Sorts lists alphabetically and dictionaries case-insensitively by key, saving with 2-space indentation.

### Framework Integration
* `tools.lib.gda_core.GDAConfig.CONFIG`: Resolves token registry path (`CONFIG.token_registry`), backups, and logs.
* `tools.lib.gda_core.GDALogger.setup_logger`: Configures `[SYS]` event-aware logging.
* `tools.lib.gda_core.GDAUtil.GDAUtil`: Coordinates Safe Backup Protocol and atomic JSON I/O.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/integration/test_gtr.py`
* **Execution:**
```powershell
pytest tests/integration/test_gtr.py -v
```

### Diagnostic Matrix
* **Exit Code 1 (`Unknown vocabulary`):** Vocabulary must match one of the defined list or dictionary categories in `_token_registry.json`.
* **No-op Notice (`already exists`):** Token is already registered with identical mapping; no write occurred.
