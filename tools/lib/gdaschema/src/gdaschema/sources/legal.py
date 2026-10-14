# Name: legal.py
# Path: tools/lib/gdaschema/src/gdaschema/sources/legal.py
# Version: 1.0.0+build.r4

"""Authoritative procedural schema generators for legal and fiscal source records.

Operational Role:
    Compiles canonical Draft 2020-12 schema definitions for divorce decrees,
    probate packets, land deed transfers, and tax assessment rolls.
    Accessible via LegalSourcesCatalog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Callable, Dict

from gdacore.introspectable import IntrospectableMixin
from gdaschema.schema_util import build_schema_envelope

__version__ = "1.0.0+build.r4"


def build_divorce_report_schema() -> Dict[str, Any]:
    """Compile schemas/sources/divorce_report.schema.json."""
    envelope = build_schema_envelope(
        title="LegalSourceDivorceReport",
        version="1.1.0",
        description="Standardized archival judicial schema capturing civil marriage dissolutions.",
        schema_id="sources/divorce_report.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "parties",
        "decree_particulars",
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
                "case_number": {"type": ["string", "null"]},
                "docket_volume": {"type": ["string", "null"]},
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
        "parties": {
            "type": "object",
            "required": ["plaintiff", "defendant"],
            "properties": {
                "plaintiff": {
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
                    },
                    "additionalProperties": True,
                },
                "defendant": {
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
                    },
                    "additionalProperties": True,
                },
            },
            "additionalProperties": True,
        },
        "decree_particulars": {
            "type": "object",
            "required": ["date", "court_name", "location"],
            "properties": {
                "date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "court_name": {"type": "string"},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "grounds_stated": {"type": ["string", "null"]},
                "custody_orders": {"type": ["string", "null"]},
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


def build_probate_record_schema() -> Dict[str, Any]:
    """Compile schemas/sources/probate_record.schema.json."""
    envelope = build_schema_envelope(
        title="LegalSourceProbateRecord",
        version="1.1.0",
        description="Standardized archival testamentary schema capturing wills, administrations, and estate inventories.",
        schema_id="sources/probate_record.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "decedent",
        "court_proceedings",
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
                "estate_file_number": {"type": ["string", "null"]},
                "will_book": {"type": ["string", "null"]},
                "will_page": {"type": ["string", "null"]},
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
        "decedent": {
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
                "death_date": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                        {"type": "null"},
                    ]
                },
                "residence": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        {"type": "null"},
                    ]
                },
            },
            "additionalProperties": True,
        },
        "court_proceedings": {
            "type": "object",
            "required": ["probate_date", "court_name", "location"],
            "properties": {
                "probate_date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "court_name": {"type": "string"},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "executors": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "beneficiaries": {
                    "type": "array",
                    "items": {"type": "string"},
                },
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


def build_land_deed_schema() -> Dict[str, Any]:
    """Compile schemas/sources/land_deed.schema.json."""
    envelope = build_schema_envelope(
        title="LegalSourceLandDeed",
        version="1.1.0",
        description="Standardized archival conveyancing schema capturing deeds, indentures, and land grants.",
        schema_id="sources/land_deed.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "conveyance_particulars",
        "grantor",
        "grantee",
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
                "deed_book": {"type": ["string", "null"]},
                "deed_page": {"type": ["string", "null"]},
                "instrument_number": {"type": ["string", "null"]},
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
        "conveyance_particulars": {
            "type": "object",
            "required": ["date", "location"],
            "properties": {
                "date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "consideration_amount": {"type": ["string", "null"]},
                "acreage": {"type": ["number", "null"]},
                "legal_description": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "grantor": {
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
                "residence": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        {"type": "null"},
                    ]
                },
            },
            "additionalProperties": True,
        },
        "grantee": {
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
                "residence": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        {"type": "null"},
                    ]
                },
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


def build_tax_assessment_schema() -> Dict[str, Any]:
    """Compile schemas/sources/tax_assessment.schema.json."""
    envelope = build_schema_envelope(
        title="LegalSourceTaxAssessment",
        version="1.1.0",
        description="Standardized archival fiscal schema capturing municipal and county tax duplicate books.",
        schema_id="sources/tax_assessment.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "taxpayer",
        "assessment_particulars",
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
                "tax_year": {"type": "integer"},
                "assessment_roll": {"type": ["string", "null"]},
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
        "taxpayer": {
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
            },
            "additionalProperties": True,
        },
        "assessment_particulars": {
            "type": "object",
            "required": ["location"],
            "properties": {
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "real_estate_value": {"type": ["number", "null"]},
                "personal_property_value": {"type": ["number", "null"]},
                "total_tax_assessed": {"type": ["number", "null"]},
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


class LegalSourcesCatalog(Mapping[str, Callable[[], Dict[str, Any]]], IntrospectableMixin):
    """Collection manager exposing indexed procedural builders for legal source schemas."""

    _BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
        "divorce_report": build_divorce_report_schema,
        "probate_record": build_probate_record_schema,
        "land_deed": build_land_deed_schema,
        "tax_assessment": build_tax_assessment_schema,
    }

    _KEY_ALIASES: Dict[str, str] = {
        "divorce": "divorce_report",
        "divorce_report": "divorce_report",
        "divorce_report.schema.json": "divorce_report",
        "will": "probate_record",
        "probate": "probate_record",
        "probate_record": "probate_record",
        "probate_record.schema.json": "probate_record",
        "deed": "land_deed",
        "land_deed": "land_deed",
        "land_deed.schema.json": "land_deed",
        "tax": "tax_assessment",
        "tax_assessment": "tax_assessment",
        "tax_assessment.schema.json": "tax_assessment",
    }

    def _resolve_key(self, key: str) -> str:
        raw = str(key or "").strip().lower()
        if raw in self._BUILDERS:
            return raw
        if raw in self._KEY_ALIASES:
            return self._KEY_ALIASES[raw]
        raise KeyError(f"No legal source builder found matching key: '{key}'")

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