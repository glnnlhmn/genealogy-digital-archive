# Name: test_sources_enumeration.py
# Path: tools/lib/gdaschema/tests/test_sources_enumeration.py
# Version: 1.0.0+build.r1

"""Unit test suite verifying enumeration sources catalog and procedural emitters.

Operational Role:
    Validates Draft 2020-12 envelope integrity, EnumerationSourcesCatalog collection
    subscription, key aliases, 'all' iterator aggregation, GSI headers,
    and roundtrip validation against golden and failure enumeration source fixtures.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integrity.
    - Dependencies: gdaschema.sources.enumeration, gdaschema.defs.base, gdaschema.schema_validator, pytest.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from gdaschema.defs.base import BaseCatalog
from gdaschema.schema_validator import GDASchemaValidator
from gdaschema.sources.enumeration import (
    EnumerationSourcesCatalog,
    build_census_schedule_schema,
    build_directory_listing_schema,
    build_immigration_manifest_schema,
    build_naturalization_record_schema,
)

# ==============================================================================
# GROUP 1: CATALOG COLLECTION ACCESS & SUBSCRIPTION
# Note: Verifies dict access, aliases, len, iter, contains, and 'all' aggregation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_length_returns_four() -> None:
    """Verify EnumerationSourcesCatalog length matches the 4 canonical schemas."""
    catalog = EnumerationSourcesCatalog()
    assert len(catalog) == 4


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_returns_compiled_dict() -> None:
    """Verify catalog subscription by logical key returns compiled schema."""
    catalog = EnumerationSourcesCatalog()
    schema = catalog["census_schedule"]
    assert isinstance(schema, dict)
    assert schema["$id"].endswith("sources/census_schedule.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_supports_alias_keys() -> None:
    """Verify catalog subscription resolves shorthand key aliases."""
    catalog = EnumerationSourcesCatalog()
    schema = catalog["immigration"]
    assert schema["$id"].endswith("sources/immigration_manifest.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_all_returns_all_four_schemas() -> None:
    """Verify catalog['all'] compiles and returns a dictionary of all four schemas."""
    catalog = EnumerationSourcesCatalog()
    all_schemas = catalog["all"]
    assert len(all_schemas) == 4
    assert "census_schedule" in all_schemas
    assert "naturalization_record" in all_schemas


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_contains_evaluates_true_for_valid_key() -> None:
    """Verify __contains__ returns True for registered keys and aliases."""
    catalog = EnumerationSourcesCatalog()
    assert "census_schedule" in catalog
    assert "directory" in catalog
    assert "all" in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_contains_evaluates_false_for_invalid_key() -> None:
    """Verify __contains__ returns False for unregistered keys or non-strings."""
    catalog = EnumerationSourcesCatalog()
    assert "unknown_enumeration" not in catalog
    assert 12345 not in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_key_error_on_unknown_key() -> None:
    """Verify accessing an unknown key raises KeyError."""
    catalog = EnumerationSourcesCatalog()
    with pytest.raises(KeyError, match="No enumeration source builder found matching key"):
        _ = catalog["ghost_enumeration"]


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_iteration_yields_all_canonical_keys() -> None:
    """Verify iterating catalog yields the 4 canonical logical keys."""
    catalog = EnumerationSourcesCatalog()
    keys = list(catalog)
    assert len(keys) == 4
    assert "directory_listing" in keys


# ==============================================================================
# GROUP 2: INDIVIDUAL BUILDERS & ENVELOPE METADATA
# Note: Verifies GSI _name, _path, and required properties
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_build_all_enumeration_schemas_declare_gsi_headers() -> None:
    """Verify all 4 enumeration builders declare valid _name and _path metadata."""
    for builder in (
        build_census_schedule_schema,
        build_directory_listing_schema,
        build_immigration_manifest_schema,
        build_naturalization_record_schema,
    ):
        schema = builder()
        assert "_name" in schema
        assert "_path" in schema
        assert schema["_path"].startswith("schemas/sources/")


# ==============================================================================
# GROUP 3: FIXTURE VALIDATION & INSTANCE ROUNDTRIP
# Note: Validates synthetic golden and failure fixtures against compiled schemas
# ==============================================================================


@pytest.fixture
def enumeration_validator() -> GDASchemaValidator:
    """Provide validator pre-registered with canonical base definition schemas."""
    validator = GDASchemaValidator()
    base_cat = BaseCatalog()
    enums_schema = base_cat["enums"]
    shared_schema = base_cat["shared_defs"]
    census_schema = base_cat["census_defs"]
    doc_schema = base_cat["document_defs"]

    resources = [
        ("_enums.schema.json", enums_schema),
        ("_shared_defs.schema.json", shared_schema),
        ("_shared_shared_defs.schema.json", shared_schema),
        ("_census_defs.schema.json", census_schema),
        ("_document_defs.schema.json", doc_schema),
    ]

    for name, schema in resources:
        if "$id" in schema:
            validator.register_resource(schema["$id"], schema)
        for prefix in ("defs/", "../defs/", ""):
            validator.register_resource(f"{prefix}{name}", schema)

    return validator


@pytest.fixture
def golden_enumeration_data() -> Dict[str, Any]:
    """Load canonical synthetic golden enumeration source test payloads."""
    repo_root = Path(__file__).resolve().parents[4]
    fixture_path = (
        repo_root
        / "tests"
        / "fixtures"
        / "sources"
        / "enumeration"
        / "golden"
        / "golden_enumeration_sources.json"
    )
    if not fixture_path.is_file():
        pytest.skip(f"Golden fixture file not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def failure_enumeration_data() -> Dict[str, Dict[str, Any]]:
    """Load failure defect payloads for enumeration sources."""
    repo_root = Path(__file__).resolve().parents[4]
    failure_dir = (
        repo_root / "tests" / "fixtures" / "sources" / "enumeration" / "failure"
    )
    if not failure_dir.is_dir():
        pytest.skip(f"Failure fixtures dir not found: {failure_dir}")
    payloads: Dict[str, Dict[str, Any]] = {}
    for item in failure_dir.glob("*.json"):
        payloads[item.stem] = json.loads(item.read_text(encoding="utf-8"))
    return payloads


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_census_schedule(
    enumeration_validator: GDASchemaValidator, golden_enumeration_data: Dict[str, Any]
) -> None:
    """Verify golden census schedule payload satisfies compiled schema."""
    schema = build_census_schedule_schema()
    errors = enumeration_validator.validate_instance(
        golden_enumeration_data["census_schedule"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_directory_listing(
    enumeration_validator: GDASchemaValidator, golden_enumeration_data: Dict[str, Any]
) -> None:
    """Verify golden directory listing payload satisfies compiled schema."""
    schema = build_directory_listing_schema()
    errors = enumeration_validator.validate_instance(
        golden_enumeration_data["directory_listing"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_immigration_manifest(
    enumeration_validator: GDASchemaValidator, golden_enumeration_data: Dict[str, Any]
) -> None:
    """Verify golden immigration manifest payload satisfies compiled schema."""
    schema = build_immigration_manifest_schema()
    errors = enumeration_validator.validate_instance(
        golden_enumeration_data["immigration_manifest"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_naturalization_record(
    enumeration_validator: GDASchemaValidator, golden_enumeration_data: Dict[str, Any]
) -> None:
    """Verify golden naturalization record payload satisfies compiled schema."""
    schema = build_naturalization_record_schema()
    errors = enumeration_validator.validate_instance(
        golden_enumeration_data["naturalization_record"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_census_missing_entries(
    enumeration_validator: GDASchemaValidator,
    failure_enumeration_data: Dict[str, Dict[str, Any]],
) -> None:
    """Verify census schedule payload missing entries array fails validation."""
    schema = build_census_schedule_schema()
    corrupt = failure_enumeration_data["corrupt_census_missing_entries"]
    errors = enumeration_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_immigration_invalid_urn(
    enumeration_validator: GDASchemaValidator,
    failure_enumeration_data: Dict[str, Dict[str, Any]],
) -> None:
    """Verify immigration manifest payload with invalid source_urn fails validation."""
    schema = build_immigration_manifest_schema()
    corrupt = failure_enumeration_data["corrupt_immigration_invalid_urn"]
    errors = enumeration_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


# ==============================================================================
# GROUP 4: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify EnumerationSourcesCatalog inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    EnumerationSourcesCatalog.help()
    output = captured.getvalue()
    assert "EnumerationSourcesCatalog" in output