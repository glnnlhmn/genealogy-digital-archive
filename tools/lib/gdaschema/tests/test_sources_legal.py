# Name: test_sources_legal.py
# Path: tools/lib/gdaschema/tests/test_sources_legal.py
# Version: 1.0.0+build.r1

"""Unit test suite verifying legal sources catalog and procedural emitters.

Operational Role:
    Validates Draft 2020-12 envelope integrity, LegalSourcesCatalog collection
    subscription, key aliases, 'all' iterator aggregation, GSI headers,
    and roundtrip validation against golden and failure legal source fixtures.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integrity.
    - Dependencies: gdaschema.sources.legal, gdaschema.defs.base, gdaschema.schema_validator, pytest.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from gdaschema.defs.base import BaseCatalog
from gdaschema.schema_validator import GDASchemaValidator
from gdaschema.sources.legal import (
    LegalSourcesCatalog,
    build_divorce_report_schema,
    build_land_deed_schema,
    build_probate_record_schema,
    build_tax_assessment_schema,
)

# ==============================================================================
# GROUP 1: CATALOG COLLECTION ACCESS & SUBSCRIPTION
# Note: Verifies dict access, aliases, len, iter, contains, and 'all' aggregation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_length_returns_four() -> None:
    """Verify LegalSourcesCatalog length matches the 4 canonical schemas."""
    catalog = LegalSourcesCatalog()
    assert len(catalog) == 4


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_returns_compiled_dict() -> None:
    """Verify catalog subscription by logical key returns compiled schema."""
    catalog = LegalSourcesCatalog()
    schema = catalog["divorce_report"]
    assert isinstance(schema, dict)
    assert schema["$id"].endswith("sources/divorce_report.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_supports_alias_keys() -> None:
    """Verify catalog subscription resolves shorthand key aliases."""
    catalog = LegalSourcesCatalog()
    schema = catalog["will"]
    assert schema["$id"].endswith("sources/probate_record.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_all_returns_all_four_schemas() -> None:
    """Verify catalog['all'] compiles and returns a dictionary of all four schemas."""
    catalog = LegalSourcesCatalog()
    all_schemas = catalog["all"]
    assert len(all_schemas) == 4
    assert "divorce_report" in all_schemas
    assert "land_deed" in all_schemas


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_contains_evaluates_true_for_valid_key() -> None:
    """Verify __contains__ returns True for registered keys and aliases."""
    catalog = LegalSourcesCatalog()
    assert "divorce_report" in catalog
    assert "deed" in catalog
    assert "all" in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_contains_evaluates_false_for_invalid_key() -> None:
    """Verify __contains__ returns False for unregistered keys or non-strings."""
    catalog = LegalSourcesCatalog()
    assert "unknown_legal" not in catalog
    assert 12345 not in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_key_error_on_unknown_key() -> None:
    """Verify accessing an unknown key raises KeyError."""
    catalog = LegalSourcesCatalog()
    with pytest.raises(KeyError, match="No legal source builder found matching key"):
        _ = catalog["ghost_legal"]


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_iteration_yields_all_canonical_keys() -> None:
    """Verify iterating catalog yields the 4 canonical logical keys."""
    catalog = LegalSourcesCatalog()
    keys = list(catalog)
    assert len(keys) == 4
    assert "tax_assessment" in keys


# ==============================================================================
# GROUP 2: INDIVIDUAL BUILDERS & ENVELOPE METADATA
# Note: Verifies GSI _name, _path, and required properties
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_build_all_legal_schemas_declare_gsi_headers() -> None:
    """Verify all 4 legal builders declare valid _name and _path metadata."""
    for builder in (
        build_divorce_report_schema,
        build_probate_record_schema,
        build_land_deed_schema,
        build_tax_assessment_schema,
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
def legal_validator() -> GDASchemaValidator:
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
def golden_legal_data() -> Dict[str, Any]:
    """Load canonical synthetic golden legal source test payloads."""
    repo_root = Path(__file__).resolve().parents[4]
    fixture_path = (
        repo_root
        / "tests"
        / "fixtures"
        / "sources"
        / "legal"
        / "golden"
        / "golden_legal_sources.json"
    )
    if not fixture_path.is_file():
        pytest.skip(f"Golden fixture file not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def failure_legal_data() -> Dict[str, Dict[str, Any]]:
    """Load failure defect payloads for legal sources."""
    repo_root = Path(__file__).resolve().parents[4]
    failure_dir = repo_root / "tests" / "fixtures" / "sources" / "legal" / "failure"
    if not failure_dir.is_dir():
        pytest.skip(f"Failure fixtures dir not found: {failure_dir}")
    payloads: Dict[str, Dict[str, Any]] = {}
    for item in failure_dir.glob("*.json"):
        payloads[item.stem] = json.loads(item.read_text(encoding="utf-8"))
    return payloads


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_divorce_report(
    legal_validator: GDASchemaValidator, golden_legal_data: Dict[str, Any]
) -> None:
    """Verify golden divorce report payload satisfies compiled schema."""
    schema = build_divorce_report_schema()
    errors = legal_validator.validate_instance(
        golden_legal_data["divorce_report"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_probate_record(
    legal_validator: GDASchemaValidator, golden_legal_data: Dict[str, Any]
) -> None:
    """Verify golden probate record payload satisfies compiled schema."""
    schema = build_probate_record_schema()
    errors = legal_validator.validate_instance(
        golden_legal_data["probate_record"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_land_deed(
    legal_validator: GDASchemaValidator, golden_legal_data: Dict[str, Any]
) -> None:
    """Verify golden land deed payload satisfies compiled schema."""
    schema = build_land_deed_schema()
    errors = legal_validator.validate_instance(
        golden_legal_data["land_deed"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_tax_assessment(
    legal_validator: GDASchemaValidator, golden_legal_data: Dict[str, Any]
) -> None:
    """Verify golden tax assessment payload satisfies compiled schema."""
    schema = build_tax_assessment_schema()
    errors = legal_validator.validate_instance(
        golden_legal_data["tax_assessment"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_probate_missing_decedent(
    legal_validator: GDASchemaValidator,
    failure_legal_data: Dict[str, Dict[str, Any]],
) -> None:
    """Verify probate record payload missing decedent fails validation."""
    schema = build_probate_record_schema()
    corrupt = failure_legal_data["corrupt_probate_missing_decedent"]
    errors = legal_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_deed_invalid_urn(
    legal_validator: GDASchemaValidator,
    failure_legal_data: Dict[str, Dict[str, Any]],
) -> None:
    """Verify land deed payload with non-matching source_urn fails validation."""
    schema = build_land_deed_schema()
    corrupt = failure_legal_data["corrupt_deed_invalid_urn"]
    errors = legal_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


# ==============================================================================
# GROUP 4: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LegalSourcesCatalog inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    LegalSourcesCatalog.help()
    output = captured.getvalue()
    assert "LegalSourcesCatalog" in output