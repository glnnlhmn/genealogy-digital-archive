# Name: test_vocabulary_manager.py
# Path: tools/lib/gdacore/tests/test_vocabulary_manager.py
# Version: 1.0.0+build.rc1

"""Unit test suite verifying GDAVocabularyManager enum list retrieval, iteration, and metadata.

Operational Role:
    Validates that GDAVocabularyManager reliably returns token lists, exposes taxonomy
    schema metadata, supports dictionary-style iteration (items, keys, values, entries),
    subscripting, case-insensitive token resolution, attribute access, and class-level
    convenience access with 100% statement and branch coverage.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 assertion mapping per test function.
    - Fully decorated: Strictly marked with @pytest.mark.unit; sanity checks
      tagged with @pytest.mark.smoke; boundary cases with @pytest.mark.regression.
    - Dependencies: Isolated in-memory GDAVocabularyManager primitives.
"""

from __future__ import annotations

__version__ = "1.0.0+build.rc1"

import json
from pathlib import Path
import pytest

from gdacore.vocabulary_manager import (
    CONTROLLED_VOCABULARIES,
    GDASchemaEnums,
    GDAVocabularyEntry,
    GDAVocabularyManager,
    SchemaEnums,
    TAXONOMY_REGISTRY,
)


@pytest.fixture(autouse=True)
def reset_vocab_manager_cache() -> None:
    """Ensure custom schema overrides and caches are cleanly reset before each test."""
    GDAVocabularyManager.reset_cache()
    yield
    GDAVocabularyManager.reset_cache()


# ==============================================================================
# GROUP 1: Dataclass and Typed Metadata Container Primitives
# Note: Verification of GDAVocabularyEntry serialization and structural invariants
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_vocabulary_entry_to_dict_contract() -> None:
    """Verify GDAVocabularyEntry produces expected metadata dictionary contract."""
    entry = GDAVocabularyEntry(
        name="test_color",
        tokens=("Red", "Blue"),
        description="Color palette",
        nullable=True,
        default="Red",
    )
    expected = {
        "description": "Color palette",
        "nullable": True,
        "default": "Red",
        "tokens": ["Red", "Blue"],
    }
    assert entry.to_dict() == expected


# ==============================================================================
# GROUP 2: Basic List and Subscript Retrieval
# Note: Verification of get_list, subscript access, and enum_ prefix normalization
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_get_list_returns_associated_list() -> None:
    """Verify get_list returns the expected list for a known enum type."""
    mgr = GDAVocabularyManager()
    assert mgr.get_list("fact_type") == CONTROLLED_VOCABULARIES["fact_type"]


@pytest.mark.unit
@pytest.mark.smoke
def test_get_list_supports_enum_prefix() -> None:
    """Verify get_list strips 'enum_' prefix if present."""
    mgr = GDAVocabularyManager()
    assert mgr.get_list("enum_date_modifier") == CONTROLLED_VOCABULARIES["date_modifier"]


@pytest.mark.unit
@pytest.mark.smoke
def test_getitem_subscription_returns_list() -> None:
    """Verify subscript syntax mgr[enum_type] returns the expected list."""
    mgr = GDAVocabularyManager()
    assert mgr["associated_role"] == CONTROLLED_VOCABULARIES["associated_role"]


@pytest.mark.unit
@pytest.mark.regression
def test_get_list_unknown_key_raises_keyerror() -> None:
    """Verify requesting an unknown enum type raises KeyError."""
    mgr = GDAVocabularyManager()
    with pytest.raises(KeyError, match="Unknown enum type"):
        _ = mgr.get_list("non_existent_type")


