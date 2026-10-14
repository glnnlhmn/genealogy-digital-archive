<!--
Name: spec_domain_entity_schemas.md
Path: docs/architecture/spec_domain_entity_schemas.md
Version: 1.0.0
-->

# Data Contract & Entity Structure Specification: `gdadomain`

## 1. Overview & System Alignment
This document establishes the canonical data structure, field specifications, data types, and validation constraints for all entities managed by the `gdadomain` package. It directly cross-references the canonical JSON Schemas located under `schemas/entities/` and `schemas/defs/`, ensuring 100% contract compliance across active registries and graveyard partitions.

---

## 2. Common & Shared Primitives

These reusable structures are embedded across multiple domain entities and align with definitions in `schemas/defs/`.

### 2.1 Note Object (`schemas/defs/_shared_notes.schema.json`)
Managed via `GDANoteCollection`. Used in `people.py`, `locations.py`, `sites.py`, and `facts.py`.

| Field Name | Type | Required | Description / Constraints | Example |
| :--- | :--- | :--- | :--- | :--- |
| `note_id` | string | Yes | Sequential system identifier `NOT-XXXXX`. | `"NOT-00001"` |
| `note_text` | string | Yes | Narrative body text (non-empty). | `"Verified via 1850 Federal Census."` |
| `note_type` | string | Yes | Controlled vocabulary (`VOCAB_MGR["note_type"]`). Defaults to `"RESEARCH"`. | `"RESEARCH"`, `"DISCREPANCY"` |
| `modified_date` | string (ISO-8601) | Yes | UTC timestamp of creation or latest edit. | `"2026-09-26T11:15:00Z"` |

### 2.2 Date Interpreted Object (`schemas/defs/_shared_dates.schema.json`)
Managed via `GDADates` (`DateEngine`).

| Field Name | Type | Required | Description / Constraints | Example |
| :--- | :--- | :--- | :--- | :--- |
| `modifier` | string | Yes | GEDCOM modifier token: `EXACT`, `ABT`, `BEF`, `AFT`, `BET`, `FROM_TO`, `UNKNOWN`. | `"BET"` |
| `date_start` | string or null | No | ISO calendar date string (`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`). | `"1845-05-14"` |
| `date_end` | string or null | No | ISO calendar end date string (for ranges). | `"1848-10-20"` |
| `raw_text` | string or null | No | Verbatim historical text transcription. | `"Between May 1845 and Oct 1848"` |

### 2.3 Vital Year Object (`schemas/defs/_shared_dates.schema.json`)
Simplified vital chronology year anchor.

| Field Name | Type | Required | Description / Constraints | Example |
| :--- | :--- | :--- | :--- | :--- |
| `year` | integer or null | Yes | 4-digit calendar year (`1000` to `2100`). | `1865` |
| `modifier` | string | Yes | GEDCOM vital modifier: `EXACT`, `ABT`, `BEF`, `AFT`, `BET`, `LIVING`, `UNKNOWN`. | `"EXACT"` |

---

## 3. Person Entity (`GDAPeople`)
* **Registry File:** `data/entities/people.json`
* **Backing Schema:** `schemas/entities/person_registry.schema.json`
* **ID Format:** `^IND-(\d{5})$`

### 3.1 Field Specification

| Field Name | Type | Required | Nullable | Description / Invariants |
| :--- | :--- | :--- | :--- | :--- |
| `person_id` | string | Yes | No | Monotonic sequential identifier (`IND-XXXXX`). Immutable once minted. |
| `display_name` | string | Yes | No | Computed standardized name. Defaults to `"UNKNOWN"` if unresolved. |
| `canonical_name` | object | Yes | No | Structured name components (see Section 3.2). |
| `sex` | string | Yes | No | Biological/recorded sex token (`M`, `F`, `U`). Normalizes to `"U"` if omitted. |
| `associated_people` | array[object] | Yes | No | Kinship and contextual edge array (see Section 3.3). |
| `unions` | array[object] | Yes | No | Spousal union relationships (see Section 3.4). |
| `notes` | array[object] | Yes | No | Array of Section 2.1 Note Objects managed by `GDANoteCollection`. |
| `is_deprecated` | boolean | Yes | No | Soft-delete tombstone indicator. Defaults to `false`. |
| `superseded_by` | string or null | Yes | Yes | Valid target `IND-XXXXX` if record was merged or superseded. |
| `created_at` | string (ISO-8601) | Yes | No | UTC timestamp of record creation. |
| `last_updated` | string (ISO-8601) | Yes | No | UTC timestamp of latest state mutation. |

