# Name: vital.py
# Path: tools/lib/gdaschema/src/gdaschema/sources/vital.py
# Version: 1.0.0+build.r6

"""Authoritative procedural schema generators for vital and ecclesiastical source records.

Operational Role:
    Compiles canonical Draft 2020-12 schema definitions for birth certificates,
    marriage licenses, death certificates, church baptisms, and cemetery headstones.
    Accessible via VitalSourcesCatalog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Callable, Dict

from gdacore.introspectable import IntrospectableMixin
from gdaschema.schema_util import build_schema_envelope

__version__ = "1.0.0+build.r6"


def build_birth_certificate_schema() -> Dict[str, Any]:
    """Compile schemas/sources/birth_certificate.schema.json."""
    envelope = build_schema_envelope(
        title="VitalSourceBirthCertificate",
        version="1.1.0",
        description="Standardized archival certificate schema capturing civil birth registrations.",
        schema_id="sources/birth_certificate.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "child",
        "event_particulars",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "description": {"type": "string"},
        "record_metadata": {
            "type": "object",
            "required": ["source_guid", "record_category", "record_type"],
            "properties": {
                "source_guid": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                    "description": "RFC 4122 lowercase UUIDv4 primary identifier of source record.",
                },
                "record_category": {"type": "string", "enum": ["VITAL"]},
                "record_type": {"type": "string", "enum": ["BIRTH_CERTIFICATE"]},
                "certificate_number": {"type": ["string", "null"]},
                "state_file_number": {"type": ["string", "null"]},
                "repository_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4"},
            },
            "additionalProperties": False,
        },
        "child": {
            "type": "object",
            "required": ["full_name", "sex"],
            "properties": {
                "person_id": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
                        {"type": "null"},
                    ]
                },
                "full_name": {"$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"},
                "sex": {"$ref": "../defs/_enums.schema.json#/$defs/enum_biological_sex"},
                "birth_order": {"type": ["string", "null"]},
                "plurality": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "event_particulars": {
            "type": "object",
            "required": ["date", "location"],
            "properties": {
                "date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "hospital_or_institution": {"type": ["string", "null"]},
                "attendant_name": {"type": ["string", "null"]},
                "attendant_role": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "parents": {
            "type": "object",
            "properties": {
                "father": {
                    "type": "object",
                    "properties": {
                        "person_id": {
                            "oneOf": [
                                {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
                                {"type": "null"},
                            ]
                        },
                        "full_name": {"$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"},
                        "age": {"$ref": "../defs/_shared_defs.schema.json#/$defs/age_record"},
                        "birthplace": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        "occupation": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
                "mother": {
                    "type": "object",
                    "properties": {
                        "person_id": {
                            "oneOf": [
                                {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
                                {"type": "null"},
                            ]
                        },
                        "full_name": {"$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"},
                        "age": {"$ref": "../defs/_shared_defs.schema.json#/$defs/age_record"},
                        "birthplace": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        "occupation": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "informant": {
            "type": "object",
            "properties": {
                "name": {"type": ["string", "null"]},
                "relation_to_child": {"type": ["string", "null"]},
                "residence": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
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
    envelope["additionalProperties"] = False
    return envelope


def build_marriage_license_schema() -> Dict[str, Any]:
    """Compile schemas/sources/marriage_license.schema.json."""
    envelope = build_schema_envelope(
        title="VitalSourceMarriageLicense",
        version="1.1.0",
        description="Standardized archival certificate schema capturing civil and holy marriage contracts.",
        schema_id="sources/marriage_license.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "spouses",
        "ceremony_particulars",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "description": {"type": "string"},
        "record_metadata": {
            "type": "object",
            "required": ["source_guid", "record_category", "record_type"],
            "properties": {
                "source_guid": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                    "description": "RFC 4122 lowercase UUIDv4 primary identifier of source record.",
                },
                "record_category": {"type": "string", "enum": ["VITAL"]},
                "record_type": {"type": "string", "enum": ["MARRIAGE_LICENSE"]},
                "license_number": {"type": ["string", "null"]},
                "docket_volume": {"type": ["string", "null"]},
                "docket_page": {"type": ["string", "null"]},
                "repository_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4"},
            },
            "additionalProperties": False,
        },
        "spouses": {
            "type": "object",
            "required": ["spouse_1", "spouse_2"],
            "properties": {
                "spouse_1": {
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
                        "residence": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        "occupation": {"type": ["string", "null"]},
                        "marital_status_prior": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
                "spouse_2": {
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
                        "residence": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        "occupation": {"type": ["string", "null"]},
                        "marital_status_prior": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "ceremony_particulars": {
            "type": "object",
            "required": ["date", "location"],
            "properties": {
                "date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "officiant_name": {"type": ["string", "null"]},
                "officiant_title": {"type": ["string", "null"]},
                "witnesses": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
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
    envelope["additionalProperties"] = False
    return envelope


def build_death_certificate_schema() -> Dict[str, Any]:
    """Compile schemas/sources/death_certificate.schema.json."""
    envelope = build_schema_envelope(
        title="VitalSourceDeathCertificate",
        version="1.1.0",
        description="Standardized archival certificate schema capturing civil death and medical records.",
        schema_id="sources/death_certificate.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "decedent",
        "event_particulars",
        "cause_of_death_details",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "description": {"type": "string"},
        "record_metadata": {
            "type": "object",
            "required": ["source_guid", "record_category", "record_type"],
            "properties": {
                "source_guid": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                    "description": "RFC 4122 lowercase UUIDv4 primary identifier of source record.",
                },
                "record_category": {"type": "string", "enum": ["VITAL"]},
                "record_type": {"type": "string", "enum": ["DEATH_CERTIFICATE"]},
                "certificate_number": {"type": ["string", "null"]},
                "registered_number": {"type": ["string", "null"]},
                "repository_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4"},
            },
            "additionalProperties": False,
        },
        "decedent": {
            "type": "object",
            "required": ["full_name", "sex"],
            "properties": {
                "person_id": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
                        {"type": "null"},
                    ]
                },
                "full_name": {"$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"},
                "sex": {"$ref": "../defs/_enums.schema.json#/$defs/enum_biological_sex"},
                "age_at_death": {"$ref": "../defs/_shared_defs.schema.json#/$defs/age_record"},
                "marital_status": {"type": ["string", "null"]},
                "spouse_name": {"type": ["string", "null"]},
                "occupation": {"type": ["string", "null"]},
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
            },
            "additionalProperties": False,
        },
        "event_particulars": {
            "type": "object",
            "required": ["date", "location"],
            "properties": {
                "date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "hospital_or_facility": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "cause_of_death_details": {
            "type": "object",
            "required": ["primary_cause"],
            "properties": {
                "primary_cause": {"$ref": "../defs/_death_defs.schema.json#/$defs/cause_of_death"},
                "contributory_causes": {
                    "type": "array",
                    "items": {"$ref": "../defs/_death_defs.schema.json#/$defs/cause_of_death"},
                },
                "certifying_physician": {"type": ["string", "null"]},
                "coroner_inquest": {"type": ["boolean", "null"]},
            },
            "additionalProperties": False,
        },
        "disposition": {
            "type": "object",
            "properties": {
                "type": {"type": ["string", "null"], "enum": ["Burial", "Cremation", "Removal", "Entombment", None]},
                "date": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                        {"type": "null"},
                    ]
                },
                "cemetery_name": {"type": ["string", "null"]},
                "location": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        {"type": "null"},
                    ]
                },
                "undertaker_name": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
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
    envelope["additionalProperties"] = False
    return envelope


def build_church_baptism_schema() -> Dict[str, Any]:
    """Compile schemas/sources/church_baptism.schema.json."""
    envelope = build_schema_envelope(
        title="VitalSourceChurchBaptism",
        version="1.1.0",
        description="Standardized archival ecclesiastical schema capturing christenings and parish baptisms.",
        schema_id="sources/church_baptism.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "initiate",
        "ceremony_particulars",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "description": {"type": "string"},
        "record_metadata": {
            "type": "object",
            "required": ["source_guid", "record_category", "record_type"],
            "properties": {
                "source_guid": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                    "description": "RFC 4122 lowercase UUIDv4 primary identifier of source record.",
                },
                "record_category": {"type": "string", "enum": ["CHURCH"]},
                "record_type": {"type": "string", "enum": ["BAPTISM_PARISH_REGISTER"]},
                "parish_register_volume": {"type": ["string", "null"]},
                "entry_number": {"type": ["string", "null"]},
                "repository_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4"},
            },
            "additionalProperties": False,
        },
        "initiate": {
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
                "sex": {"$ref": "../defs/_enums.schema.json#/$defs/enum_biological_sex"},
                "birth_date": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                        {"type": "null"},
                    ]
                },
            },
            "additionalProperties": False,
        },
        "ceremony_particulars": {
            "type": "object",
            "required": ["date", "church_name", "location"],
            "properties": {
                "date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "church_name": {"type": "string"},
                "denomination": {"type": ["string", "null"]},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "officiant_name": {"type": ["string", "null"]},
                "sponsors": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
        },
        "parents": {
            "type": "object",
            "properties": {
                "father_name": {"type": ["string", "null"]},
                "mother_name": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
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
    envelope["additionalProperties"] = False
    return envelope


def build_cemetery_marker_schema() -> Dict[str, Any]:
    """Compile schemas/sources/cemetery_marker.schema.json."""
    envelope = build_schema_envelope(
        title="VitalSourceCemeteryMarker",
        version="1.1.0",
        description="Standardized archival physical monument schema capturing headstones and cemetery surveys.",
        schema_id="sources/cemetery_marker.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "monument_particulars",
        "inscriptions",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "description": {"type": "string"},
        "record_metadata": {
            "type": "object",
            "required": ["source_guid", "record_category", "record_type"],
            "properties": {
                "source_guid": {
                    "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                    "description": "RFC 4122 lowercase UUIDv4 primary identifier of source record.",
                },
                "record_category": {"type": "string", "enum": ["VITAL"]},
                "record_type": {"type": "string", "enum": ["CEMETERY_MARKER"]},
                "cemetery_name": {"type": "string"},
                "site_id": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/site_id"},
                        {"type": "null"},
                    ]
                },
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "survey_date": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                        {"type": "null"},
                    ]
                },
            },
            "additionalProperties": False,
        },
        "monument_particulars": {
            "type": "object",
            "properties": {
                "plot_section": {"type": ["string", "null"]},
                "plot_number": {"type": ["string", "null"]},
                "material": {"type": ["string", "null"], "enum": ["Granite", "Marble", "Sandstone", "Slate", "Bronze", "Limestone", "Wood", None]},
                "condition": {"type": ["string", "null"], "enum": ["Sound", "Weathered", "Broken", "Sunken", "Illegible", "Overgrown", None]},
            },
            "additionalProperties": False,
        },
        "inscriptions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["inscribed_name"],
                "properties": {
                    "person_id": {
                        "oneOf": [
                            {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
                            {"type": "null"},
                        ]
                    },
                    "inscribed_name": {"$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"},
                    "birth_date": {
                        "oneOf": [
                            {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                            {"type": "null"},
                        ]
                    },
                    "death_date": {
                        "oneOf": [
                            {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                            {"type": "null"},
                        ]
                    },
                    "age_inscribed": {"type": ["string", "null"]},
                    "epitaph": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
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
    envelope["additionalProperties"] = False
    return envelope


class VitalSourcesCatalog(Mapping[str, Callable[[], Dict[str, Any]]], IntrospectableMixin):
    """Collection manager exposing indexed procedural builders for vital source schemas."""

    _BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
        "birth_certificate": build_birth_certificate_schema,
        "marriage_license": build_marriage_license_schema,
        "death_certificate": build_death_certificate_schema,
        "church_baptism": build_church_baptism_schema,
        "cemetery_marker": build_cemetery_marker_schema,
    }

    _KEY_ALIASES: Dict[str, str] = {
        "birth": "birth_certificate",
        "birth_certificate": "birth_certificate",
        "birth_certificate.schema.json": "birth_certificate",
        "marriage": "marriage_license",
        "marriage_license": "marriage_license",
        "marriage_license.schema.json": "marriage_license",
        "death": "death_certificate",
        "death_certificate": "death_certificate",
        "death_certificate.schema.json": "death_certificate",
        "baptism": "church_baptism",
        "church_baptism": "church_baptism",
        "church_baptism.schema.json": "church_baptism",
        "cemetery": "cemetery_marker",
        "cemetery_marker": "cemetery_marker",
        "marker": "cemetery_marker",
        "cemetery_marker.schema.json": "cemetery_marker",
    }

    def _resolve_key(self, key: str) -> str:
        raw = str(key or "").strip().lower()
        if raw in self._BUILDERS:
            return raw
        if raw in self._KEY_ALIASES:
            return self._KEY_ALIASES[raw]
        raise KeyError(f"No vital source builder found matching key: '{key}'")

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