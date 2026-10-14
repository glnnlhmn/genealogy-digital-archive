# Name: test_xrefs.py
# Path: tools/lib/gdaschema/tests/test_xrefs.py
# Version: 1.0.0+build.r1

"""Unit test suite verifying cross-reference catalog and procedural emitters.

Operational Role:
    Validates Draft 2020-12 envelope integrity, XRefCatalog collection
    subscription, key aliases, 'all' iterator aggregation, GSI headers,
    and roundtrip validation against golden and failure cross-reference fixtures.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integrity.
    - Dependencies: gdaschema.defs.xrefs, gdaschema.defs.base, gdaschema.schema_validator, pytest.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from gdaschema.defs.base import BaseCatalog
from gdaschema.defs.xrefs import (
    XRefCatalog,
    build_ahnentafel_xref_schema,
    build_family_group_xref_schema,
    build_newspaper_obituary_xref_schema,
)
from gdaschema.schema_validator import GDASchemaValidator

# ==============================================================================
# GROUP 1: CATALOG COLLECTION ACCESS & SUBSCRIPTION
# Note: Verifies dict access, aliases, len, iter, contains, and 'all' aggregation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_length_returns_three() -> None:
    """Verify XRefCatalog length matches the 3 canonical cross-reference schemas."""
    catalog = XRefCatalog()
    assert len(catalog) == 3


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_returns_compiled_dict() -> None:
    """Verify catalog subscription by logical key returns compiled schema."""
    catalog = XRefCatalog()
    schema = catalog["people_family_group_xref"]
    assert isinstance(schema, dict)
    assert schema["$id"].endswith("xrefs/people_family_group_xref.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_supports_alias_keys() -> None:
    """Verify catalog subscription resolves shorthand key aliases."""
    catalog = XRefCatalog()
    schema = catalog["family_group"]
    assert schema["$id"].endswith("xrefs/people_family_group_xref.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_all_returns_all_three_schemas() -> None:
    """Verify catalog['all'] compiles and returns a dictionary of all three schemas."""
    catalog = XRefCatalog()
    all_schemas = catalog["all"]
    assert len(all_schemas) == 3
    assert "people_family_group_xref" in all_schemas
    assert "people_ahnentafel_xref" in all_schemas
    assert "sources_newspaper_obituary_xref" in all_schemas


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_contains_evaluates_true_for_valid_key() -> None:
    """Verify __contains__ returns True for registered keys and aliases."""
    catalog = XRefCatalog()
    assert "people_family_group_xref" in catalog
    assert "ahnentafel" in catalog
    assert "all" in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_contains_evaluates_false_for_invalid_key() -> None:
    """Verify __contains__ returns False for unregistered keys or non-strings."""
    catalog = XRefCatalog()
    assert "unknown_xref" not in catalog
    assert 12345 not in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_key_error_on_unknown_key() -> None:
    """Verify accessing an unknown key raises KeyError."""
    catalog = XRefCatalog()
    with pytest.raises(KeyError, match="No cross-reference builder found matching key"):
        _ = catalog["ghost_xref"]


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_iteration_yields_all_canonical_keys() -> None:
    """Verify iterating catalog yields the 3 canonical logical keys."""
    catalog = XRefCatalog()
    keys = list(catalog)
    assert len(keys) == 3
    assert "people_ahnentafel_xref" in keys


# ==============================================================================
# GROUP 2: INDIVIDUAL BUILDERS & ENVELOPE METADATA
# Note: Verifies GSI _name, _path, and required properties
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_build_all_xref_schemas_declare_gsi_headers() -> None:
    """Verify all 3 xref builders declare valid _name and _path metadata."""
    for builder in (
        build_family_group_xref_schema,
        build_ahnentafel_xref_schema,
        build_newspaper_obituary_xref_schema,
    ):
        schema = builder()
        assert "_name" in schema
        assert "_path" in schema
        assert schema["_path"].startswith("schemas/xrefs/")


# ==============================================================================
# GROUP 3: FIXTURE VALIDATION & INSTANCE ROUNDTRIP
# Note: Validates synthetic golden and failure fixtures against compiled schemas
# ==============================================================================


@pytest.fixture
def xref_validator() -> GDASchemaValidator:
    """Provide validator pre-registered with canonical base definition schemas."""
    validator = GDASchemaValidator()
    base_cat = BaseCatalog()
    validator.register_resource("defs/_enums.schema.json", base_cat["enums"])
    validator.register_resource("../defs/_enums.schema.json", base_cat["enums"])
    validator.register_resource("defs/_shared_defs.schema.json", base_cat["shared_defs"])
    validator.register_resource("../defs/_shared_defs.schema.json", base_cat["shared_defs"])
    return validator


@pytest.fixture
def golden_xrefs_data() -> Dict[str, Any]:
    """Load canonical synthetic golden cross-reference test payloads."""
    repo_root = Path(__file__).resolve().parents[4]
    fixture_path = repo_root / "tests" / "fixtures" / "xrefs" / "golden" / "golden_xrefs.json"
    if not fixture_path.is_file():
        pytest.skip(f"Golden fixture file not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def failure_xrefs_data() -> Dict[str, Dict[str, Any]]:
    """Load failure defect payloads for cross-references."""
    repo_root = Path(__file__).resolve().parents[4]
    failure_dir = repo_root / "tests" / "fixtures" / "xrefs" / "failure"
    if not failure_dir.is_dir():
        pytest.skip(f"Failure fixtures dir not found: {failure_dir}")
    payloads: Dict[str, Dict[str, Any]] = {}
    for item in failure_dir.glob("*.json"):
        payloads[item.stem] = json.loads(item.read_text(encoding="utf-8"))
    return payloads


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_family_group_xref(
    xref_validator: GDASchemaValidator, golden_xrefs_data: Dict[str, Any]
) -> None:
    """Verify golden family group xref payload satisfies compiled schema."""
    schema = build_family_group_xref_schema()
    errors = xref_validator.validate_instance(
        golden_xrefs_data["people_family_group_xref"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_ahnentafel_xref(
    xref_validator: GDASchemaValidator, golden_xrefs_data: Dict[str, Any]
) -> None:
    """Verify golden ahnentafel xref payload satisfies compiled schema."""
    schema = build_ahnentafel_xref_schema()
    errors = xref_validator.validate_instance(
        golden_xrefs_data["people_ahnentafel_xref"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_newspaper_obituary_xref(
    xref_validator: GDASchemaValidator, golden_xrefs_data: Dict[str, Any]
) -> None:
    """Verify golden newspaper obituary xref payload satisfies compiled schema."""
    schema = build_newspaper_obituary_xref_schema()
    errors = xref_validator.validate_instance(
        golden_xrefs_data["sources_newspaper_obituary_xref"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_family_invalid_fam_id(
    xref_validator: GDASchemaValidator, failure_xrefs_data: Dict[str, Dict[str, Any]]
) -> None:
    """Verify family group payload with invalid family_id pattern fails validation."""
    schema = build_family_group_xref_schema()
    corrupt = failure_xrefs_data["corrupt_family_invalid_fam_id"]
    errors = xref_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_ahnentafel_zero_number(
    xref_validator: GDASchemaValidator, failure_xrefs_data: Dict[str, Dict[str, Any]]
) -> None:
    """Verify ahnentafel payload with number < 1 fails validation."""
    schema = build_ahnentafel_xref_schema()
    corrupt = failure_xrefs_data["corrupt_ahnentafel_zero_number"]
    errors = xref_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


# ==============================================================================
# GROUP 4: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify XRefCatalog inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    XRefCatalog.help()
    output = captured.getvalue()
    assert "XRefCatalog" in output