# Name: test_entity_containers.py
# Path: tools/lib/gdaschema/tests/test_entity_containers.py
# Version: 1.0.0+build.r2

"""Unit and integrity tests for top-level entity registry container schemas.

Operational Role:
    Verifies that EntityCatalog provides builders for whole-store container files
    (people.json, facts.json, locations.json, sites.json), enforces registry headers,
    and accurately validates synthetic golden container payloads.

Test Structure & Protocol:
    - Atomized tests: 1:1 behavioral mapping across catalog keys and schema validations.
    - Fully decorated: Decorated with @pytest.mark.unit and @pytest.mark.integrity.
    - Dependencies: GDASchemaValidator, EntityCatalog, BaseCatalog, golden fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from gdaschema.defs.base import BaseCatalog
from gdaschema.entities.catalog import (
    EntityCatalog,
    build_facts_container_schema,
    build_locations_container_schema,
    build_people_container_schema,
    build_sites_container_schema,
)
from gdaschema.schema_validator import GDASchemaValidator

# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def entity_validator() -> GDASchemaValidator:
    """Provide a GDASchemaValidator preloaded with base defs resources."""
    validator = GDASchemaValidator()
    base_catalog = BaseCatalog()
    validator.register_resource("defs/_enums.schema.json", base_catalog["enums"])
    validator.register_resource("_enums.schema.json", base_catalog["enums"])
    validator.register_resource("defs/_shared_defs.schema.json", base_catalog["shared_defs"])
    validator.register_resource("_shared_defs.schema.json", base_catalog["shared_defs"])
    return validator


@pytest.fixture
def golden_containers_data() -> Dict[str, Any]:
    """Load the canonical synthetic container payloads from test fixtures."""
    # Resolved relative to tools/lib/gdaschema/tests/ -> root tests/fixtures/
    fixture_path = (
        Path(__file__).resolve().parents[4]
        / "tests"
        / "fixtures"
        / "entities"
        / "golden"
        / "golden_entity_containers.json"
    )
    with open(fixture_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# ==============================================================================
# GROUP 1: CATALOG REGISTRATION & ACCESS
# ==============================================================================


@pytest.mark.unit
def test_entity_catalog_contains_container_builders() -> None:
    """Verify EntityCatalog exposes all four container schema builders."""
    catalog = EntityCatalog()
    assert "people_container" in catalog
    assert "facts_container" in catalog
    assert "locations_container" in catalog
    assert "sites_container" in catalog


@pytest.mark.unit
def test_entity_catalog_resolves_container_file_aliases() -> None:
    """Verify EntityCatalog resolves disk file name aliases to container builders."""
    catalog = EntityCatalog()
    assert catalog["people.json"]["title"] == "PeopleRegistryContainerStore"
    assert catalog["facts.json"]["title"] == "FactsRegistryContainerStore"
    assert catalog["locations.json"]["title"] == "LocationsRegistryContainerStore"
    assert catalog["sites.json"]["title"] == "SitesRegistryContainerStore"


@pytest.mark.unit
def test_entity_catalog_introspection_lists_container_keys() -> None:
    """Verify EntityCatalog introspects container builders via len and iter."""
    catalog = EntityCatalog()
    keys = list(iter(catalog))
    assert "people_container" in keys
    assert "facts_container" in keys
    assert "locations_container" in keys
    assert "sites_container" in keys
    assert len(catalog) >= 8


# ==============================================================================
# GROUP 2: SCHEMA STRUCTURAL INTEGRITY
# ==============================================================================


@pytest.mark.unit
def test_people_container_schema_structure() -> None:
    """Verify people_container schema defines required envelope fields."""
    schema = build_people_container_schema()
    assert schema["type"] == "object"
    assert "_name" in schema["required"]
    assert "last_updated" in schema["required"]
    assert "people" in schema["required"]
    assert schema["properties"]["people"]["type"] == "array"


@pytest.mark.unit
def test_facts_container_schema_structure() -> None:
    """Verify facts_container schema defines required envelope fields."""
    schema = build_facts_container_schema()
    assert schema["type"] == "object"
    assert "_name" in schema["required"]
    assert "last_updated" in schema["required"]
    assert "facts" in schema["required"]
    assert schema["properties"]["facts"]["type"] == "array"


@pytest.mark.unit
def test_locations_container_schema_structure() -> None:
    """Verify locations_container schema defines required envelope fields."""
    schema = build_locations_container_schema()
    assert schema["type"] == "object"
    assert "_name" in schema["required"]
    assert "last_updated" in schema["required"]
    assert "locations" in schema["required"]
    assert schema["properties"]["locations"]["type"] == "array"


@pytest.mark.unit
def test_sites_container_schema_structure() -> None:
    """Verify sites_container schema defines required envelope fields."""
    schema = build_sites_container_schema()
    assert schema["type"] == "object"
    assert "_name" in schema["required"]
    assert "last_updated" in schema["required"]
    assert "sites" in schema["required"]
    assert schema["properties"]["sites"]["type"] == "array"


# ==============================================================================
# GROUP 3: GOLDEN CONTAINER VALIDATION ROUNDTRIP
# ==============================================================================


@pytest.mark.integrity
def test_validate_golden_people_container(
    entity_validator: GDASchemaValidator,
    golden_containers_data: Dict[str, Any],
) -> None:
    """Verify golden people_container payload passes schema validation."""
    schema = build_people_container_schema()
    errors = entity_validator.validate_instance(
        golden_containers_data["people_container"], schema
    )
    assert errors == []


@pytest.mark.integrity
def test_validate_golden_facts_container(
    entity_validator: GDASchemaValidator,
    golden_containers_data: Dict[str, Any],
) -> None:
    """Verify golden facts_container payload passes schema validation."""
    schema = build_facts_container_schema()
    errors = entity_validator.validate_instance(
        golden_containers_data["facts_container"], schema
    )
    assert errors == []


@pytest.mark.integrity
def test_validate_golden_locations_container(
    entity_validator: GDASchemaValidator,
    golden_containers_data: Dict[str, Any],
) -> None:
    """Verify golden locations_container payload passes schema validation."""
    schema = build_locations_container_schema()
    errors = entity_validator.validate_instance(
        golden_containers_data["locations_container"], schema
    )
    assert errors == []


@pytest.mark.integrity
def test_validate_golden_sites_container(
    entity_validator: GDASchemaValidator,
    golden_containers_data: Dict[str, Any],
) -> None:
    """Verify golden sites_container payload passes schema validation."""
    schema = build_sites_container_schema()
    errors = entity_validator.validate_instance(
        golden_containers_data["sites_container"], schema
    )
    assert errors == []


# ==============================================================================
# GROUP 4: NEGATIVE CONSTRAINT ENFORCEMENT
# ==============================================================================


@pytest.mark.unit
def test_people_container_rejects_missing_last_updated(
    entity_validator: GDASchemaValidator,
    golden_containers_data: Dict[str, Any],
) -> None:
    """Verify people_container validation fails when last_updated is missing."""
    schema = build_people_container_schema()
    bad_payload = dict(golden_containers_data["people_container"])
    del bad_payload["last_updated"]
    errors = entity_validator.validate_instance(bad_payload, schema)
    assert any("last_updated" in err for err in errors)


@pytest.mark.unit
def test_facts_container_rejects_invalid_fact_item(
    entity_validator: GDASchemaValidator,
    golden_containers_data: Dict[str, Any],
) -> None:
    """Verify facts_container validation fails when an inner fact item is invalid."""
    schema = build_facts_container_schema()
    bad_payload = json.loads(json.dumps(golden_containers_data["facts_container"]))
    bad_payload["facts"][0]["fact_id"] = "not-a-valid-uuid"
    errors = entity_validator.validate_instance(bad_payload, schema)
    assert len(errors) > 0