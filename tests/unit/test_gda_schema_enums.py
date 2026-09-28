# Name: test_gda_schema_enums.py
# Path: tests/unit/test_gda_schema_enums.py
# Version: 1.0.2+build.20260927.1

"""Consolidated unit test suite for GDASchemaEnums controlled vocabulary registry.

Operational Role:
    Verifies primary enum resolution, schema fallback lookup cascades,
    cross-population, malformed JSON recovery, warm cache short-circuiting,
    and non-enum schema filtering under GDASchemaEnums (SchemaEnums).

Test Structure & Protocol:
    - Atomized tests: 1:1 mapping of single assertions per test function.
    - Fully decorated: Decorated with @pytest.mark.unit.
    - Dependencies: tmp_path and monkeypatch for hermetic filesystem sandboxing.
"""

import json
from pathlib import Path
from unittest.mock import PropertyMock
import pytest

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDASchemaEnums import SchemaEnums


@pytest.fixture(autouse=True)
def clean_enum_cache():
    """Ensures each test starts and ends with an empty in-memory enum cache."""
    SchemaEnums.reset_cache()
    yield
    SchemaEnums.reset_cache()


# =============================================================================
# Production Vocabulary & Lookup Invariants
# =============================================================================

@pytest.mark.unit
def test_enum_fact_type_lookup_returns_list():
    """Ensures looking up enum_fact_type returns a list."""
    assert isinstance(SchemaEnums["enum_fact_type"], list)


@pytest.mark.unit
def test_enum_fact_type_contains_census():
    """Ensures standard fact types include 'Census'."""
    assert "Census" in SchemaEnums["enum_fact_type"]


@pytest.mark.unit
def test_enum_fact_type_contains_birth():
    """Ensures standard fact types include 'Birth'."""
    assert "Birth" in SchemaEnums["enum_fact_type"]


@pytest.mark.unit
def test_enum_sex_contains_male():
    """Ensures biological sex controlled vocabulary contains 'Male'."""
    assert "Male" in SchemaEnums["enum_sex"]


@pytest.mark.unit
def test_enum_sex_contains_unknown():
    """Ensures biological sex controlled vocabulary contains 'Unknown'."""
    assert "Unknown" in SchemaEnums["enum_sex"]


@pytest.mark.unit
def test_subscription_missing_enum_raises_keyerror():
    """Ensures querying an unmapped vocabulary raises KeyError."""
    with pytest.raises(KeyError, match="Enum 'nonexistent_enum' not found"):
        _ = SchemaEnums["nonexistent_enum"]


# =============================================================================
# Validation Helper Tests (is_valid & get_allowed)
# =============================================================================

@pytest.mark.unit
def test_is_valid_returns_true_for_valid_value():
    """Ensures is_valid returns True when value is permitted by the enum."""
    assert SchemaEnums.is_valid("enum_sex", "Male") is True


@pytest.mark.unit
def test_is_valid_returns_true_for_none():
    """Ensures is_valid permits None by default across all enums."""
    assert SchemaEnums.is_valid("enum_sex", None) is True


@pytest.mark.unit
def test_is_valid_returns_false_for_invalid_value():
    """Ensures is_valid returns False when value violates enum constraints."""
    assert SchemaEnums.is_valid("enum_sex", "M") is False


@pytest.mark.unit
def test_is_valid_returns_true_for_unmapped_enum():
    """Ensures is_valid defaults to True when the enum key is unmapped in schema."""
    assert SchemaEnums.is_valid("unmapped_arbitrary_enum", "AnyValue") is True


@pytest.mark.unit
def test_get_allowed_returns_set_for_existing_enum():
    """Ensures get_allowed returns a set containing permitted entries."""
    allowed = SchemaEnums.get_allowed("enum_sex")
    assert isinstance(allowed, set)


@pytest.mark.unit
def test_get_allowed_contains_female():
    """Ensures get_allowed set contains valid member."""
    assert "Female" in SchemaEnums.get_allowed("enum_sex")


@pytest.mark.unit
def test_get_allowed_returns_empty_set_for_unmapped_enum():
    """Ensures get_allowed returns empty set for unmapped enum."""
    assert SchemaEnums.get_allowed("unmapped_arbitrary_enum") == set()


# =============================================================================
# Cache Mechanics & Schema Traversal
# =============================================================================

@pytest.mark.unit
def test_cache_hit_skips_reload(monkeypatch):
    """Ensures consecutive calls leverage warm cache without re-parsing files."""
    _ = SchemaEnums["enum_sex"]
    
    # Poison CONFIG.enums; if re-parsed it would raise AttributeError
    monkeypatch.setattr(type(CONFIG), "enums", None)
    
    # Must retrieve successfully from warm in-memory cache (line 20)
    assert "Male" in SchemaEnums["enum_sex"]


@pytest.mark.unit
def test_non_enum_defs_are_safely_ignored(tmp_path, monkeypatch):
    """Ensures non-dict or non-enum items in $defs are skipped (branch 45->44)."""
    schema_dir = tmp_path / "schemas" / "defs"
    schema_dir.mkdir(parents=True)
    sample_file = schema_dir / "mixed_defs.json"
    sample_payload = {
        "$defs": {
            "valid_enum": {"type": "string", "enum": ["ACTIVE"]},
            "non_enum_def": {"type": "string", "description": "No enum list"},
            "scalar_def": "unexpected_string_definition"
        }
    }
    sample_file.write_text(json.dumps(sample_payload), encoding="utf-8")

    monkeypatch.setattr(type(CONFIG), "enums", PropertyMock(return_value=sample_file))
    monkeypatch.setattr(type(CONFIG), "schema_defs", PropertyMock(return_value=schema_dir))

    assert SchemaEnums["valid_enum"] == ["ACTIVE"]


