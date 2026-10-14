<!--
Name: GDALocations.md
Path: docs/lib/gda_core/GDALocations.md
-->
# Core Framework Library: `GDALocations`

`GDALocations` is the master registry manager governing civil jurisdictions, administrative hierarchies, and historical boundary shifts stored in `data/entities/locations.json`.

---

## Technical Overview

Civil jurisdictions form the administrative foundation for all genealogical assertions in GDA. Because municipal and county boundaries shift, divide, and dissolve over time, `GDALocations` models jurisdictions as first-class temporal entities rather than simple text strings.

### Key Capabilities
* **Offline US State Normalization:** Integrates the `us` package to validate and resolve USPS postal codes and colloquial abbreviations (`PA` -> `Pennsylvania`).
* **Hierarchical Jurisdiction Lookup:** Structured queries matching combinations of `country`, `state_or_province`, `county`, and `local_jurisdiction`.
* **Temporal Lineage Tracking:** Resolves legal boundary validity at specific historical dates via `is_valid_at_date()` and traverses predecessor/successor splits (`get_predecessor()`, `get_successor()`).
* **Multi-Strategy Search:** Ranks search results across canonical names, structured components, and alias variants using exact matching, glob wildcard patterns (`*Frankford*`), and fuzzy string similarity.
* **Decoupled Persistence:** Supports isolated scratch testing via `save(output_path=...)` while enforcing atomic pre-write snapshots via `GDAUtil.save_json` on production paths.

---

## Schema Contract

Governed by `schemas/entities/location_registry.schema.json` and `schemas/entities/location.schema.json`.

```json
{
  "location_id": "LOC-00006",
  "canonical_name": "Carlisle, Cumberland County, Pennsylvania, USA",
  "aliases": [
    "Carlisle",
    "Carlisle Borough",
    "Cumberland Co Seat"
  ],
  "jurisdiction": {
    "country": "USA",
    "state_or_province": "Pennsylvania",
    "county": "Cumberland",
    "local_jurisdiction": "Carlisle"
  },
  "temporal_validity": {
    "date_established": "1751-01-27",
    "date_dissolved": null,
    "predecessor_location_id": null,
    "successor_location_id": null
  },
  "notes": [],
  "last_updated": "2026-09-29T12:00:00Z"
}
```

---

## API Reference

### Initialization & Persistence
* **`__init__(filepath=None, auto_load=True)`**: Initializes the registry instance. Defaults to `data/entities/locations.json` via `GDAConfig`.
* **`load() -> None`**: Reads and parses the JSON registry, resetting internal dirty tracking and active view filters.
* **`refresh() -> None`**: Alias for `load()`; reloads state from disk and discards staged in-memory mutations.
* **`save(output_path=None, force=False, create_backup=True) -> bool`**: Atomically persists entities sorted by monotonic numeric ID. When writing to canonical paths, automatically triggers the Safe Backup Protocol.

### State Properties
* **`is_dirty -> bool`**: Returns `True` if in-memory entities have been modified since last load/save.
* **`count -> int`**: Total number of locations in memory.
* **`filtered_count -> int`**: Number of entities currently passing active filter criteria.

### CRUD & ID Minting
* **`exists(location_id: str) -> bool`**: Validates whether a primary key is registered (used for site foreign-key verification).
* **`get_by_id(location_id: str) -> Optional[Dict[str, Any]]`**: Retrieves an isolated copy of a location entity by primary key.
* **`add(country, state_or_province=None, county=None, local_jurisdiction=None, canonical_name=None, location_id=None, aliases=None, date_established=None, date_dissolved=None, predecessor_location_id=None, successor_location_id=None, notes=None) -> str`**: Validates, normalizes, mints monotonic zero-padded `LOC-XXXXX` identifier (if omitted), and stages the entity.
* **`edit(location_id: str, updates: Dict[str, Any], overwrite_none: bool = False) -> bool`**: Applies field-level modifications and sets `is_dirty = True`.
* **`delete(location_id: str) -> bool`**: Removes a location by primary identifier.

### Alias Management
* **`add_alias(location_id: str, alias: str) -> bool`**: Appends a unique alias variant to a location. Marks registry dirty.
* **`remove_alias(location_id: str, alias: str) -> bool`**: Prunes an alias variant from a location. Marks registry dirty.

### Queries & Lineage
* **`find_by_jurisdiction(country, state_or_province=None, county=None, local_jurisdiction=None) -> Optional[Dict[str, Any]]`**: Resolves structured civil components with case-insensitive matching and automatic county suffix normalization.
* **`is_valid_at_date(location_id: str, date_iso: str) -> bool`**: Evaluates whether the location was legally extant at an ISO date string (`YYYY-MM-DD`).
* **`get_predecessor(location_id: str) -> Optional[Dict[str, Any]]`**: Retrieves the predecessor entity for divided or renamed jurisdictions.
* **`get_successor(location_id: str) -> Optional[Dict[str, Any]]`**: Retrieves the successor entity for dissolved or merged jurisdictions.
* **`search(query=None, country=None, state_or_province=None, county=None, use_fuzzy=True, fuzzy_threshold=0.75) -> List[Dict[str, Any]]`**: Searches against canonical names, aliases, and civil parts, returning scored matches.
* **`find_one(query: str, country=None, state_or_province=None, fuzzy_threshold=0.85) -> Optional[Dict[str, Any]]`**: Returns the single highest-scoring match.

### View Filtering & Batch Operations
* **`set_filter(predicate=None, country=None, state_or_province=None, county=None, name_pattern=None) -> int`**: Constrains subsequent query operations to matching records.
* **`clear_filter() -> None`**: Restores working set to the full registry.
* **`get_filtered() -> List[Dict[str, Any]]`**: Returns list of records in the active filtered view.
* **`update_filtered(updates: Dict[str, Any]) -> int`**: Applies batch modifications across all locations matching active filter.

---

## Usage Example

```python
from tools.lib.gda_core.GDALocations import GDALocations

# Initialize registry
locations = GDALocations()

# Structured lookup
loc = locations.find_by_jurisdiction(
    country="USA",
    state_or_province="PA",
    county="Cumberland",
    local_jurisdiction="Carlisle"
)

# Check historical validity during a census year
if loc:
    is_valid = locations.is_valid_at_date(loc["location_id"], "1850-06-01")
    print(f"Extant in 1850: {is_valid}")

# Add alias variant discovered in probate documents
locations.add_alias(loc["location_id"], "Carlisle Borough")

# Commit changes with Safe Backup
locations.save()
```