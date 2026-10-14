# Name: enumeration.py
# Path: tools/lib/gdaschema/src/gdaschema/sources/enumeration.py
# Version: 1.0.0+build.r4

"""Authoritative procedural schema generators for enumeration and transit source records.

Operational Role:
    Compiles canonical Draft 2020-12 schema definitions for census schedules,
    city directory listings, ship passenger manifests, and naturalization certificates.
    Accessible via EnumerationSourcesCatalog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Callable, Dict

from gdacore.introspectable import IntrospectableMixin
from gdaschema.schema_util import build_schema_envelope

__version__ = "1.0.0+build.r4"


def build_census_schedule_schema() -> Dict[str, Any]:
    """Compile schemas/sources/census_schedule.schema.json."""
    envelope = build_schema_envelope(
        title="EnumerationSourceCensusSchedule",
        version="1.1.0",
        description="Standardized archival schema capturing federal and state population census schedules.",
        schema_id="sources/census_schedule.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "enumeration_scope",
        "entries",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "description": {"type": "string"},
        "record_metadata": {
            "type": "object",
            "required": ["record_category", "record_type"],
            "properties": {
                "source_guid": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                    "description": "RFC 4122 lowercase UUIDv4 primary identifier of source record.",
                },
                "source_urn": {
                    "type": "string",
                    "description": "Legacy citation pointer accepted for backward compatibility.",
                },
                "record_category": {"type": "string"},
                "record_type": {"type": "string"},
                "census_year": {"type": "integer"},
                "nara_roll": {"type": ["string", "null"]},
                "repository_id": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4"},
                        {"type": "string", "pattern": "^REP-\\d{5}$"},
                    ]
                },
            },
            "anyOf": [
                {"required": ["source_guid"]},
                {"required": ["source_urn"]},
            ],
            "additionalProperties": True,
        },
        "enumeration_scope": {
            "type": "object",
            "required": ["location"],
            "properties": {
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "enumeration_district": {"type": ["string", "null"]},
                "supervisor_district": {"type": ["string", "null"]},
                "sheet_number": {"type": ["string", "null"]},
                "sheet_side": {"type": ["string", "null"], "enum": ["A", "B", None]},
                "enumerator_name": {"type": ["string", "null"]},
                "enumeration_date": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                        {"type": "null"},
                    ]
                },
            },
            "additionalProperties": True,
        },
        "entries": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "../defs/_census_defs.schema.json#/$defs/census_line_entry"},
        },
        "media_files": {
            "type": "array",
            "items": {"$ref": "../defs/_document_defs.schema.json#/$defs/source_media"},
        },
        "associated_people": {
            "type": "array",
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/associated_person_entry"},
        },
    }
    envelope["additionalProperties"] = True
    return envelope


def build_directory_listing_schema() -> Dict[str, Any]:
    """Compile schemas/sources/directory_listing.schema.json."""
    envelope = build_schema_envelope(
        title="EnumerationSourceDirectoryListing",
        version="1.1.0",
        description="Standardized archival schema capturing historical city, town, and business directories.",
        schema_id="sources/directory_listing.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "individual",
        "residence",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "description": {"type": "string"},
        "record_metadata": {
            "type": "object",
            "required": ["record_category", "record_type"],
            "properties": {
                "source_guid": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                    "description": "RFC 4122 lowercase UUIDv4 primary identifier of source record.",
                },
                "source_urn": {
                    "type": "string",
                    "description": "Legacy citation pointer accepted for backward compatibility.",
                },
                "record_category": {"type": "string"},
                "record_type": {"type": "string"},
                "directory_title": {"type": "string"},
                "publication_year": {"type": "integer"},
                "page_number": {"type": ["string", "null"]},
                "repository_id": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4"},
                        {"type": "string", "pattern": "^REP-\\d{5}$"},
                    ]
                },
            },
            "anyOf": [
                {"required": ["source_guid"]},
                {"required": ["source_urn"]},
            ],
            "additionalProperties": True,
        },
        "individual": {
            "type": "object",
            "required": ["name_raw"],
            "properties": {
                "person_id": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
                        {"type": "null"},
                    ]
                },
                "name_raw": {"type": "string"},
                "full_name": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"},
                        {"type": "null"},
                    ]
                },
                "occupation": {"type": ["string", "null"]},
                "business_name": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "residence": {
            "type": "object",
            "required": ["location"],
            "properties": {
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "street_address": {"$ref": "../defs/_shared_defs.schema.json#/$defs/street_address"},
                "tenure_status": {"type": ["string", "null"], "enum": ["Owner", "Boarder", "Tenant", None]},
            },
            "additionalProperties": True,
        },
        "media_files": {
            "type": "array",
            "items": {"$ref": "../defs/_document_defs.schema.json#/$defs/source_media"},
        },
        "associated_people": {
            "type": "array",
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/associated_person_entry"},
        },
    }
    envelope["additionalProperties"] = True
    return envelope


def build_immigration_manifest_schema() -> Dict[str, Any]:
    """Compile schemas/sources/immigration_manifest.schema.json."""
    envelope = build_schema_envelope(
        title="EnumerationSourceImmigrationManifest",
        version="1.1.0",
        description="Standardized archival schema capturing ship passenger manifests and port arrival lists.",
        schema_id="sources/immigration_manifest.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "voyage_particulars",
        "passenger",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "description": {"type": "string"},
        "record_metadata": {
            "type": "object",
            "required": ["record_category", "record_type"],
            "properties": {
                "source_guid": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                    "description": "RFC 4122 lowercase UUIDv4 primary identifier of source record.",
                },
                "source_urn": {
                    "type": "string",
                    "description": "Legacy citation pointer accepted for backward compatibility.",
                },
                "record_category": {"type": "string"},
                "record_type": {"type": "string"},
                "nara_series": {"type": ["string", "null"]},
                "roll_number": {"type": ["string", "null"]},
                "repository_id": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4"},
                        {"type": "string", "pattern": "^REP-\\d{5}$"},
                    ]
                },
            },
            "anyOf": [
                {"required": ["source_guid"]},
                {"required": ["source_urn"]},
            ],
            "additionalProperties": True,
        },
        "voyage_particulars": {
            "type": "object",
            "required": ["vessel_name", "port_of_arrival", "date_of_arrival"],
            "properties": {
                "vessel_name": {"type": "string"},
                "shipping_line": {"type": ["string", "null"]},
                "port_of_departure": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        {"type": "null"},
                    ]
                },
                "port_of_arrival": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "date_of_arrival": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
            },
            "additionalProperties": True,
        },
        "passenger": {
            "type": "object",
            "required": ["full_name"],
            "properties": {
                "person_id": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
                        {"type": "null"},
                    ]
                },
                "full_name": {"$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"},
                "age": {"$ref": "../defs/_shared_defs.schema.json#/$defs/age_record"},
                "sex": {"$ref": "../defs/_enums.schema.json#/$defs/enum_biological_sex"},
                "calling_or_occupation": {"type": ["string", "null"]},
                "country_of_origin": {"type": ["string", "null"]},
                "last_permanent_residence": {"type": ["string", "null"]},
                "destination": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "media_files": {
            "type": "array",
            "items": {"$ref": "../defs/_document_defs.schema.json#/$defs/source_media"},
        },
        "associated_people": {
            "type": "array",
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/associated_person_entry"},
        },
    }
    envelope["additionalProperties"] = True
    return envelope


def build_naturalization_record_schema() -> Dict[str, Any]:
    """Compile schemas/sources/naturalization_record.schema.json."""
    envelope = build_schema_envelope(
        title="EnumerationSourceNaturalizationRecord",
        version="1.1.0",
        description="Standardized archival schema capturing declarations of intention and naturalization petitions.",
        schema_id="sources/naturalization_record.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "petitioner",
        "court_particulars",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "description": {"type": "string"},
        "record_metadata": {
            "type": "object",
            "required": ["record_category", "record_type"],
            "properties": {
                "source_guid": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                    "description": "RFC 4122 lowercase UUIDv4 primary identifier of source record.",
                },
                "source_urn": {
                    "type": "string",
                    "description": "Legacy citation pointer accepted for backward compatibility.",
                },
                "record_category": {"type": "string"},
                "record_type": {"type": "string"},
                "certificate_number": {"type": ["string", "null"]},
                "petition_number": {"type": ["string", "null"]},
                "repository_id": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4"},
                        {"type": "string", "pattern": "^REP-\\d{5}$"},
                    ]
                },
            },
            "anyOf": [
                {"required": ["source_guid"]},
                {"required": ["source_urn"]},
            ],
            "additionalProperties": True,
        },
        "petitioner": {
            "type": "object",
            "required": ["full_name"],
            "properties": {
                "person_id": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
                        {"type": "null"},
                    ]
                },
                "full_name": {"$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"},
                "birth_date": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                        {"type": "null"},
                    ]
                },
                "birth_place": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        {"type": "null"},
                    ]
                },
                "foreign_allegiance": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "court_particulars": {
            "type": "object",
            "required": ["court_name", "date", "location"],
            "properties": {
                "court_name": {"type": "string"},
                "date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "presiding_judge": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "media_files": {
            "type": "array",
            "items": {"$ref": "../defs/_document_defs.schema.json#/$defs/source_media"},
        },
        "associated_people": {
            "type": "array",
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/associated_person_entry"},
        },
    }
    envelope["additionalProperties"] = True
    return envelope


class EnumerationSourcesCatalog(Mapping[str, Callable[[], Dict[str, Any]]], IntrospectableMixin):
    """Collection manager exposing indexed procedural builders for enumeration source schemas."""

    _BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
        "census_schedule": build_census_schedule_schema,
        "directory_listing": build_directory_listing_schema,
        "immigration_manifest": build_immigration_manifest_schema,
        "naturalization_record": build_naturalization_record_schema,
    }

    _KEY_ALIASES: Dict[str, str] = {
        "census": "census_schedule",
        "census_schedule": "census_schedule",
        "census_schedule.schema.json": "census_schedule",
        "directory": "directory_listing",
        "directory_listing": "directory_listing",
        "directory_listing.schema.json": "directory_listing",
        "immigration": "immigration_manifest",
        "manifest": "immigration_manifest",
        "immigration_manifest": "immigration_manifest",
        "immigration_manifest.schema.json": "immigration_manifest",
        "naturalization": "naturalization_record",
        "naturalization_record": "naturalization_record",
        "naturalization_record.schema.json": "naturalization_record",
    }

    def _resolve_key(self, key: str) -> str:
        raw = str(key or "").strip().lower()
        if raw in self._BUILDERS:
            return raw
        if raw in self._KEY_ALIASES:
            return self._KEY_ALIASES[raw]
        raise KeyError(f"No enumeration source builder found matching key: '{key}'")

    def __getitem__(self, key: str) -> Any:
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