# Name: indexes.py
# Path: tools/lib/gdaschema/src/gdaschema/defs/indexes.py
# Version: 1.0.0+build.r1

"""Authoritative procedural schema generators for schemas/indexes/ specifications.

Operational Role:
    Compiles canonical Draft 2020-12 schema definitions for single-table secondary
    projections, alias redirections, and foreign key lookup indexes across core
    entities (people, facts, locations, sites). Accessible via IndexCatalog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Callable, Dict

from gdacore.introspectable import IntrospectableMixin
from gdaschema.schema_util import build_schema_envelope

__version__ = "1.0.0+build.r1"


def build_people_surname_idx_schema() -> Dict[str, Any]:
    """Compile schemas/indexes/people_surname_idx.schema.json."""
    envelope = build_schema_envelope(
        title="People_Surname_Index",
        version="1.0.0",
        description="Lookup index mapping normalized lowercase surnames and spelling variants to canonical person references.",
        schema_id="indexes/people_surname_idx.schema.json",
    )
    envelope["unevaluatedProperties"] = False
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "last_modified",
        "total_surnames",
        "surnames",
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "people_surname_idx.json",
        },
        "_path": {
            "type": "string",
            "const": "data/indexes/people_surname_idx.json",
        },
        "$schema": {"type": "string"},
        "schema_version": {"type": "string", "const": "1.0.0"},
        "last_modified": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp of last index compilation.",
        },
        "total_surnames": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of canonical surnames indexed.",
        },
        "aliases": {
            "type": "object",
            "description": "Lookup dictionary mapping normalized lowercase spelling variants directly to canonical surname keys.",
            "additionalProperties": {
                "type": "string",
                "description": "Canonical normalized surname key.",
            },
        },
        "surnames": {
            "type": "object",
            "description": "Dictionary keyed by normalized lowercase surname mapping to matching person entries.",
            "additionalProperties": {
                "type": "object",
                "unevaluatedProperties": False,
                "required": ["canonical_surname", "total_persons", "persons"],
                "properties": {
                    "canonical_surname": {
                        "type": "string",
                        "description": "Standardized capitalized surname representation.",
                    },
                    "spelling_variants": {
                        "type": "array",
                        "description": "Observed or historical spelling variations associated with this surname.",
                        "items": {"type": "string"},
                    },
                    "total_persons": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Total count of persons matching this surname.",
                    },
                    "persons": {
                        "type": "array",
                        "description": "List of person identifiers associated with this surname.",
                        "items": {
                            "$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"
                        },
                    },
                },
            },
        },
    }
    return envelope


def build_people_surname_alias_idx_schema() -> Dict[str, Any]:
    """Compile schemas/indexes/people_surname_alias_idx.schema.json."""
    envelope = build_schema_envelope(
        title="People_Surname_Alias_Index",
        version="1.0.0",
        description="Validation contract governing directional variant-to-canonical surname alias lookups.",
        schema_id="indexes/people_surname_alias_idx.schema.json",
    )
    envelope["unevaluatedProperties"] = False
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "last_modified",
        "total_aliases",
        "description",
        "aliases",
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "people_surname_alias_idx.json",
        },
        "_path": {
            "type": "string",
            "const": "data/indexes/people_surname_alias_idx.json",
        },
        "$schema": {"type": "string"},
        "schema_version": {"type": "string", "const": "1.0.0"},
        "last_modified": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp of last index compilation.",
        },
        "total_aliases": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of directional alias mappings.",
        },
        "description": {
            "type": "string",
            "description": "Functional description of the alias authority registry.",
        },
        "aliases": {
            "type": "object",
            "description": "Directional mapping of normalized variant keys to canonical surname keys.",
            "propertyNames": {"pattern": "^[a-z0-9\\-]+$"},
            "additionalProperties": {
                "type": "string",
                "pattern": "^[a-z0-9\\-]+$",
            },
        },
    }
    return envelope


def build_locations_redirect_idx_schema() -> Dict[str, Any]:
    """Compile schemas/indexes/locations_redirect_idx.schema.json."""
    envelope = build_schema_envelope(
        title="Locations_Redirect_Index",
        version="1.0.0",
        description="Lightweight lookup index resolving verbatim, shorthand, or historical location strings to canonical location IDs.",
        schema_id="indexes/locations_redirect_idx.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "last_modified",
        "total_mappings",
        "redirects",
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "locations_redirect_idx.json",
        },
        "_path": {
            "type": "string",
            "const": "data/indexes/locations_redirect_idx.json",
        },
        "$schema": {"type": "string"},
        "schema_version": {"type": "string", "const": "1.0.0"},
        "last_modified": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp of last index update.",
        },
        "total_mappings": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of redirect keys registered in the index.",
        },
        "redirects": {
            "type": "object",
            "description": "Dictionary keyed by normalized lowercase alias mapping directly to canonical location references.",
            "additionalProperties": {
                "type": "object",
                "required": ["location_id", "standardized"],
                "properties": {
                    "location_id": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/location_id"
                    },
                    "standardized": {
                        "type": "string",
                        "description": "Canonical standardized jurisdiction string matching location entity.",
                    },
                },
                "additionalProperties": False,
            },
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_facts_location_idx_schema() -> Dict[str, Any]:
    """Compile schemas/indexes/facts_location_idx.schema.json."""
    envelope = build_schema_envelope(
        title="Facts_Location_Index",
        version="1.0.0",
        description="Inverted foreign-key lookup index mapping canonical location_id to associated fact_ids in facts.json.",
        schema_id="indexes/facts_location_idx.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "last_modified",
        "total_locations",
        "locations",
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "facts_location_idx.json",
        },
        "_path": {
            "type": "string",
            "const": "data/indexes/facts_location_idx.json",
        },
        "$schema": {"type": "string"},
        "schema_version": {"type": "string", "const": "1.0.0"},
        "last_modified": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp of last index update.",
        },
        "total_locations": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of indexed civil locations.",
        },
        "locations": {
            "type": "object",
            "description": "Dictionary keyed by canonical location_id mapping to arrays of fact_ids.",
            "propertyNames": {"pattern": "^LOC-\\d{5}$"},
            "additionalProperties": {
                "type": "array",
                "description": "List of fact assertions referencing this location.",
                "items": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/fact_id"
                },
            },
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_facts_person_idx_schema() -> Dict[str, Any]:
    """Compile schemas/indexes/facts_person_idx.schema.json."""
    envelope = build_schema_envelope(
        title="Facts_Person_Index",
        version="1.0.0",
        description="Inverted foreign-key lookup index mapping canonical person_id to associated fact_ids in facts.json.",
        schema_id="indexes/facts_person_idx.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "last_modified",
        "total_people",
        "people",
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "facts_person_idx.json",
        },
        "_path": {
            "type": "string",
            "const": "data/indexes/facts_person_idx.json",
        },
        "$schema": {"type": "string"},
        "schema_version": {"type": "string", "const": "1.0.0"},
        "last_modified": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp of last index update.",
        },
        "total_people": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of indexed primary individuals.",
        },
        "people": {
            "type": "object",
            "description": "Dictionary keyed by canonical person_id mapping to arrays of fact_ids.",
            "propertyNames": {"pattern": "^IND-\\d{5}$"},
            "additionalProperties": {
                "type": "array",
                "description": "List of fact assertions asserted for this individual.",
                "items": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/fact_id"
                },
            },
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_sites_location_idx_schema() -> Dict[str, Any]:
    """Compile schemas/indexes/sites_location_idx.schema.json."""
    envelope = build_schema_envelope(
        title="Sites_Location_Index",
        version="1.0.0",
        description="Inverted administrative lookup index mapping parent location_id to physical site_ids in sites.json.",
        schema_id="indexes/sites_location_idx.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "last_modified",
        "total_locations",
        "locations",
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "sites_location_idx.json",
        },
        "_path": {
            "type": "string",
            "const": "data/indexes/sites_location_idx.json",
        },
        "$schema": {"type": "string"},
        "schema_version": {"type": "string", "const": "1.0.0"},
        "last_modified": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp of last index update.",
        },
        "total_locations": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of civil locations hosting sites.",
        },
        "locations": {
            "type": "object",
            "description": "Dictionary keyed by parent location_id mapping to arrays of site_ids.",
            "propertyNames": {"pattern": "^LOC-\\d{5}$"},
            "additionalProperties": {
                "type": "array",
                "description": "List of physical sites located within this civil jurisdiction.",
                "items": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/site_id"
                },
            },
        },
    }
    envelope["additionalProperties"] = False
    return envelope


class IndexCatalog(Mapping[str, Callable[[], Dict[str, Any]]], IntrospectableMixin):
    """Collection manager exposing indexed procedural builders for index schemas."""

    _BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
        "people_surname_idx": build_people_surname_idx_schema,
        "people_surname_alias_idx": build_people_surname_alias_idx_schema,
        "locations_redirect_idx": build_locations_redirect_idx_schema,
        "facts_location_idx": build_facts_location_idx_schema,
        "facts_person_idx": build_facts_person_idx_schema,
        "sites_location_idx": build_sites_location_idx_schema,
    }

    _KEY_ALIASES: Dict[str, str] = {
        "surname": "people_surname_idx",
        "surname_idx": "people_surname_idx",
        "people_surname": "people_surname_idx",
        "surname_index": "people_surname_idx",
        "surname_index.schema.json": "people_surname_idx",
        "people_surname_idx.schema.json": "people_surname_idx",
        "surname_alias": "people_surname_alias_idx",
        "surname_aliases": "people_surname_alias_idx",
        "surname_aliases.schema.json": "people_surname_alias_idx",
        "people_surname_alias_idx.schema.json": "people_surname_alias_idx",
        "location_redirect": "locations_redirect_idx",
        "location_index": "locations_redirect_idx",
        "location_index.schema.json": "locations_redirect_idx",
        "locations_redirect_idx.schema.json": "locations_redirect_idx",
        "facts_location": "facts_location_idx",
        "facts_location_idx.schema.json": "facts_location_idx",
        "facts_person": "facts_person_idx",
        "facts_person_idx.schema.json": "facts_person_idx",
        "sites_location": "sites_location_idx",
        "sites_location_idx.schema.json": "sites_location_idx",
    }

    def _resolve_key(self, key: str) -> str:
        """Normalize raw key or alias into canonical logical key."""
        raw = str(key or "").strip().lower()
        if raw in self._BUILDERS:
            return raw
        if raw in self._KEY_ALIASES:
            return self._KEY_ALIASES[raw]
        raise KeyError(f"No index builder found matching key: '{key}'")

    def __getitem__(self, key: str) -> Any:
        """Retrieve compiled schema by logical key, or dictionary of all schemas via 'all'."""
        if str(key).strip().lower() == "all":
            return {logical_key: builder() for logical_key, builder in self._BUILDERS.items()}
        canonical_key = self._resolve_key(key)
        return self._BUILDERS[canonical_key]()

    def __len__(self) -> int:
        return len(self._BUILDERS)

    def __iter__(self) -> Iterator[str]:
        return iter(self._BUILDERS)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        raw = key.strip().lower()
        return raw == "all" or raw in self._BUILDERS or raw in self._KEY_ALIASES