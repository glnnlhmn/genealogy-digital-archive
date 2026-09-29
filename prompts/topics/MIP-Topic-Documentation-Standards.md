<!--
Name: MIP-Topic-Documentation-Standards.md
Path: prompts/topics/MIP-Topic-Documentation-Standards.md
-->
# Topic Specification: Documentation & Tool Promotion Standards
<!-- Version: 1.0.1 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Documentation Architecture (`docs/`)
All technical specifications, protocols, and operational runbooks anchor under `docs/` and register in `docs/index.md`.

* **Master Navigation Index (`docs/index.md`):** Authoritative catalog registering active technical runbooks, architecture specifications, and workflow protocols.
* **Architecture Blueprints (`docs/architecture/`):** Structural blueprints, environmental topology, and filesystem specifications.
* **Operational Protocols & Definitions (`docs/defs/`):** Formal governing protocol specifications (e.g., `def-safe-backup-v1.0.0.md`).
* **Core Library Documentation (`docs/lib/gda_core/`):** API reference, component contracts, and class documentation for `gda_core` primitives.
* **Tool Runbooks (`docs/tools/`):** Comprehensive technical runbooks for operational scripts residing in `tools/ops/` and `tools/sys/`.

---

## 2. Cross-Format Metadata Intake Header Standard
All generated source files, test suites, schemas, and documentation deliverables must include mandatory metadata declarations within the first 15 lines. `tools/ops/gsi.py` relies on these tags to resolve target destinations, enforce Safe Backups, and execute atomic intake (`python ./tools/ops/gsi.py -r`):

### Python, PowerShell, and Plain Text (`.py`, `.ps1`, `.txt`)
```text
# Name: <filename.ext>
# Path: <relative/path/to/destination>
```

### Markdown (`.md`)
HTML comment block placed at the top of the file:
```text
<!--
Name: <filename.md>
Path: <relative/path/to/destination>
-->
```

### JSON (`.json`)
Top-level string attributes prefixed with an underscore:
```json
{
  "_name": "<filename.json>",
  "_path": "<relative/path/to/destination>"
}
```

---

## 3. Tool Promotion Lifecycle (`gtemp/` -> `tools/ops/`)
1. **Scratch Incubation:** Ephemeral utilities, one-off transform scripts, and scratch experiments reside in `gtemp/XX_[purpose].py`. Execution traces log locally to `gtemp/[script]-[timestamp].log`.
2. **Promotion Gate:**
   * Target destination must be `tools/ops/[tool].py` (or `tools/sys/[tool].py` for developer environment scripts).
   * Logging must integrate with `GDALogger` routing to `logs/[tool]-[timestamp].log`.
   * Standard CLI parameters (`--help`, `--verbose`, `--debug`) and Safe Backup pre-checks must be implemented.
   * Module version string must be declared conforming to PEP 440 local build identifiers (`__version__ = "1.0.0+build.YYYYMMDD.1"`).
   * Author a 4-tier operational runbook in `docs/tools/[tool].md` and register it in `docs/index.md`.

---

## 4. Four-Tier Operational Tool Runbook Format
Every operational tool runbook in `docs/tools/` must strictly implement the 4-tier layout:

1. **Header Metadata Table:**
   * Summary table tracking Tool Name, Script Path, Version (PEP 440), Test Suite Path, Log Destination, and Safe Backup Target.
2. **Tier 1: Operator Reference & Quick-Start:**
   * Operational purpose, standard CLI invocation syntax, complete argparse flag reference table, and ready-to-run execution examples.
3. **Tier 2: Technical Architecture & Data Lifecycle:**
   * Execution lifecycle, internal state machine breakdown, schema input/output contracts, and framework integration with `GDAConfig`, `GDALogger`, and `GDAUtil`.
4. **Tier 3: Verification Harness & Diagnostic Matrix:**
   * Associated pytest suite location, marker filters, test execution commands, and an exhaustive Diagnostic Matrix mapping specific error codes/messages to root causes and explicit operator remediation actions.

---

## 5. Tokenized Code-Fence Generation Protocol
When an automation script generates Markdown documentation containing nested code fences, it should emit intermediate string tokens rather than literal triple backticks to avoid premature string-termination crashes:
* Opening Tokens: `<<PWSH_BLOCK>>`, `<<PY_BLOCK>>`, `<<TEXT_BLOCK>>`, `<<JSON_BLOCK>>`
* Closing Token: `<<BLOCK_END>>`
* Post-Processing: Replace intermediate tokens with corresponding Markdown triple backticks prior to writing output files to disk.