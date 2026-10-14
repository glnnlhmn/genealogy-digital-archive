# Name: test_sources_vital.py
# Path: tools/lib/gdaschema/tests/test_sources_vital.py
# Version: 1.0.0+build.r4

"""Unit test suite verifying vital sources catalog and procedural emitters.

Operational Role:
    Validates Draft 2020-12 envelope integrity, VitalSourcesCatalog collection
    subscription, key aliases, 'all' iterator aggregation, GSI headers,
    and roundtrip validation against golden and failure vital source fixtures.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integrity.
    - Dependencies: gdaschema.sources.vital, gdaschema.defs.base, gdaschema.schema_validator, pytest.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from gdaschema.defs.base import BaseCatalog
from gdaschema.schema_validator import GDASchemaValidator
from gdaschema.sources.vital import (
    VitalSourcesCatalog,
    build_birth_certificate_schema,
    build_cemetery_marker_schema,
    build_church_baptism_schema,
    build_death_certificate_schema,
    build_marriage_license_schema,
)

# ==============================================================================
# GROUP 1: CATALOG COLLECTION ACCESS & SUBSCRIPTION
# Note: Verifies dict access, aliases, len, iter, contains, and 'all' aggregation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_length_returns_five() -> None:
    """Verify VitalSourcesCatalog length matches the 5 canonical vital schemas."""
    catalog = VitalSourcesCatalog()
    assert len(catalog) == 5


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_returns_compiled_dict() -> None:
    """Verify catalog subscription by logical key returns compiled schema."""
    catalog = VitalSourcesCatalog()
    schema = catalog["birth_certificate"]
    assert isinstance(schema, dict)
    assert schema["$id"].endswith("sources/birth_certificate.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_supports_alias_keys() -> None:
    """Verify catalog subscription resolves shorthand key aliases."""
    catalog = VitalSourcesCatalog()
    schema = catalog["death"]
    assert schema["$id"].endswith("sources/death_certificate.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_all_returns_all_five_schemas() -> None:
    """Verify catalog['all'] compiles and returns a dictionary of all five schemas."""
    catalog = VitalSourcesCatalog()
    all_schemas = catalog["all"]
    assert len(all_schemas) == 5
    assert "birth_certificate" in all_schemas
    assert "cemetery_marker" in all_schemas


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_contains_evaluates_true_for_valid_key() -> None:
    """Verify __contains__ returns True for registered keys and aliases."""
    catalog = VitalSourcesCatalog()
    assert "birth_certificate" in catalog
    assert "cemetery" in catalog
    assert "all" in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_contains_evaluates_false_for_invalid_key() -> None:
    """Verify __contains__ returns False for unregistered keys or non-strings."""
    catalog = VitalSourcesCatalog()
    assert "unknown_vital" not in catalog
    assert 12345 not in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_key_error_on_unknown_key() -> None:
    """Verify accessing an unknown key raises KeyError."""
    catalog = VitalSourcesCatalog()
    with pytest.raises(KeyError, match="No vital source builder found matching key"):
        _ = catalog["ghost_vital"]


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_iteration_yields_all_canonical_keys() -> None:
    """Verify iterating catalog yields the 5 canonical logical keys."""
    catalog = VitalSourcesCatalog()
    keys = list(catalog)
    assert len(keys) == 5
    assert "church_baptism" in keys


# ==============================================================================
# GROUP 2: INDIVIDUAL BUILDERS & ENVELOPE METADATA
# Note: Verifies GSI _name, _path, and required properties
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_build_all_vital_schemas_declare_gsi_headers() -> None:
    """Verify all 5 vital builders declare valid _name and _path metadata."""
    for builder in (
        build_birth_certificate_schema,
        build_marriage_license_schema,
        build_death_certificate_schema,
        build_church_baptism_schema,
        build_cemetery_marker_schema,
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
def vital_validator() -> GDASchemaValidator:
    """Provide validator pre-registered with canonical base definition schemas."""
    validator = GDASchemaValidator()
    base_cat = BaseCatalog()
    enums_schema = base_cat["enums"]
    shared_schema = base_cat["shared_defs"]
    death_schema = base_cat["death_defs"]
    doc_schema = base_cat["document_defs"]

    resources = [
        ("_enums.schema.json", enums_schema),
        ("_shared_defs.schema.json", shared_schema),
        ("_shared_shared_defs.schema.json", shared_schema),
        ("_death_defs.schema.json", death_schema),
        ("_document_defs.schema.json", doc_schema),
    ]

    for name, schema in resources:
        if "$id" in schema:
            validator.register_resource(schema["$id"], schema)
        for prefix in ("defs/", "../defs/", ""):
            validator.register_resource(f"{prefix}{name}", schema)

    return validator


@pytest.fixture
def golden_vital_data() -> Dict[str, Any]:
    """Load canonical synthetic golden vital source test payloads."""
    repo_root = Path(__file__).resolve().parents[4]
    fixture_path = (
        repo_root
        / "tests"
        / "fixtures"
        / "sources"
        / "vital"
        / "golden"
        / "golden_vital_sources.json"
    )
    if not fixture_path.is_file():
        pytest.skip(f"Golden fixture file not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def failure_vital_data() -> Dict[str, Dict[str, Any]]:
    """Load failure defect payloads for vital sources."""
    repo_root = Path(__file__).resolve().parents[4]
    failure_dir = repo_root / "tests" / "fixtures" / "sources" / "vital" / "failure"
    if not failure_dir.is_dir():
        pytest.skip(f"Failure fixtures dir not found: {failure_dir}")
    payloads: Dict[str, Dict[str, Any]] = {}
    for item in failure_dir.glob("*.json"):
        payloads[item.stem] = json.loads(item.read_text(encoding="utf-8"))
    return payloads


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_birth_certificate(
    vital_validator: GDASchemaValidator, golden_vital_data: Dict[str, Any]
) -> None:
    """Verify golden birth certificate payload satisfies compiled schema."""
    schema = build_birth_certificate_schema()
    errors = vital_validator.validate_instance(
        golden_vital_data["birth_certificate"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_marriage_license(
    vital_validator: GDASchemaValidator, golden_vital_data: Dict[str, Any]
) -> None:
    """Verify golden marriage license payload satisfies compiled schema."""
    schema = build_marriage_license_schema()
    errors = vital_validator.validate_instance(
        golden_vital_data["marriage_license"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_death_certificate(
    vital_validator: GDASchemaValidator, golden_vital_data: Dict[str, Any]
) -> None:
    """Verify golden death certificate payload satisfies compiled schema."""
    schema = build_death_certificate_schema()
    errors = vital_validator.validate_instance(
        golden_vital_data["death_certificate"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_church_baptism(
    vital_validator: GDASchemaValidator, golden_vital_data: Dict[str, Any]
) -> None:
    """Verify golden church baptism payload satisfies compiled schema."""
    schema = build_church_baptism_schema()
    errors = vital_validator.validate_instance(
        golden_vital_data["church_baptism"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_cemetery_marker(
    vital_validator: GDASchemaValidator, golden_vital_data: Dict[str, Any]
) -> None:
    """Verify golden cemetery marker payload satisfies compiled schema."""
    schema = build_cemetery_marker_schema()
    errors = vital_validator.validate_instance(
        golden_vital_data["cemetery_marker"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_birth_missing_child(
    vital_validator: GDASchemaValidator, failure_vital_data: Dict[str, Dict[str, Any]]
) -> None:
    """Verify birth certificate payload missing child fails validation."""
    schema = build_birth_certificate_schema()
    corrupt = failure_vital_data["corrupt_birth_missing_child"]
    errors = vital_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_death_invalid_urn(
    vital_validator: GDASchemaValidator, failure_vital_data: Dict[str, Dict[str, Any]]
) -> None:
    """Verify death certificate payload with non-matching source_urn fails validation."""
    schema = build_death_certificate_schema()
    corrupt = failure_vital_data["corrupt_death_invalid_urn"]
    errors = vital_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


# ==============================================================================
# GROUP 4: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify VitalSourcesCatalog inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    VitalSourcesCatalog.help()
    output = captured.getvalue()
    assert "VitalSourcesCatalog" in output