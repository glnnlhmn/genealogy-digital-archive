# Name: specialized.py
# Path: tools/lib/gdaschema/src/gdaschema/sources/specialized.py
# Version: 1.0.0+build.r4

"""Authoritative procedural schema generators for specialized and media source records.

Operational Role:
    Compiles canonical Draft 2020-12 schema definitions for academic diplomas,
    military draft cards, newspaper clippings, personal testimonies, and miscellaneous records.
    Accessible via SpecializedSourcesCatalog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Callable, Dict

from gdacore.introspectable import IntrospectableMixin
from gdaschema.schema_util import build_schema_envelope

__version__ = "1.0.0+build.r4"


def build_academic_credential_schema() -> Dict[str, Any]:
    """Compile schemas/sources/academic_credential.schema.json."""
    envelope = build_schema_envelope(
        title="SpecializedSourceAcademicCredential",
        version="1.1.0",
        description="Standardized archival educational schema capturing diplomas, degrees, and commencement notices.",
        schema_id="sources/academic_credential.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "student",
        "conferral_particulars",
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
                "institution_name": {"type": "string"},
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
        "student": {
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
        "conferral_particulars": {
            "type": "object",
            "required": ["degree_or_certification", "date", "location"],
            "properties": {
                "degree_or_certification": {"type": "string"},
                "date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "honors": {"type": ["string", "null"]},
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


def build_military_draft_schema() -> Dict[str, Any]:
    """Compile schemas/sources/military_draft.schema.json."""
    envelope = build_schema_envelope(
        title="SpecializedSourceMilitaryDraft",
        version="1.1.0",
        description="Standardized archival selective service schema capturing WWI/WWII draft registration cards.",
        schema_id="sources/military_draft.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "registrant",
        "draft_particulars",
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
                "conflict_era": {"type": ["string", "null"]},
                "draft_board": {"type": ["string", "null"]},
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
        "registrant": {
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
                "residence": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        {"type": "null"},
                    ]
                },
                "employer": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "draft_particulars": {
            "type": "object",
            "required": ["registration_date", "location"],
            "properties": {
                "registration_date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "serial_number": {"type": ["string", "null"]},
                "order_number": {"type": ["string", "null"]},
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


def build_newspaper_article_schema() -> Dict[str, Any]:
    """Compile schemas/sources/newspaper_article.schema.json."""
    envelope = build_schema_envelope(
        title="SpecializedSourceNewspaperArticle",
        version="1.1.0",
        description="Standardized archival journalistic schema capturing notices, obituaries, and news clippings.",
        schema_id="sources/newspaper_article.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "publication_particulars",
        "article_content",
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
                "pub_code": {"type": "string"},
                "article_classification": {"type": "string"},
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
        "publication_particulars": {
            "type": "object",
            "required": ["newspaper_title", "issue_date", "location"],
            "properties": {
                "newspaper_title": {"type": "string"},
                "issue_date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "location": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                "page_number": {"type": ["string", "null"]},
                "column_number": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "article_content": {
            "type": "object",
            "required": ["headline"],
            "properties": {
                "headline": {"type": "string"},
                "subheading": {"type": ["string", "null"]},
                "transcript": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "media_files": {
            "type": "array",
            "items": {"$ref": "../defs/_document_defs.schema.json#/$defs/media_clipping"},
        },
        "associated_people": {
            "type": "array",
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/associated_person_entry"},
        },
    }
    envelope["additionalProperties"] = True
    return envelope


def build_personal_testimony_schema() -> Dict[str, Any]:
    """Compile schemas/sources/personal_testimony.schema.json."""
    envelope = build_schema_envelope(
        title="SpecializedSourcePersonalTestimony",
        version="1.1.0",
        description="Standardized archival narrative schema capturing oral histories, interviews, and family diaries.",
        schema_id="sources/personal_testimony.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "informant",
        "narrative_particulars",
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
        "informant": {
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
                "relationship_to_subject": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "narrative_particulars": {
            "type": "object",
            "required": ["recorded_date"],
            "properties": {
                "recorded_date": {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                "interviewer_name": {"type": ["string", "null"]},
                "location": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        {"type": "null"},
                    ]
                },
                "summary": {"type": ["string", "null"]},
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


def build_other_miscellaneous_schema() -> Dict[str, Any]:
    """Compile schemas/sources/other_miscellaneous.schema.json."""
    envelope = build_schema_envelope(
        title="SpecializedSourceOtherMiscellaneous",
        version="1.1.0",
        description="Standardized archival flexible schema capturing unclassified ephemera and documents.",
        schema_id="sources/other_miscellaneous.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "description",
        "record_metadata",
        "document_summary",
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
        "document_summary": {
            "type": "object",
            "required": ["title"],
            "properties": {
                "title": {"type": "string"},
                "date": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                        {"type": "null"},
                    ]
                },
                "location": {
                    "oneOf": [
                        {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                        {"type": "null"},
                    ]
                },
                "notes": {"type": ["string", "null"]},
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


class SpecializedSourcesCatalog(Mapping[str, Callable[[], Dict[str, Any]]], IntrospectableMixin):
    """Collection manager exposing indexed procedural builders for specialized source schemas."""

    _BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
        "academic_credential": build_academic_credential_schema,
        "military_draft": build_military_draft_schema,
        "newspaper_article": build_newspaper_article_schema,
        "personal_testimony": build_personal_testimony_schema,
        "other_miscellaneous": build_other_miscellaneous_schema,
    }

    _KEY_ALIASES: Dict[str, str] = {
        "academic": "academic_credential",
        "academic_credential": "academic_credential",
        "academic_credential.schema.json": "academic_credential",
        "draft": "military_draft",
        "military": "military_draft",
        "military_draft": "military_draft",
        "military_draft.schema.json": "military_draft",
        "news": "newspaper_article",
        "newspaper": "newspaper_article",
        "newspaper_article": "newspaper_article",
        "newspaper_article.schema.json": "newspaper_article",
        "testimony": "personal_testimony",
        "personal_testimony": "personal_testimony",
        "personal_testimony.schema.json": "personal_testimony",
        "miscellaneous": "other_miscellaneous",
        "other": "other_miscellaneous",
        "other_miscellaneous": "other_miscellaneous",
        "other_miscellaneous.schema.json": "other_miscellaneous",
    }

    def _resolve_key(self, key: str) -> str:
        raw = str(key or "").strip().lower()
        if raw in self._BUILDERS:
            return raw
        if raw in self._KEY_ALIASES:
            return self._KEY_ALIASES[raw]
        raise KeyError(f"No specialized source builder found matching key: '{key}'")

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