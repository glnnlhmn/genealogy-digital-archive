# Name: test_sources_registries.py
# Path: tools/lib/gdaschema/tests/test_sources_registries.py
# Version: 1.0.0+build.r3

"""Unit test suite verifying archival source registries catalog and procedural emitters.

Operational Role:
    Validates Draft 2020-12 envelope integrity, SourceRegistriesCatalog collection
    subscription, key aliases, 'all' iterator aggregation, GSI headers,
    and roundtrip validation against golden and failure registry fixtures using UUIDv4 identifiers.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integrity.
    - Dependencies: gdaschema.sources.registries, gdaschema.defs.base, gdaschema.schema_validator, pytest.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from gdaschema.defs.base import BaseCatalog
from gdaschema.schema_validator import GDASchemaValidator
from gdaschema.sources.registries import (
    SourceRegistriesCatalog,
    build_cemetery_registry_schema,
    build_newspaper_registry_schema,
    build_source_registry_schema,
)

# ==============================================================================
# GROUP 1: CATALOG COLLECTION ACCESS & SUBSCRIPTION
# Note: Verifies dict access, aliases, len, iter, contains, and 'all' aggregation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_length_returns_three() -> None:
    """Verify SourceRegistriesCatalog length matches the 3 canonical registry schemas."""
    catalog = SourceRegistriesCatalog()
    assert len(catalog) == 3


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_returns_compiled_dict() -> None:
    """Verify catalog subscription by logical key returns compiled schema."""
    catalog = SourceRegistriesCatalog()
    schema = catalog["source_registry"]
    assert isinstance(schema, dict)
    assert schema["$id"].endswith("sources/source_registry.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_supports_alias_keys() -> None:
    """Verify catalog subscription resolves shorthand key aliases."""
    catalog = SourceRegistriesCatalog()
    schema = catalog["newspapers"]
    assert schema["$id"].endswith("sources/newspaper_registry.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_all_returns_all_three_schemas() -> None:
    """Verify catalog['all'] compiles and returns a dictionary of all three schemas."""
    catalog = SourceRegistriesCatalog()
    all_schemas = catalog["all"]
    assert len(all_schemas) == 3
    assert "source_registry" in all_schemas
    assert "cemetery_registry" in all_schemas


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_contains_evaluates_true_for_valid_key() -> None:
    """Verify __contains__ returns True for registered keys and aliases."""
    catalog = SourceRegistriesCatalog()
    assert "source_registry" in catalog
    assert "cemetery" in catalog
    assert "all" in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_contains_evaluates_false_for_invalid_key() -> None:
    """Verify __contains__ returns False for unregistered keys or non-strings."""
    catalog = SourceRegistriesCatalog()
    assert "unknown_registry" not in catalog
    assert 12345 not in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_key_error_on_unknown_key() -> None:
    """Verify accessing an unknown key raises KeyError."""
    catalog = SourceRegistriesCatalog()
    with pytest.raises(KeyError, match="No source registry builder found matching key"):
        _ = catalog["ghost_registry"]


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_iteration_yields_all_canonical_keys() -> None:
    """Verify iterating catalog yields the 3 canonical logical keys."""
    catalog = SourceRegistriesCatalog()
    keys = list(catalog)
    assert len(keys) == 3
    assert "newspaper_registry" in keys


# ==============================================================================
# GROUP 2: INDIVIDUAL BUILDERS & ENVELOPE METADATA
# Note: Verifies GSI _name, _path, and required properties
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_build_all_registry_schemas_declare_gsi_headers() -> None:
    """Verify all 3 registry builders declare valid _name and _path metadata."""
    for builder in (
        build_source_registry_schema,
        build_newspaper_registry_schema,
        build_cemetery_registry_schema,
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
def registry_validator() -> GDASchemaValidator:
    """Provide validator pre-registered with canonical base definition schemas."""
    validator = GDASchemaValidator()
    base_cat = BaseCatalog()
    enums_schema = base_cat["enums"]
    shared_schema = base_cat["shared_defs"]
    doc_schema = base_cat["document_defs"]

    resources = [
        ("_enums.schema.json", enums_schema),
        ("_shared_defs.schema.json", shared_schema),
        ("_shared_shared_defs.schema.json", shared_schema),
        ("_document_defs.schema.json", doc_schema),
    ]

    for name, schema in resources:
        if "$id" in schema:
            validator.register_resource(schema["$id"], schema)
        for prefix in ("defs/", "../defs/", ""):
            validator.register_resource(f"{prefix}{name}", schema)

    return validator


@pytest.fixture
def golden_registry_data() -> Dict[str, Any]:
    """Load canonical synthetic golden source registry test payloads."""
    repo_root = Path(__file__).resolve().parents[4]
    fixture_path = (
        repo_root
        / "tests"
        / "fixtures"
        / "sources"
        / "registries"
        / "golden"
        / "golden_source_registries.json"
    )
    if not fixture_path.is_file():
        pytest.skip(f"Golden fixture file not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def failure_registry_data() -> Dict[str, Dict[str, Any]]:
    """Load failure defect payloads for source registries."""
    repo_root = Path(__file__).resolve().parents[4]
    failure_dir = (
        repo_root / "tests" / "fixtures" / "sources" / "registries" / "failure"
    )
    payloads: Dict[str, Dict[str, Any]] = {}
    if failure_dir.is_dir():
        for item in failure_dir.glob("*.json"):
            payloads[item.stem] = json.loads(item.read_text(encoding="utf-8"))

    if "corrupt_source_registry_missing_guid" not in payloads:
        payloads["corrupt_source_registry_missing_guid"] = {
            "_name": "sources.json",
            "_path": "data/sources/sources.json",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "version": "1.1.0",
            "last_updated": "2026-10-13T16:20:00Z",
            "sources": [
                {
                    "title": "Missing GUID Record",
                    "record_category": "VITAL",
                    "repository_id": "REP-00001",
                }
            ],
        }

    if "corrupt_cemetery_registry_missing_plots" not in payloads:
        payloads["corrupt_cemetery_registry_missing_plots"] = {
            "_name": "cemetery_transcripts.json",
            "_path": "data/sources/cemetery_transcripts.json",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "version": "1.1.0",
            "last_updated": "2026-10-13T16:20:00Z",
            "site_id": "SID-00001",
            "cemetery_name": "Newville Cemetery",
            "location": {
                "location_id": "LOC-00001",
                "verbatim": "Newville, PA",
            },
        }

    return payloads


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_source_registry(
    registry_validator: GDASchemaValidator,
    golden_registry_data: Dict[str, Any],
) -> None:
    """Verify golden source registry payload satisfies compiled schema."""
    schema = build_source_registry_schema()
    errors = registry_validator.validate_instance(
        golden_registry_data["source_registry"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_newspaper_registry(
    registry_validator: GDASchemaValidator,
    golden_registry_data: Dict[str, Any],
) -> None:
    """Verify golden newspaper registry payload satisfies compiled schema."""
    schema = build_newspaper_registry_schema()
    errors = registry_validator.validate_instance(
        golden_registry_data["newspaper_registry"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_cemetery_registry(
    registry_validator: GDASchemaValidator,
    golden_registry_data: Dict[str, Any],
) -> None:
    """Verify golden cemetery registry payload satisfies compiled schema."""
    schema = build_cemetery_registry_schema()
    errors = registry_validator.validate_instance(
        golden_registry_data["cemetery_registry"], schema
    )
    assert errors == []


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_source_registry_missing_guid(
    registry_validator: GDASchemaValidator,
    failure_registry_data: Dict[str, Dict[str, Any]],
) -> None:
    """Verify source registry missing source_guid fails validation."""
    schema = build_source_registry_schema()
    corrupt = failure_registry_data["corrupt_source_registry_missing_guid"]
    errors = registry_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_cemetery_registry_missing_plots(
    registry_validator: GDASchemaValidator,
    failure_registry_data: Dict[str, Dict[str, Any]],
) -> None:
    """Verify cemetery registry missing plots array fails validation."""
    schema = build_cemetery_registry_schema()
    corrupt = failure_registry_data["corrupt_cemetery_registry_missing_plots"]
    errors = registry_validator.validate_instance(corrupt, schema)
    assert len(errors) > 0


# ==============================================================================
# GROUP 4: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify SourceRegistriesCatalog inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    SourceRegistriesCatalog.help()
    output = captured.getvalue()
    assert "SourceRegistriesCatalog" in output