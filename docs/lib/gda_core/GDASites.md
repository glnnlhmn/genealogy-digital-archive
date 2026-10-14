<!--
Name: GDASites.md
Path: docs/lib/gda_core/GDASites.md
-->
# Core Framework Library: `GDASites`

`GDASites` is the master registry manager governing physical facilities, cemeteries, churches, landmarks, and residences stored in `data/entities/sites.json`.

---

## Technical Overview

While `GDALocations` models legal and administrative jurisdictions, `GDASites` models physical geographic entities. Every site entity references a parent civil jurisdiction (`location_id`), ensuring clear separation between administrative boundaries and physical structures.

### Key Capabilities
* **Physical Site Classification:** Enforces standard site categorization (`FACILITY`, `CEMETERY`, `CHURCH`, `LANDMARK`, `RESIDENCE`, `ORGANIZATION`).
* **Foreign Key Referential Integrity:** Validates that `location_id` attributes conform to `LOC-[0-9]{5}` and optionally verifies existence against a `GDALocations` instance.
* **Monotonic Primary Key Auto-Minting:** Automatically calculates and assigns zero-padded monotonic identifiers (`SITE-00001` through `SITE-99999`).
* **Geographic Address & Coordinate Structures:** Standardizes physical street addresses, postal codes, and `(latitude, longitude)` floating-point coordinate dictionaries.
* **Dynamic Alias Management:** Supports recording historical variants, building names, and transcription typos (`add_alias()`, `remove_alias()`).
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
* **`save(output_path=None, force=False, create_backup=True) -> bool`**: Persists records sorted monotonically by `site_id`. Generates atomic backups when targeting canonical production files.

### State Properties
* **`is_dirty -> bool`**: Returns `True` if in-memory entities have been modified.
* **`count -> int`**: Total count of registered site entities.
* **`filtered_count -> int`**: Count of entities matching the active view filter.

### CRUD & Auto-Minting
* **`get_by_id(site_id: str) -> Optional[Dict[str, Any]]`**: Retrieves an isolated copy of a site entity by primary key.
* **`add(site_type: str, name: str, location_id: str, site_id=None, aliases=None, address_line_1=None, address_line_2=None, postal_code=None, coordinates=None, notes=None) -> str`**: Validates site type, verifies foreign key, auto-mints `SITE-XXXXX` (if omitted), and stages entity.
* **`edit(site_id: str, updates: Dict[str, Any], overwrite_none: bool = False) -> bool`**: Applies field-level modifications to an existing site.
* **`delete(site_id: str) -> bool`**: Removes a site by primary identifier.

### Alias Management
* **`add_alias(site_id: str, alias: str) -> bool`**: Appends a unique alias to a site entity. Marks registry dirty.
* **`remove_alias(site_id: str, alias: str) -> bool`**: Removes an alias variant from a site entity. Marks registry dirty.

### Search Engine
* **`search(query=None, location_id=None, site_type=None, has_coordinates=None, use_fuzzy=True, fuzzy_threshold=0.75) -> List[Dict[str, Any]]`**: Searches registered sites across names and aliases using substring, glob wildcard (`*Hospital*`), or fuzzy ratio matching.
* **`find_one(query: str, location_id=None, site_type=None, fuzzy_threshold=0.85) -> Optional[Dict[str, Any]]`**: Returns the single highest-scoring match.

### View State & Filtering
* **`set_filter(predicate=None, location_id=None, site_type=None, name_pattern=None) -> int`**: Constrains operations to records satisfying the filter criteria.
* **`clear_filter() -> None`**: Clears filter constraints.
* **`get_filtered() -> List[Dict[str, Any]]`**: Returns list of records in the active filtered view.
* **`update_filtered(updates: Dict[str, Any], validate_location: bool = True) -> int`**: Batch-applies modifications across all sites passing active filter.

---

## Usage Example

```python
from tools.lib.gda_core.GDALocations import GDALocations
from tools.lib.gda_core.GDASites import GDASites

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

# Commit changes with Safe Backup
sites.save()
```