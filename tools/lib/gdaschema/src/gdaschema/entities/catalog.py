# Name: catalog.py
# Path: tools/lib/gdaschema/src/gdaschema/entities/catalog.py
# Version: 1.0.0+build.r6

"""Authoritative procedural schema generators for domain entity items and containers.

Operational Role:
    Compiles canonical Draft 2020-12 schema definitions for individual entity items
    (person, fact, location, site) and top-level serialized disk containers
    (people_container, facts_container, locations_container, sites_container).
    Accessible via EntityCatalog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Callable, Dict

from gdacore.introspectable import IntrospectableMixin
from gdaschema.schema_util import build_schema_envelope

__version__ = "1.0.0+build.r6"


# ==============================================================================
# INDIVIDUAL ENTITY ITEM BUILDERS
# ==============================================================================


def build_person_schema() -> Dict[str, Any]:
    """Compile schemas/entities/person.schema.json for an individual individual record."""
    envelope = build_schema_envelope(
        title="IndividualPersonEntity",
        version="1.1.0",
        description="Individual person assertion schema capturing demographic, kinship, and vital identities.",
        schema_id="entities/person.schema.json",
    )
    envelope["required"] = ["person_id", "canonical_name", "created_at"]
    envelope["properties"] = {
        "person_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
        "canonical_name": {"$ref": "../defs/_shared_defs.schema.json#/$defs/canonical_name"},
        "sex": {"$ref": "../defs/_enums.schema.json#/$defs/enum_sex"},
        "notes": {
            "type": "array",
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/note_entry"},
        },
        "created_at": {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
        "updated_at": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
                {"type": "null"},
            ]
        },
        "tombstone": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/tombstone"},
                {"type": "null"},
            ]
        },
        "external_identifiers": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_external_identifiers"},
                {"type": "null"},
            ]
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_fact_schema() -> Dict[str, Any]:
    """Compile schemas/entities/fact.schema.json for an individual life assertion."""
    envelope = build_schema_envelope(
        title="IndividualFactAssertionEntity",
        version="1.1.0",
        description="Individual biographical or historical fact assertion anchoring people to events.",
        schema_id="entities/fact.schema.json",
    )
    envelope["required"] = ["fact_id", "fact_type", "primary_person_id", "created_at"]
    envelope["properties"] = {
        "fact_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/fact_id"},
        "fact_type": {"$ref": "../defs/_enums.schema.json#/$defs/enum_fact_type"},
        "primary_person_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/person_id"},
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
        "sources": {
            "type": "array",
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/source_reference"},
        },
        "notes": {
            "type": "array",
            "items": {"$ref": "../defs/_shared_defs.schema.json#/$defs/note_entry"},
        },
        "created_at": {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
        "updated_at": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
                {"type": "null"},
            ]
        },
        "tombstone": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/tombstone"},
                {"type": "null"},
            ]
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_location_schema() -> Dict[str, Any]:
    """Compile schemas/entities/location.schema.json for a civil jurisdiction record."""
    envelope = build_schema_envelope(
        title="CivilLocationEntity",
        version="1.1.0",
        description="Standardized civil jurisdiction hierarchy representing geographic locations.",
        schema_id="entities/location.schema.json",
    )
    envelope["required"] = ["location_id", "verbatim", "created_at"]
    envelope["properties"] = {
        "location_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location_id"},
        "verbatim": {"type": "string"},
        "location_type": {"$ref": "../defs/_enums.schema.json#/$defs/enum_location_type"},
        "city": {"type": ["string", "null"]},
        "county": {"type": ["string", "null"]},
        "state": {"type": ["string", "null"]},
        "country": {"type": ["string", "null"]},
        "created_at": {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
        "updated_at": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
                {"type": "null"},
            ]
        },
        "tombstone": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/tombstone"},
                {"type": "null"},
            ]
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_site_schema() -> Dict[str, Any]:
    """Compile schemas/entities/site.schema.json for a physical facility record."""
    envelope = build_schema_envelope(
        title="PhysicalSiteFacilityEntity",
        version="1.1.0",
        description="Physical site facility entity such as cemeteries, churches, and hospitals.",
        schema_id="entities/site.schema.json",
    )
    envelope["required"] = ["site_id", "site_name", "site_type", "location_id", "created_at"]
    envelope["properties"] = {
        "site_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/site_id"},
        "site_name": {"type": "string"},
        "site_type": {"$ref": "../defs/_enums.schema.json#/$defs/enum_site_type"},
        "location_id": {"$ref": "../defs/_shared_defs.schema.json#/$defs/location_id"},
        "street_address": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/street_address"},
                {"type": "null"},
            ]
        },
        "operational_status": {"$ref": "../defs/_enums.schema.json#/$defs/enum_operational_status"},
        "created_at": {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
        "updated_at": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
                {"type": "null"},
            ]
        },
        "tombstone": {
            "oneOf": [
                {"$ref": "../defs/_shared_defs.schema.json#/$defs/tombstone"},
                {"type": "null"},
            ]
        },
    }
    envelope["additionalProperties"] = False
    return envelope


# ==============================================================================
# TOP-LEVEL REGISTRY STORE CONTAINER BUILDERS
# ==============================================================================


def build_people_container_schema() -> Dict[str, Any]:
    """Compile schemas/entities/people_container.schema.json for data/entities/people.json."""
    envelope = build_schema_envelope(
        title="PeopleRegistryContainerStore",
        version="1.0.0",
        description="Top-level envelope schema for data/entities/people.json registry store.",
        schema_id="entities/people_container.schema.json",
    )
    person_item = build_person_schema()
    envelope["$defs"] = {"person_item": person_item}
    envelope["required"] = ["_name", "_path", "version", "last_updated", "people"]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "version": {"type": "string"},
        "last_updated": {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
        "description": {"type": "string"},
        "people": {
            "type": "array",
            "items": {"$ref": "#/$defs/person_item"},
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_facts_container_schema() -> Dict[str, Any]:
    """Compile schemas/entities/facts_container.schema.json for data/entities/facts.json."""
    envelope = build_schema_envelope(
        title="FactsRegistryContainerStore",
        version="1.0.0",
        description="Top-level envelope schema for data/entities/facts.json registry store.",
        schema_id="entities/facts_container.schema.json",
    )
    fact_item = build_fact_schema()
    envelope["$defs"] = {"fact_item": fact_item}
    envelope["required"] = ["_name", "_path", "version", "last_updated", "facts"]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "version": {"type": "string"},
        "last_updated": {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
        "description": {"type": "string"},
        "facts": {
            "type": "array",
            "items": {"$ref": "#/$defs/fact_item"},
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_locations_container_schema() -> Dict[str, Any]:
    """Compile schemas/entities/locations_container.schema.json for data/entities/locations.json."""
    envelope = build_schema_envelope(
        title="LocationsRegistryContainerStore",
        version="1.0.0",
        description="Top-level envelope schema for data/entities/locations.json registry store.",
        schema_id="entities/locations_container.schema.json",
    )
    location_item = build_location_schema()
    envelope["$defs"] = {"location_item": location_item}
    envelope["required"] = ["_name", "_path", "version", "last_updated", "locations"]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "version": {"type": "string"},
        "last_updated": {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
        "description": {"type": "string"},
        "locations": {
            "type": "array",
            "items": {"$ref": "#/$defs/location_item"},
        },
    }
    envelope["additionalProperties"] = False
    return envelope


def build_sites_container_schema() -> Dict[str, Any]:
    """Compile schemas/entities/sites_container.schema.json for data/entities/sites.json."""
    envelope = build_schema_envelope(
        title="SitesRegistryContainerStore",
        version="1.0.0",
        description="Top-level envelope schema for data/entities/sites.json registry store.",
        schema_id="entities/sites_container.schema.json",
    )
    site_item = build_site_schema()
    envelope["$defs"] = {"site_item": site_item}
    envelope["required"] = ["_name", "_path", "version", "last_updated", "sites"]
    envelope["properties"] = {
        "_name": {"type": "string"},
        "_path": {"type": "string"},
        "version": {"type": "string"},
        "last_updated": {"$ref": "../defs/_shared_defs.schema.json#/$defs/timestamp_iso"},
        "description": {"type": "string"},
        "sites": {
            "type": "array",
            "items": {"$ref": "#/$defs/site_item"},
        },
    }
    envelope["additionalProperties"] = False
    return envelope


# ==============================================================================
# CATALOG INTERFACE
# ==============================================================================


class EntityCatalog(Mapping[str, Callable[[], Dict[str, Any]]], IntrospectableMixin):
    """Collection manager exposing indexed procedural builders for entity items and containers."""

    _BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
        "person": build_person_schema,
        "fact": build_fact_schema,
        "location": build_location_schema,
        "site": build_site_schema,
        "people_container": build_people_container_schema,
        "facts_container": build_facts_container_schema,
        "locations_container": build_locations_container_schema,
        "sites_container": build_sites_container_schema,
    }

    _KEY_ALIASES: Dict[str, str] = {
        "person": "person",
        "people": "person",
        "person.schema.json": "person",
        "fact": "fact",
        "facts": "fact",
        "fact.schema.json": "fact",
        "location": "location",
        "locations": "location",
        "location.schema.json": "location",
        "site": "site",
        "sites": "site",
        "site.schema.json": "site",
        "people_container": "people_container",
        "people_store": "people_container",
        "people.json": "people_container",
        "people_container.schema.json": "people_container",
        "facts_container": "facts_container",
        "facts_store": "facts_container",
        "facts.json": "facts_container",
        "facts_container.schema.json": "facts_container",
        "locations_container": "locations_container",
        "locations_store": "locations_container",
        "locations.json": "locations_container",
        "locations_container.schema.json": "locations_container",
        "sites_container": "sites_container",
        "sites_store": "sites_container",
        "sites.json": "sites_container",
        "sites_container.schema.json": "sites_container",
    }

    def _resolve_key(self, key: str) -> str:
        raw = str(key or "").strip().lower()
        if raw in self._BUILDERS:
            return raw
        if raw in self._KEY_ALIASES:
            return self._KEY_ALIASES[raw]
        raise KeyError(f"No entity definition builder found matching key: '{key}'")

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