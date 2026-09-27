# MIPLET-014: GSI Intake and Execution Workflow
<!-- Version: 1.0.0 -->
<!-- Target: MIP Section 3 (Operational Protocols & Scripting Safeguards) -->

## Operational Intent
Define the standardized lifecycle for staging, validating, archiving, and running automation scripts, documentation, and data assets using GSI (`tools/ops/gsi.py`). Eliminates manual copy-paste errors, guarantees atomic Safe Backups before overwriting production assets, and automates contextual verification.

## Staging & Relocation Lifecycle

1. **Staging:** Generate or stage candidate files in the repository root (`.`) using names matching the substring `gemini` (case-insensitive) across allowed extensions:
   * `.py` (Python scripts and unit tests)
   * `.md` (Archival runbooks, blueprints, and narrative docs)
   * `.ps1` (PowerShell maintenance tools)
   * `.json` (Structured entity payloads and data files)
   * `.txt` (Notes, transcriptions, and schemas)

2. **Inspection & Relocation (No Run):**
   Execute GSI without flags to inspect metadata headers, perform Safe Backups if targets already exist, and relocate files:
```powershell
python tools/ops/gsi.py
```

3. **Intake and Contextual Execution (`-r`):**
   Execute GSI with `-r` to relocate candidates and immediately spawn their contextual runners:
```powershell
python tools/ops/gsi.py -r
```

## Runner Dispatch Table

| Target Type | Dispatch Behavior | Notes |
| :--- | :--- | :--- |
| **Pytest Suites** (`test_*.py`, `*_test.py`) | `pytest <file> -v` | Inherits project environment and reports test failures with exit code. |
| **Python Tools** (`*.py`) | `python <file>` | Runs target in subprocess; non-zero exit aborts pipeline. |
| **PowerShell Scripts** (`*.ps1`) | `powershell.exe -ExecutionPolicy Bypass -File <file>` | Executes script directly in Windows PowerShell. |
| **Markdown Documents** (`*.md`) | Google Chrome / Default Browser | Launches rendered document in Google Chrome or default browser. |
| **Non-Executable Assets** (`*.json`, `*.txt`) | Relocation Only | Logs `Successfully relocated ... (Can not execute)` notice. |