# =============================================================================
# Fallback Resolution Cascades & Error Recovery (Lines 26–36, 56–64)
# =============================================================================

@pytest.mark.unit
def test_fallback_to_enums_schema_json(tmp_path, monkeypatch):
    """Ensures registry falls back to enums.schema.json if CONFIG.enums is missing."""
    schema_dir = tmp_path / "schemas" / "defs"
    schema_dir.mkdir(parents=True)
    fallback_file = schema_dir / "enums.schema.json"
    fallback_payload = {
        "$defs": {
            "enum_fallback_test": {"enum": ["ALPHA", "BETA"]}
        }
    }
    fallback_file.write_text(json.dumps(fallback_payload), encoding="utf-8")

    monkeypatch.setattr(type(CONFIG), "enums", PropertyMock(return_value=schema_dir / "missing.json"))
    monkeypatch.setattr(type(CONFIG), "schema_defs", PropertyMock(return_value=schema_dir))

    assert SchemaEnums["enum_fallback_test"] == ["ALPHA", "BETA"]


@pytest.mark.unit
def test_fallback_to_shared_defs_schema_json(tmp_path, monkeypatch):
    """Ensures registry falls back to _shared_defs.schema.json if prior candidates missing."""
    schema_dir = tmp_path / "schemas" / "defs"
    schema_dir.mkdir(parents=True)
    shared_file = schema_dir / "_shared_defs.schema.json"
    shared_payload = {
        "$defs": {
            "enum_shared_only": {"enum": ["GAMMA", "DELTA"]}
        }
    }
    shared_file.write_text(json.dumps(shared_payload), encoding="utf-8")

    monkeypatch.setattr(type(CONFIG), "enums", PropertyMock(return_value=schema_dir / "missing.json"))
    monkeypatch.setattr(type(CONFIG), "schema_defs", PropertyMock(return_value=schema_dir))

    assert SchemaEnums["enum_shared_only"] == ["GAMMA", "DELTA"]


@pytest.mark.unit
def test_no_candidate_files_exist_initializes_empty_cache(tmp_path, monkeypatch):
    """Ensures registry safely defaults to empty caches if no schema files exist."""
    schema_dir = tmp_path / "empty_schemas"
    schema_dir.mkdir(parents=True)

    monkeypatch.setattr(type(CONFIG), "enums", PropertyMock(return_value=schema_dir / "missing.json"))
    monkeypatch.setattr(type(CONFIG), "schema_defs", PropertyMock(return_value=schema_dir))

    with pytest.raises(KeyError):
        _ = SchemaEnums["enum_any"]


@pytest.mark.unit
def test_cross_population_from_shared_defs(tmp_path, monkeypatch):
    """Ensures non-overlapping enums in _shared_defs are cross-populated."""
    schema_dir = tmp_path / "schemas" / "defs"
    schema_dir.mkdir(parents=True)

    primary_file = schema_dir / "primary.json"
    primary_file.write_text(json.dumps({
        "$defs": {
            "enum_primary": {"enum": ["VAL1"]}
        }
    }), encoding="utf-8")

    shared_file = schema_dir / "_shared_defs.schema.json"
    shared_file.write_text(json.dumps({
        "$defs": {
            "enum_primary": {"enum": ["OVERWRITE_ATTEMPT"]},
            "enum_shared": {"enum": ["VAL2"]}
        }
    }), encoding="utf-8")

    monkeypatch.setattr(type(CONFIG), "enums", PropertyMock(return_value=primary_file))
    monkeypatch.setattr(type(CONFIG), "schema_defs", PropertyMock(return_value=schema_dir))

    assert SchemaEnums["enum_shared"] == ["VAL2"]


@pytest.mark.unit
def test_cross_population_does_not_overwrite_primary_enum(tmp_path, monkeypatch):
    """Ensures cross-population never overwrites an existing primary enum."""
    schema_dir = tmp_path / "schemas" / "defs"
    schema_dir.mkdir(parents=True)

    primary_file = schema_dir / "primary.json"
    primary_file.write_text(json.dumps({
        "$defs": {
            "enum_conflict": {"enum": ["ORIGINAL"]}
        }
    }), encoding="utf-8")

    shared_file = schema_dir / "_shared_defs.schema.json"
    shared_file.write_text(json.dumps({
        "$defs": {
            "enum_conflict": {"enum": ["COLLISION"]}
        }
    }), encoding="utf-8")

    monkeypatch.setattr(type(CONFIG), "enums", PropertyMock(return_value=primary_file))
    monkeypatch.setattr(type(CONFIG), "schema_defs", PropertyMock(return_value=schema_dir))

    assert SchemaEnums["enum_conflict"] == ["ORIGINAL"]


@pytest.mark.unit
def test_malformed_json_resets_to_empty_cache(tmp_path, monkeypatch):
    """Ensures malformed JSON in schema file safely falls back to empty cache."""
    schema_dir = tmp_path / "corrupt_schema"
    schema_dir.mkdir(parents=True)
    corrupt_file = schema_dir / "corrupt.json"
    corrupt_file.write_text("{ unquoted_broken_json : 123", encoding="utf-8")

    monkeypatch.setattr(type(CONFIG), "enums", PropertyMock(return_value=corrupt_file))
    monkeypatch.setattr(type(CONFIG), "schema_defs", PropertyMock(return_value=schema_dir))

    with pytest.raises(KeyError):
        _ = SchemaEnums["any_enum"]