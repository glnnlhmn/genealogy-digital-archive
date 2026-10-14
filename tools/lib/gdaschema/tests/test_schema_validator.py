# Name: test_schema_validator.py
# Path: tools/lib/gdaschema/tests/test_schema_validator.py
# Version: 1.0.0+build.rc2

"""Unit test suite verifying GDASchemaValidator engine and referencing resolver.

Operational Role:
    Validates in-memory instance evaluation, local $ref schema resolution
    via referencing.Registry, disk file verification, auto-discovery via $schema,
    defensive error handling, and introspection compliance in schema_validator.py.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit, @pytest.mark.smoke,
      @pytest.mark.integrity, and @pytest.mark.regression.
    - Dependencies: gdaschema.schema_validator, gdacore, tmp_path.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from gdaschema.schema_validator import GDASchemaValidator

# ==============================================================================
# GROUP 1: IN-MEMORY INSTANCE VALIDATION
# Note: Verifies instance checking against Draft 2020-12 specifications
# ==============================================================================


@pytest.fixture
def sample_schema() -> Dict[str, Any]:
    """Provide minimal Draft 2020-12 schema specification."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["name", "age"],
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    }


@pytest.mark.unit
@pytest.mark.smoke
def test_validate_instance_returns_empty_list_on_valid(sample_schema: Dict[str, Any], tmp_path: Path) -> None:
    """Verify validate_instance returns an empty list for compliant payloads."""
    validator = GDASchemaValidator(schemas_dir=tmp_path)
    errors = validator.validate_instance({"name": "Glenn", "age": 42}, sample_schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.smoke
def test_validate_instance_captures_missing_required_property(
    sample_schema: Dict[str, Any], tmp_path: Path
) -> None:
    """Verify validate_instance reports missing required properties."""
    validator = GDASchemaValidator(schemas_dir=tmp_path)
    errors = validator.validate_instance({"name": "Glenn"}, sample_schema)
    assert len(errors) == 1
    assert "age" in errors[0]


@pytest.mark.unit
@pytest.mark.regression
def test_validate_instance_captures_type_mismatch(sample_schema: Dict[str, Any], tmp_path: Path) -> None:
    """Verify validate_instance flags property type mismatches."""
    validator = GDASchemaValidator(schemas_dir=tmp_path)
    errors = validator.validate_instance({"name": "Glenn", "age": "forty-two"}, sample_schema)
    assert len(errors) == 1
    assert "[age]" in errors[0]


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_returns_true_for_valid_payload(sample_schema: Dict[str, Any], tmp_path: Path) -> None:
    """Verify is_valid returns True for conforming instances."""
    validator = GDASchemaValidator(schemas_dir=tmp_path)
    assert validator.is_valid({"name": "Glenn", "age": 42}, sample_schema) is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_returns_false_for_invalid_payload(sample_schema: Dict[str, Any], tmp_path: Path) -> None:
    """Verify is_valid returns False when schema validation fails."""
    validator = GDASchemaValidator(schemas_dir=tmp_path)
    assert validator.is_valid({"name": 123}, sample_schema) is False


# ==============================================================================
# GROUP 2: LOCAL $REF RESOLUTION & DEFENSIVE REGISTRY INDEXING
# Note: Verifies registry initialization, directory edge cases, and in-memory refs
# ==============================================================================


@pytest.mark.unit
@pytest.mark.regression
def test_build_local_registry_handles_nonexistent_schemas_dir(tmp_path: Path) -> None:
    """Verify _build_local_registry handles non-existent schemas directory."""
    non_existent = tmp_path / "does_not_exist"
    validator = GDASchemaValidator(schemas_dir=non_existent)
    assert len(validator._registry) == 0


@pytest.mark.unit
@pytest.mark.regression
def test_build_local_registry_skips_directories_matching_json_pattern(tmp_path: Path) -> None:
    """Verify _build_local_registry skips directories named with .json extension."""
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    pseudo_dir = schemas_dir / "folder.json"
    pseudo_dir.mkdir(parents=True, exist_ok=True)

    validator = GDASchemaValidator(schemas_dir=schemas_dir)
    assert len(validator._registry) == 0


@pytest.mark.unit
@pytest.mark.regression
def test_build_local_registry_skips_non_dict_json(tmp_path: Path) -> None:
    """Verify _build_local_registry safely ignores json files containing arrays."""
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    array_file = schemas_dir / "array.json"
    array_file.write_text(json.dumps(["item1", "item2"]), encoding="utf-8")

    validator = GDASchemaValidator(schemas_dir=schemas_dir)
    assert validator.is_valid({"test": 1}, {"type": "object"}) is True


@pytest.mark.unit
@pytest.mark.regression
def test_build_local_registry_handles_schema_without_id(tmp_path: Path) -> None:
    """Verify _build_local_registry indexes schemas lacking an explicit $id property."""
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    no_id_file = schemas_dir / "no_id.schema.json"
    no_id_file.write_text(json.dumps({"type": "string"}), encoding="utf-8")

    validator = GDASchemaValidator(schemas_dir=schemas_dir)
    assert validator.is_valid("test", {"$ref": "no_id.schema.json"}) is True


@pytest.mark.unit
@pytest.mark.regression
def test_build_local_registry_handles_corrupt_json_file(tmp_path: Path) -> None:
    """Verify _build_local_registry logs debug and ignores unparseable json files."""
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    bad_file = schemas_dir / "corrupted.json"
    bad_file.write_text("{ unclosed syntax ...", encoding="utf-8")

    validator = GDASchemaValidator(schemas_dir=schemas_dir)
    assert validator.is_valid({"key": "val"}, {"type": "object"}) is True


@pytest.mark.unit
@pytest.mark.integrity
def test_local_ref_resolution_across_schemas(tmp_path: Path) -> None:
    """Verify referencing.Registry resolves local $ref to sibling definitions."""
    schemas_dir = tmp_path / "schemas"
    defs_dir = schemas_dir / "defs"
    defs_dir.mkdir(parents=True, exist_ok=True)

    shared_def = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://genealogy.archive/schemas/defs/_id_def.schema.json",
        "$defs": {
            "entity_id": {
                "type": "string",
                "pattern": "^IND-\\d{5}$",
            }
        },
    }
    (defs_dir / "_id_def.schema.json").write_text(json.dumps(shared_def), encoding="utf-8")

    parent_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["person_id"],
        "properties": {
            "person_id": {"$ref": "defs/_id_def.schema.json#/$defs/entity_id"},
        },
    }

    validator = GDASchemaValidator(schemas_dir=schemas_dir)
    assert validator.is_valid({"person_id": "IND-00042"}, parent_schema) is True
    assert validator.is_valid({"person_id": "INVALID-ID"}, parent_schema) is False


