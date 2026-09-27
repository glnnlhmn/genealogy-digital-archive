<!--
Name: runbook-gsi.md
Path: docs/tools/runbook-gsi.md
-->

# Technical Runbook: GSI (Genealogy Script Importer)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `gsi.py` |
| **Script Path** | `tools/ops/gsi.py` |
| **Version** | `1.0.5+build.20260926.04` |
| **Test Suite** | `tests/unit/test_gsi.py` |
| **Log Output** | `logs/gsi-[YYYYMMDD_HHMMSS].log` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
GSI automates the discovery, metadata parsing, Safe Backup creation, destination routing, and contextual execution of staged intake files matching the pattern `gemini` in the repository root. It handles Python scripts, test suites, Markdown documentation, PowerShell scripts, and JSON/text assets without manual file relocation.

### CLI Syntax
```powershell
python tools/ops/gsi.py [-r]
```

### Options & Parameter Reference
* `-h, --help`: Displays CLI usage syntax and parameter definitions.
* `-r, --run`: Triggers contextual execution immediately following successful file relocation:
  * `test_*.py` / `*_test.py`: Spawns isolated pytest runner (`pytest <file> -v`).
  * `*.py`: Executes via active Python interpreter (`python <file>`).
  * `*.ps1`: Spawns PowerShell with bypass policy (`powershell.exe -ExecutionPolicy Bypass -File <file>`).
  * `*.md`: Opens rendered documentation directly in Google Chrome (with default browser fallback).
  * `*.json`, `*.txt`: Skips execution and outputs `(Can not execute)` notification.

### Quick Runbook
Inspect and relocate staged candidates without execution:
```powershell
python tools/ops/gsi.py
```

Relocate staged files and execute runners contextually:
```powershell
python tools/ops/gsi.py -r
```

---

## 2. Technical Architecture & Data Lifecycle

### Metadata Header Standards
Every candidate file must include destination metadata within its first 15 lines.

#### Python, PowerShell, Plaintext (`.py`, `.ps1`, `.txt`)
Standard single-line comment format:
```text
# Name: filename.ext
# Path: relative/path/to/filename.ext
```

#### Markdown (`.md`)
Suppressed HTML comment block (invisible in rendered displays):
```markdown
<!--
Name: filename.md
Path: relative/path/to/filename.md
-->
```

#### Structured JSON (`.json`)
Top-level metadata properties:
```json
{
  "_name": "filename.json",
  "_path": "relative/path/to/filename.json"
}
```

### Pipeline Execution Stages
1. **Root Candidate Scanning:** Evaluates files strictly in the repository root (`.`) matching the substring `gemini` (case-insensitive) across allowed extensions (`.py`, `.md`, `.ps1`, `.txt`, `.json`).
2. **Metadata Header Extraction:** Inspects the first 15 lines of candidate files using regular expressions. Extracts target filename and destination path while stripping comment tokens, trailing slashes, and quotes.
3. **Traversal Trap & Destination Resolution:** Confirms the destination path resolves strictly within the repository root anchor. If the destination points to an existing directory or ends with a slash, appends the extracted target filename automatically.
4. **Pre-Execution Safe Backup Protocol:** Checks whether the target destination already exists as a regular file (`dest_path.is_file()`). If found, invokes `GDAUtil.create_safe_backup()` to snapshot the existing target to `backups/[filename].[timestamp].bk`.
5. **Atomic Relocation & Path Logging:** Relocates the candidate file to its destination via `shutil.move()` and reports the operation using normalized Windows paths (`.\path\filename.ext`).
6. **Context-Aware Execution (`-r`):** If the run flag is provided, dispatches to the corresponding subsystem runner and halts pipeline execution if a non-zero exit code is returned.

### Framework Integration
* `tools.lib.gda_core.GDAConfig`: Resolves root archive directory topology anchors and log destinations.
* `tools.lib.gda_core.GDALogger.setup_logger`: Configures session-level file logging under `logs/`.
* `tools.lib.gda_core.GDAUtil.GDAUtil`: Coordinates pre-write Safe Backup generation prior to file overwrites.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/unit/test_gsi.py`
* **Execution:**
```powershell
pytest tests/unit/test_gsi.py -v --cov=tools.ops.gsi --cov-branch --cov-report=term-missing
```

### Diagnostic Matrix
* **`Missing valid metadata headers ... within first 15 lines`:** The candidate file does not contain recognized `Name:` / `Path:` comments or `_name` / `_path` JSON fields within lines 1–15. Relocation skipped.
* **`Security error: Destination attempts escape outside repository root`:** Target path uses `..` traversal reaching above the root archive directory. Relocation blocked.
* **`Execution finished with non-zero exit code <N>`:** Post-intake runner execution failed. Inspect tool or test failure details output directly to standard output.
* **`(Can not execute)` Log Notice:** File was relocated successfully, but the `-r` flag was supplied for a non-executable asset type (`.json` or `.txt`).

---

## 4. Maintenance History & Changelog

| Date | Version | Description |
| :--- | :--- | :--- |
| 2026-09-22 | `1.0.3+build.20260922.2` | Initial baseline operational implementation[cite: 1]. |
| 2026-09-24 | `1.0.4+build.20260924.1` | Added CLI flag options, interactive confirmation prompts, and argument passthrough. |
| 2026-09-26 | `1.0.5+build.20260926.04` | Streamlined CLI; enforced fixed root scope; added multi-format intake (`.md`, `.ps1`, `.txt`, `.json`); introduced HTML comment and JSON key header parsing; added automated directory filename resolution; routed tests to `pytest -v`, `.md` to Chrome, and flagged non-executable assets with `(Can not execute)`. |