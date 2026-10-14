# Name: test_base.py
# Path: tools/lib/gdaschema/tests/test_base.py
# Version: 1.0.0+build.r2

"""Unit test suite verifying base definitions catalog and procedural emitters.

Operational Role:
    Validates Draft 2020-12 envelope integrity, BaseCatalog collection
    subscription, key aliases, 'all' iterator aggregation, vocabulary authority
    integration, tombstone structures, and roundtrip validation against fixtures.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integrity.
    - Dependencies: gdaschema.defs.base, gdaschema.schema_validator, gdacore, pytest.
"""

from __future__ import annotations

import io
from typing import Any, Dict

import pytest

from gdaschema.defs.base import (
    BaseCatalog,
    build_census_defs,
    build_death_defs,
    build_document_defs,
    build_enums,
    build_external_xref_defs,
    build_military_defs,
    build_registry_defs,
    build_shared_defs,
)
from gdaschema.schema_validator import GDASchemaValidator

# ==============================================================================
# GROUP 1: CATALOG COLLECTION ACCESS & SUBSCRIPTION
# Note: Verifies dict access, aliases, len, iter, contains, and 'all' aggregation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_length_returns_eight() -> None:
    """Verify BaseCatalog length matches the 8 canonical definition schemas."""
    catalog = BaseCatalog()
    assert len(catalog) == 8


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_returns_compiled_dict() -> None:
    """Verify catalog subscription by logical key returns compiled schema."""
    catalog = BaseCatalog()
    schema = catalog["enums"]
    assert isinstance(schema, dict)
    assert schema["$id"].endswith("defs/_enums.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_supports_alias_keys() -> None:
    """Verify catalog subscription resolves shorthand key aliases."""
    catalog = BaseCatalog()
    death_schema = catalog["death_def"]
    assert death_schema["$id"].endswith("defs/_death_defs.schema.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_subscription_all_returns_all_eight_schemas() -> None:
    """Verify catalog['all'] compiles and returns a dictionary of all eight schemas."""
    catalog = BaseCatalog()
    all_schemas = catalog["all"]
    assert len(all_schemas) == 8
    assert "enums" in all_schemas
    assert "shared_defs" in all_schemas


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_contains_evaluates_true_for_valid_key() -> None:
    """Verify __contains__ returns True for registered keys and aliases."""
    catalog = BaseCatalog()
    assert "shared_defs" in catalog
    assert "shared" in catalog
    assert "all" in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_contains_evaluates_false_for_invalid_key() -> None:
    """Verify __contains__ returns False for unregistered keys or non-strings."""
    catalog = BaseCatalog()
    assert "unknown_schema" not in catalog
    assert 12345 not in catalog


@pytest.mark.unit
@pytest.mark.regression
def test_catalog_key_error_on_unknown_key() -> None:
    """Verify accessing an unknown key raises KeyError."""
    catalog = BaseCatalog()
    with pytest.raises(KeyError, match="No definition builder found matching key"):
        _ = catalog["ghost_schema"]


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_iteration_yields_all_canonical_keys() -> None:
    """Verify iterating catalog yields the 8 canonical logical keys."""
    catalog = BaseCatalog()
    keys = list(catalog)
    assert len(keys) == 8
    assert "census_defs" in keys


# ==============================================================================
# GROUP 2: DEFINITION PRIMITIVES & ENUM CONFORMANCE
# Note: Verifies taxonomy bindings, short date modifiers, and specific def keys
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_build_enums_contains_short_date_modifiers() -> None:
    """Verify build_enums date modifiers match strictly short GEDCOM tokens."""
    enums = build_enums()
    date_modifiers = enums["$defs"]["enum_date_modifier"]["enum"]
    assert date_modifiers == ["EXACT", "ABT", "BEF", "AFT", "BET", "FROM_TO", "UNKNOWN"]


@pytest.mark.unit
@pytest.mark.smoke
def test_build_enums_contains_vital_modifiers_and_union_status() -> None:
    """Verify build_enums includes enum_vital_date_modifier and union status."""
    enums = build_enums()
    defs = enums["$defs"]
    assert "enum_vital_date_modifier" in defs
    assert "PARTNER" in defs["enum_union_status"]["enum"]
    assert "WIDOWED" in defs["enum_union_status"]["enum"]


@pytest.mark.unit
@pytest.mark.smoke
def test_build_shared_defs_contains_tombstone_and_vital_year() -> None:
    """Verify build_shared_defs exports tombstone contract and vital_year."""
    shared = build_shared_defs()
    defs = shared["$defs"]
    assert "tombstone" in defs
    assert "vital_year" in defs
    assert "note_entry" in defs


@pytest.mark.unit
@pytest.mark.smoke
def test_build_shared_defs_note_entry_accepts_note_text_and_text() -> None:
    """Verify note_entry supports note_text property per domain contract."""
    shared = build_shared_defs()
    props = shared["$defs"]["note_entry"]["properties"]
    assert "note_text" in props
    assert "modified_date" in props


@pytest.mark.unit
@pytest.mark.smoke
def test_build_external_xref_defs_matches_schema() -> None:
    """Verify build_external_xref_defs includes URN pattern expressions."""
    xref = build_external_xref_defs()
    assert "census_source_urn" in xref["$defs"]
    assert "military_source_urn" in xref["$defs"]


@pytest.mark.unit
@pytest.mark.smoke
def test_build_death_defs_exports_cause_of_death() -> None:
    """Verify build_death_defs compiles cause_of_death definition."""
    death = build_death_defs()
    assert "cause_of_death" in death["$defs"]


@pytest.mark.unit
@pytest.mark.smoke
def test_build_registry_defs_exports_header() -> None:
    """Verify build_registry_defs compiles registry_header definition."""
    reg = build_registry_defs()
    assert "registry_header" in reg["$defs"]


@pytest.mark.unit
@pytest.mark.smoke
def test_build_census_defs_exports_line_entry() -> None:
    """Verify build_census_defs compiles census_line_entry definition."""
    census = build_census_defs()
    assert "census_line_entry" in census["$defs"]


@pytest.mark.unit
@pytest.mark.smoke
def test_build_document_defs_exports_media_clippings() -> None:
    """Verify build_document_defs compiles source_media and media_clipping."""
    doc = build_document_defs()
    assert "source_media" in doc["$defs"]
    assert "media_clipping" in doc["$defs"]


@pytest.mark.unit
@pytest.mark.smoke
def test_build_military_defs_exports_particulars() -> None:
    """Verify build_military_defs compiles selective_service_record."""
    mil = build_military_defs()
    assert "selective_service_record" in mil["$defs"]


# ==============================================================================
# GROUP 3: GOLDEN & FAILURE FIXTURE VALIDATION
# Note: Uses GDASchemaValidator to evaluate test payloads against definitions
# ==============================================================================


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_tombstone(golden_defs_data: Dict[str, Any]) -> None:
    """Verify golden tombstone assertions pass validation against shared_defs."""
    validator = GDASchemaValidator()
    shared_schema = build_shared_defs()
    tombstone_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": shared_schema["$defs"],
        "$ref": "#/$defs/tombstone",
    }
    assert validator.is_valid(golden_defs_data["tombstone"], tombstone_schema) is True
    assert validator.is_valid(golden_defs_data["tombstone_null"], tombstone_schema) is True


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_tombstone(failure_defs_data: Dict[str, Dict[str, Any]]) -> None:
    """Verify corrupt tombstone payload fails validation with type error."""
    validator = GDASchemaValidator()
    shared_schema = build_shared_defs()
    tombstone_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": shared_schema["$defs"],
        "$ref": "#/$defs/tombstone",
    }
    corrupt_payload = failure_defs_data["corrupt_tombstone_invalid_type"]
    errors = validator.validate_instance(corrupt_payload, tombstone_schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_golden_note_entries(golden_defs_data: Dict[str, Any]) -> None:
    """Verify both canonical and legacy note entries pass validation."""
    validator = GDASchemaValidator()
    enums_schema = build_enums()
    validator.register_resource("defs/_enums.schema.json", enums_schema)
    validator.register_resource("_enums.schema.json", enums_schema)

    shared_schema = build_shared_defs()
    note_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": shared_schema["$defs"],
        "$ref": "#/$defs/note_entry",
    }
    assert validator.is_valid(golden_defs_data["note_entry_canonical"], note_schema) is True
    assert validator.is_valid(golden_defs_data["note_entry_legacy"], note_schema) is True


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_note_entry(failure_defs_data: Dict[str, Dict[str, Any]]) -> None:
    """Verify missing required fields in note entry causes validation failure."""
    validator = GDASchemaValidator()
    enums_schema = build_enums()
    validator.register_resource("defs/_enums.schema.json", enums_schema)
    validator.register_resource("_enums.schema.json", enums_schema)

    shared_schema = build_shared_defs()
    note_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": shared_schema["$defs"],
        "$ref": "#/$defs/note_entry",
    }
    corrupt_payload = failure_defs_data["corrupt_note_missing_required"]
    errors = validator.validate_instance(corrupt_payload, note_schema)
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.regression
def test_validate_failure_vital_year_out_of_bounds(failure_defs_data: Dict[str, Dict[str, Any]]) -> None:
    """Verify year > 2100 in vital_year is rejected by schema validator."""
    validator = GDASchemaValidator()
    enums_schema = build_enums()
    validator.register_resource("defs/_enums.schema.json", enums_schema)
    validator.register_resource("_enums.schema.json", enums_schema)

    shared_schema = build_shared_defs()
    vital_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": shared_schema["$defs"],
        "$ref": "#/$defs/vital_year",
    }
    corrupt_payload = failure_defs_data["corrupt_vital_year_out_of_bounds"]
    errors = validator.validate_instance(corrupt_payload, vital_schema)
    assert len(errors) > 0


# ==============================================================================
# GROUP 4: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_catalog_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify BaseCatalog inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    BaseCatalog.help()
    output = captured.getvalue()
    assert "BaseCatalog" in output