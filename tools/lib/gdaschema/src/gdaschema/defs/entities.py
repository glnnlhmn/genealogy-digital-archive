# Name: entities.py
# Path: tools/lib/gdaschema/src/gdaschema/defs/entities.py
# Version: 1.0.0+build.r1

"""Authoritative procedural schema generators for schemas/entities/ specifications.

Operational Role:
    Compiles canonical Draft 2020-12 schema definitions for primary domain entities
    (person, fact, location, site) and their respective administrative registry envelopes.
    Enforces in-place tombstoning contracts and GSI routing headers. Accessible via EntityCatalog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Callable, Dict

from gdacore.introspectable import IntrospectableMixin
from gdaschema.schema_util import build_schema_envelope

__version__ = "1.0.0+build.r1"


def build_person_schema() -> Dict[str, Any]:
    """Compile schemas/entities/person.schema.json."""
    envelope = build_schema_envelope(
        title="Person",
        version="1.0.4",
        description="Represents an individual person entity in the master registry.",
        schema_id="entities/person.schema.json",
    )
    envelope["unevaluatedProperties"] = False
    envelope["required"] = ["person_id", "display_name", "canonical_name"]
    envelope["properties"] = {
        "person_id": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"
        },
        "display_name": {
            "type": "string",
            "description": "Primary preferred name for listing and UI rendering."
        },
        "sex": {
            "$ref": "../defs/_enums.schema.json#/$defs/enum_sex"
        },
        "canonical_name": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"
        },
        "vitals": {
            "type": "object",
            "unevaluatedProperties": False,
            "properties": {
                "birth": {
                    "type": "object",
                    "unevaluatedProperties": False,
                    "properties": {
                        "date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                        "place": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"}
                    }
                },
                "death": {
                    "type": "object",
                    "unevaluatedProperties": False,
                    "properties": {
                        "date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                        "place": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"}
                    }
                }
            }
        },
        "associated_people": {
            "type": ["array", "null"],
            "description": "Linked secondary people or non-minted parents/kin with assigned roles.",
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/associated_person_entry"}
        },
        "unions": {
            "type": "array",
            "description": "List of domestic partnerships and spousal unions.",
            "items": {
                "type": "object",
                "unevaluatedProperties": False,
                "required": ["spouse_id", "status"],
                "properties": {
                    "spouse_id": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/person_id",
                        "description": "Identifier of the spouse or domestic/biological co-parent."
                    },
                    "status": {
                        "$ref": "../defs/_enums.schema.json#/$defs/enum_union_status",
                        "description": "Current or final lifecycle status of the partnership."
                    },
                    "marriage_date": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted",
                        "description": "Working date and modifier for wedding or union establishment."
                    },
                    "end_date": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted",
                        "description": "Working date and modifier for union dissolution or termination."
                    },
                    "place": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/location",
                        "description": "Geographic location of the marriage or domestic union."
                    },
                    "notes": {
                        "type": ["string", "null"],
                        "description": "Working contextual note regarding union circumstances."
                    }
                }
            }
        },
        "notes": {
            "type": ["array", "null"],
            "description": "Structured notes and research tracking entries for the entity.",
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/note_entry"}
        },
        "external_identifiers": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/external_identifiers"
        },
        "is_deprecated": {
            "type": "boolean",
            "default": False,
            "description": "True if soft-deleted, merged, or invalidated."
        },
        "superseded_by": {
            "type": ["string", "null"],
            "description": "Pointer to the replacing canonical IND-XXXXX if superseded or merged."
        },
        "created_at": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp tracking when the entity was first created."
        },
        "last_updated": {
            "type": "string",
            "description": "ISO-8601 timestamp representing the last modification to this entity."
        }
    }
    return envelope


def build_person_registry_schema() -> Dict[str, Any]:
    """Compile schemas/entities/person_registry.schema.json."""
    envelope = build_schema_envelope(
        title="Person_Registry",
        version="1.0.2",
        description="Master administrative registry container for individual person entities.",
        schema_id="entities/person_registry.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "created_at",
        "last_modified",
        "total_persons",
        "persons"
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "people.json"
        },
        "_path": {
            "type": "string",
            "const": "data/entities/people.json"
        },
        "$schema": {
            "type": "string"
        },
        "schema_version": {
            "type": "string",
            "const": "1.0.2"
        },
        "created_at": {
            "type": "string"
        },
        "last_modified": {
            "type": "string"
        },
        "total_persons": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of person entities contained in the registry."
        },
        "persons": {
            "type": "array",
            "description": "List of master person records.",
            "items": {"$ref": "person.schema.json"}
        }
    }
    envelope["additionalProperties"] = False
    return envelope


def build_fact_schema() -> Dict[str, Any]:
    """Compile schemas/entities/fact.schema.json."""
    envelope = build_schema_envelope(
        title="Fact",
        version="1.0.6",
        description="Represents an assertion linking a person to a source document.",
        schema_id="entities/fact.schema.json",
    )
    envelope["required"] = [
        "fact_id",
        "person_id",
        "fact_type",
        "quay_score",
        "description",
        "created_at",
        "updated_at",
        "source"
    ]
    envelope["properties"] = {
        "fact_id": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/fact_id"
        },
        "person_id": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"
        },
        "fact_type": {
            "$ref": "../defs/_enums.schema.json#/$defs/enum_fact_type",
            "description": "Standardized category of the historical fact assertion."
        },
        "quay_score": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/quay_score"
        },
        "date": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                {"type": "null"}
            ],
            "description": "Genealogical date for the fact or null."
        },
        "location": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/location",
            "description": "Standardized and verbatim location."
        },
        "description": {
            "type": "string",
            "description": "Human- and AI-readable contextual display string summarizing the asserted fact."
        },
        "notes": {
            "type": ["array", "null"],
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/note_entry"},
            "description": "List of structured research notes adhering to canonical note_entry, or null."
        },
        "life_story": {
            "type": ["string", "null"],
            "description": "Qualitative narrative describing the human context of the event."
        },
        "associated_people": {
            "type": ["array", "null"],
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/associated_person_entry"},
            "description": "List of other individuals involved in this event and their specific roles."
        },
        "external_identifiers": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/fact_external_identifiers",
            "description": "Cross-reference mapping to external GEDCOM events and sources."
        },
        "is_deprecated": {
            "type": "boolean",
            "default": False,
            "description": "True if soft-deleted, merged, or invalidated."
        },
        "superseded_by": {
            "type": ["string", "null"],
            "description": "Pointer to the absorbing canonical UUIDv4 fact_id if consolidated."
        },
        "created_at": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO 8601 timestamp tracking when the fact entry was first created."
        },
        "updated_at": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO 8601 timestamp tracking when the fact entry was last modified."
        },
        "source": {
            "description": "Primary source reference pairing archival URNs with physical filenames.",
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/source_reference"},
                {
                    "type": "array",
                    "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/source_reference"},
                    "minItems": 1
                }
            ]
        },
        "absorbed_at": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
                {"type": "null"}
            ],
            "description": "ISO 8601 timestamp tracking when this assertion was absorbed by a canonical record."
        },
        "canonical_fact_id": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/fact_id"},
                {"type": "null"}
            ],
            "description": "Pointer to the absorbing canonical fact_id if this assertion was consolidated."
        }
    }
    envelope["additionalProperties"] = False
    return envelope


def build_fact_registry_schema() -> Dict[str, Any]:
    """Compile schemas/entities/fact_registry.schema.json."""
    envelope = build_schema_envelope(
        title="Fact_Registry",
        version="1.0.2",
        description="Master administrative registry container for discrete fact assertions.",
        schema_id="entities/fact_registry.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "created_at",
        "last_modified",
        "total_facts",
        "facts"
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "facts.json"
        },
        "_path": {
            "type": "string",
            "const": "data/entities/facts.json"
        },
        "$schema": {
            "type": "string"
        },
        "schema_version": {
            "type": "string",
            "const": "1.0.2"
        },
        "created_at": {
            "type": "string"
        },
        "last_modified": {
            "type": "string"
        },
        "total_facts": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of discrete fact assertions contained in the registry."
        },
        "facts": {
            "type": "array",
            "description": "List of master fact assertion records.",
            "items": {"$ref": "fact.schema.json"}
        }
    }
    envelope["additionalProperties"] = False
    return envelope


def build_location_schema() -> Dict[str, Any]:
    """Compile schemas/entities/location.schema.json."""
    envelope = build_schema_envelope(
        title="Master Civil Location Entity Schema",
        version="1.2.0",
        description="Authoritative civil jurisdiction entity schema.",
        schema_id="entities/location.schema.json",
    )
    envelope["required"] = [
        "location_id",
        "canonical_name",
        "aliases",
        "jurisdiction"
    ]
    envelope["properties"] = {
        "location_id": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/location_id"
        },
        "canonical_name": {
            "type": "string",
            "description": "Clean, unpunctuated civil designation: [Jurisdiction, County County, State, Country]."
        },
        "aliases": {
            "type": "array",
            "description": "Recognized spelling variations, historical abbreviations, and colloquial names.",
            "items": {"type": "string"}
        },
        "jurisdiction": {
            "type": "object",
            "description": "Normalized civil administrative hierarchy.",
            "required": ["country"],
            "properties": {
                "local_jurisdiction": {
                    "type": ["string", "null"],
                    "description": "Township, borough, parish, town, or city."
                },
                "county": {
                    "type": ["string", "null"],
                    "description": "County or administrative district name without the word 'County'."
                },
                "state_or_province": {
                    "type": ["string", "null"],
                    "description": "State, province, historical duchy, or region."
                },
                "country": {
                    "type": "string",
                    "description": "Sovereign nation or crown territory."
                }
            },
            "additionalProperties": False
        },
        "temporal_validity": {
            "type": ["object", "null"],
            "description": "Civil establishment, reorganization, and dissolution boundaries.",
            "properties": {
                "date_established": {"type": ["string", "null"]},
                "date_dissolved": {"type": ["string", "null"]},
                "predecessor_location_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location_id"},
                "successor_location_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location_id"}
            },
            "additionalProperties": False
        },
        "historical_periods": {
            "type": "array",
            "description": "Chronological slices of jurisdictional changes, partitions, and boundary shifts.",
            "items": {
                "type": "object",
                "required": ["period_id", "date_start", "country"],
                "properties": {
                    "period_id": {"type": "string"},
                    "date_start": {"type": "string"},
                    "date_end": {"type": ["string", "null"]},
                    "local_jurisdiction": {"type": ["string", "null"]},
                    "county": {"type": ["string", "null"]},
                    "state_or_province": {"type": ["string", "null"]},
                    "country": {"type": "string"},
                    "note": {"type": ["string", "null"]}
                },
                "additionalProperties": False
            }
        },
        "is_deprecated": {
            "type": "boolean",
            "default": False,
            "description": "True if soft-deleted, merged, or invalidated."
        },
        "superseded_by": {
            "type": ["string", "null"],
            "description": "Pointer to the replacing canonical LOC-XXXXX if superseded or merged."
        },
        "notes": {
            "type": ["array", "null"],
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/note_entry"}
        },
        "last_updated": {
            "type": "string",
            "description": "ISO-8601 timestamp tracking entity modification."
        }
    }
    envelope["additionalProperties"] = False
    return envelope


def build_location_registry_schema() -> Dict[str, Any]:
    """Compile schemas/entities/location_registry.schema.json."""
    envelope = build_schema_envelope(
        title="Location Registry Schema",
        version="1.2.0",
        description="Master administrative registry envelope for locations.json.",
        schema_id="entities/location_registry.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "created_at",
        "last_modified",
        "total_locations",
        "locations"
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "locations.json"
        },
        "_path": {
            "type": "string",
            "const": "data/entities/locations.json"
        },
        "$schema": {
            "type": "string"
        },
        "schema_version": {
            "type": "string",
            "const": "1.2.0"
        },
        "created_at": {
            "type": "string"
        },
        "last_modified": {
            "type": "string"
        },
        "total_locations": {
            "type": "integer",
            "minimum": 0
        },
        "locations": {
            "type": "array",
            "description": "Authoritative list of master civil jurisdictions.",
            "items": {"$ref": "location.schema.json"}
        }
    }
    envelope["additionalProperties"] = False
    return envelope


def build_site_schema() -> Dict[str, Any]:
    """Compile schemas/entities/site.schema.json."""
    envelope = build_schema_envelope(
        title="Master Physical Site Entity Schema",
        version="1.2.0",
        description="Authoritative physical facility, cemetery, church, residence, or landmark entity schema.",
        schema_id="entities/site.schema.json",
    )
    envelope["required"] = [
        "site_id",
        "site_type",
        "name",
        "location_id"
    ]
    envelope["properties"] = {
        "site_id": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/site_id",
            "description": "Standardized canonical site identifier format (SID-XXXXX)."
        },
        "site_type": {
            "$ref": "../defs/_enums.schema.json#/$defs/enum_site_type",
            "description": "Classification of the physical or institutional site entity."
        },
        "name": {
            "type": "string",
            "description": "Authoritative primary designation of the physical site or landmark."
        },
        "aliases": {
            "type": "array",
            "description": "Alternative names, historical designations, or colloquial variations.",
            "items": {"type": "string"}
        },
        "location_id": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/location_id",
            "description": "Foreign key link to the parent civil jurisdiction in locations.json."
        },
        "address": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/street_address",
            "description": "Physical postal delivery line and geocoordinates."
        },
        "operational_status": {
            "$ref": "../defs/_enums.schema.json#/$defs/enum_operational_status",
            "default": "ACTIVE",
            "description": "Real-world historical or operational condition of the physical facility."
        },
        "is_deprecated": {
            "type": "boolean",
            "default": False,
            "description": "True if soft-deleted, merged, or invalidated due to integrity issues."
        },
        "superseded_by": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/site_id"},
                {"type": "null"}
            ],
            "description": "Pointer to the replacing canonical SID-##### if superseded or merged."
        },
        "dissolution_date": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                {"type": "null"}
            ],
            "description": "Date when the facility, congregation, or cemetery closed or ceased operation."
        },
        "notes": {
            "type": ["array", "null"],
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/note_entry"}
        },
        "last_updated": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp tracking entity modification."
        }
    }
    envelope["additionalProperties"] = False
    return envelope


def build_site_registry_schema() -> Dict[str, Any]:
    """Compile schemas/entities/site_registry.schema.json."""
    envelope = build_schema_envelope(
        title="Site Registry Schema",
        version="1.0.0",
        description="Master administrative registry envelope for sites.json.",
        schema_id="entities/site_registry.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "created_at",
        "last_modified",
        "total_sites",
        "sites"
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "sites.json"
        },
        "_path": {
            "type": "string",
            "const": "data/entities/sites.json"
        },
        "$schema": {
            "type": "string"
        },
        "schema_version": {
            "type": "string",
            "const": "1.0.0"
        },
        "created_at": {
            "type": "string"
        },
        "last_modified": {
            "type": "string"
        },
        "total_sites": {
            "type": "integer",
            "minimum": 0
        },
        "sites": {
            "type": "array",
            "description": "Authoritative list of physical sites, cemeteries, and landmarks.",
            "items": {"$ref": "site.schema.json"}
        }
    }
    envelope["additionalProperties"] = False
    return envelope


class EntityCatalog(Mapping[str, Callable[[], Dict[str, Any]]], IntrospectableMixin):
    """Collection manager exposing indexed procedural builders for entity schemas."""

    _BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
        "person": build_person_schema,
        "person_registry": build_person_registry_schema,
        "fact": build_fact_schema,
        "fact_registry": build_fact_registry_schema,
        "location": build_location_schema,
        "location_registry": build_location_registry_schema,
        "site": build_site_schema,
        "site_registry": build_site_registry_schema,
    }

    _KEY_ALIASES: Dict[str, str] = {
        "person.schema.json": "person",
        "people": "person_registry",
        "person_registry.schema.json": "person_registry",
        "fact.schema.json": "fact",
        "facts": "fact_registry",
        "fact_registry.schema.json": "fact_registry",
        "location.schema.json": "location",
        "locations": "location_registry",
        "location_registry.schema.json": "location_registry",
        "site.schema.json": "site",
        "sites": "site_registry",
        "site_registry.schema.json": "site_registry",
    }

    def _resolve_key(self, key: str) -> str:
        """Normalize raw key or alias into canonical logical key."""
        raw = str(key or "").strip().lower()
        if raw in self._BUILDERS:
            return raw
        if raw in self._KEY_ALIASES:
            return self._KEY_ALIASES[raw]
        raise KeyError(f"No entity definition builder found matching key: '{key}'")

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


# Backward-compatible catalog alias
EntityDefsCatalog = EntityCatalog