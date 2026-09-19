# Architecture: Package & Directory Structure
<!-- Version: 1.0.0 -->

* **Document:** Package & Directory Architecture
* **Path:** `docs/architecture/package_structure.md`
* **Root Anchor:** `G:/My Drive/genealogy-digital-archive`

---

## 1. Directory Topology

```text
genealogy-digital-archive/
|-- gda_config.json             # System baseline configuration manifest
|-- gda_config.json.bk          # Single-level safe backup of manifest
|-- .gitignore                  # VCS exclusions (gtemp/, logs/, reports/, venv/, .idea/)
|-- backups/                    # Timestamped atomic backups ([file].[timestamp].bk)
|-- gtemp/                      # Temporary scripts, scratchpads, and execution workspaces
|-- logs/                       # Permanent operational tool execution logs
|-- reports/                    # Generated system integrity, audit, and analysis reports
|-- import/                     # Raw intake staging pipeline
|   \-- hold/                   # Pending review, unverified, or problematic incoming assets
|-- data/                       # Production archival data stores
|   |-- archival_records/       # Core source documents (includes deprecated/)
|   |-- entities/               # Canonical records (people, families, places, orgs)
|   |-- indexes/                # Search indices and cross-reference registries
|   |-- media/                  # Ingested, production-ready digital assets
|   |-- queues/                 # Ingestion trackers and pipeline queues
|   |-- stories/                # Compiled biographical and historical narratives
|   \-- transcript/             # Document and record transcriptions
|-- schemas/                    # System data models and validation specifications
|   |-- defs/                   # Reusable base primitives, types, and enums
|   |-- entities/               # Core entity structures
|   |-- indices/                # Index and lookup table specifications
|   |-- naming/                 # Standard slug and file naming rules
|   |-- sources/                # Citation and source formatting schemas
|   \-- archive/                # Deprecated schemas (excluded from active scans)
|-- tools/                      # Automation tooling and utilities
|   |-- ops/                    # Permanent operational tools (Read/Write; e.g., gna.py)
|   \-- lib/                    # Shared modules and utility libraries
\-- docs/                       # System documentation and manuals
    |-- architecture/           # Structural blueprints and environment setups
    |-- defs/                   # Technical definitions and protocols
    \-- tools/                  # Runbooks and CLI usage manuals
```

---

## 2. Directory Roles & Access Rules

### `tools/ops/` vs. `gtemp/`
* **`tools/ops/`:** Production-grade permanent tools. Standard CLI flags (`--help`, `--verbose`, `--debug`) are supported, and execution traces write directly to `logs/[tool]-[timestamp].log`.
* **`gtemp/`:** Disposable scratch workspace. Scripts follow numeric prefixes (`XX_[purpose].py`). Execution logs write locally to `gtemp/`.

### `backups/` vs. `schemas/archive/`
* **`backups/`:** Dedicated repository for automated pre-execution data snapshots (`[filename].[YYYYMMDD_HHMMSS].bk`) created via the Safe Backup Protocol prior to writes in `data/`.
* **`schemas/archive/`:** Preserves deprecated schemas and configurations. Version management of operational code is tracked via Git tags, keeping active production trees clean.

---

## 3. IDE & Environment Configuration (PyCharm)

* **Interpreter:** Local virtual environment (`venv/`) targeting Python 3.10+.
* **Project Root:** Set to `G:/My Drive/genealogy-digital-archive`.
* **Path Exclusions:** Mark the following directories as **Excluded** in PyCharm settings to prevent indexing overhead, unwanted search noise, and accidental modifications:
  * `gtemp/`
  * `logs/`
  * `reports/`
  * `backups/`
  * `schemas/archive/`