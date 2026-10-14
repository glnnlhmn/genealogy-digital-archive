<!--
Name: schema_enums.md
Path: docs/lib/gda_core/schema_enums.md
-->
# Technical Specification: GDASchemaEnums (Controlled Vocabularies)
<!-- Version: 1.1.0+build.20260930.1 -->

| Property | Value |
| :--- | :--- |
| **Module Name** | `schema_enums.py` |
| **Module Path** | `tools/lib/gda_core/schema_enums.py` |
| **Version** | `1.1.0+build.20260930.2` |
| **Test Suite** | `tests/gda_core/test_schema_enums.py` |
| **Package** | `tools.lib.gda_core` |
| **Dependencies** | `json`, `pathlib` |

## 1. Developer Reference & API Specification

### Operational Intent
`GDASchemaEnums` dynamically reflects controlled vocabularies directly from `schemas/defs/_enums.schema.json`. It provides in-memory caching and fast set lookups for fact types, date modifiers, union statuses, and kinship roles.

### Core API Methods

* `GDASchemaEnums[enum_name: str] -> List[str]`
  * Class subscription syntax returning permitted values for a schema definition (e.g. `GDASchemaEnums["enum_sex"]`).
* `get_allowed(enum_name: str) -> Set[str]`
  * Returns set of permitted string options, or an empty set if unmapped.
* `get_fact_types() -> Set[str]`
  * Resolves approved fact types from `fact_type` or `enum_fact_type` definitions.
* `get_date_modifiers() -> Set[str]`
  * Resolves approved date qualifiers (`EXACT`, `ABOUT`, `ESTIMATED`).
* `get_union_statuses() -> Set[str]`
  * Resolves approved relationship statuses (`MARRIED`, `DIVORCED`, etc.).
* `get_kinship_roles() -> Set[str]`
  * Resolves approved family roles (`FATH`, `MOTH`, `CHIL`, `SPOU`).
* `is_valid(enum_name: str, value: Optional[str]) -> bool`
  * Validates value conformity against named enum. Permissively returns `True` for `None` or unmapped keys.
* `clear_cache() -> None` / `reset_cache() -> None`
  * Flushes vocabulary cache and clears any custom test schema overrides.