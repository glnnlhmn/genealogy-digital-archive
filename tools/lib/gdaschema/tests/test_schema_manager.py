# Name: test_schema_manager.py
# Path: tools/lib/gdaschema/tests/test_schema_manager.py
# Version: 1.0.0+build.r6

"""Unit test suite verifying GDASchemaManager compilation, validation, emission, and drift inspection.

Operational Role:
    Validates complete catalog registration (46 schemas across defs, entities, indexes,
    xrefs, sources), dictionary access, Draft 2020-12 meta-schema compliance, disk
    emission with Safe Backups, drift inspection, and instance validation.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integrity.
    - Dependencies: gdaschema.schema_manager, gdacore, pytest.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from gdaschema.schema_manager import GDASchemaManager, SchemaItem

# ==============================================================================
# GROUP 1: CATALOG REGISTRATION & DICTIONARY ACCESS
# Note: Verifies schema counting, key lookups, aliases, iteration, containment, and config fallbacks
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_default_instantiation_resolves_config_schemas_dir() -> None:
    """Verify GDASchemaManager instantiates cleanly using default CONFIG attributes without raising AttributeError."""
    manager = GDASchemaManager()
    assert manager._schemas_dir is not None
    assert len(manager) == 46


@pytest.mark.unit
@pytest.mark.regression
def test_manager_instantiation_falls_back_to_root_dir(tmp_path: Path) -> None:
    """Verify GDASchemaManager falls back to config.root_dir / schemas when schemas_dir attribute is absent."""
    mock_cfg = MagicMock(spec=[])
    mock_cfg.root_dir = tmp_path
    manager = GDASchemaManager(config=mock_cfg)
    assert manager._schemas_dir == tmp_path / "schemas"


@pytest.mark.unit
@pytest.mark.regression
def test_manager_instantiation_falls_back_to_relative_schemas_default() -> None:
    """Verify GDASchemaManager falls back to relative Path('schemas') when config lacks both attributes."""
    mock_cfg = MagicMock(spec=[])
    manager = GDASchemaManager(config=mock_cfg)
    assert manager._schemas_dir == Path("schemas")


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_registers_all_forty_six_schemas(tmp_path: Path) -> None:
    """Verify GDASchemaManager registers all 46 canonical schemas across all domains."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    assert len(manager) == 46


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_subscription_by_logical_key(tmp_path: Path) -> None:
    """Verify subscription by logical key returns a SchemaItem with valid builder."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    item = manager["person"]
    assert isinstance(item, SchemaItem)
    assert item.key == "person"
    assert item.schema_type == "entity"


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_subscription_by_filename_alias(tmp_path: Path) -> None:
    """Verify subscription by filename alias resolves to the target SchemaItem."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    item = manager["birth_certificate.schema.json"]
    assert item.key == "birth_certificate"
    assert item.schema_type == "source"


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_contains_returns_true_for_keys_and_aliases(tmp_path: Path) -> None:
    """Verify __contains__ returns True for registered keys and filename aliases."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    assert "enums" in manager
    assert "_enums.schema.json" in manager
    assert "source_registry" in manager
    assert "newspaper_registry" in manager
    assert "cemetery_registry" in manager


@pytest.mark.unit
@pytest.mark.regression
def test_manager_contains_returns_false_for_invalid_keys(tmp_path: Path) -> None:
    """Verify __contains__ returns False for unregistered strings or non-string types."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    assert "nonexistent_schema" not in manager
    assert 99999 not in manager


@pytest.mark.unit
@pytest.mark.regression
def test_manager_raises_key_error_on_unknown_schema(tmp_path: Path) -> None:
    """Verify accessing an unknown schema raises KeyError."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    with pytest.raises(KeyError, match="No schema registered matching key"):
        _ = manager["unknown_key"]


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_iteration_yields_all_keys(tmp_path: Path) -> None:
    """Verify iterating manager yields all registered logical keys."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    keys = list(manager)
    assert len(keys) == 46
    assert "source_registry" in keys


# ==============================================================================
# GROUP 2: META-SCHEMA VALIDATION & PAYLOAD ACCESS
# Note: Verifies get_schema() and Draft 2020-12 meta-schema compliance
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_get_schema_returns_dict(tmp_path: Path) -> None:
    """Verify get_schema() returns compiled schema dictionary."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    schema = manager.get_schema("location")
    assert isinstance(schema, dict)
    assert schema["title"] == "Master Civil Location Entity Schema"


@pytest.mark.unit
@pytest.mark.integrity
def test_all_registered_schemas_pass_draft202012_validation(tmp_path: Path) -> None:
    """Verify every registered schema satisfies Draft 2020-12 meta-schema constraints."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    for key, item in manager._schemas.items():
        is_valid, err = item.validate()
        assert is_valid is True, f"Schema '{key}' failed meta-schema check: {err}"