# ==============================================================================
# GROUP 3: Collection and Mapping Protocol Operations
# Note: Verification of len, iter, items, keys, values, and entries
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_manager_len_matches_taxonomy_registry() -> None:
    """Verify len(mgr) returns the count of registered taxonomies."""
    mgr = GDAVocabularyManager()
    assert len(mgr) == len(TAXONOMY_REGISTRY)


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_iteration_yields_all_keys() -> None:
    """Verify iterating over mgr yields all registered vocabulary names."""
    mgr = GDAVocabularyManager()
    assert list(mgr) == list(TAXONOMY_REGISTRY.keys())


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_items_yields_expected_tuples() -> None:
    """Verify mgr.items() yields (name, tokens) pairs matching source data."""
    mgr = GDAVocabularyManager()
    assert dict(mgr.items()) == CONTROLLED_VOCABULARIES


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_keys_yields_all_registered_keys() -> None:
    """Verify mgr.keys() yields all registered vocabulary names."""
    mgr = GDAVocabularyManager()
    assert list(mgr.keys()) == list(TAXONOMY_REGISTRY.keys())


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_values_yields_all_registered_lists() -> None:
    """Verify mgr.values() yields list of tokens matching source values."""
    mgr = GDAVocabularyManager()
    assert list(mgr.values()) == list(CONTROLLED_VOCABULARIES.values())


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_entries_yields_full_metadata() -> None:
    """Verify mgr.entries() yields (name, metadata) pairs matching TAXONOMY_REGISTRY."""
    mgr = GDAVocabularyManager()
    assert dict(mgr.entries()) == TAXONOMY_REGISTRY


# ==============================================================================
# GROUP 4: Metadata and Entry Retrieval
# Note: Verification of get_metadata and get_entry handlers
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_get_metadata_returns_entry_dict() -> None:
    """Verify get_metadata returns the metadata dictionary for a known enum."""
    mgr = GDAVocabularyManager()
    assert mgr.get_metadata("fact_type") == TAXONOMY_REGISTRY["fact_type"]


@pytest.mark.unit
@pytest.mark.smoke
def test_get_metadata_supports_enum_prefix() -> None:
    """Verify get_metadata strips 'enum_' prefix if present."""
    mgr = GDAVocabularyManager()
    assert mgr.get_metadata("enum_sex") == TAXONOMY_REGISTRY["sex"]


@pytest.mark.unit
@pytest.mark.regression
def test_get_metadata_unknown_key_raises_keyerror() -> None:
    """Verify requesting metadata for an unknown enum type raises KeyError."""
    mgr = GDAVocabularyManager()
    with pytest.raises(KeyError, match="Unknown enum type"):
        _ = mgr.get_metadata("unknown_type")


@pytest.mark.unit
@pytest.mark.smoke
def test_get_entry_returns_typed_dataclass() -> None:
    """Verify get_entry returns typed GDAVocabularyEntry dataclass."""
    mgr = GDAVocabularyManager()
    entry = mgr.get_entry("fact_type")
    assert isinstance(entry, GDAVocabularyEntry)
    assert entry.name == "fact_type"


@pytest.mark.unit
@pytest.mark.regression
def test_get_entry_unknown_key_raises_keyerror() -> None:
    """Verify requesting entry for unknown enum type raises KeyError."""
    mgr = GDAVocabularyManager()
    with pytest.raises(KeyError, match="Unknown enum type"):
        _ = mgr.get_entry("unknown_type")


# ==============================================================================
# GROUP 5: Membership Testing and Attribute Access
# Note: Verification of in operator, attribute lookup, and dynamic getattr
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_manager_contains_registered_key() -> None:
    """Verify 'in mgr' returns True for a registered vocabulary name."""
    mgr = GDAVocabularyManager()
    assert ("fact_type" in mgr) is True


@pytest.mark.unit
@pytest.mark.smoke
def test_manager_contains_with_enum_prefix() -> None:
    """Verify 'in mgr' returns True when prefixed with 'enum_'."""
    mgr = GDAVocabularyManager()
    assert ("enum_fact_type" in mgr) is True


@pytest.mark.unit
@pytest.mark.regression
def test_manager_contains_missing_key() -> None:
    """Verify 'in mgr' returns False for an unregistered vocabulary name."""
    mgr = GDAVocabularyManager()
    assert ("unknown_taxonomy" in mgr) is False


@pytest.mark.unit
@pytest.mark.regression
def test_manager_contains_non_string_returns_false() -> None:
    """Verify 'in mgr' returns False when queried with non-string key."""
    mgr = GDAVocabularyManager()
    assert (12345 in mgr) is False  # type: ignore[operator]


@pytest.mark.unit
@pytest.mark.smoke
def test_attribute_access_returns_list() -> None:
    """Verify direct attribute access mgr.sex returns the token list."""
    mgr = GDAVocabularyManager()
    assert mgr.sex == ["Male", "Female", "Unknown"]


