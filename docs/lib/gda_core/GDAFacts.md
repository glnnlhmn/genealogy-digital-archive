<!--
Name: GDAFacts.md
Path: docs/lib/gda_core/GDAFacts.md
-->
# Technical Specification: GDAFacts (Core Fact Registry Container)

| Property | Value |
| :--- | :--- |
| **Module Name** | `GDAFacts.py` |
| **Module Path** | `tools/lib/gda_core/GDAFacts.py` |
| **Version** | `1.0.3+build.20260928.1` |
| **Test Suite** | `tests/unit/test_gda_facts.py` |
| **Package** | `tools.lib.gda_core` |
| **Dependencies** | `GDAConfig`, `GDAUtil`, `logging`, `pathlib` |

---

## 1. Developer Reference & API Specification

### Operational Intent
`GDAFacts` is the transactional, in-memory management container for `data/entities/facts.json`. It maintains dual-index structures (primary identity lookup and inverted person foreign-key cross-referencing), tracks dirty records across mutation lifecycles, and guarantees transactional filesystem safety via automated Safe Backup Protocol integration upon commit.

### Core API Methods

#### Context Management & Session Control
* `GDAFacts(facts_path: Optional[Path] = None, auto_commit: bool = True, logger: Optional[Logger] = None)`
  * Instantiates the container, defaults `facts_path` to `CONFIG.facts`, and parses disk state via `_load()`.
* `__enter__() -> GDAFacts` / `__exit__(exc_type, exc_val, exc_tb) -> None`
  * Implements Python context manager semantics. Automatically invokes `commit()` upon normal exit if `is_dirty` is `True`. Aborts changes if an unhandled exception occurs.
* `commit() -> bool`
  * Generates an atomic pre-write snapshot (`facts.json.[timestamp].bk`) in `backups/` via `GDAUtil.create_safe_backup()` and saves the payload. Resets `dirty_ids`.
* `rollback() -> None`
  * Discards all staged in-memory mutations and reloads clean disk state.

#### Retrieval & Inspection Interface
* `get(fact_id: str) -> Optional[dict]`
  * Resolves a fact assertion by exact 36-character UUIDv4 or 8+ character prefix match. Returns `None` if absent or ambiguous.
* `get_by_person(person_id: str) -> List[dict]`
  * Queries the inverted cross-reference index (`_person_xref`) and returns all assertions assigned to the target person ID. Returns `[]` if unindexed.
* `existing_ids -> Set[str]`
  * Read-only property returning the set of all active canonical `fact_id` values indexed in memory.
* `is_dirty -> bool`
  * Read-only property returning `True` if one or more records are staged in `dirty_ids`.
* `__len__() -> int` / `__iter__() -> Iterator[dict]`
  * Supports standard `len(facts_mgr)` and sequential iteration (`for fact in facts_mgr:`).

#### Mutation & Remediation Interface
* `mark_dirty(fact_id: str) -> None`
  * Flags an existing fact as modified, queuing the session for safe persistence.
* `replace(fact_id: str, new_fact: dict) -> bool`
  * Replaces an existing record in-place within `facts_list`, preserving array ordering.
  * Re-synchronizes `_person_xref` if `person_id` was updated.
  * Enforces `fact_id` immutability: raises `ValueError` if `new_fact['fact_id']` does not match `fact_id`.
* `add(fact: dict) -> bool`
  * Appends a new fact assertion, registers keys in `_index` and `_person_xref`, and marks dirty.
  * Raises `ValueError` if `fact_id` is missing or collides with an existing assertion.
* `remove(fact_id: str) -> bool`
  * Removes an assertion from memory and indices, staging the deletion in `dirty_ids`. Returns `False` if not found.

---

## 2. Technical Architecture & Invariants

### Inverted Foreign Key Architecture (`_person_xref`)
`GDAFacts._person_xref` is strictly an inverted index mapping `person_id -> list[fact_dict]`. It is **not** a complete person registry; individuals present in `data/entities/people.json` with zero asserted facts do not appear in `_person_xref`.

### Strict Primary Key Immutability
Under the GDA Facts Domain Specification, assertion IDs (`fact_id`) are immutable UUIDv4 strings. Methods mutating records (`replace()`) forbid altering the `fact_id`. Re-keying is prohibited; obsolete assertions must be retired or merged via `facts_merge.py`.

### Safe Backup Protocol Integration
Any mutation to `facts_list` flags the target `fact_id` in `dirty_ids`. `commit()` will not touch disk unless `is_dirty` is `True`. Upon confirmation of dirty state, an atomic snapshot is preserved in `backups/` before `GDAUtil.save_json()` executes.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/unit/test_gda_facts.py`
* **Marker Taxonomy:** `@pytest.mark.smoke`, `@pytest.mark.unit`, `@pytest.mark.regression`
* **Execution:**
```powershell
# Fast smoke validation (< 1s)
pytest tests/unit/test_gda_facts.py -v -m smoke

# Complete unit & boundary verification with coverage report
pytest tests/unit/test_gda_facts.py -v -m "unit or regression" --cov=tools.lib.gda_core.GDAFacts --cov-report=term-missing
```

### Diagnostic Matrix

| Diagnostic / Error Signature | Root Cause & Resolution |
| :--- | :--- |
| `ValueError: Replacement fact record must contain a valid 'fact_id'.` | Payload passed to `replace()` is missing the `fact_id` key. Ensure the dictionary retains its identifier. |
| `ValueError: fact_id is immutable. Cannot replace '[ID1]' with '[ID2]'.` | Caller attempted to alter `fact_id` during replacement. Fact IDs cannot be modified. |
| `ValueError: Fact with ID '[ID]' already exists.` | Attempted to `add()` a fact whose UUID is already indexed in `_index`. Consolidate or mint a distinct UUIDv4. |
| Ambiguous short prefix warning in logs | A prefix query of length >= 8 matched multiple UUIDs. Use the full 36-character canonical identifier. |
