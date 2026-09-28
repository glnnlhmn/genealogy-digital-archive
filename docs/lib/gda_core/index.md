<!--
Name: index.md
Path: docs/lib/gda_core/index.md
-->
# Core Framework Library: `tools.lib.gda_core`

The `gda_core` package provides the foundational architecture, configuration singletons, transactional entity containers, and filesystem safeguards shared across all operational tools (`tools/ops/`) in the Genealogy Digital Archive.

---

## Architecture Overview

All tools in the archive interact with underlying file stores through `gda_core` abstractions rather than performing direct ad-hoc filesystem I/O. This ensures:
* **Single Configuration Authority:** Paths anchor deterministically via `GDAConfig`.
* **Zero Data Loss:** Write operations execute through the Safe Backup Protocol.
* **Controlled Vocabularies:** Value constraints resolve against centralized schema definitions.
* **Hermetic Test Isolation:** Core objects can be sandboxed in `tmp_path` without mutating production registries.

```text
                    ┌─────────────────────────┐
                    │        GDAConfig        │
                    │ (Paths, Config, Enums)  │
                    └────────────┬────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│     GDAUtil      │   │  GDASchemaEnums  │   │     GDAFacts     │
│ (Backups, JSON,  │   │  (Vocabularies,  │   │ (Facts Registry, │
│  Hashing, Temp)  │   │   Validation)    │   │  Index & Xref)   │
└──────────────────┘   └──────────────────┘   └──────────────────┘
```

---

## Core Modules & Technical Specifications

### 1. [GDAConfig](GDAConfig.md)
* **Role:** Centralized configuration singleton and environment resolver.
* **Responsibilities:** Resolves root anchors (`G:/My Drive/genealogy-digital-archive`), manages runtime configuration (`gda_config.json`), provides absolute paths for all data stores, entities, schemas, and reports.

### 2. [GDAFacts](GDAFacts.md)
* **Role:** Transactional container and indexing engine for `data/entities/facts.json`.
* **Responsibilities:** Manages primary UUID index (`_index`) and secondary foreign-key index (`_person_xref`), tracks dirty state, enforces `fact_id` immutability, and coordinates atomic pre-write backups.

### 3. [GDAUtil](GDAUtil.md)
* **Role:** Operational filesystem utilities and cryptographic routines.
* **Responsibilities:** Executes Safe Backup Protocol (`create_safe_backup`, `restore_backup`, `prune_backups`), chunked SHA-256 calculation, atomic UTF-8 JSON read/write routines, and workspace hygiene (`clear_gtemp`).

### 4. [GDASchemaEnums](GDASchemaEnums.md)
* **Role:** Controlled vocabulary cache and validation engine.
* **Responsibilities:** Parses and caches enum constraints from `schemas/defs/_enums.schema.json`, handles schema discovery fallbacks, and validates entity attributes.

---

## Verification & Testing
The `gda_core` suite maintains strict >= 95% branch coverage with isolated unit and regression test harnesses:

```powershell
# Run smoke tests across the core framework
pytest tests/unit/test_gda_*.py -m smoke -v

# Run full core framework verification with branch coverage
pytest tests/unit/test_gda_*.py -m "unit or regression" --cov=tools.lib.gda_core --cov-report=term-missing
```
