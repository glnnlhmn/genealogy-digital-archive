# Name: test_sources_specialized.py
# Path: tools/lib/gdaschema/tests/test_sources_specialized.py
# Version: 1.0.0+build.r1

"""Unit test suite verifying specialized sources catalog and procedural emitters.

Operational Role:
    Validates Draft 2020-12 envelope integrity, SpecializedSourcesCatalog collection
    subscription, key aliases, 'all' iterator aggregation, GSI headers,
    and roundtrip validation against golden and failure specialized source fixtures.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integrity.
    - Dependencies: gdaschema.sources.specialized, gdaschema.defs.base, gdaschema.schema_validator, pytest.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from gdaschema.defs.base import BaseCatalog
from gdaschema.schema_validator import GDASchemaValidator
from gdaschema.sources.specialized import (
    SpecializedSourcesCatalog,
    build_academic_credential_schema,
    build_military_draft_schema,
    build_newspaper_article_schema,
    build_other_miscellaneous_schema,
    build_personal_testimony_schema,
)

# ==============================================================================
# GROUP 1: CATALOG COLLECTION ACCESS & SUBSCRIPTION
# Note: Verifies dict access, aliases, len, iter, contains, and 'all' aggregation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_length_returns_five() -> None:
    """Verify SpecializedSourcesCatalog length matches the 5 canonical schemas."""
    catalog = SpecializedSourcesCatalog()
    assert len(catalog) == 5


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_returns_compiled_dict() -> None:
    """Verify catalog subscription by logical key returns compiled schema."""
    catalog = SpecializedSourcesCatalog()
    schema = catalog["academic_credential"]
    assert isinstance(schema, dict)
    assert schema["$id"].endswith("sources/academic_credential.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_supports_alias_keys() -> None:
    """Verify catalog subscription resolves shorthand key aliases."""
    catalog = SpecializedSourcesCatalog()
    schema = catalog["newspaper"]
    assert schema["$id"].endswith("sources/newspaper_article.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_all_returns_all_five_schemas() -> None:
    """Verify catalog['all'] compiles and returns a dictionary of all five schemas."""
    catalog = SpecializedSourcesCatalog()
    all_schemas = catalog["all"]
    assert len(all_schemas) == 5
    assert "military_draft" in all_schemas
    assert "personal_testimony" in all_schemas


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_contains_evaluates_true_for_valid_key() -> None:
    """Verify __contains__ returns True for registered keys and aliases."""
    catalog = SpecializedSourcesCatalog()
    assert "academic_credential" in catalog
    assert "draft" in catalog
    assert "all" in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_contains_evaluates_false_for_invalid_key() -> None:
    """Verify __contains__ returns False for unregistered keys or non-strings."""
    catalog = SpecializedSourcesCatalog()
    assert "unknown_specialized" not in catalog
    assert 12345 not in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_key_error_on_unknown_key() -> None:
    """Verify accessing an unknown key raises KeyError."""
    catalog = SpecializedSourcesCatalog()
    with pytest.raises(KeyError, match="No specialized source builder found matching key"):
        _ = catalog["ghost_specialized"]


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_iteration_yields_all_canonical_keys() -> None:
    """Verify iterating catalog yields the 5 canonical logical keys."""
    catalog = SpecializedSourcesCatalog()
    keys = list(catalog)
    assert len(keys) == 5
    assert "other_miscellaneous" in keys


# ==============================================================================
# GROUP 2: INDIVIDUAL BUILDERS & ENVELOPE METADATA
# Note: Verifies GSI _name, _path, and required properties
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_build_all_specialized_schemas_declare_gsi_headers() -> None:
    """Verify all 5 specialized builders declare valid _name and _path metadata."""
    for builder in (
        build_academic_credential_schema,
        build_military_draft_schema,
        build_newspaper_article_schema,
        build_personal_testimony_schema,
        build_other_miscellaneous_schema,
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
def specialized_validator() -> GDASchemaValidator:
    """Provide validator pre-registered with canonical base definition schemas."""
    validator = GDASchemaValidator()
    base_cat = BaseCatalog()
    enums_schema = base_cat["enums"]
    shared_schema = base_cat["shared_defs"]
    military_schema = base_cat["military_defs"]
    doc_schema = base_cat["document_defs"]

    resources = [
        ("_enums.schema.json", enums_schema),
        ("_shared_defs.schema.json", shared_schema),
        ("_shared_shared_defs.schema.json", shared_schema),
        ("_military_defs.schema.json", military_schema),
        ("_document_defs.schema.json", doc_schema),
    ]

    for name, schema in resources:
        if "$id" in schema:
            validator.register_resource(schema["$id"], schema)
        for prefix in ("defs/", "../defs/", ""):
            validator.register_resource(f"{prefix}{name}", schema)

    return validator


@pytest.fixture
def golden_specialized_data() -> Dict[str, Any]:
    """Load canonical synthetic golden specialized source test payloads."""
    repo_root = Path(__file__).resolve().parents[4]
    fixture_path = (
        repo_root
        / "tests"
        / "fixtures"
        / "sources"
        / "specialized"
        / "golden"
        / "golden_specialized_sources.json"
    )
    if not fixture_path.is_file():
        pytest.skip(f"Golden fixture file not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def failure_specialized_data() -> Dict[str, Dict[str, Any]]:
    """Load failure defect payloads for specialized sources."""
    repo_root = Path(__file__).resolve().parents[4]
    failure_dir = (
        repo_root / "tests" / "fixtures" / "sources" / "specialized" / "failure"
    )
    if not failure_dir.is_dir():
        pytest.skip(f"Failure fixtures dir not found: {failure_dir}")
    payloads: Dict[str, Dict[str, Any]] = {}
    for item in failure_dir.glob("*.json"):
        payloads[item.stem] = json.loads(item.read_text(encoding="utf-8"))
    return payloads


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_academic_credential(
    specialized_validator: GDASchemaValidator,
    golden_specialized_data: Dict[str, Any],
) -> None:
    """Verify golden academic credential payload satisfies compiled schema."""
    schema = build_academic_credential_schema()
    errors = specialized_validator.validate_instance(
        golden_specialized_data["academic_credential"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_military_draft(
    specialized_validator: GDASchemaValidator,
    golden_specialized_data: Dict[str, Any],
) -> None:
    """Verify golden military draft payload satisfies compiled schema."""
    schema = build_military_draft_schema()
    errors = specialized_validator.validate_instance(
        golden_specialized_data["military_draft"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_newspaper_article(
    specialized_validator: GDASchemaValidator,
    golden_specialized_data: Dict[str, Any],
) -> None:
    """Verify golden newspaper article payload satisfies compiled schema."""
    schema = build_newspaper_article_schema()
    errors = specialized_validator.validate_instance(
        golden_specialized_data["newspaper_article"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_personal_testimony(
    specialized_validator: GDASchemaValidator,
    golden_specialized_data: Dict[str, Any],
) -> None:
    """Verify golden personal testimony payload satisfies compiled schema."""
    schema = build_personal_testimony_schema()
    errors = specialized_validator.validate_instance(
        golden_specialized_data["personal_testimony"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_other_miscellaneous(
    specialized_validator: GDASchemaValidator,
    golden_specialized_data: Dict[str, Any],
) -> None:
    """Verify golden other miscellaneous payload satisfies compiled schema."""
    schema = build_other_miscellaneous_schema()
    errors = specialized_validator.validate_instance(
        golden_specialized_data["other_miscellaneous"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_academic_missing_subject(
    specialized_validator: GDASchemaValidator,
    failure_specialized_data: Dict[str, Dict[str, Any]],
) -> None:
    """Verify academic credential payload missing subject fails validation."""
    schema = build_academic_credential_schema()
    corrupt = failure_specialized_data["corrupt_academic_missing_subject"]
    errors = specialized_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_draft_invalid_urn(
    specialized_validator: GDASchemaValidator,
    failure_specialized_data: Dict[str, Dict[str, Any]],
) -> None:
    """Verify military draft payload with non-matching source_urn fails validation."""
    schema = build_military_draft_schema()
    corrupt = failure_specialized_data["corrupt_draft_invalid_urn"]
    errors = specialized_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


# ==============================================================================
# GROUP 4: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify SpecializedSourcesCatalog inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    SpecializedSourcesCatalog.help()
    output = captured.getvalue()
    assert "SpecializedSourcesCatalog" in output