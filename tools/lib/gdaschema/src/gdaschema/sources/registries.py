# Name: registries.py
# Path: tools/lib/gdaschema/src/gdaschema/sources/registries.py
# Version: 1.0.0+build.r3

"""Authoritative procedural schema generators for archival source registry schemas.

Operational Role:
    Compiles canonical Draft 2020-12 schema definitions for master source citation
    registries, consolidated newspaper clipping indices, and sexton cemetery rolls.
    Accessible via SourceRegistriesCatalog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Callable, Dict

from gdacore.introspectable import IntrospectableMixin
from gdaschema.schema_util import build_schema_envelope

__version__ = "1.0.0+build.r3"


def build_source_registry_schema() -> Dict[str, Any]:
    """Compile schemas/sources/source_registry.schema.json."""
    envelope = build_schema_envelope(
        title="MasterSourceRegistry",
        version="1.1.0",
        description="Master authoritative registry tracking physical custody, provenance, and citations for all archival sources.",
        schema_id="sources/source_registry.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "version",
        "last_updated",
        "sources",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "version": {"type": "string"},
        "last_updated": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source_guid", "title", "record_category", "repository_id"],
                "properties": {
                    "source_guid": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                        "description": "RFC 4122 lowercase UUIDv4 primary identifier of source citation.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Formal or descriptive citation title.",
                    },
                    "record_category": {
                        "type": "string",
                        "description": "High-level domain category (e.g. VITAL, CENSUS, LEGAL, CHURCH, NEWS, OTHER).",
                    },
                    "record_type": {
                        "type": "string",
                        "description": "Granular classification token matching _token_registry.json.",
                    },
                    "repository_id": {
                        "type": "string",
                        "pattern": "^REP-\\d{5}$",
                        "description": "Foreign key reference to custodial repository in repositories.json.",
                    },
                    "collection_title": {
                        "type": ["string", "null"],
                        "description": "Name of archival collection, record group, or series.",
                    },
                    "call_number": {
                        "type": ["string", "null"],
                        "description": "Shelf mark, volume locator, microfilm roll, or digital identifier.",
                    },
                    "jurisdiction": {
                        "oneOf": [
                            {"$ref": "../defs/_shared_defs.schema.json#/$defs/location"},
                            {"type": "null"},
                        ]
                    },
                    "coverage_dates": {
                        "type": "object",
                        "properties": {
                            "date_start": {"type": ["string", "null"]},
                            "date_end": {"type": ["string", "null"]},
                        },
                        "additionalProperties": False,
                    },
                    "digital_access_url": {
                        "type": ["string", "null"],
                        "description": "Canonical persistent external URL (e.g., FamilySearch, Ancestry, NARA).",
                    },
                    "record_count": {
                        "type": ["integer", "null"],
                        "minimum": 0,
                    },
                    "notes": {
                        "type": ["string", "null"],
                        "description": "Custodial history, provenance, or condition notes.",
                    },
                },
                "additionalProperties": False,
            },
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_newspaper_registry_schema() -> Dict[str, Any]:
    """Compile schemas/sources/newspaper_registry.schema.json."""
    envelope = build_schema_envelope(
        title="NewspaperRegistryRecord",
        version="1.1.0",
        description="Consolidated registry indexing historical newspaper publications, issues, clippings, and articles.",
        schema_id="sources/newspaper_registry.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "version",
        "last_updated",
        "publications",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "version": {"type": "string"},
        "last_updated": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"
        },
        "publications": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["pub_code", "pub_name", "location", "issues"],
                "properties": {
                    "pub_code": {
                        "type": "string",
                        "maxLength": 6,
                        "description": "Standard publication identifier token matching pub_codes in _token_registry.json.",
                    },
                    "pub_name": {
                        "type": "string",
                        "description": "Formal newspaper title (e.g., 'The Carlisle Sentinel').",
                    },
                    "location": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/location",
                        "description": "Town or city where the newspaper was published.",
                    },
                    "frequency": {
                        "type": ["string", "null"],
                        "enum": ["Daily", "Weekly", "Semi-Weekly", "Monthly", None],
                    },
                    "issues": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["issue_date", "articles"],
                            "properties": {
                                "issue_date": {
                                    "$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"
                                },
                                "edition": {"type": ["string", "null"]},
                                "page_count": {"type": ["integer", "null"], "minimum": 1},
                                "articles": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["source_guid", "category"],
                                        "properties": {
                                            "source_guid": {
                                                "$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4",
                                                "description": "RFC 4122 lowercase UUIDv4 primary identifier of news article.",
                                            },
                                            "headline": {"type": ["string", "null"]},
                                            "category": {
                                                "type": "string",
                                                "maxLength": 6,
                                                "description": "Classification code matching news_classifications.",
                                            },
                                            "page_number": {"type": ["string", "null"]},
                                            "column": {"type": ["string", "null"]},
                                            "primary_subject_ids": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"
                                                },
                                            },
                                            "clippings": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "../defs/_document_defs.schema.json#/$defs/media_clipping"
                                                },
                                            },
                                        },
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "additionalProperties": False,
                        },
                    },
                },
                "additionalProperties": False,
            },
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_cemetery_registry_schema() -> Dict[str, Any]:
    """Compile schemas/sources/cemetery_registry.schema.json."""
    envelope = build_schema_envelope(
        title="CemeteryRegistryRecord",
        version="1.1.0",
        description="Standardized registry capturing cemetery plot ledgers, sexton books, and grave surveys.",
        schema_id="sources/cemetery_registry.schema.json",
    )
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "version",
        "last_updated",
        "site_id",
        "cemetery_name",
        "location",
        "plots",
    ]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "$schema": {"type": "string"},
        "version": {"type": "string"},
        "last_updated": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"
        },
        "site_id": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/site_id",
            "description": "Foreign key reference to physical site in sites.json.",
        },
        "cemetery_name": {"type": "string"},
        "location": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/location"
        },
        "sexton_or_custodian": {"type": ["string", "null"]},
        "survey_date": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                {"type": "null"},
            ]
        },
        "plots": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["plot_locator", "interments"],
                "properties": {
                    "plot_locator": {
                        "type": "string",
                        "description": "Lot, Section, Row, or Tomb coordinate.",
                    },
                    "marker_guid": {
                        "oneOf": [
                            {"$ref": "../defs/_shared_defs.schema.json#/$defs/uuid_v4"},
                            {"type": "null"},
                        ],
                        "description": "Optional UUIDv4 link to detailed cemetery_marker source record.",
                    },
                    "condition": {
                        "type": ["string", "null"],
                        "enum": ["Sound", "Weathered", "Broken", "Sunken", "Illegible", "Overgrown", None],
                    },
                    "interments": {
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
                                "inscribed_name": {
                                    "$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"
                                },
                                "birth_year": {"type": ["integer", "null"]},
                                "death_year": {"type": ["integer", "null"]},
                                "age_inscribed": {"type": ["string", "null"]},
                                "relationship_text": {"type": ["string", "null"]},
                            },
                            "additionalProperties": False,
                        },
                    },
                },
                "additionalProperties": False,
            },
        },
    }
    envelope["additionalProperties"] = False
    return envelope


class SourceRegistriesCatalog(
    Mapping[str, Callable[[], Dict[str, Any]]], IntrospectableMixin
):
    """Collection manager exposing indexed procedural builders for source registry schemas."""

    _BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
        "source_registry": build_source_registry_schema,
        "newspaper_registry": build_newspaper_registry_schema,
        "cemetery_registry": build_cemetery_registry_schema,
    }

    _KEY_ALIASES: Dict[str, str] = {
        "sources": "source_registry",
        "source": "source_registry",
        "source_registry.schema.json": "source_registry",
        "newspapers": "newspaper_registry",
        "newspaper_registry.schema.json": "newspaper_registry",
        "cemetery": "cemetery_registry",
        "cemetery_registry.schema.json": "cemetery_registry",
    }

    def _resolve_key(self, key: str) -> str:
        """Normalize raw key or alias into canonical logical key."""
        raw = str(key or "").strip().lower()
        if raw in self._BUILDERS:
            return raw
        if raw in self._KEY_ALIASES:
            return self._KEY_ALIASES[raw]
        raise KeyError(f"No source registry builder found matching key: '{key}'")

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