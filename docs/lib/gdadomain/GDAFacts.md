<!--
Name: GDAFacts.md
Path: docs/lib/gdadomain/GDAFacts.md
-->
# Technical Specification: GDAFacts (Core Fact Registry Container)

| Property | Value |
| :--- | :--- |
| **Component** | `GDAFacts` |
| **Package** | `gdadomain` |
| **Module Path** | `tools/lib/gdadomain/src/gdadomain/facts.py` |
| **Version** | `1.2.0+build.20261005.1` |
| **Target Stores** | `data/entities/facts.json`, `data/entities/facts_archive.json` |
| **Test Suite** | `tools/lib/gdadomain/tests/test_entity_facts.py` |
| **Dependencies** | `gdacore.config`, `gdacore.introspectable`, `gdacore.logger`, `gdacore.reference_manager`, `gdacore.util`, `gdacore.vocabulary_manager` |
| **Safe Backup Target** | `backups/facts.json.[timestamp].bk`, `backups/facts_archive.json.[timestamp].bk` |

---

## 1. Developer Reference & API Specification

### Operational Intent
`GDAFacts` is the transactional, in-memory management container for active assertions (`data/entities/facts.json`) and archival assertions (`data/entities/facts_archive.json`). It maintains multi-index lookup structures (primary identity, person cross-referencing across primary and associated roles, location indexing, and fact type indexing), enforces reciprocal kinship parity, facilitates bulk foreign key cascading following merges, and guarantees atomic filesystem persistence via the Safe Backup Protocol.

### Core API Methods

#### Context Management & Session Control
* `GDAFacts(facts_path: Optional[Path] = None, archive_path: Optional[Path] = None, auto_commit: bool = True, logger: Optional[Logger] = None)`
  * Instantiates the container, defaulting active facts to `CONFIG.entities / "facts.json"` and archival facts to `CONFIG.entities / "facts_archive.json"`. Loads disk state via `_load()`.
* `__enter__() -> GDAFacts` / `__exit__(exc_type, exc_val, exc_tb) -> None`
  * Python context manager semantics. Automatically invokes `save()` upon normal exit if `is_dirty` is `True`. Aborts persistence if an unhandled exception occurs.
* `save(create_backup: bool = True) -> bool`
  * Persists dirty active and archival registries via `GDAUtil.save_json()`, generating timestamped backups in `backups/`. Clears dirty flags.
* `reload() -> None`
  * Discards staged in-memory mutations and reloads clean state from disk.
* `rollback() -> None`
  * Legacy domain alias for `reload()`.

#### Retrieval & Inspection Interface
* `exists(fact_id: str) -> bool`
  * Checks whether a fact assertion exists in the active registry by exact 36-character UUIDv4 or unique 8+ character prefix match.
* `get(fact_id: str) -> Optional[dict]`
  * Resolves a fact assertion by exact 36-character UUIDv4 or 8+ character prefix match. Returns `None` if absent or ambiguous.
* `get_fact(fact_id: str) -> Optional[dict]`
  * Legacy domain alias for `get()`.
* `get_facts_for_person(person_id: str, include_roles: bool = True) -> list[dict]`
  * Queries `_person_xref` for assertions associated with a person. When `include_roles=True`, returns facts where the person is the primary subject or registered in `associated_people`.
* `get_facts_by_location(location_id: str) -> list[dict]`
  * Queries `_location_xref` for facts occurring at the specified location identifier.
* `get_facts_by_type(fact_type: str) -> list[dict]`
  * Queries `_type_xref` for assertions matching a specific controlled fact type.
* `existing_ids -> set[str]`
  * Returns the set of all active canonical `fact_id` values indexed in memory.
* `is_dirty -> bool`
  * Returns `True` if active assertions or archival stores have unpersisted mutations.
* Container Protocols: `__len__() -> int`, `__iter__() -> Iterator[dict]`, `__contains__(fact_id: str) -> bool`.

#### Mutation & Remediation Interface
* `add(fact_data: dict) -> str`
  * Auto-mints a lowercase UUIDv4 if omitted, validates schema and vocabularies, appends to the active registry, updates all secondary indices, and stages changes. Returns the canonical `fact_id`.