### 3.2 `canonical_name` Object Structure

| Subfield | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `given` | string | No | Given / first name(s). |
| `middle` | string | No | Middle name(s) or initials. |
| `surname` | string | No | Family surname / maiden name. |
| `suffix` | string | No | Generational or titular suffix (`Jr.`, `Sr.`, `III`). |
| `raw_name` | string | No | Fallback verbatim unparsed name string. |

### 3.3 `associated_people` Edge Object Structure

| Subfield | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `person_id` | string | Yes | Valid target `IND-XXXXX` identifier. |
| `role` | string | Yes | Kinship or contextual role: `FATH`, `MOTH`, `CHIL`, `SPOU`, `SIBL`, `PARENT`, `WITN`, `OFFICIANT`, `INFORMANT`. |

### 3.4 `unions` Object Structure

| Subfield | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `spouse_id` | string | Yes | Valid spouse `IND-XXXXX` identifier. |
| `status` | string | Yes | Controlled union status: `MARRIED`, `DIVORCED`, `SEPARATED`, `COMMON_LAW`, `PARTNER`, `WIDOWED`. |
| `marriage_date` | string or object | No | ISO date string or Interpreted Date Object (Section 2.2). |
| `marriage_location_id` | string or null | No | Optional parent civil jurisdiction identifier `LOC-XXXXX`. |
| `end_date` | string or object | No | Optional dissolution date. |
| `place` | object or null | No | Optional unstandardized / standardized place dictionary. |
| `notes` | string or null | No | Optional union annotation text. |

---

## 4. Fact Entity (`GDAFacts`)
* **Registry File:** `data/entities/facts.json`
* **Backing Schema:** `schemas/entities/fact_registry.schema.json`
* **ID Format:** Lowercase RFC 4122 UUIDv4 (`^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`)

### 4.1 Field Specification

| Field Name | Type | Required | Nullable | Description / Invariants |
| :--- | :--- | :--- | :--- | :--- |
| `fact_id` | string | Yes | No | Lowercase UUIDv4 identifier. Immutable once minted. |
| `person_id` | string | Yes | No | Primary assertion subject (`IND-XXXXX`). |
| `fact_type` | string | Yes | No | Controlled fact type (e.g., `Birth`, `Death`, `Marriage`, `Census`, `Burial`). |
| `date` | object | No | No | Date Interpreted Object (see Section 2.2). |
| `location_id` | string or null | No | Yes | Optional foreign key to civil jurisdiction (`LOC-XXXXX`). |
| `site_id` | string or null | No | Yes | Optional foreign key to physical site (`SID-XXXXX`). |
| `associated_people` | array[object] | No | No | Array of secondary participants (`person_id`, `role`). |
| `citation_ids` | array[string] | No | No | Optional list of supporting evidence citations (`CIT-XXXXX`). |
| `notes` | array[string or object] | No | No | Array of annotations or Note Objects (Section 2.1). |
| `is_deprecated` | boolean | Yes | No | Soft-delete tombstone indicator. Defaults to `false`. |
| `superseded_by` | string or null | Yes | Yes | Valid target `UUIDv4` if assertion was absorbed or superseded. |
| `last_updated` | string (ISO-8601) | Yes | No | UTC timestamp of latest state mutation. |

---

## 5. Location Entity (`GDALocations`)
* **Registry File:** `data/entities/locations.json`
* **Backing Schema:** `schemas/entities/location_registry.schema.json`
* **ID Format:** `^LOC-(\d{5})$`

### 5.1 Field Specification

| Field Name | Type | Required | Nullable | Description / Invariants |
| :--- | :--- | :--- | :--- | :--- |
| `location_id` | string | Yes | No | Monotonic sequential identifier (`LOC-XXXXX`). |
| `canonical_name` | string | Yes | No | Hierarchical comma-delimited jurisdiction string (`Local, County, State, Country`). |
| `aliases` | array[string] | Yes | No | Alternate historical names, former spellings, or colloquial labels. |
| `jurisdiction` | object | Yes | No | Structured administrative hierarchy (see Section 5.2). |
| `temporal_validity` | object | Yes | No | Temporal boundaries and predecessor/successor links (see Section 5.3). |
| `historical_periods` | array[object] | No | No | Optional array of historical epoch mappings. |
| `operational_status` | string | Yes | No | Controlled vocabulary: `ACTIVE`, `HISTORICAL`, `DEFUNCT`. |
| `is_deprecated` | boolean | Yes | No | Soft-delete tombstone indicator. Defaults to `false`. |
| `superseded_by` | string or null | Yes | Yes | Valid target `LOC-XXXXX` if merged into a primary entity. |
| `dissolution_date` | string or null | No | Yes | ISO date string or year of jurisdiction dissolution. |
| `notes` | array[object] | Yes | No | Array of Section 2.1 Note Objects managed by `GDANoteCollection`. |
| `last_updated` | string (ISO-8601) | Yes | No | UTC timestamp of latest state mutation. |

