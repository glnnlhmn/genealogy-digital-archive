# MIPLET-013: Cross-Format Metadata Intake Header Standard
<!-- Version: 1.0.0 -->
<!-- Target: MIP Section 3 (Operational Protocols & Scripting Safeguards) -->

## Operational Intent
Standardize target metadata declarations across all file types ingested into the repository archive. GSI (`tools/ops/gsi.py`) inspects the first 15 lines of candidate files located in the repository root to determine destination filenames and directory routing prior to executing relocation and Safe Backup protocols.

## Format Specifications

### 1. Python, PowerShell, and Plain Text (`.py`, `.ps1`, `.txt`)
Use single-line comment format placed within the first 15 lines:
```text
# Name: <filename.ext>
# Path: <relative/path/to/destination>
```

### 2. Markdown (`.md`)
Use HTML comment blocks placed at the top of the file to prevent metadata rendering in document viewers:
```text
<!--
Name: <filename.md>
Path: <relative/path/to/filename.md>
-->
```

### 3. JSON (`.json`)
Use top-level string attributes prefixed with an underscore to designate destination routing:
```json
{
  "_name": "<filename.json>",
  "_path": "<relative/path/to/filename.json>"
}
```

## Path Resolution Safeguards
* **Root Anchor:** Relative paths automatically anchor to repository root (`G:/My Drive/genealogy-digital-archive`). Do not include drive letters or leading slashes.
* **Directory Targets:** If the `# Path:` header specifies a directory (or ends with a slash), GSI automatically resolves destination as `<Path>/<Name>`.
* **Security Boundaries:** Paths attempting directory traversal (`../`) outside the repository root boundary trigger a security fault and are skipped.
