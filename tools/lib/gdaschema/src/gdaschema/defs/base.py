# Name: base.py
# Path: tools/lib/gdaschema/src/gdaschema/defs/base.py
# Version: 1.0.0+build.r9

"""Authoritative procedural schema generators for base definitions and shared structures.

Operational Role:
    Compiles canonical Draft 2020-12 schema definitions for controlled vocabularies
    (enums), shared structural primitives, cross-references, cause of death,
    registry envelopes, census line entries, and military service records.
    Accessible via BaseCatalog and BaseDefsCatalog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Callable, Dict

from gdacore.introspectable import IntrospectableMixin
from gdacore.vocabulary_manager import GDAVocabularyManager
from gdaschema.schema_util import build_schema_envelope

__version__ = "1.0.0+build.r9"


def build_enums() -> Dict[str, Any]:
    """Compile schemas/defs/_enums.schema.json dynamically from GDAVocabularyManager."""
    vocab_mgr = GDAVocabularyManager()
    envelope = build_schema_envelope(
        title="GenealogyControlledVocabularies",
        version="1.1.0",
        description="Authoritative single source of truth for controlled taxonomies across the archive.",
        schema_id="defs/_enums.schema.json",
    )
    defs_map: Dict[str, Any] = {}
    if hasattr(vocab_mgr, "compile_json_schemas") and callable(vocab_mgr.compile_json_schemas):
        defs_map = vocab_mgr.compile_json_schemas()
    elif hasattr(vocab_mgr, "compile_all_json_schemas") and callable(vocab_mgr.compile_all_json_schemas):
        defs_map = vocab_mgr.compile_all_json_schemas()
    elif hasattr(vocab_mgr, "get_all_schemas") and callable(vocab_mgr.get_all_schemas):
        defs_map = vocab_mgr.get_all_schemas()
    else:
        for voc_name in vocab_mgr:
            def_name = f"enum_{voc_name}" if not str(voc_name).startswith("enum_") else str(voc_name)
            if hasattr(vocab_mgr, "get_json_schema") and callable(vocab_mgr.get_json_schema):
                defs_map[def_name] = vocab_mgr.get_json_schema(voc_name)
            else:
                tokens = list(vocab_mgr[voc_name])
                defs_map[def_name] = {
                    "type": "string",
                    "enum": tokens,
                    "description": f"Controlled vocabulary tokens for {voc_name}.",
                }

    if "enum_date_modifier" in defs_map and "enum_vital_date_modifier" not in defs_map:
        defs_map["enum_vital_date_modifier"] = defs_map["enum_date_modifier"]
    if "enum_sex" in defs_map and "enum_biological_sex" not in defs_map:
        defs_map["enum_biological_sex"] = defs_map["enum_sex"]

    envelope["$defs"] = defs_map
    return envelope


def build_shared_defs() -> Dict[str, Any]:
    """Compile schemas/defs/_shared_defs.schema.json."""
    envelope = build_schema_envelope(
        title="CentralizedSharedSchemaDefinitions",
        version="1.2.0",
        description="Authoritative reusable structural primitives, identifier patterns, and sub-schemas.",
        schema_id="defs/_shared_defs.schema.json",
    )
    envelope["$defs"] = {
        "uuid_v4": {
            "type": "string",
            "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            "description": "RFC 4122 lowercase UUIDv4 format.",
        },
        "person_id": {
            "type": "string",
            "pattern": "^IND-\\d{5}$",
            "description": "Sequential 5-digit canonical individual identifier.",
        },
        "location_id": {
            "type": "string",
            "pattern": "^LOC-\\d{5}$",
            "description": "Sequential 5-digit canonical location identifier.",
        },
        "site_id": {
            "type": "string",
            "pattern": "^SID-\\d{5}$",
            "description": "Sequential 5-digit canonical physical facility identifier.",
        },
        "source_id": {
            "$ref": "#/$defs/uuid_v4",
            "description": "UUIDv4 source citation identifier.",
        },
        "fact_id": {
            "$ref": "#/$defs/uuid_v4",
            "description": "RFC 4122 lowercase UUIDv4 assertion identifier.",
        },
        "note_id": {
            "type": "string",
            "pattern": "^NOT-\\d{5}$",
            "description": "Sequential 5-digit canonical note entry identifier.",
        },
        "vital_year": {
            "type": "integer",
            "minimum": 1500,
            "maximum": 2100,
            "description": "Constrained integer year for vital life events.",
        },
        "timestamp_iso": {
            "type": "string",
            "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z|[+-]\\d{2}:\\d{2})?$",
            "description": "ISO 8601 extended timestamp format.",
        },
        "tombstone": {
            "type": "object",
            "description": "In-place deprecation and tombstone metadata for absorbed or superseded records.",
            "required": ["is_deprecated"],
            "properties": {
                "is_deprecated": {"type": "boolean"},
                "superseded_by": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "null"},
                    ]
                },
                "deprecated_at": {
                    "oneOf": [
                        {"$ref": "#/$defs/timestamp_iso"},
                        {"type": "null"},
                    ]
                },
                "reason": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "quay_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 3,
            "description": "0=Unreliable, 1=Questionable, 2=Secondary, 3=Direct Primary Evidence.",
        },
        "age_record": {
            "type": "object",
            "description": "Documented age assertion supporting both parsed integers and raw text.",
            "properties": {
                "years": {"type": ["integer", "null"], "minimum": 0},
                "months": {"type": ["integer", "null"], "minimum": 0, "maximum": 11},
                "days": {"type": ["integer", "null"], "minimum": 0, "maximum": 30},
                "raw_text": {"type": ["string", "null"]},
                "verbatim": {"type": ["string", "null"]},
            },
            "anyOf": [
                {"required": ["years"]},
                {"required": ["raw_text"]},
                {"required": ["verbatim"]},
            ],
            "additionalProperties": False,
        },
        "street_address": {
            "type": "object",
            "description": "Physical postal delivery line and coordinates anchored to a civil location_id.",
            "properties": {
                "address_line_1": {"type": ["string", "null"]},
                "address_line_2": {"type": ["string", "null"]},
                "postal_code": {"type": ["string", "null"]},
                "coordinates": {
                    "type": ["object", "null"],
                    "properties": {
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"},
                    },
                    "required": ["latitude", "longitude"],
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "date_interpreted": {
            "type": "object",
            "description": "Structured genealogical temporal expression.",
            "required": ["date_raw", "year"],
            "properties": {
                "date_raw": {"type": "string"},
                "date_iso": {"type": ["string", "null"]},
                "year": {"$ref": "#/$defs/vital_year"},
                "month": {"type": ["integer", "null"], "minimum": 1, "maximum": 12},
                "day": {"type": ["integer", "null"], "minimum": 1, "maximum": 31},
                "modifier": {"$ref": "_enums.schema.json#/$defs/enum_date_modifier"},
                "quay_start": {"type": ["integer", "null"], "minimum": 0, "maximum": 3},
                "quay_end": {"type": ["integer", "null"], "minimum": 0, "maximum": 3},
                "confidence": {"type": ["number", "null"], "minimum": 0.0, "maximum": 1.0},
            },
            "additionalProperties": False,
        },
        "location": {
            "type": "object",
            "description": "Location assertion reference linking canonical IDs to verbatim text.",
            "required": ["location_id", "verbatim"],
            "properties": {
                "location_id": {"$ref": "#/$defs/location_id"},
                "verbatim": {"type": "string"},
                "site_id": {
                    "oneOf": [
                        {"$ref": "#/$defs/site_id"},
                        {"type": "null"},
                    ]
                },
            },
            "additionalProperties": False,
        },
        "note_entry": {
            "type": "object",
            "description": "Archival contextual note block.",
            "required": ["note_id", "created_at"],
            "properties": {
                "note_id": {"$ref": "#/$defs/note_id"},
                "text": {"type": "string"},
                "note_text": {"type": "string"},
                "type": {"$ref": "_enums.schema.json#/$defs/enum_note_type"},
                "note_type": {"$ref": "_enums.schema.json#/$defs/enum_note_type"},
                "created_at": {"$ref": "#/$defs/timestamp_iso"},
                "modified_date": {
                    "oneOf": [
                        {"$ref": "#/$defs/timestamp_iso"},
                        {"type": "null"},
                    ]
                },
            },
            "anyOf": [
                {"required": ["text"]},
                {"required": ["note_text"]},
            ],
            "additionalProperties": False,
        },
        "source_reference": {
            "type": "object",
            "required": ["citation_text"],
            "properties": {
                "record_guid": {
                    "$ref": "#/$defs/uuid_v4",
                    "description": "RFC 4122 lowercase UUIDv4 primary identifier of source record.",
                },
                "record_urn": {
                    "type": "string",
                    "description": "Legacy citation pointer accepted for backward compatibility.",
                },
                "citation_text": {"type": "string"},
                "source_id": {"type": ["string", "null"]},
                "page_or_side": {"type": ["string", "null"]},
                "side": {"$ref": "_enums.schema.json#/$defs/enum_document_side"},
            },
            "anyOf": [
                {"required": ["record_guid"]},
                {"required": ["record_urn"]},
            ],
            "additionalProperties": False,
        },
        "associated_person_entry": {
            "type": "object",
            "required": ["role"],
            "properties": {
                "person_id": {
                    "oneOf": [
                        {"$ref": "#/$defs/person_id"},
                        {"type": "null"},
                    ]
                },
                "role": {"$ref": "_enums.schema.json#/$defs/enum_kinship_role"},
                "name_raw": {"type": ["string", "null"]},
                "notes": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "canonical_name": {
            "type": "object",
            "required": ["given", "surname"],
            "properties": {
                "given": {"type": "string"},
                "middle": {"type": ["string", "null"]},
                "surname": {"type": "string"},
                "suffix": {"type": ["string", "null"]},
                "maiden_name": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "person_external_identifiers": {
            "type": "object",
            "description": "Cross-reference mapping to external person records.",
            "properties": {
                "person_id": {"$ref": "#/$defs/person_id"},
                "gedcom_id": {"type": ["string", "null"]},
                "familysearch_id": {"type": ["string", "null"]},
                "findagrave_id": {"type": ["string", "null"]},
                "wikitree_id": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "fact_external_identifiers": {
            "type": "object",
            "description": "Cross-reference mapping to external event and assertion records.",
            "properties": {
                "fact_id": {"$ref": "#/$defs/fact_id"},
                "gedcom_event_id": {"type": ["string", "null"]},
                "ancestry_fact_id": {"type": ["string", "null"]},
                "familysearch_event_id": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "external_identifiers": {
            "type": "object",
            "description": "Generic external cross-reference fallback.",
            "properties": {
                "gedcom_id": {"type": ["string", "null"]},
                "familysearch_id": {"type": ["string", "null"]},
                "findagrave_id": {"type": ["string", "null"]},
                "wikitree_id": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
    }
    return envelope


def build_external_xref_defs() -> Dict[str, Any]:
    """Compile schemas/defs/_external_xref_defs.schema.json."""
    envelope = build_schema_envelope(
        title="ExternalCrossReferenceDefinitions",
        version="1.1.0",
        description="Definitions for uniform cross-reference syntax linking external repositories.",
        schema_id="defs/_external_xref_defs.schema.json",
    )
    envelope["$defs"] = {
        "fact_external_identifiers": {
            "type": "object",
            "properties": {
                "gedcom_event_id": {"type": ["string", "null"]},
                "ancestry_fact_id": {"type": ["string", "null"]},
                "familysearch_event_id": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "census_source_urn": {
            "type": ["string", "null"],
            "description": "Historical census citation pointer retained for external cross-reference compatibility.",
        },
        "military_source_urn": {
            "type": ["string", "null"],
            "description": "Historical military citation pointer retained for external cross-reference compatibility.",
        },
    }
    return envelope


def build_death_defs() -> Dict[str, Any]:
    """Compile schemas/defs/_death_defs.schema.json."""
    envelope = build_schema_envelope(
        title="DeathAssertionDefinitions",
        version="1.0.0",
        description="Definitions for medical cause of death, contributory factors, and ICD classifications.",
        schema_id="defs/_death_defs.schema.json",
    )
    envelope["$defs"] = {
        "cause_of_death": {
            "type": "object",
            "properties": {
                "verbatim": {"type": "string"},
                "icd_code": {"type": ["string", "null"]},
                "duration": {"type": ["string", "null"]},
            },
            "required": ["verbatim"],
            "additionalProperties": False,
        }
    }
    return envelope


def build_registry_defs() -> Dict[str, Any]:
    """Compile schemas/defs/_registry_defs.schema.json."""
    envelope = build_schema_envelope(
        title="MasterRegistryEnvelopeDefinitions",
        version="1.0.0",
        description="Structural definitions for registry envelope headers and entity containers.",
        schema_id="defs/_registry_defs.schema.json",
    )
    envelope["$defs"] = {
        "registry_header": {
            "type": "object",
            "required": ["_name", "_path", "version", "last_updated"],
            "properties": {
                "_name": {"type": "string"},
                "_path": {"type": "string"},
                "version": {"type": "string"},
                "last_updated": {"$ref": "_shared_defs.schema.json#/$defs/timestamp_iso"},
            },
        }
    }
    return envelope


def build_census_defs() -> Dict[str, Any]:
    """Compile schemas/defs/_census_defs.schema.json."""
    envelope = build_schema_envelope(
        title="CensusScheduleFieldDefinitions",
        version="1.0.0",
        description="Definitions for census line entries and enumerated population questions.",
        schema_id="defs/_census_defs.schema.json",
    )
    envelope["$defs"] = {
        "census_line_entry": {
            "type": "object",
            "required": ["line_number", "name_verbatim"],
            "properties": {
                "line_number": {"type": "integer"},
                "name_verbatim": {"type": "string"},
                "age_raw": {"type": ["string", "null"]},
                "naturalization_status": {
                    "type": ["string", "null"],
                    "description": "Historical census notation; normalized via GDAReferenceManager.",
                },
            },
            "additionalProperties": True,
        }
    }
    return envelope


def build_document_defs() -> Dict[str, Any]:
    """Compile schemas/defs/_document_defs.schema.json."""
    envelope = build_schema_envelope(
        title="ArchivalDocumentMediaDefinitions",
        version="1.0.0",
        description="Definitions for source document pages, scanned sheets, and digital media attachments.",
        schema_id="defs/_document_defs.schema.json",
    )
    envelope["$defs"] = {
        "source_media": {
            "type": "object",
            "required": ["file_name", "mime_type"],
            "properties": {
                "file_name": {"type": "string"},
                "mime_type": {"type": "string"},
                "side": {"$ref": "_enums.schema.json#/$defs/enum_document_side"},
                "notes": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "media_clipping": {
            "type": "object",
            "required": ["file_name", "side"],
            "properties": {
                "file_name": {"type": "string"},
                "side": {"$ref": "_enums.schema.json#/$defs/enum_document_side"},
                "notes": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
    }
    return envelope


def build_military_defs() -> Dict[str, Any]:
    """Compile schemas/defs/_military_defs.schema.json."""
    envelope = build_schema_envelope(
        title="MilitarySelectiveServiceDefinitions",
        version="1.0.0",
        description="Definitions for military enlistments, service records, and Selective Service draft cards.",
        schema_id="defs/_military_defs.schema.json",
    )
    envelope["$defs"] = {
        "wwi_particulars": {
            "type": "object",
            "properties": {
                "serial_number": {"type": ["string", "null"]},
                "order_number": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "selective_service_record": {
            "type": "object",
            "required": ["classification"],
            "properties": {
                "classification": {"$ref": "_enums.schema.json#/$defs/enum_selective_service_class"},
                "board_jurisdiction": {"type": ["string", "null"]},
                "date": {"$ref": "_shared_defs.schema.json#/$defs/date_interpreted"},
            },
            "additionalProperties": False,
        },
    }
    return envelope


class BaseCatalog(Mapping[str, Callable[[], Dict[str, Any]]], IntrospectableMixin):
    """Collection manager exposing indexed procedural builders for base definition schemas."""

    _BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
        "enums": build_enums,
        "shared_defs": build_shared_defs,
        "external_xref_defs": build_external_xref_defs,
        "death_defs": build_death_defs,
        "registry_defs": build_registry_defs,
        "census_defs": build_census_defs,
        "document_defs": build_document_defs,
        "military_defs": build_military_defs,
    }

    _KEY_ALIASES: Dict[str, str] = {
        "enum": "enums",
        "enums": "enums",
        "_enums": "enums",
        "_enums.schema.json": "enums",
        "shared": "shared_defs",
        "shared_def": "shared_defs",
        "shared_defs": "shared_defs",
        "_shared_defs": "shared_defs",
        "_shared_defs.schema.json": "shared_defs",
        "external_xref": "external_xref_defs",
        "external_xref_defs": "external_xref_defs",
        "_external_xref_defs": "external_xref_defs",
        "_external_xref_defs.schema.json": "external_xref_defs",
        "death": "death_defs",
        "death_def": "death_defs",
        "death_defs": "death_defs",
        "_death_defs": "death_defs",
        "_death_defs.schema.json": "death_defs",
        "registry": "registry_defs",
        "registry_def": "registry_defs",
        "registry_defs": "registry_defs",
        "_registry_defs": "registry_defs",
        "_registry_defs.schema.json": "registry_defs",
        "census": "census_defs",
        "census_def": "census_defs",
        "census_defs": "census_defs",
        "_census_defs": "census_defs",
        "_census_defs.schema.json": "census_defs",
        "document": "document_defs",
        "document_def": "document_defs",
        "document_defs": "document_defs",
        "_document_defs": "document_defs",
        "_document_defs.schema.json": "document_defs",
        "military": "military_defs",
        "military_def": "military_defs",
        "military_defs": "military_defs",
        "_military_defs": "military_defs",
        "_military_defs.schema.json": "military_defs",
    }

    def _resolve_key(self, key: str) -> str:
        raw = str(key or "").strip().lower()
        if raw in self._BUILDERS:
            return raw
        if raw in self._KEY_ALIASES:
            return self._KEY_ALIASES[raw]
        raise KeyError(f"No definition builder found matching key: '{key}'")

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


BaseDefsCatalog = BaseCatalog