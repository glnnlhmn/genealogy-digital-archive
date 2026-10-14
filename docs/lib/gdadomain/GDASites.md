<!--
Name: GDASites.md
Path: docs/lib/gdadomain/GDASites.md
-->
# Domain Entity Library: `GDASites`

`GDASites` is the master registry manager governing physical facilities, cemeteries, churches, landmarks, and residences stored in `data/entities/sites.json`.

---

## Technical Overview

While `GDALocations` models legal and administrative jurisdictions, `GDASites` models physical geographic entities. Every site entity references a parent civil jurisdiction (`location_id`), ensuring clear separation between administrative boundaries and physical structures.

### Key Capabilities
* **Physical Site Classification:** Enforces canonical site categorization (`FACILITY`, `CEMETERY`, `CHURCH`, `LANDMARK`, `RESIDENCE`, `ORGANIZATION`) governed directly by `GDAReferenceManager`.
* **Foreign Key Referential Integrity:** Validates that `location_id` attributes conform to `LOC-[0-9]{5}` and verifies existence in real-time against an injected `GDALocations` instance.
* **Reverse Geographic Lookups:** Directly retrieves all physical landmarks, facilities, and repositories mapped under a specific civil jurisdiction (`get_by_location()`).
* **Monotonic Primary Key Auto-Minting:** Calculates and assigns zero-padded monotonic identifiers (`SITE-00001` through `SITE-99999`) validated by `GDAReferenceManager.is_valid_site_id_format()`.
* **Structural Record Auditing:** Validates payloads against mandatory identifiers, names, valid geographic coordinate ranges, and foreign key boundaries before staging or committing (`validate_site()`, `validate_all()`).
* **Site Consolidation & Entity Merging:** Consolidates multiple duplicate site records into a primary anchor entity (`merge_sites()`), rolling secondary names and historical variants into `aliases[]`, backfilling missing address and coordinate fields, unioning notes, and appending merge audit trails.
* **Geographic Address & Coordinate Structures:** Standardizes physical street addresses, postal codes, and `(latitude, longitude)` floating-point coordinate dictionaries.
* **Dynamic Alias Management:** Supports recording historical variants, building names, and transcription typos (`add_alias()`, `remove_alias()`).
* **Multi-Mode Search & Ranking:** Performs exact, glob wildcard (`*Hospital*`), and fuzzy string matching across names and aliases, featuring single best-match resolution (`find_one()`).
* **Decoupled Persistence & Sandbox Safety:** Supports isolated persistence via `save(output_path=...)` for scratch scripts and interactive notebooks.

---

## Schema Contract

Governed by `schemas/entities/site_registry.schema.json` and `schemas/entities/site.schema.json`.

```json
{
  "site_id": "SITE-00001",
  "site_type": "FACILITY",
  "name": "Carlisle Hospital",
  "aliases": [
    "Carlisle Hospital",
    "Carlisle Hosp",
    "Carlisle Hospital (DOA)"
  ],
  "location_id": "LOC-00006",
  "address": {
    "address_line_1": "402 W Louther St",
    "address_line_2": null,
    "postal_code": "17013",
    "coordinates": {
      "latitude": 40.2035,
      "longitude": -77.1952
    }
  },
  "notes": [],
  "last_updated": "2026-09-29T12:00:00Z"
}
```

---

## API Reference

### Initialization & Persistence
* **`__init__(filepath=None, auto_load=True, locations_provider=None)`**: Initializes the registry instance. Accepts an optional `locations_provider` (`GDALocations`) to enforce real-time foreign key existence.
* **`load() -> None`**: Loads and parses the JSON registry from disk, resetting dirty flags and filter views.
* **`refresh() -> None`**: Discards unstaged modifications and reloads the file from disk.
* **`save(output_path=None, force=False, create_backup=True) -> bool`**: Persists records sorted monotonically by `site_id`. Generates atomic Safe Backups under `backups/` when targeting canonical production files.

### State Properties
* **`is_dirty -> bool`**: Returns `True` if in-memory entities have been modified.
* **`count -> int`**: Total count of registered site entities.
* **`filtered_count -> int`**: Count of entities matching the active view filter.