* `add_fact(fact_data: dict) -> str`
  * Legacy domain alias for `add()`.
* `edit(fact_id: str, new_fact: dict) -> bool`
  * Replaces an existing active record in-place, preserving array ordering while strictly enforcing `fact_id` immutability.
* `replace_fact(fact_id: str, new_fact: dict) -> bool`
  * Legacy domain alias for `edit()`.
* `delete(fact_id: str) -> bool`
  * Deletes a fact assertion from active memory and updates all secondary indices.
* `remove_fact(fact_id: str) -> bool`
  * Legacy domain alias for `delete()`.
* `repoint_person(new_person_id: str, old_person_ids: list[str]) -> int`
  * Cascades bulk person merges across primary subject and associated roles.
* `repoint_locations(new_location_id: str, old_location_ids: list[str]) -> int`
  * Cascades bulk location merges across all matching assertions.
* `verify_reciprocal_facts(fact_id: str) -> tuple[bool, list[dict]]`
  * Inspects kinship assertions per `MIP-Topic-People-Domain` without mutation. Returns `(is_reciprocated, missing_templates)`.
* `add_reciprocal_facts(fact_id: str) -> list[str]`
  * Mints and inserts missing reciprocal kinship facts discovered by `verify_reciprocal_facts()`.
* `archive_fact(fact_id: str, canonical_id: Optional[str] = None, reason: str = "") -> bool`
  * Transfers an assertion to `facts_archive.json` with provenance timestamps.
* `unarchive_fact(fact_id: str, reason: str = "") -> bool`
  * Restores an archived assertion back into active registry, clearing archival provenance flags.
* `validate_fact_schema(fact_data: dict) -> list[str]`
  * Validates schema structure, ID formats via `GDAReferenceManager`, and controlled vocabularies via `GDAVocabularyManager`.

---

## 2. Technical Architecture & Invariants

### Inverted Index Architecture
`GDAFacts` maintains five concurrent in-memory indexes rebuilt upon load and mutation:
1. `_index`: Exact `fact_id -> dict` mapping.
2. `_person_xref`: Inverted index mapping `person_id -> list[dict]` across primary subjects and `associated_people`.
3. `_location_xref`: Inverted index mapping `location_id -> list[dict]`.
4. `_type_xref`: Inverted index mapping `fact_type -> list[dict]`.
5. `_archive_index`: Archival index mapping `fact_id -> dict` for assertions preserved in `facts_archive.json`.

### Safe Backup Protocol Integration
Any mutation to active records or archival records flags `dirty_ids` or `archive_dirty`. `save()` will not touch disk unless `is_dirty` is `True`. When dirty, an atomic pre-write snapshot is preserved in `backups/` before `GDAUtil.save_json()` executes.

---

## 3. Verification Harness & Diagnostics

### Test Execution Command
```powershell
pytest tools/lib/gdadomain/tests/test_entity_facts.py -v --cov=gdadomain.facts --cov-branch --cov-report=term-missing --basetemp=gtemp/pytest_tmp
```

### Diagnostic Matrix

| Diagnostic / Error Signature | Root Cause & Resolution |
| :--- | :--- |
| `ValueError: Fact schema validation failed: ...` | Provided payload violates `GDAReferenceManager` ID patterns or `GDAVocabularyManager` fact types. |
| `ValueError: fact_id is immutable. Cannot replace '[ID1]' with '[ID2]'.` | Caller attempted to alter `fact_id` during replacement. Fact IDs cannot be modified. |
| `ValueError: Fact with ID '[ID]' already exists.` | Attempted to `add()` with an identifier already indexed in `_index`. Consolidate or mint a distinct UUIDv4. |
| `ValueError: Cannot unarchive fact '[ID]': already exists in active registry.` | An active assertion with that UUID is already present in `facts.json`. Reconcile duplicate before unarchiving. |
| `KeyError: Fact with ID '[ID]' not found.` | `verify_reciprocal_facts()` called on a non-existent fact ID. Ensure ID exists in active registry. |
