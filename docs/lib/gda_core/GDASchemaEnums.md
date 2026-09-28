<!--
Name: GDASchemaEnums.md
Path: docs/lib/gda_core/GDASchemaEnums.md
-->
# Technical Specification: GDASchemaEnums (Controlled Vocabulary Registry)

| Property | Value |
| :--- | :--- |
| **Module Name** | `GDASchemaEnums.py` |
| **Module Path** | `tools/lib/gda_core/GDASchemaEnums.py` |
| **Version** | `1.0.0+build.20260927.1` |
| **Test Suite** | `tests/unit/test_gda_schema_enums.py` |
| **Package** | `tools.lib.gda_core` |
| **Dependencies** | `GDAConfig`, `json`, `pathlib` |

---

## 1. Developer Reference & API Specification

### Operational Intent
`GDASchemaEnums` (aliased as `SchemaEnums` for backwards compatibility) provides a centralized, cached lookup and validation engine for all archive controlled vocabularies. It dynamically extracts enum definitions from `schemas/defs/_enums.schema.json` and supports graceful fallback cascades, cross-population from shared schema definitions, and safe exception recovery.

### Core API Methods

#### Vocabulary Subscription & Access
* `GDASchemaEnums[enum_name: str] -> List[Any]`
  * Direct class-level indexing (e.g., `SchemaEnums["enum_fact_type"]`).
  * Returns the defined vocabulary list for the given enum key.
  * Raises `KeyError` if the requested enum is unmapped across schema definitions.
* `get_allowed(enum_name: str) -> Set[Any]`
  * Returns the allowed values of an enum as a Python set for rapid membership testing.
  * Returns an empty set `set()` if the enum is unmapped.

#### Validation & Cache Management
* `is_valid(enum_name: str, value: Any) -> bool`
  * Validates whether a value is permissible under the specified enum definition.
  * Returns `True` if `value` is `None` (permitting optional unpopulated attributes).
  * Returns `True` if the `enum_name` is unmapped (non-restrictive default).
  * Returns `True` if `value` is in the allowed set, otherwise `False`.
* `reset_cache() -> None`
  * Flushes the in-memory cache lists and sets. Forces subsequent queries to reload and re-parse schema files from disk.

---

## 2. Technical Architecture & Invariants

### Schema Discovery & Fallback Cascade
When initializing or populating cache state, `_load_enums()` resolves schemas in the following deterministic sequence:
1. **Primary Target:** Path defined by `CONFIG.enums` (`schemas/defs/_enums.schema.json`).
2. **Fallback 1:** Legacy location `CONFIG.schema_defs / "enums.schema.json"`.
3. **Fallback 2:** Shared definitions file `CONFIG.schema_defs / "_shared_defs.schema.json"`.
4. **Missing Safeguard:** If no candidates exist, initializes empty in-memory caches without raising filesystem errors.

### Cross-Population Protocol
If the resolved primary target is not `_shared_defs.schema.json`, `GDASchemaEnums` inspects `CONFIG.schema_defs / "_shared_defs.schema.json"`. Any non-overlapping enum definitions present in `_shared_defs` that do not exist in the primary registry are cross-populated. Definitions in the primary schema always take strict precedence and are never overwritten.

### Error Resilience & Cache Invariants
* **Malformed JSON Suppression:** If an enum schema file contains syntax errors or corrupt JSON, `GDASchemaEnums` intercepts the parsing exception and safely falls back to empty cache sets, protecting consuming tools from fatal crashes during bootstrap.
* **Warm Cache Short-Circuiting:** Once populated, calls bypass filesystem I/O entirely until `reset_cache()` is called.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/unit/test_gda_schema_enums.py`
* **Coverage Scope:** 100.00% statement and branch coverage verifying primary vocabulary lookups, fallback chains, cross-population collisions, cache warm hits, and unmapped key error states.
* **Execution:**
```powershell
# Fast unit validation
pytest -m unit tests/unit/test_gda_schema_enums.py -v

# Verification with 100% coverage check
pytest tests/unit/test_gda_schema_enums.py --cov=tools.lib.gda_core.GDASchemaEnums --cov-report=term-missing
```

### Diagnostic Matrix

| Diagnostic / Error Signature | Root Cause & Resolution |
| :--- | :--- |
| `KeyError: "Enum '[enum_name]' not found in archive schemas."` | The requested enum key is not defined under `$defs` in `_enums.schema.json`. Check `schemas/defs/_enums.schema.json` for vocabulary name accuracy. |
| Validation failure (`is_valid(...) is False`) | Value violated the controlled vocabulary constraint. Verify permitted values using `GDASchemaEnums.get_allowed(...)`. |