### CRUD & Auto-Minting
* **`exists(site_id: str) -> bool`**: Checks presence of primary key in memory.
* **`get_by_id(site_id: str) -> Optional[Dict[str, Any]]`**: Retrieves an isolated copy of a site entity by primary key.
* **`get_by_location(location_id: str) -> List[Dict[str, Any]]`**: Retrieves all site entities linked to a specific jurisdiction identifier.
* **`add(site_type: str, name: str, location_id: str, site_id=None, aliases=None, address_line_1=None, address_line_2=None, postal_code=None, coordinates=None, notes=None) -> str`**: Validates site type against `GDAReferenceManager`, verifies foreign key, auto-mints `SITE-XXXXX` (if omitted), and stages entity.
* **`edit(site_id: str, updates: Dict[str, Any], overwrite_none: bool = False) -> bool`**: Applies field-level modifications to an existing site.
* **`delete(site_id: str) -> bool`**: Removes a site by primary identifier.

### Integrity Audits & Consolidation
* **`validate_site(site_data: Dict[str, Any]) -> List[str]`**: Evaluates structural integrity, identifier format, required fields, coordinate ranges (-90 <= lat <= 90, -180 <= lon <= 180), and foreign key boundaries for a single site payload.
* **`validate_all() -> Dict[str, List[str]]`**: Audits all loaded sites in memory, returning a mapping of invalid site IDs to their specific defect codes.
* **`merge_sites(primary_id: str, *secondary_ids: str, keep_secondary_aliases: bool = True) -> Dict[str, Any]`**: Merges one or more secondary sites into a primary anchor entity. Secondary names and aliases are rolled into `aliases[]`, missing address fields and coordinates are backfilled, notes are unioned, an audit trail note is appended, and secondary records are removed.

### Alias Management
* **`add_alias(site_id: str, alias: str) -> bool`**: Appends a unique alias to a site entity. Marks registry dirty.
* **`remove_alias(site_id: str, alias: str) -> bool`**: Removes an alias variant from a site entity. Marks registry dirty.

### Search Engine
* **`search(query=None, location_id=None, site_type=None, has_coordinates=None, use_fuzzy=True, fuzzy_threshold=0.75) -> List[Dict[str, Any]]`**: Searches registered sites across names and aliases using exact matching, glob wildcards (`*Hospital*`), or fuzzy ratio matching.
* **`find_one(query: str, location_id=None, site_type=None, fuzzy_threshold=0.85) -> Optional[Dict[str, Any]]`**: Returns the single highest-scoring match across primary names and aliases, ranking exact matches first and sorting fuzzy candidates by similarity ratio.

### View State & Filtering
* **`set_filter(predicate=None, location_id=None, site_type=None, name_pattern=None) -> int`**: Constrains operations to records satisfying the filter criteria.
* **`clear_filter() -> None`**: Clears filter constraints.
* **`get_filtered() -> List[Dict[str, Any]]`**: Returns list of records in the active filtered view.
* **`update_filtered(updates: Dict[str, Any], validate_location: bool = True) -> int`**: Batch-applies modifications across all sites passing active filter.

---

## Usage Example

```python
from gdadomain.locations import GDALocations
from gdadomain.sites import GDASites

# Initialize with referential integrity binding
locations = GDALocations()
sites = GDASites(locations_provider=locations)

# Search for a cemetery using wildcard
cemeteries = sites.search(query="*Rolling Green*", site_type="CEMETERY")

# Add a newly discovered historic church
new_site_id = sites.add(
    site_type="CHURCH",
    name="Zion Evangelical Lutheran Church",
    location_id="LOC-00049",
    aliases=["Zion Lutheran"],
    address_line_1="2730 Booser Ave",
    postal_code="17103",
    coordinates={"latitude": 40.2741, "longitude": -76.8523}
)

# Merge a duplicate site entry into the newly added canonical site
sites.merge_sites(new_site_id, "SITE-00088", keep_secondary_aliases=True)

# Run full registry audit to ensure zero dangling locations or coordinate errors
audit_errors = sites.validate_all()
if not audit_errors:
    # Commit changes with Safe Backup
    sites.save()
```
