# Name: xrefs.py
# Path: tools/lib/gdaschema/src/gdaschema/defs/xrefs.py
# Version: 1.0.0+build.r1

"""Authoritative procedural schema generators for schemas/xrefs/ specifications.

Operational Role:
    Compiles canonical Draft 2020-12 schema definitions for multi-entity relationship
    graphs, pedigree numbering projections, and entity-to-source associative bridges.
    Accessible via XRefCatalog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Callable, Dict

from gdacore.introspectable import IntrospectableMixin
from gdaschema.schema_util import build_schema_envelope

__version__ = "1.0.0+build.r1"


def build_family_group_xref_schema() -> Dict[str, Any]:
    """Compile schemas/xrefs/people_family_group_xref.schema.json."""
    envelope = build_schema_envelope(
        title="People_Family_Group_XRef",
        version="1.1.0",
        description="Master cross-reference index of nuclear family groups mapping parental pairings to children.",
        schema_id="xrefs/people_family_group_xref.schema.json",
    )
    envelope["unevaluatedProperties"] = False
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "last_modified",
        "total_families",
        "families",
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "people_family_group_xref.json",
        },
        "_path": {
            "type": "string",
            "const": "data/indexes/people_family_group_xref.json",
        },
        "$schema": {"type": "string"},
        "schema_version": {"type": "string", "const": "1.1.0"},
        "last_modified": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp of last index compilation.",
        },
        "total_families": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of nuclear family groups cataloged.",
        },
        "families": {
            "type": "object",
            "propertyNames": {"pattern": "^FAM-[0-9]{5}-[A-Z]$"},
            "additionalProperties": {
                "type": "object",
                "unevaluatedProperties": False,
                "required": [
                    "family_id",
                    "parent_x",
                    "parent_y",
                    "total_children",
                    "children",
                ],
                "properties": {
                    "family_id": {
                        "type": "string",
                        "pattern": "^FAM-[0-9]{5}-[A-Z]$",
                        "description": "Sequential canonical nuclear family group identifier.",
                    },
                    "parent_x": {
                        "oneOf": [
                            {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
                            {"type": "null"},
                        ]
                    },
                    "parent_y": {
                        "oneOf": [
                            {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
                            {"type": "null"},
                        ]
                    },
                    "total_children": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Total number of children in this nuclear family group.",
                    },
                    "children": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "unevaluatedProperties": False,
                            "required": ["person_id"],
                            "properties": {
                                "person_id": {
                                    "$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"
                                },
                                "relationship_note": {"type": ["string", "null"]},
                            },
                        },
                    },
                },
            },
        },
    }
    return envelope


def build_ahnentafel_xref_schema() -> Dict[str, Any]:
    """Compile schemas/xrefs/people_ahnentafel_xref.schema.json."""
    envelope = build_schema_envelope(
        title="People_Ahnentafel_XRef",
        version="1.0.0",
        description="Structured Ahnentafel lineage cross-reference mapping mathematical pedigree positions to individuals.",
        schema_id="xrefs/people_ahnentafel_xref.schema.json",
    )
    envelope["unevaluatedProperties"] = False
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "last_modified",
        "total_ancestors",
        "ancestors",
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "people_ahnentafel_xref.json",
        },
        "_path": {
            "type": "string",
            "const": "data/indexes/people_ahnentafel_xref.json",
        },
        "$schema": {"type": "string"},
        "schema_version": {"type": "string", "const": "1.0.0"},
        "last_modified": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp of last index compilation.",
        },
        "total_ancestors": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of indexed pedigree ancestor positions.",
        },
        "ancestors": {
            "type": "array",
            "description": "Sequential list of ancestor records mapped by Ahnentafel numbers.",
            "items": {
                "type": "object",
                "unevaluatedProperties": False,
                "required": ["ahnentafel_number", "person_id"],
                "properties": {
                    "ahnentafel_number": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Mathematical position of the ancestor in the pedigree tree.",
                    },
                    "person_id": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"
                    },
                },
            },
        },
    }
    return envelope


def build_newspaper_obituary_xref_schema() -> Dict[str, Any]:
    """Compile schemas/xrefs/sources_newspaper_obituary_xref.schema.json."""
    envelope = build_schema_envelope(
        title="Sources_Newspaper_Obituary_XRef",
        version="1.0.0",
        description="Associative cross-reference bridging deceased individuals, vital dates, and source clippings.",
        schema_id="xrefs/sources_newspaper_obituary_xref.schema.json",
    )
    envelope["unevaluatedProperties"] = False
    envelope["required"] = [
        "_name",
        "_path",
        "$schema",
        "schema_version",
        "last_modified",
        "total_obituaries",
        "obituaries",
    ]
    envelope["properties"] = {
        "_name": {
            "type": "string",
            "const": "sources_newspaper_obituary_xref.json",
        },
        "_path": {
            "type": "string",
            "const": "data/indexes/sources_newspaper_obituary_xref.json",
        },
        "$schema": {"type": "string"},
        "schema_version": {"type": "string", "const": "1.0.0"},
        "last_modified": {
            "$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso",
            "description": "ISO-8601 timestamp of last index compilation.",
        },
        "total_obituaries": {
            "type": "integer",
            "minimum": 0,
            "description": "Total count of obituary entries cataloged in the cross-reference.",
        },
        "obituaries": {
            "type": "array",
            "description": "Cataloged list of published obituaries linking individuals to source clippings.",
            "items": {
                "type": "object",
                "unevaluatedProperties": False,
                "required": [
                    "person_id",
                    "death_date",
                    "source_urn",
                    "pub_code",
                    "pub_date",
                    "headline",
                    "file_path",
                ],
                "properties": {
                    "person_id": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"
                    },
                    "birth_date": {
                        "oneOf": [
                            {"$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"},
                            {"type": "null"},
                        ]
                    },
                    "death_date": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"
                    },
                    "age_at_death": {
                        "oneOf": [
                            {"$ref": "../defs/_shared_defs.schema.json#/$defs/age_record"},
                            {"type": "null"},
                        ]
                    },
                    "source_urn": {
                        "type": "string",
                        "description": "Archival Uniform Resource Name for the obituary clipping.",
                    },
                    "pub_code": {
                        "type": "string",
                        "maxLength": 6,
                        "description": "Standardized newspaper publication authority token.",
                    },
                    "pub_date": {
                        "$ref": "../defs/_shared_defs.schema.json#/$defs/date_interpreted"
                    },
                    "headline": {
                        "type": "string",
                        "description": "Verbatim or standardized article headline.",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the granular archival record file on disk.",
                    },
                },
            },
        },
    }
    return envelope


class XRefCatalog(Mapping[str, Callable[[], Dict[str, Any]]], IntrospectableMixin):
    """Collection manager exposing indexed procedural builders for cross-reference schemas."""

    _BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
        "people_family_group_xref": build_family_group_xref_schema,
        "people_ahnentafel_xref": build_ahnentafel_xref_schema,
        "sources_newspaper_obituary_xref": build_newspaper_obituary_xref_schema,
    }

    _KEY_ALIASES: Dict[str, str] = {
        "family_group": "people_family_group_xref",
        "family_group_index": "people_family_group_xref",
        "family_group_index.schema.json": "people_family_group_xref",
        "people_family_group": "people_family_group_xref",
        "people_family_group_xref.schema.json": "people_family_group_xref",
        "ahnentafel": "people_ahnentafel_xref",
        "ahnentafel_index": "people_ahnentafel_xref",
        "ahnentafel_index.schema.json": "people_ahnentafel_xref",
        "people_ahnentafel": "people_ahnentafel_xref",
        "people_ahnentafel_xref.schema.json": "people_ahnentafel_xref",
        "newspaper_obituary": "sources_newspaper_obituary_xref",
        "newspaper_obituary_index": "sources_newspaper_obituary_xref",
        "newspaper_obituary_index.schema.json": "sources_newspaper_obituary_xref",
        "obituary": "sources_newspaper_obituary_xref",
        "sources_newspaper_obituary_xref.schema.json": "sources_newspaper_obituary_xref",
    }

    def _resolve_key(self, key: str) -> str:
        """Normalize raw key or alias into canonical logical key."""
        raw = str(key or "").strip().lower()
        if raw in self._BUILDERS:
            return raw
        if raw in self._KEY_ALIASES:
            return self._KEY_ALIASES[raw]
        raise KeyError(f"No cross-reference builder found matching key: '{key}'")

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