@pytest.mark.unit
@pytest.mark.regression
def test_schema_item_validate_returns_false_on_schema_error(tmp_path: Path) -> None:
    """Verify SchemaItem.validate() returns False and error message when schema definition is invalid."""
    invalid_builder = lambda: {"type": "not_a_valid_json_type"}
    item = SchemaItem("invalid", tmp_path / "invalid.json", invalid_builder)
    is_valid, err = item.validate()
    assert is_valid is False
    assert err is not None


# ==============================================================================
# GROUP 3: DISK EMISSION & SAFE BACKUP PROTOCOL
# Note: Verifies write_all(), directory creation, and dry run behavior
# ==============================================================================


@pytest.mark.unit
@pytest.mark.integration
def test_manager_write_all_emits_all_schemas(tmp_path: Path) -> None:
    """Verify write_all() writes all 46 schema files to disk under target directory."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    written_paths = manager.write_all(dry_run=False, create_backup=False)

    assert len(written_paths) == 46
    for path in written_paths:
        assert path.is_file()
        assert path.stat().st_size > 0


@pytest.mark.unit
@pytest.mark.integration
def test_manager_write_all_dry_run_creates_no_files(tmp_path: Path) -> None:
    """Verify write_all() with dry_run=True creates no physical files."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    written_paths = manager.write_all(dry_run=True, create_backup=False)

    assert len(written_paths) == 46
    for path in written_paths:
        assert not path.exists()


# ==============================================================================
# GROUP 4: DRIFT INSPECTION & HAS_DRIFT PROPERTY
# Note: Verifies missing files, content drift, and intact matches
# ==============================================================================


@pytest.mark.unit
@pytest.mark.integrity
def test_manager_inspect_drift_detects_missing_files(tmp_path: Path) -> None:
    """Verify inspect_drift() flags all schemas as drifted when disk is empty."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    drift = manager.inspect_drift()
    assert len(drift) == 46


@pytest.mark.unit
@pytest.mark.integrity
def test_manager_inspect_drift_returns_empty_when_synced(tmp_path: Path) -> None:
    """Verify inspect_drift() returns empty dictionary when all disk files match generators."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    manager.write_all(dry_run=False, create_backup=False)

    drift = manager.inspect_drift()
    assert drift == {}


@pytest.mark.unit
@pytest.mark.smoke
def test_schema_item_has_drift_property(tmp_path: Path) -> None:
    """Verify SchemaItem.has_drift evaluates to True when file is missing and False when synced."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    item = manager["person"]
    assert item.has_drift is True
    item.write(dry_run=False, create_backup=False)
    assert item.has_drift is False


@pytest.mark.unit
@pytest.mark.regression
def test_manager_inspect_drift_detects_modified_file(tmp_path: Path) -> None:
    """Verify inspect_drift() identifies a surgically altered file on disk."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    manager.write_all(dry_run=False, create_backup=False)

    target_file = manager["person"].target_path
    target_file.write_text('{"corrupted": true}', encoding="utf-8")

    drift = manager.inspect_drift()
    assert "person" in drift
    assert "Schema drift detected" in drift["person"]


@pytest.mark.unit
@pytest.mark.regression
def test_manager_inspect_drift_detects_unparseable_file(tmp_path: Path) -> None:
    """Verify inspect_drift() flags an invalid JSON file on disk."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    manager.write_all(dry_run=False, create_backup=False)

    target_file = manager["person"].target_path
    target_file.write_text('{invalid-json}', encoding="utf-8")

    drift = manager.inspect_drift()
    assert "person" in drift
    assert "Failed to parse disk schema" in drift["person"]


# ==============================================================================
# GROUP 5: INSTANCE DATA VALIDATION
# Note: Verifies single-entry validate_instance() against pre-wired validator
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_validate_instance_success(tmp_path: Path) -> None:
    """Verify validate_instance() returns empty list for valid instance payload."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    valid_location = {
        "location_id": "LOC-00001",
        "canonical_name": "Concord, Merrimack, New Hampshire, USA",
        "aliases": ["Concord, NH"],
        "jurisdiction": {
            "country": "USA",
            "state_or_province": "New Hampshire",
            "county": "Merrimack",
            "local_jurisdiction": "Concord",
        },
    }
    errors = manager.validate_instance(valid_location, "location")
    assert errors == []


@pytest.mark.unit
@pytest.mark.regression
def test_manager_validate_instance_failure(tmp_path: Path) -> None:
    """Verify validate_instance() returns error strings for invalid payload."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    invalid_location = {
        "location_id": "NOT-A-LOC-ID",
        "aliases": [],
    }
    errors = manager.validate_instance(invalid_location, "location")
    assert len(errors) > 0


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_create_validator_registers_schemas_without_id(tmp_path: Path) -> None:
    """Verify create_validator() registers schemas that do not declare an $id property."""
    manager = GDASchemaManager(schemas_dir=tmp_path)
    manager.register("no_id", tmp_path / "no_id.json", lambda: {"type": "object"})
    validator = manager.create_validator()
    assert validator is not None


# ==============================================================================
# GROUP 6: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GDASchemaManager inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    GDASchemaManager.help()
    output = captured.getvalue()
    assert "GDASchemaManager" in output