@pytest.mark.unit
@pytest.mark.smoke
def test_register_resource_in_memory_resolution(tmp_path: Path) -> None:
    """Verify register_resource permits dynamic in-memory $ref resolution."""
    validator = GDASchemaValidator(schemas_dir=tmp_path)
    custom_def = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {"code": {"type": "integer", "maximum": 999}},
    }
    validator.register_resource("urn:custom:codes", custom_def)

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "properties": {"val": {"$ref": "urn:custom:codes#/$defs/code"}},
    }
    assert validator.is_valid({"val": 500}, schema) is True
    assert validator.is_valid({"val": 1500}, schema) is False


# ==============================================================================
# GROUP 3: FILE VALIDATION ON DISK & CANDIDATE RESOLUTION
# Note: Verifies file loading, auto-resolution of $schema, and error paths
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_validate_file_explicit_schema(sample_schema: Dict[str, Any], tmp_path: Path) -> None:
    """Verify validate_file evaluates on-disk JSON file against supplied schema."""
    target_file = tmp_path / "record.json"
    target_file.write_text(json.dumps({"name": "Glenn", "age": 42}), encoding="utf-8")

    validator = GDASchemaValidator(schemas_dir=tmp_path)
    errors = validator.validate_file(target_file, schema=sample_schema)
    assert errors == []


