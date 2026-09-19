# Tool Runbook: gsi.py
<!-- Version: 1.0.2 -->
<!-- Location: tools/ops/gsi.py -->

## Synopsis
Scans source directories for executable scripts (`.py`, `.ps1`), extracts mandatory header metadata (`# Name:`, `# Path:`), manages automated pre-overwrite Safe Backups, routes files to repository locations, and optionally executes them.

---

## Command Syntax
```powershell
python tools/ops/gsi.py [-s SOURCE] [-p PATTERN] [-r] [-f] [-- <PASSTHROUGH_ARGS>]
```

## Parameters
* `-s, --source-dir PATH`: Directory to scan (Default: archive repository root).
* `-p, --pattern TEXT`: Filter string for filenames (Default: `gemini`).
* `-r, --run`: Automatically executes relocated script post-import.
* `-f, --force`: Overwrites existing target without interactive confirmation (still executes safe backup).
* `-- <ARGS>`: Forwards all trailing arguments directly to target script execution.

## Safety & Logging Features
* **Mandatory Header Verification:** Requires `# Name:` and `# Path:` headers in the first 15 lines of candidate files. Skips non-compliant files without failing the batch.
* **Safe Backup Protocol:** Automatically generates an atomic pre-write copy in `backups/` (`[filename].[timestamp].bk`) prior to replacing any existing target file.
* **Centralized Logging:** Automatically logs all scan, backup, move, and execution events to `logs/gsi-[timestamp].log`. No CLI flag is required.
* **Execution Decoupling:** Spawns target scripts directly without intercepting or capturing child process stdout/stderr into the importer session log.
* **Venv Auto-Detection:** Automatically invokes `ROOT/.venv` Python interpreter when executing Python targets, falling back to active runtime environment.