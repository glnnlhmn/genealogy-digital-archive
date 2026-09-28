# Topic Specification: GDA Core Framework Architecture
<!-- Version: 1.0.0 -->
<!-- Location: prompts/topics/MIP-Topic-GDACore-Framework.md -->

## 1. Operational Intent
`tools/lib/gda_core/` provides the shared runtime foundation for the repository archive, managing environment resolution, standardized logging, atomic data protection, and centralized vocabulary registries.

---

## 2. Framework Components

### GDAConfig (`tools/lib/gda_core/GDAConfig.py`)
Centralized singleton configuration managing path resolution and manifest integrity:
* **Root Anchor:** Dynamically binds to `G:/My Drive/genealogy-digital-archive` with fallback to parent directory traversal.
* **Path Properties:** Exposes immutable path getters for data directories (`entities`, `indexes`, `media`, `quarantine`), schemas (`schema_defs`, `schema_entities`), and runtime output paths (`backups`, `logs`, `reports`).
* **Manifest Verification:** Verifies tracked schemas and prompt specifications declared in `gda_config.json`.

### GDALogger (`tools/lib/gda_core/GDALogger.py`)
Standardized logging subsystem enforcing event-aware formatting:
* **GDALogFormatter:** Formats records with timestamps, log levels, and automatic `[SYS]` tag deduplication for system-level lifecycle events.
* **Dual Handlers:** Initializes concurrent console streams and UTF-8 timestamped file loggers (`logs/[tool]-[timestamp].log`).
* **Ephemeral Routing:** Supports scratch execution logging routed to `gtemp/`.

### GDAUtil (`tools/lib/gda_core/GDAUtil.py`)
Atomic data manipulation and filesystem utilities:
* **Safe Backup Protocol:** Executes pre-write atomic snapshots into `backups/[filename].[YYYYMMDD_HHMMSS].bk` prior to write or append operations.
* **Atomic JSON Serialization:** Uses temporary file writing followed by atomic replacement (`os.replace`) with UTF-8 encoding and indented formatting.
* **Integrity Hashing:** Calculates SHA-256 digests across archival assets and manifest tracking tables.
* **Quarantine Routing:** Safely isolates non-conforming or corrupted payloads into `data/entities/quarantine/`.

### SchemaEnums (`../../tools/lib/gda_core/GDASchemaEnums.py`)
Dynamic vocabulary resolver loading definitions directly from `schemas/defs/_enums.schema.json`:
* **Single Source of Truth:** Centralizes valid enumerations for `fact_type`, `date_modifier`, `union_status`, and `kinship_role`.
* **Zero Hardcoding:** Prevents drift by resolving valid vocabulary choices dynamically at runtime.
