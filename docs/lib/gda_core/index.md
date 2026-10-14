<!--
Name: index.md
Path: docs/lib/gda_core/index.md
-->
# Core Framework Library: `tools.lib.gda_core`
<!-- Version: 1.1.0+build.20260930.1 -->

The `gda_core` package provides foundational architecture, immutable configuration singletons, structured logging, dynamic schema reflection, and filesystem safeguards shared across operational tools (`tools/ops/`), system utilities (`tools/sys/`), and verification suites (`tests/`).

## Architectural Topology

* `tools/lib/gda_core/__init__.py`: Package exports and version metadata (`__version__ = "1.1.0+build.20260930.1"`).
* `tools/lib/gda_core/config.py`: Centralized `GDAConfig` singleton and filesystem directory anchors.
* `tools/lib/gda_core/logger.py`: Dual-handler logging (`setup_logger`) and `GDALogFormatter` with action tags.
* `tools/lib/gda_core/reference.py`: Canonical URN parsing, identifier validation, and static table cache.
* `tools/lib/gda_core/schema_enums.py`: Dynamic JSON Schema controlled vocabulary registry (`GDASchemaEnums`).
* `tools/lib/gda_core/util.py`: Safe Backup Protocol, atomic JSON I/O, SHA-256 digests, and workspace hygiene.

## Component Architecture & Contracts

| Module | Primary Class | Role & Invariants | Specification |
| :--- | :--- | :--- | :--- |
| `config.py` | `GDAConfig`, `CONFIG` | Single configuration authority; anchors filesystem to repository root; provides immutable path accessors. | [config.md](config.md) |
| `logger.py` | `setup_logger`, `GDALogFormatter` | Dual interactive/file logging with structured action tags (`[SYS]`, `[NEW]`, `[ADD]`, etc.). | [logger.md](logger.md) |
| `reference.py` | `ReferenceManager` | Validates `IND-XXXXX` and UUIDv4 keys; parses canonical URNs; caches static reference tables. | [reference.md](reference.md) |
| `schema_enums.py` | `GDASchemaEnums` | Dynamically resolves and caches controlled vocabularies directly from `_enums.schema.json`. | [schema_enums.md](schema_enums.md) |
| `util.py` | `GDAUtil` | Transactional filesystem safety via the Safe Backup Protocol, atomic UTF-8 file replacement, and SHA-256 digests. | [util.md](util.md) |

## System Invariants

1. **100% Statement & Branch Coverage:** Every module in `gda_core` maintains 100% statement and branch coverage verified by atomized pytest harnesses in `tests/gda_core/`.
2. **Transactional Pre-Write Snapshots:** All operational mutations against persistent data must invoke `GDAUtil.create_safe_backup()` prior to writing.
3. **Single Source of Truth:** Controlled vocabularies are never hardcoded; they reflect dynamically from `schemas/defs/_enums.schema.json`.
4. **Hermetic Test Isolation:** All paths resolve dynamically via `GDAConfig.load()`, allowing `tests/conftest.py` to seamlessly isolate test suites inside `tmp_path` sandboxes.

## Installation as a Local Package

Install in editable mode within the repository virtual environment:

```powershell
pip install -e .