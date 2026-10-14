# Name: test_indexes.py
# Path: tools/lib/gdaschema/tests/test_indexes.py
# Version: 1.0.0+build.r3

"""Unit test suite verifying index definitions catalog and procedural emitters.

Operational Role:
    Validates Draft 2020-12 envelope integrity, IndexCatalog collection
    subscription, key aliases, 'all' iterator aggregation, GSI headers,
    and roundtrip validation against golden and failure index fixtures.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integrity.
    - Dependencies: gdaschema.defs.indexes, gdaschema.defs.base, gdaschema.schema_validator, pytest.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from gdaschema.defs.base import BaseCatalog
from gdaschema.defs.indexes import (
    IndexCatalog,
    build_facts_location_idx_schema,
    build_facts_person_idx_schema,
    build_locations_redirect_idx_schema,
    build_people_surname_alias_idx_schema,
    build_people_surname_idx_schema,
    build_sites_location_idx_schema,
)
from gdaschema.schema_validator import GDASchemaValidator

# ==============================================================================
# GROUP 1: CATALOG COLLECTION ACCESS & SUBSCRIPTION
# Note: Verifies dict access, aliases, len, iter, contains, and 'all' aggregation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_length_returns_six() -> None:
    """Verify IndexCatalog length matches the 6 canonical index schemas."""
    catalog = IndexCatalog()
    assert len(catalog) == 6


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_returns_compiled_dict() -> None:
    """Verify catalog subscription by logical key returns compiled schema."""
    catalog = IndexCatalog()
    schema = catalog["locations_redirect_idx"]
    assert isinstance(schema, dict)
    assert schema["$id"].endswith("indexes/locations_redirect_idx.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_supports_alias_keys() -> None:
    """Verify catalog subscription resolves shorthand key aliases."""
    catalog = IndexCatalog()
    schema = catalog["surname"]
    assert schema["$id"].endswith("indexes/people_surname_idx.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_all_returns_all_six_schemas() -> None:
    """Verify catalog['all'] compiles and returns a dictionary of all six schemas."""
    catalog = IndexCatalog()
    all_schemas = catalog["all"]
    assert len(all_schemas) == 6
    assert "people_surname_idx" in all_schemas
    assert "facts_location_idx" in all_schemas


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_contains_evaluates_true_for_valid_key() -> None:
    """Verify __contains__ returns True for registered keys and aliases."""
    catalog = IndexCatalog()
    assert "facts_location_idx" in catalog
    assert "location_redirect" in catalog
    assert "all" in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_contains_evaluates_false_for_invalid_key() -> None:
    """Verify __contains__ returns False for unregistered keys or non-strings."""
    catalog = IndexCatalog()
    assert "unknown_index" not in catalog
    assert 12345 not in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_key_error_on_unknown_key() -> None:
    """Verify accessing an unknown key raises KeyError."""
    catalog = IndexCatalog()
    with pytest.raises(KeyError, match="No index builder found matching key"):
        _ = catalog["ghost_index"]


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_iteration_yields_all_canonical_keys() -> None:
    """Verify iterating catalog yields the 6 canonical logical keys."""
    catalog = IndexCatalog()
    keys = list(catalog)
    assert len(keys) == 6
    assert "sites_location_idx" in keys


# ==============================================================================
# GROUP 2: INDIVIDUAL BUILDERS & ENVELOPE METADATA
# Note: Verifies GSI _name, _path, and required properties
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_build_all_index_schemas_declare_gsi_headers() -> None:
    """Verify all 6 index builders declare valid _name and _path metadata."""
    for builder in (
        build_people_surname_idx_schema,
        build_people_surname_alias_idx_schema,
        build_locations_redirect_idx_schema,
        build_facts_location_idx_schema,
        build_facts_person_idx_schema,
        build_sites_location_idx_schema,
    ):
        schema = builder()
        assert "_name" in schema
        assert "_path" in schema
        assert schema["_path"].startswith("schemas/indexes/")


# ==============================================================================
# GROUP 3: FIXTURE VALIDATION & INSTANCE ROUNDTRIP
# Note: Validates synthetic golden and failure fixtures against compiled schemas
# ==============================================================================


@pytest.fixture
def index_validator() -> GDASchemaValidator:
    """Provide validator pre-registered with canonical base definition schemas."""
    validator = GDASchemaValidator()
    base_cat = BaseCatalog()
    validator.register_resource("defs/_enums.schema.json", base_cat["enums"])
    validator.register_resource("../defs/_enums.schema.json", base_cat["enums"])
    validator.register_resource("defs/_shared_defs.schema.json", base_cat["shared_defs"])
    validator.register_resource("../defs/_shared_defs.schema.json", base_cat["shared_defs"])
    return validator


@pytest.fixture
def golden_indexes_data() -> Dict[str, Any]:
    """Load canonical synthetic golden index test payloads."""
    repo_root = Path(__file__).resolve().parents[4]
    fixture_path = repo_root / "tests" / "fixtures" / "indexes" / "golden" / "golden_indexes.json"
    if not fixture_path.is_file():
        pytest.skip(f"Golden fixture file not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def failure_indexes_data() -> Dict[str, Dict[str, Any]]:
    """Load failure defect payloads for indexes."""
    repo_root = Path(__file__).resolve().parents[4]
    failure_dir = repo_root / "tests" / "fixtures" / "indexes" / "failure"
    if not failure_dir.is_dir():
        pytest.skip(f"Failure fixtures dir not found: {failure_dir}")
    payloads: Dict[str, Dict[str, Any]] = {}
    for item in failure_dir.glob("*.json"):
        payloads[item.stem] = json.loads(item.read_text(encoding="utf-8"))
    return payloads


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_people_surname_idx(
    index_validator: GDASchemaValidator, golden_indexes_data: Dict[str, Any]
) -> None:
    """Verify golden people_surname_idx payload satisfies compiled schema."""
    schema = build_people_surname_idx_schema()
    errors = index_validator.validate_instance(golden_indexes_data["people_surname_idx"], schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_locations_redirect_idx(
    index_validator: GDASchemaValidator, golden_indexes_data: Dict[str, Any]
) -> None:
    """Verify golden locations_redirect_idx payload satisfies compiled schema."""
    schema = build_locations_redirect_idx_schema()
    errors = index_validator.validate_instance(golden_indexes_data["locations_redirect_idx"], schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_facts_location_idx(
    index_validator: GDASchemaValidator, golden_indexes_data: Dict[str, Any]
) -> None:
    """Verify golden facts_location_idx payload satisfies compiled schema."""
    schema = build_facts_location_idx_schema()
    errors = index_validator.validate_instance(golden_indexes_data["facts_location_idx"], schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_facts_person_idx(
    index_validator: GDASchemaValidator, golden_indexes_data: Dict[str, Any]
) -> None:
    """Verify golden facts_person_idx payload satisfies compiled schema."""
    schema = build_facts_person_idx_schema()
    errors = index_validator.validate_instance(golden_indexes_data["facts_person_idx"], schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_sites_location_idx(
    index_validator: GDASchemaValidator, golden_indexes_data: Dict[str, Any]
) -> None:
    """Verify golden sites_location_idx payload satisfies compiled schema."""
    schema = build_sites_location_idx_schema()
    errors = index_validator.validate_instance(golden_indexes_data["sites_location_idx"], schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_location_redirect_invalid_loc_id(
    index_validator: GDASchemaValidator, failure_indexes_data: Dict[str, Dict[str, Any]]
) -> None:
    """Verify location_redirect payload with invalid location_id fails validation."""
    schema = build_locations_redirect_idx_schema()
    corrupt = failure_indexes_data["corrupt_location_redirect_invalid_loc_id"]
    errors = index_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_facts_location_invalid_uuid(
    index_validator: GDASchemaValidator, failure_indexes_data: Dict[str, Dict[str, Any]]
) -> None:
    """Verify facts_location payload containing non-UUID fact_id fails validation."""
    schema = build_facts_location_idx_schema()
    corrupt = failure_indexes_data["corrupt_facts_location_invalid_uuid"]
    errors = index_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


# ==============================================================================
# GROUP 4: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify IndexCatalog inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    IndexCatalog.help()
    output = captured.getvalue()
    assert "IndexCatalog" in output