### 5.2 `jurisdiction` Object Structure

| Subfield | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `country` | string | Yes | National jurisdiction (e.g., `"USA"`, `"Germany"`). |
| `state_or_province` | string or null | No | State or province name. Normalized to full name for US via `us` library. |
| `county` | string or null | No | County or district name. Normalizes with or without `"County"` suffix. |
| `local_jurisdiction` | string or null | No | Municipal boundary (city, borough, township, parish). |

### 5.3 `temporal_validity` Object Structure

| Subfield | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `date_established` | string or null | No | ISO date or year string when boundary was formally created. |
| `date_dissolved` | string or null | No | ISO date or year string when boundary ceased operation. Must be `>= date_established`. |
| `predecessor_location_id` | string or null | No | Valid `LOC-XXXXX` from which this entity was split or created. Cannot equal own ID. |
| `successor_location_id` | string or null | No | Valid `LOC-XXXXX` into which this entity was absorbed. Cannot equal own ID. |

---

## 6. Site Entity (`GDASites`)
* **Registry File:** `data/entities/sites.json`
* **Backing Schema:** `schemas/entities/site_registry.schema.json`
* **ID Format:** `^SID-(\d{5})$`

### 6.1 Field Specification

| Field Name | Type | Required | Nullable | Description / Invariants |
| :--- | :--- | :--- | :--- | :--- |
| `site_id` | string | Yes | No | Monotonic sequential identifier (`SID-XXXXX`). |
| `name` | string | Yes | No | Primary canonical name of the landmark, structure, or facility. |
| `site_type` | string | Yes | No | Controlled vocabulary: `CEMETERY`, `CHURCH`, `HOSPITAL`, `FACILITY`, `LANDMARK`, `RESIDENCE`, `MILITARY_POST`, `CIVIC`. |
| `location_id` | string | Yes | No | Mandatory foreign key to parent civil jurisdiction (`LOC-XXXXX`). Must exist in `GDALocations`. |
| `aliases` | array[string] | Yes | No | Alternate historic or colloquial designations. |
| `address` | object or null | No | Yes | Physical street address and geographic coordinates (see Section 6.2). |
| `operational_status` | string | Yes | No | Controlled status: `ACTIVE`, `HISTORICAL`, `DEFUNCT`. |
| `is_deprecated` | boolean | Yes | No | Soft-delete tombstone indicator. Defaults to `false`. |
| `superseded_by` | string or null | Yes | Yes | Valid target `SID-XXXXX` if merged or superseded. |
| `dissolution_date` | string or null | No | Yes | Optional ISO date when site was demolished or closed. |
| `notes` | array[object] | Yes | No | Array of Section 2.1 Note Objects managed by `GDANoteCollection`. |
| `last_updated` | string (ISO-8601) | Yes | No | UTC timestamp of latest state mutation. |

### 6.2 `address` Object Structure

| Subfield | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `address_line_1` | string or null | No | Street address line 1. |
| `address_line_2` | string or null | No | Suite, unit, or auxiliary line. |
| `postal_code` | string or null | No | Postal or ZIP code string. |
| `coordinates` | object or null | No | Spatial coordinates dictionary: `{"latitude": float, "longitude": float}`. |

---

## 7. Registry Envelope Standards

When persisted to disk under `data/entities/*.json`, each collection is enclosed within a standard metadata envelope:

```json
{
  "_name": "people.json",
  "_path": "data/entities/people.json",
  "$schema": "schemas/entities/person_registry.schema.json",
  "schema_version": "1.0.0",
  "created_at": "2026-01-01T00:00:00Z",
  "last_modified": "2026-09-26T11:15:00Z",
  "total_people": 62,
  "people": [
    {
      "person_id": "IND-00000",
      "display_name": "Arthur Pendelton Sterling",
      ...
    }
  ]
}
```

Envelope root arrays map directly to their entity plural names:
* `people.json`: `"people"` (or `"persons"` during intake hydration)
* `facts.json`: `"facts"`
* `locations.json`: `"locations"`
* `sites.json`: `"sites"`