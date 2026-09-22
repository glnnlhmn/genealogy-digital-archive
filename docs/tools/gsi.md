# Technical Runbook: GSI (Genealogy Script Importer)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `gsi.py` |
| **Script Path** | `tools/ops/gsi.py` |
| **Version** | `1.0.3+build.20260922.2` |
| **Test Suite** | `tests/integration/test_gsi.py` |
| **Log Output** | `logs/gsi-[YYYYMMDD_HHMMSS].log` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
GSI moves generated automation scripts from temporary scratchpads (`gtemp/`) into permanent repository locations. It validates header metadata, enforces the Safe Backup Protocol before overwriting existing files, and optionally runs the relocated script.

### CLI Syntax
```powershell
python tools/ops/gsi.py [-s SOURCE_DIR] [-p PATTERN] [-r] [-f] [-v] [--debug] [-- <ARGS>]
```

### Options & Parameter Reference
* `-s, --source-dir PATH`: Directory scanned for pending scripts (Default: repository root).
* `-p, --pattern TEXT`: Filter string for matching script filenames (Default: `gemini`).
* `-r, --run`: Spawns the target script post-import within the project `.venv`.
* `-f, --force`: Suppresses interactive overwrite prompts (pre-execution safe backup is still performed).
* `-v, --verbose`: Logs detailed scan traces to `logs/gsi-[timestamp].log`.
* `--debug`: Outputs live execution traces directly to stderr.
* `-- <ARGS>`: Forwards trailing arguments directly to target script execution when combined with `-r`.

### Quick Runbook
Import scripts matching 'gam' interactively:
```powershell
python tools/ops/gsi.py -s gtemp -p "gam"
```
Force overwrite and execute relocated tool with passthrough arguments:
```powershell
python tools/ops/gsi.py -s gtemp -p "gpa" -f -r -- --all -v
```

---

## 2. Technical Architecture & Data Lifecycle

### Pipeline Execution Stages
1. **Candidate Discovery & Header Verification:** Scans source directory for `.py` or `.ps1` files matching pattern. Inspects the first 15 lines for mandatory headers (`# Name:`, `# Path:`). Non-compliant files are skipped.
2. **Path Resolution & Collision Handling:** Resolves destination relative to repository root (`CONFIG.root`). If destination exists:
   * Displays prompt: `Overwrite destination? [Y/n]` (defaults to Yes).
   * Generates Safe Backup in `backups/[filename].[timestamp].bk`.
3. **Relocation & Decoupled Execution:** Moves source file into place atomically. If `-r` is set, locates `.venv` Python and spawns the process via `subprocess.run()`, allowing stdout/stderr to stream cleanly.

### Framework Integration
* `tools.lib.gda_core.GDAConfig.CONFIG`: Resolves root anchor and destination paths.
* `tools.lib.gda_core.GDALogger.setup_logger`: Configures `[SYS]` event-aware logging.
* `tools.lib.gda_core.GDAUtil.GDAUtil`: Coordinates pre-write Safe Backup generation.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/integration/test_gsi.py`
* **Execution:**
```powershell
pytest tests/integration/test_gsi.py -v
```

### Diagnostic Matrix
* **Skipped File (`Missing mandatory headers`):** Ensure the first 15 lines of the script include `# Name: <filename>` and `# Path: <relative_path>`.
* **Prompt Aborted (`Target retained`):** Operator selected 'n' during overwrite confirmation. Use `-f` to bypass interactive prompts in automated pipelines.
