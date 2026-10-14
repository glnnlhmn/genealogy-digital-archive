<!--
Name: reference.md
Path: docs/lib/gda_core/reference.md
-->
# Technical Specification: ReferenceManager (Entity IDs & References)
<!-- Version: 1.1.0+build.20260930.1 -->

| Property | Value |
| :--- | :--- |
| **Module Name** | `reference.py` |
| **Module Path** | `tools/lib/gda_core/reference.py` |
| **Version** | `1.1.0+build.20260930.3` |
| **Test Suite** | `tests/gda_core/test_reference.py` |
| **Package** | `tools.lib.gda_core` |
| **Dependencies** | `re`, `json`, `pathlib` |

## 1. Developer Reference & API Specification

### Operational Intent
`ReferenceManager` validates primary key syntax, constructs and parses standardized archive URNs, and loads/caches static tabular lookups from `data/reference/`.

### Core API Methods

* `is_valid_person_id(person_id: str) -> bool`
  * Validates whether a string matches the canonical person ID pattern (`^IND-\d{5}$`).
* `is_valid_fact_id(fact_id: str) -> bool`
  * Validates standard lowercase UUIDv4 format (`^[a-f0-9]{8}-...-[a-f0-9]{12}$`).
* `parse_urn(urn: str) -> Optional[Dict[str, str]]`
  * Parses `urn:gda:<namespace>:<entity_id>` into component dictionary (`{"namespace": ..., "entity_id": ...}`).
* `build_urn(namespace: str, entity_id: str) -> str`
  * Formats canonical URN strings (e.g. `urn:gda:person:IND-00042`).
* `get_table(table_name: str) -> Dict[str, Any]`
  * Loads and caches static JSON reference tables from `data/reference/<table_name>.json`.
* `get_colloquial_states() -> Dict[str, str]`
  * Returns dictionary mapping colloquial US state abbreviations and historical aliases to canonical state names.
* `clear_cache() -> None`
  * Evicts all cached reference tables from memory.