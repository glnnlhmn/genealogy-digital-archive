# Name: test_entities.py
# Path: tools/lib/gdaschema/tests/test_entities.py
# Version: 1.0.0+build.r1

"""Unit test suite verifying entity definitions catalog and procedural emitters.

Operational Role:
    Validates Draft 2020-12 envelope integrity, EntityCatalog collection
    subscription, key aliases, 'all' iterator aggregation, in-place tombstoning
    attributes, and roundtrip validation against golden and failure entity fixtures.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integrity.
    - Dependencies: gdaschema.defs.entities, gdaschema.schema_validator, pytest.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from gdaschema.defs.base import build_enums, build_shared_defs
from gdaschema.defs.entities import (
    EntityCatalog,
    build_fact_registry_schema,
    build_fact_schema,
    build_location_registry_schema,
    build_location_schema,
    build_person_registry_schema,
    build_person_schema,
    build_site_registry_schema,
    build_site_schema,
)
from gdaschema.schema_validator import GDASchemaValidator

# ==============================================================================
# GROUP 1: CATALOG COLLECTION ACCESS & SUBSCRIPTION
# Note: Verifies dict access, aliases, len, iter, contains, and 'all' aggregation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_length_returns_eight() -> None:
    """Verify EntityCatalog length matches the 8 canonical entity schemas."""
    catalog = EntityCatalog()
    assert len(catalog) == 8


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_returns_compiled_dict() -> None:
    """Verify catalog subscription by logical key returns compiled schema."""
    catalog = EntityCatalog()
    schema = catalog["person"]
    assert isinstance(schema, dict)
    assert schema["$id"].endswith("entities/person.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_supports_alias_keys() -> None:
    """Verify catalog subscription resolves shorthand key aliases."""
    catalog = EntityCatalog()
    schema = catalog["people"]
    assert schema["$id"].endswith("entities/person_registry.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_all_returns_all_eight_schemas() -> None:
    """Verify catalog['all'] compiles and returns a dictionary of all eight schemas."""
    catalog = EntityCatalog()
    all_schemas = catalog["all"]
    assert len(all_schemas) == 8
    assert "person" in all_schemas
    assert "fact_registry" in all_schemas


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_contains_evaluates_true_for_valid_key() -> None:
    """Verify __contains__ returns True for registered keys and aliases."""
    catalog = EntityCatalog()
    assert "person" in catalog
    assert "facts" in catalog
    assert "all" in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_contains_evaluates_false_for_invalid_key() -> None:
    """Verify __contains__ returns False for unregistered keys or non-strings."""
    catalog = EntityCatalog()
    assert "unknown_entity" not in catalog
    assert 12345 not in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_key_error_on_unknown_key() -> None:
    """Verify accessing an unknown key raises KeyError."""
    catalog = EntityCatalog()
    with pytest.raises(KeyError, match="No entity definition builder found matching key"):
        _ = catalog["ghost_entity"]


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_iteration_yields_all_canonical_keys() -> None:
    """Verify iterating catalog yields the 8 canonical logical keys."""
    catalog = EntityCatalog()
    keys = list(catalog)
    assert len(keys) == 8
    assert "site_registry" in keys


# ==============================================================================
# GROUP 2: INDIVIDUAL BUILDERS & ENVELOPE METADATA
# Note: Verifies GSI _name, _path, required properties, and tombstoning
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_build_person_schema_contains_tombstone_fields() -> None:
    """Verify build_person_schema includes is_deprecated and superseded_by."""
    schema = build_person_schema()
    props = schema["properties"]
    assert "is_deprecated" in props
    assert "superseded_by" in props
    assert schema["_name"] == "person.schema.json"
    assert schema["_path"] == "schemas/entities/person.schema.json"


@pytest.mark.unit
@pytest.mark.smoke
def test_build_fact_schema_contains_tombstone_fields() -> None:
    """Verify build_fact_schema includes is_deprecated and superseded_by."""
    schema = build_fact_schema()
    props = schema["properties"]
    assert "is_deprecated" in props
    assert "superseded_by" in props
    assert schema["_name"] == "fact.schema.json"


@pytest.mark.unit
@pytest.mark.smoke
def test_build_location_schema_contains_tombstone_fields() -> None:
    """Verify build_location_schema includes is_deprecated and superseded_by."""
    schema = build_location_schema()
    props = schema["properties"]
    assert "is_deprecated" in props
    assert "superseded_by" in props
    assert schema["_name"] == "location.schema.json"


@pytest.mark.unit
@pytest.mark.smoke
def test_build_site_schema_contains_tombstone_fields() -> None:
    """Verify build_site_schema includes is_deprecated and superseded_by."""
    schema = build_site_schema()
    props = schema["properties"]
    assert "is_deprecated" in props
    assert "superseded_by" in props
    assert schema["_name"] == "site.schema.json"


@pytest.mark.unit
@pytest.mark.smoke
def test_build_registries_declare_gsi_headers() -> None:
    """Verify all 4 registry builders enforce _name, _path, and schema_version."""
    for builder in (
        build_person_registry_schema,
        build_fact_registry_schema,
        build_location_registry_schema,
        build_site_registry_schema,
    ):
        schema = builder()
        assert "_name" in schema["required"]
        assert "_path" in schema["required"]
        assert "schema_version" in schema["required"]


# ==============================================================================
# GROUP 3: FIXTURE VALIDATION & INSTANCE ROUNDTRIP
# Note: Validates synthetic golden and failure fixtures against compiled schemas
# ==============================================================================


@pytest.fixture
def entity_validator() -> GDASchemaValidator:
    """Provide validator pre-registered with canonical base definition schemas."""
    validator = GDASchemaValidator()
    validator.register_resource("defs/_enums.schema.json", build_enums())
    validator.register_resource("../defs/_enums.schema.json", build_enums())
    validator.register_resource("defs/_shared_defs.schema.json", build_shared_defs())
    validator.register_resource("../defs/_shared_defs.schema.json", build_shared_defs())
    return validator


@pytest.fixture
def golden_entities_data() -> Dict[str, Any]:
    """Load canonical synthetic golden entities test payloads."""
    repo_root = Path(__file__).resolve().parents[4]
    fixture_path = repo_root / "tests" / "fixtures" / "entities" / "golden" / "golden_entities.json"
    if not fixture_path.is_file():
        pytest.skip(f"Golden fixture file not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def failure_entities_data() -> Dict[str, Dict[str, Any]]:
    """Load failure defect payloads for entities."""
    repo_root = Path(__file__).resolve().parents[4]
    failure_dir = repo_root / "tests" / "fixtures" / "entities" / "failure"
    if not failure_dir.is_dir():
        pytest.skip(f"Failure fixtures dir not found: {failure_dir}")
    payloads: Dict[str, Dict[str, Any]] = {}
    for item in failure_dir.glob("*.json"):
        payloads[item.stem] = json.loads(item.read_text(encoding="utf-8"))
    return payloads


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_person(
    entity_validator: GDASchemaValidator, golden_entities_data: Dict[str, Any]
) -> None:
    """Verify golden person payload satisfies compiled person schema."""
    schema = build_person_schema()
    errors = entity_validator.validate_instance(golden_entities_data["person"], schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_fact(
    entity_validator: GDASchemaValidator, golden_entities_data: Dict[str, Any]
) -> None:
    """Verify golden fact payload satisfies compiled fact schema."""
    schema = build_fact_schema()
    errors = entity_validator.validate_instance(golden_entities_data["fact"], schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_location(
    entity_validator: GDASchemaValidator, golden_entities_data: Dict[str, Any]
) -> None:
    """Verify golden location payload satisfies compiled location schema."""
    schema = build_location_schema()
    errors = entity_validator.validate_instance(golden_entities_data["location"], schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_site(
    entity_validator: GDASchemaValidator, golden_entities_data: Dict[str, Any]
) -> None:
    """Verify golden site payload satisfies compiled site schema."""
    schema = build_site_schema()
    errors = entity_validator.validate_instance(golden_entities_data["site"], schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_person(
    entity_validator: GDASchemaValidator, failure_entities_data: Dict[str, Dict[str, Any]]
) -> None:
    """Verify person payload lacking required names fails validation."""
    schema = build_person_schema()
    corrupt = failure_entities_data["corrupt_person_missing_required"]
    errors = entity_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_fact(
    entity_validator: GDASchemaValidator, failure_entities_data: Dict[str, Dict[str, Any]]
) -> None:
    """Verify fact payload with non-UUIDv4 fact_id fails validation."""
    schema = build_fact_schema()
    corrupt = failure_entities_data["corrupt_fact_invalid_uuid"]
    errors = entity_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_location(
    entity_validator: GDASchemaValidator, failure_entities_data: Dict[str, Dict[str, Any]]
) -> None:
    """Verify location payload lacking required country fails validation."""
    schema = build_location_schema()
    corrupt = failure_entities_data["corrupt_location_missing_country"]
    errors = entity_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


# ==============================================================================
# GROUP 4: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify EntityCatalog inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    EntityCatalog.help()
    output = captured.getvalue()
    assert "EntityCatalog" in output