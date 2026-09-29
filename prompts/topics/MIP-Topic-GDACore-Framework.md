<!--
Name: MIP-Topic-GDACore-Framework.md
Path: prompts/topics/MIP-Topic-GDACore-Framework.md
-->
# Topic Specification: GDA Core Framework Architecture
<!-- Version: 1.0.1 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Operational Intent
`tools/lib/gda_core/` houses the foundational singleton services, configuration resolvers, logging subsystems, and controlled vocabulary managers shared across all operational CLI tools (`tools/ops/`), developer utilities (`tools/sys/`), and test harnesses (`tests/`).

---

## 2. Framework Component Contracts

### 2.1 GDAConfig (`tools/lib/gda_core/GDAConfig.py`)
Centralized singleton configuration managing filesystem anchoring, path resolution, and environment verification.
* **Root Anchor Resolution:** Dynamically anchors to repository root `G:/My Drive/genealogy-digital-archive` with deterministic fallback to parent directory traversal when executed in alternative sandboxes.
* **Property Path Accessors:** Exposes immutable `Path` properties:
  * Directories: `entities_dir`, `indexes_dir`, `media_dir`, `quarantine_dir`, `profiles_dir`, `backups_dir`, `logs_dir`, `reports_dir`.
  * Schemas: `schema_defs_dir`, `schema_entities_dir`, `token_registry_path`.
* **Manifest Validation:** Validates `gda_config.json` manifest schema tracking and ensures runtime paths exist prior to file operations.

### 2.2 GDALogger (`tools/lib/gda_core/GDALogger.py`)
Standardized logging subsystem enforcing consistent output formatting across interactive terminals and persistent audit logs.
* **`GDALogFormatter` Mechanics:** Automatically enriches log records with timestamps, standardized log levels (`INFO`, `WARN`, `ERROR`, `DEBUG`), and deduplicates system tags (`[SYS]`) on framework-level lifecycle events.
* **Dual Handler Pattern:**
  * Interactive Stream: Emits clean, actionable lines to `sys.stderr` / `sys.stdout`.
  * Persistent File Handler: Writes uncompressed UTF-8 traces to `logs/[tool-name]-[timestamp].log`.
* **Ephemeral Mode:** Redirects tool output to `gtemp/[script]-[timestamp].log` when running scratch utilities.

### 2.3 GDAUtil (`tools/lib/gda_core/GDAUtil.py`)
Shared atomic I/O routines, data manipulation utilities, and filesystem safeguards.
* **Safe Backup Protocol (`create_safe_backup`):** Creates an atomic, pre-write copy of target files in `backups/[filename].[YYYYMMDD_HHMMSS].bk` before destructive writes or appends.
* **Atomic JSON Serialization (`save_json`):** Writes JSON payloads to a temporary sibling file (`[filename].tmp`) before executing an atomic filesystem rename (`os.replace`). Enforces `encoding="utf-8"`, `indent=2`, and ensures parent directories exist.
* **Integrity Hashing (`calculate_sha256`):** Generates deterministic SHA-256 hex digests across entity registries, raw media assets, and manifest records.
* **Quarantine Handler (`quarantine_payload`):** Safely isolates malformed or unparseable payloads to `data/entities/quarantine/` with diagnostic metadata.

### 2.4 GDASchemaEnums (`tools/lib/gda_core/GDASchemaEnums.py`)
Dynamic vocabulary resolver providing schema-backed enum validation without code-level duplication.
* **Single Source of Truth:** Loads vocabulary definitions directly from `schemas/defs/_enums.schema.json` using `GDAConfig.schema_defs_dir`.
* **Runtime Caching:** Caches enum definitions in memory upon initial load to ensure zero disk I/O overhead during batch loops.
* **Backward Compatibility:** Exports `SchemaEnums` as an alias to `GDASchemaEnums`[cite: 5].
* **Supported Domains:** Exposes sets and validation methods for `fact_type`, `date_modifier`, `union_status`, and `kinship_role`.

---

## 3. Profile Architecture Integration (`data/profiles/`)
* **Operator Dossier (`glenn_profile.json`):** JSON-structured profile (SchemaVersion 1.0.5) defining personal context, communication tone, and developer conventions[cite: 14].
* **System Ledger & Backlog Store (`gda_profile.json`):** Structured repository ledger tracking strategic architecture decisions, test coverage matrices, and the master operational to-do backlog[cite: 15]. Tools querying task states or system backlog read and update this structured JSON file directly.