@pytest.mark.unit
@pytest.mark.smoke
def test_marital_status_attribute_access() -> None:
    """Verify direct attribute access mgr.marital_status returns the token list."""
    mgr = GDAVocabularyManager()
    assert mgr.marital_status == ["Single", "Married", "Widowed", "Divorced", "Unknown"]


@pytest.mark.unit
@pytest.mark.regression
def test_attribute_access_unknown_raises_attribute_error() -> None:
    """Verify accessing an unknown vocabulary as attribute raises AttributeError."""
    mgr = GDAVocabularyManager()
    with pytest.raises(AttributeError, match="has no attribute or vocabulary"):
        _ = mgr.non_existent_vocab


# ==============================================================================
# GROUP 6: Set Retrieval and Token Validation
# Note: Verification of get_set, is_valid, and case-insensitive resolve_token
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_get_set_returns_set() -> None:
    """Verify get_set returns a set equivalent to the defined tokens."""
    mgr = GDAVocabularyManager()
    assert mgr.get_set("sex") == {"Male", "Female", "Unknown"}


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_accepts_valid_token() -> None:
    """Verify is_valid returns True for a valid member."""
    mgr = GDAVocabularyManager()
    assert mgr.is_valid("fact_type", "Birth") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_rejects_invalid_token() -> None:
    """Verify is_valid returns False for an invalid member."""
    mgr = GDAVocabularyManager()
    assert mgr.is_valid("fact_type", "InvalidToken") is False


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_rejects_none_for_sex() -> None:
    """Verify is_valid returns False for None when checking sex."""
    mgr = GDAVocabularyManager()
    assert mgr.is_valid("sex", None) is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_rejects_unknown_enum() -> None:
    """Verify is_valid returns False for an unknown enum type."""
    mgr = GDAVocabularyManager()
    assert mgr.is_valid("unknown_enum", "value") is False


@pytest.mark.unit
@pytest.mark.smoke
def test_resolve_token_successful_case_normalization() -> None:
    """Verify resolve_token resolves case variations to canonical token."""
    mgr = GDAVocabularyManager()
    assert mgr.resolve_token("sex", "  female  ") == "Female"
    assert mgr.resolve_token("fact_type", "death") == "Death"


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_token_invalid_returns_none() -> None:
    """Verify resolve_token returns None for unlisted tokens."""
    mgr = GDAVocabularyManager()
    assert mgr.resolve_token("sex", "Alien") is None


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_token_empty_or_none_returns_none() -> None:
    """Verify resolve_token returns None for empty, whitespace, or non-string inputs."""
    mgr = GDAVocabularyManager()
    assert mgr.resolve_token("sex", "") is None
    assert mgr.resolve_token("sex", "   ") is None
    assert mgr.resolve_token("sex", None) is None
    assert mgr.resolve_token("non_existent", "value") is None


# ==============================================================================
# GROUP 7: Class-Level Dual Access & Convenience Getters
# Note: Verification of static subscription and convenience domain helpers
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_class_level_subscription_and_length() -> None:
    """Verify GDAVocabularyManager class directly supports subscription, iter, and len."""
    assert GDAVocabularyManager["fact_type"] == CONTROLLED_VOCABULARIES["fact_type"]
    assert len(GDAVocabularyManager) == len(TAXONOMY_REGISTRY)
    assert "fact_type" in GDAVocabularyManager
    assert (999 in GDAVocabularyManager) is False  # type: ignore[operator]
    assert list(iter(GDAVocabularyManager)) == list(TAXONOMY_REGISTRY.keys())


@pytest.mark.unit
@pytest.mark.smoke
def test_class_level_convenience_domain_getters() -> None:
    """Verify class-level convenience getters return canonical tokens."""
    assert "Birth" in GDAVocabularyManager.get_fact_types()
    assert "ACTIVE" in GDAVocabularyManager.get_operational_statuses()
    assert "1-A" in GDAVocabularyManager.get_selective_service_classes()
    assert "FRONT" in GDAVocabularyManager.get_document_sides()
    assert "FATH" in GDAVocabularyManager.get_kinship_roles()
    assert "MARRIED" in GDAVocabularyManager.get_union_statuses()


@pytest.mark.unit
@pytest.mark.smoke
def test_class_level_get_allowed() -> None:
    """Verify class-level get_allowed returns set of permitted tokens."""
    assert GDAVocabularyManager.get_allowed("union_status") == set(CONTROLLED_VOCABULARIES["union_status"])


