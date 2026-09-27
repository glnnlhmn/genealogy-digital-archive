# Topic Specification: Documentation & Tool Promotion Standards
<!-- Version: 1.0.0 -->
<!-- Location: prompts/topics/MIP-Topic-Documentation-Standards.md -->

## 1. Documentation Architecture (`docs/`)
All technical references, protocols, and runbooks anchor under `docs/` and register in `docs/index.md`.

* **Master Navigation (`docs/index.md`):** Central catalog tracking active technical runbooks, architecture specifications, and workflow protocols.
* **Architecture Specifications (`docs/architecture/`):** Structural blueprints, environmental conventions, and filesystem layouts.
* **Operational Definitions & Protocols (`docs/defs/`):** Formal governing specifications (e.g., `def-safe-backup-v1.0.0.md`).
* **Tool Runbooks (`docs/tools/`):** Technical user and maintenance guides for operational tools residing in `tools/ops/`.

---

## 2. Cross-Format Metadata Intake Header Standard
`tools/ops/gsi.py` inspects the first 15 lines of candidate files located in the repository root matching the `gemini*` substring to determine routing and Safe Backup requirements.

### Python, PowerShell, and Plain Text (`.py`, `.ps1`, `.txt`)
```text
# Name: <filename.ext>
# Path: <relative/path/to/destination>
```

### Markdown (`.md`)
Use HTML comment blocks placed at the top of the file:
```text
<!--
Name: <filename.md>
Path: <relative/path/to/filename.md>
-->
```

### JSON (`.json`)
Use top-level string attributes prefixed with an underscore:
```json
{
  "_name": "<filename.json>",
  "_path": "<relative/path/to/filename.json>"
}
```

---

## 3. Tool Promotion Lifecycle (`gtemp/` -> `tools/ops/`)
1. **Incubation:** Develop scratch utilities and one-off emitters in `gtemp/XX_[name].py`. Execution logs write to `gtemp/[script]-timestamp.log`.
2. **Promotion Gate:**
   * Move script to `tools/ops/[tool].py`.
   * Update logging to target `logs/[tool]-[timestamp].log`.
   * Implement standard CLI flags (`--help`, `--verbose`, `--debug`) and Safe Backup pre-checks.
   * Author dedicated runbook in `docs/tools/[tool].md`.
   * Register the tool runbook in `docs/index.md`.

---

## 4. Four-Tier Operational Tool Runbook Format
Every operational tool runbook in `docs/tools/` must contain:
1. **Header Metadata Table:** Tool Name, Script Path, Version (PEP 440), Test Suite, Log Output, and Safe Backup paths.
2. **Section 1: Operator Reference & Quick-Start:** Operational intent, CLI syntax, options reference, and copy-pasteable execution examples.
3. **Section 2: Technical Architecture & Data Lifecycle:** Internal state machine, algorithmic rules, and framework integration.
4. **Section 3: Verification Harness & Diagnostics:** Test suite location, test execution commands, and diagnostic matrix detailing error messages and remedies.
