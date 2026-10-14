<!--
Name: topic_operational_tools.md
Path: prompts/topics/topic_operational_tools.md
-->
# Topic Specification: Operational Tooling Architecture (`tools/ops/`)
<!-- Version: 1.0.0 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Architectural Scope & Operational Role
Permanent operational tools under `tools/ops/` serve as production orchestrators with Read/Write authority across canonical registries, schemas, and indices. They coordinate intake, auditing, and maintenance pipelines by consuming shared framework libraries (`gdacore`, `gdaschema`, `gdadomain`).

---

## 2. Production Operational Inventory

| Tool Name | Subpath | Category | Core Purpose | Runbook |
| :--- | :--- | :--- | :--- | :--- |
| `gam.py` | `tools/ops/` | Ops | Archive manager: SHA-256 digests, manifest auditing, and persona drift detection. | `docs/tools/runbook-gam.md` |
| `gpi.py` | `tools/ops/` | Ops | Person intake: 7-stage state machine for staging raw persona assertions. | `docs/tools/runbook-gpi.md` |
| `gpa.py` | `tools/ops/` | Ops | People auditor: Schema compliance, reciprocal kinship graphs, and vital plausibility. | `docs/tools/runbook-gpa.md` |
| `gfi.py` | `tools/ops/` | Ops | Fact intake: Factoid envelope staging, quarantine routing, and master appending. | `docs/tools/runbook-gfi.md` |
| `gtr.py` | `tools/ops/` | Ops | Token registry: Controlled vocabulary auditing and colloquial alias normalization. | `docs/tools/runbook-gtr.md` |
| `facts_insp.py` | `tools/ops/` | Ops | Fact inspection: Plausibility audits and post-mortem vital exemptions. | `docs/tools/runbook-facts_insp.md` |
| `facts_md.py` | `tools/ops/` | Ops | Narrative renderer: Chronological timeline and biographical Markdown formatting. | `docs/tools/runbook-facts_md.md` |
| `facts_merge.py` | `tools/ops/` | Ops | Fact consolidation: 6-group resolution engine and in-place tombstoning. | `docs/tools/runbook-facts_merge.md` |
| `gix.py` | `tools/ops/` | Ops | Index engine: Builds and refreshes secondary indexes in `data/indexes/`. | `docs/tools/runbook-gix.md` |
| `gsi.py` | `tools/sys/` | System | Script importer: Header parsing, safe backups, canonical routing, and pytest runs. | `docs/tools/runbook-gsi.md` |
| `install_hooks.py` | `tools/sys/` | System | Git hook deployment: Installs pre-commit and pre-push hooks with POSIX permissions. | `docs/tools/runbook-install_hooks.md` |

---

## 3. Mandatory Operational Tool Invariants
Every production tool within `tools/ops/` must strictly comply with four operational standards:

* **Pre-Execution Safe Backup Protocol:** Any tool executing mutations, appends, or replacements against production data (`data/`) or token registries (`schemas/naming/_token_registry.json`) must trigger an atomic pre-write backup snapshot in `backups/` (`[filename].[YYYYMMDD_HHMMSS].bk`) via `GDAUtil` prior to committing changes.
* **PEP 440 Module Versioning:** Every operational tool must declare a module-level `__version__` string conforming to PEP 440 local build identifiers (`__version__ = "<major>.<minor>.<rev>+build.<YYYYMMDD>.<counter>"`).
* **Standardized Logging Subsystem:** Operational scripts must route dual-handler execution traces (console and file) through `GDALogger` directly to `logs/[tool-name]-[timestamp].log`.
* **Standard CLI Interface:** Tools must implement standard `argparse` arguments:
  * `-h`, `--help`: Usage syntax and argument reference.
  * `-v`, `--verbose`: Emits detailed diagnostic execution traces to the log.
  * `--debug`: Outputs diagnostic traces directly to `sys.stderr` or stdout.

---

## 4. Domain & State Invariants
* **In-Place Entity Lifecycle:** Merging, deduplication, or absorption tools must adhere to the in-place tombstoning standard; superseded entities remain in their primary stores marked with deprecation flags and replacement pointers.
* **Mandatory Timestamp Updates:** Any write operation, property edit, or tombstone transition must update the target record's `updated_at` / `last_modified` timestamp to the current UTC ISO 8601 string.
* **Decoupled Downstream Indexing:** Operational intake and editing tools must remain strictly decoupled from secondary index generation. Downstream indexers evaluate `last_modified` timestamps independently to determine re-indexing requirements.

---

## 5. Documentation & Promotion Standards
Operational tools must maintain a corresponding 4-tier operational runbook in `docs/tools/runbook-[tool].md` and register in `docs/index.md` as specified in `topic_documentation_standards.md`. Specific method contracts, flags, and diagnostic matrices are maintained in their respective runbooks and PEP 257 / Google-style docstrings.