@pytest.mark.unit
@pytest.mark.regression
def test_class_level_get_allowed_unknown_raises_keyerror() -> None:
    """Verify class-level get_allowed raises KeyError for unknown category."""
    with pytest.raises(KeyError, match="Unknown enum type"):
        GDAVocabularyManager.get_allowed("non_existent")


# ==============================================================================
# GROUP 8: Custom Registry and External Schema Path Overrides
# Note: Verification of isolated injection and custom schema loading
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_custom_registry_injection() -> None:
    """Verify custom registry can be supplied for isolated instance testing."""
    custom = {
        "colors": {
            "description": "Base primary colors",
            "nullable": False,
            "default": "Red",
            "tokens": ["Red", "Green", "Blue"],
        }
    }
    mgr = GDAVocabularyManager(registry=custom)
    assert mgr.get_list("colors") == ["Red", "Green", "Blue"]
    assert mgr.get_set("colors") == {"Red", "Green", "Blue"}
    assert mgr.get_metadata("colors")["default"] == "Red"
    assert mgr.get_entry("colors").name == "colors"
    assert mgr.is_valid("colors", "Red") is True
    assert mgr.resolve_token("colors", "blue") == "Blue"


@pytest.mark.unit
@pytest.mark.smoke
def test_set_custom_schema_path_loads_definitions(tmp_path: Path) -> None:
    """Verify set_custom_schema_path dynamically loads external JSON schema."""
    schema_file = tmp_path / "custom_enums.json"
    schema_data = {
        "$defs": {
            "custom_tier": {
                "description": "Tier ranking",
                "enum": ["Gold", "Silver", "Bronze"],
            },
            "non_enum_def": {
                "type": "string",
            },
            "scalar_def": 12345,
        }
    }
    schema_file.write_text(json.dumps(schema_data), encoding="utf-8")
    GDAVocabularyManager.set_custom_schema_path(schema_file)
    assert GDAVocabularyManager.get_allowed("custom_tier") == {"Gold", "Silver", "Bronze"}


@pytest.mark.unit
@pytest.mark.regression
def test_set_custom_schema_path_non_dict_defs_handled(tmp_path: Path) -> None:
    """Verify set_custom_schema_path handles schemas where definitions is not a dictionary."""
    schema_file = tmp_path / "non_dict_defs.json"
    schema_file.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    GDAVocabularyManager.set_custom_schema_path(schema_file)
    assert len(GDAVocabularyManager.get_names()) == 0


@pytest.mark.unit
@pytest.mark.regression
def test_set_custom_schema_path_missing_file_raises(tmp_path: Path) -> None:
    """Verify set_custom_schema_path raises FileNotFoundError for missing path."""
    with pytest.raises(FileNotFoundError, match="Custom schema file does not exist"):
        GDAVocabularyManager.set_custom_schema_path(tmp_path / "missing.json")


@pytest.mark.unit
@pytest.mark.smoke
def test_clear_cache_restores_default_registry(tmp_path: Path) -> None:
    """Verify clear_cache restores default definitions after custom injection."""
    schema_file = tmp_path / "custom_temp.json"
    schema_file.write_text(json.dumps({"temp": {"enum": ["A"]}}), encoding="utf-8")
    GDAVocabularyManager.set_custom_schema_path(schema_file)
    GDAVocabularyManager.clear_cache()
    assert "fact_type" in GDAVocabularyManager


# ==============================================================================
# GROUP 9: Backward Compatibility Aliases and Introspection
# Note: Verification of SchemaEnums alias identity and help introspection
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_backward_compatibility_alias_gda_schema_enums() -> None:
    """Verify GDASchemaEnums alias points to GDAVocabularyManager."""
    assert GDASchemaEnums is GDAVocabularyManager


@pytest.mark.unit
@pytest.mark.smoke
def test_backward_compatibility_alias_schema_enums() -> None:
    """Verify SchemaEnums alias points to GDAVocabularyManager."""
    assert SchemaEnums is GDAVocabularyManager


@pytest.mark.unit
@pytest.mark.smoke
def test_vocabulary_manager_introspectable_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify GDAVocabularyManager inherits IntrospectableMixin and renders directory help."""
    GDAVocabularyManager.help()
    captured = capsys.readouterr().out
    assert "=== GDAVocabularyManager Public Directory ===" in captured