@pytest.mark.unit
@pytest.mark.integrity
def test_validate_file_auto_resolves_schema_reference(tmp_path: Path) -> None:
    """Verify validate_file resolves schema automatically from $schema property."""
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    schema_file = schemas_dir / "item.schema.json"
    schema_def = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["item_id"],
        "properties": {"item_id": {"type": "string"}},
    }
    schema_file.write_text(json.dumps(schema_def), encoding="utf-8")

    data_file = tmp_path / "data.json"
    data_payload = {
        "$schema": "item.schema.json",
        "item_id": "ITM-01",
    }
    data_file.write_text(json.dumps(data_payload), encoding="utf-8")

    validator = GDASchemaValidator(schemas_dir=schemas_dir)
    errors = validator.validate_file(data_file)
    assert errors == []


@pytest.mark.unit
@pytest.mark.regression
def test_validate_file_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    """Verify validate_file raises FileNotFoundError for missing path."""
    validator = GDASchemaValidator(schemas_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="Target file for validation not found"):
        validator.validate_file(tmp_path / "non_existent.json")


@pytest.mark.unit
@pytest.mark.regression
def test_validate_file_invalid_json_raises_value_error(tmp_path: Path) -> None:
    """Verify validate_file raises ValueError when target file contains syntax errors."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ unclosed json ...", encoding="utf-8")

    validator = GDASchemaValidator(schemas_dir=tmp_path)
    with pytest.raises(ValueError, match="Failed to parse JSON file"):
        validator.validate_file(bad_file)


@pytest.mark.unit
@pytest.mark.regression
def test_validate_file_missing_schema_ref_raises_value_error(tmp_path: Path) -> None:
    """Verify validate_file raises ValueError when no schema is given or declared."""
    no_schema_file = tmp_path / "no_schema.json"
    no_schema_file.write_text(json.dumps({"title": "test"}), encoding="utf-8")

    validator = GDASchemaValidator(schemas_dir=tmp_path)
    with pytest.raises(ValueError, match="does not declare a '\\$schema' string"):
        validator.validate_file(no_schema_file)


@pytest.mark.unit
@pytest.mark.regression
def test_validate_file_unresolvable_schema_raises_value_error(tmp_path: Path) -> None:
    """Verify validate_file raises ValueError when referenced schema cannot be found."""
    orphan_file = tmp_path / "orphan.json"
    orphan_file.write_text(json.dumps({"$schema": "ghost.schema.json"}), encoding="utf-8")

    validator = GDASchemaValidator(schemas_dir=tmp_path)
    with pytest.raises(ValueError, match="Unable to resolve referenced schema"):
        validator.validate_file(orphan_file)


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_schema_from_ref_handles_corrupted_candidate_file(tmp_path: Path) -> None:
    """Verify _resolve_schema_from_ref skips candidate file when json load fails."""
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    corrupted_cand = schemas_dir / "target.schema.json"
    corrupted_cand.write_text("{ syntax error ...", encoding="utf-8")

    validator = GDASchemaValidator(schemas_dir=schemas_dir)
    resolved = validator._resolve_schema_from_ref("target.schema.json")
    assert resolved is None


# ==============================================================================
# GROUP 4: INTROSPECTION COMPLIANCE
# Note: Verifies IntrospectableMixin directory generation
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_validator_help_introspectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GDASchemaValidator inherits IntrospectableMixin and formats help output."""
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)

    GDASchemaValidator.help()
    output = captured.getvalue()
    assert "GDASchemaValidator" in output
    assert "validate_instance" in output
    assert "validate_file" in output