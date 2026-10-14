# Name: test_reference_manager.py
# Path: tools/lib/gdacore/tests/test_reference_manager.py
# Version: 1.0.0+build.rc1

"""Unit test harness verifying GDAReferenceManager entity identifier and table resolution.

Operational Role:
    Validates person/site/location/source/note/fact identifier pattern matching,
    unified is_valid_gda_id dispatching, prefix extraction, static reference table
    loading, in-memory caching, colloquial state resolution, Option A bridge sets,
    error handling, and runtime introspection.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly marked with @pytest.mark.unit; sanity checks
      tagged with @pytest.mark.smoke; boundary cases with @pytest.mark.regression.
    - Dependencies: Isolated hermetic tmp_path sandboxes.
"""

from __future__ import annotations

__version__ = "1.0.0+build.rc1"

import json
from pathlib import Path
from typing import Any
import pytest

from gdacore import config
from gdacore.config import GDAConfig
from gdacore.reference_manager import GDAReferenceManager


@pytest.fixture(autouse=True)
def reset_reference_cache() -> None:
    """Ensure in-memory cache on GDAReferenceManager is cleanly reset before each test."""
    GDAReferenceManager.clear_cache()
    yield
    GDAReferenceManager.clear_cache()


@pytest.fixture
def mock_reference_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Configure a hermetic GDAConfig with an isolated data/reference directory."""
    sandbox_config = GDAConfig(root=tmp_path.resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)
    ref_dir = sandbox_config.data / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    return ref_dir


# ==============================================================================
# GROUP 1: Prefix Extraction and Registry Inventory
# Note: Verification of prefix sets and token isolation
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_get_all_valid_id_prefixes_contains_canonical() -> None:
    """Verify get_all_valid_id_prefixes contains exactly IND, SID, LOC, SRC, NOT."""
    expected = {"IND", "SID", "LOC", "SRC", "NOT"}
    assert GDAReferenceManager.get_all_valid_id_prefixes() == expected


@pytest.mark.unit
@pytest.mark.regression
def test_get_all_valid_id_prefixes_returns_independent_copy() -> None:
    """Verify mutating returned set from get_all_valid_id_prefixes does not alter constant."""
    prefixes = GDAReferenceManager.get_all_valid_id_prefixes()
    prefixes.add("MUTATION")
    assert "MUTATION" not in GDAReferenceManager.get_all_valid_id_prefixes()


@pytest.mark.unit
@pytest.mark.smoke
def test_extract_id_prefix_valid_person() -> None:
    """Verify extract_id_prefix returns uppercase IND for person IDs."""
    assert GDAReferenceManager.extract_id_prefix("IND-00042") == "IND"


@pytest.mark.unit
@pytest.mark.smoke
def test_extract_id_prefix_valid_site() -> None:
    """Verify extract_id_prefix returns uppercase SID for site IDs."""
    assert GDAReferenceManager.extract_id_prefix("SID-00001") == "SID"


@pytest.mark.unit
@pytest.mark.smoke
def test_extract_id_prefix_lowercase_input() -> None:
    """Verify extract_id_prefix normalizes lowercase prefix to uppercase."""
    assert GDAReferenceManager.extract_id_prefix("loc-00005") == "LOC"


@pytest.mark.unit
@pytest.mark.regression
def test_extract_id_prefix_no_hyphen_returns_none() -> None:
    """Verify extract_id_prefix returns None for non-hyphenated strings."""
    assert GDAReferenceManager.extract_id_prefix("INVALID") is None


@pytest.mark.unit
@pytest.mark.regression
def test_extract_id_prefix_leading_hyphen_returns_none() -> None:
    """Verify extract_id_prefix returns None when prefix segment is empty."""
    assert GDAReferenceManager.extract_id_prefix("-00001") is None


@pytest.mark.unit
@pytest.mark.regression
def test_extract_id_prefix_empty_string_returns_none() -> None:
    """Verify extract_id_prefix returns None for empty string."""
    assert GDAReferenceManager.extract_id_prefix("") is None


@pytest.mark.unit
@pytest.mark.regression
def test_extract_id_prefix_non_string_returns_none() -> None:
    """Verify extract_id_prefix returns None for non-string input."""
    assert GDAReferenceManager.extract_id_prefix(None) is None  # type: ignore[arg-type]


# ==============================================================================
# GROUP 2: Person Identifier Validation Tests
# Note: Verification of IND-XXXXX pattern syntax
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_person_id_valid() -> None:
    """Verify is_valid_person_id returns True for standard IND-XXXXX identifiers."""
    assert GDAReferenceManager.is_valid_person_id("IND-00042") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_person_id_invalid_numeric_length() -> None:
    """Verify is_valid_person_id returns False for non-five-digit numbers."""
    assert GDAReferenceManager.is_valid_person_id("IND-42") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_person_id_invalid_prefix() -> None:
    """Verify is_valid_person_id returns False for non-IND prefix."""
    assert GDAReferenceManager.is_valid_person_id("PERSON-00001") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_person_id_empty_string() -> None:
    """Verify is_valid_person_id returns False for empty string."""
    assert GDAReferenceManager.is_valid_person_id("") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_person_id_non_string() -> None:
    """Verify is_valid_person_id returns False for non-string types."""
    assert GDAReferenceManager.is_valid_person_id(None) is False  # type: ignore[arg-type]


# ==============================================================================
# GROUP 3: Site Identifier Validation Tests
# Note: Verification of SID-XXXXX pattern syntax and SITE-XXXXX legacy support
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_site_id_format_valid_sid() -> None:
    """Verify is_valid_site_id_format returns True for standard SID-XXXXX identifiers."""
    assert GDAReferenceManager.is_valid_site_id_format("SID-00001") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_site_id_format_legacy_site() -> None:
    """Verify is_valid_site_id_format returns True for legacy SITE-XXXXX identifiers."""
    assert GDAReferenceManager.is_valid_site_id_format("SITE-00001") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_site_id_format_boundary_high() -> None:
    """Verify is_valid_site_id_format returns True for highest five-digit values."""
    assert GDAReferenceManager.is_valid_site_id_format("SID-99999") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_site_id_format_with_whitespace() -> None:
    """Verify is_valid_site_id_format strips whitespace correctly."""
    assert GDAReferenceManager.is_valid_site_id_format("  SID-00100  ") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_site_id_format_invalid_short_digits() -> None:
    """Verify is_valid_site_id_format returns False for four digits."""
    assert GDAReferenceManager.is_valid_site_id_format("SID-0001") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_site_id_format_invalid_long_digits() -> None:
    """Verify is_valid_site_id_format returns False for six digits."""
    assert GDAReferenceManager.is_valid_site_id_format("SID-000001") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_site_id_format_invalid_prefix() -> None:
    """Verify is_valid_site_id_format returns False for non-site prefix."""
    assert GDAReferenceManager.is_valid_site_id_format("IND-00001") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_site_id_format_lowercase_prefix() -> None:
    """Verify is_valid_site_id_format returns False for lowercase prefix."""
    assert GDAReferenceManager.is_valid_site_id_format("sid-00001") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_site_id_format_empty_string() -> None:
    """Verify is_valid_site_id_format returns False for empty string."""
    assert GDAReferenceManager.is_valid_site_id_format("") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_site_id_format_none_value() -> None:
    """Verify is_valid_site_id_format returns False for None input."""
    assert GDAReferenceManager.is_valid_site_id_format(None) is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_site_id_format_non_string() -> None:
    """Verify is_valid_site_id_format returns False for non-string types."""
    assert GDAReferenceManager.is_valid_site_id_format(12345) is False  # type: ignore[arg-type]


# ==============================================================================
# GROUP 4: Location, Source, and Note Identifier Validation Tests
# Note: Verification of LOC-XXXXX, SRC-XXXXX, and NOT-XXXXX pattern syntax
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_location_id_format_valid() -> None:
    """Verify is_valid_location_id_format returns True for standard LOC-XXXXX identifiers."""
    assert GDAReferenceManager.is_valid_location_id_format("LOC-00042") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_location_id_format_invalid_short() -> None:
    """Verify is_valid_location_id_format returns False for four digits."""
    assert GDAReferenceManager.is_valid_location_id_format("LOC-0042") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_location_id_format_empty_string() -> None:
    """Verify is_valid_location_id_format returns False for empty string."""
    assert GDAReferenceManager.is_valid_location_id_format("") is False


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_source_id_valid() -> None:
    """Verify is_valid_source_id returns True for standard SRC-XXXXX identifiers."""
    assert GDAReferenceManager.is_valid_source_id("SRC-00100") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_source_id_invalid_prefix() -> None:
    """Verify is_valid_source_id returns False for non-SRC prefix."""
    assert GDAReferenceManager.is_valid_source_id("SOURCE-00100") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_source_id_empty_or_none() -> None:
    """Verify is_valid_source_id returns False for empty string or None."""
    assert GDAReferenceManager.is_valid_source_id("") is False
    assert GDAReferenceManager.is_valid_source_id(None) is False  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_note_id_valid() -> None:
    """Verify is_valid_note_id returns True for standard NOT-XXXXX identifiers."""
    assert GDAReferenceManager.is_valid_note_id("NOT-00001") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_note_id_invalid_prefix() -> None:
    """Verify is_valid_note_id returns False for non-NOT prefix."""
    assert GDAReferenceManager.is_valid_note_id("NOTE-00001") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_note_id_empty_or_none() -> None:
    """Verify is_valid_note_id returns False for empty string or None."""
    assert GDAReferenceManager.is_valid_note_id("") is False
    assert GDAReferenceManager.is_valid_note_id(None) is False  # type: ignore[arg-type]


# ==============================================================================
# GROUP 5: Fact and GUID Identifier Validation Tests
# Note: Verification of 36-char lowercase UUIDv4 matching
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_guid_valid() -> None:
    """Verify is_valid_guid returns True for valid UUIDv4 strings."""
    assert GDAReferenceManager.is_valid_guid("c3b5d278-8314-4eb9-a035-7cf008e73be5") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_guid_uppercase_normalized() -> None:
    """Verify is_valid_guid accepts uppercase UUID strings via case insensitivity."""
    assert GDAReferenceManager.is_valid_guid("C3B5D278-8314-4EB9-A035-7CF008E73BE5") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_fact_id_delegates_to_guid() -> None:
    """Verify is_valid_fact_id returns True for valid UUIDv4 strings."""
    assert GDAReferenceManager.is_valid_fact_id("c3b5d278-8314-4eb9-a035-7cf008e73be5") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_guid_invalid_string() -> None:
    """Verify is_valid_guid returns False for arbitrary non-UUID strings."""
    assert GDAReferenceManager.is_valid_guid("not-a-uuid") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_guid_truncated() -> None:
    """Verify is_valid_guid returns False for truncated UUIDs."""
    assert GDAReferenceManager.is_valid_guid("c3b5d278-8314-4eb9-a035") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_guid_empty_or_none() -> None:
    """Verify is_valid_guid returns False for empty string or None."""
    assert GDAReferenceManager.is_valid_guid("") is False
    assert GDAReferenceManager.is_valid_guid(None) is False  # type: ignore[arg-type]


# ==============================================================================
# GROUP 6: Unified Entity Identifier Validation Tests (is_valid_gda_id)
# Note: Verification of AUTO routing and explicit type checking
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_auto_person() -> None:
    """Verify is_valid_gda_id in AUTO mode detects valid person ID."""
    assert GDAReferenceManager.is_valid_gda_id("IND-00042") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_auto_site_sid() -> None:
    """Verify is_valid_gda_id in AUTO mode detects valid SID site ID."""
    assert GDAReferenceManager.is_valid_gda_id("SID-00001") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_auto_site_legacy() -> None:
    """Verify is_valid_gda_id in AUTO mode detects valid legacy SITE site ID."""
    assert GDAReferenceManager.is_valid_gda_id("SITE-00001") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_auto_location() -> None:
    """Verify is_valid_gda_id in AUTO mode detects valid location ID."""
    assert GDAReferenceManager.is_valid_gda_id("LOC-00005") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_auto_source() -> None:
    """Verify is_valid_gda_id in AUTO mode detects valid source ID."""
    assert GDAReferenceManager.is_valid_gda_id("SRC-00100") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_auto_note() -> None:
    """Verify is_valid_gda_id in AUTO mode detects valid note ID."""
    assert GDAReferenceManager.is_valid_gda_id("NOT-00001") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_auto_guid() -> None:
    """Verify is_valid_gda_id in AUTO mode detects valid GUID."""
    assert GDAReferenceManager.is_valid_gda_id("c3b5d278-8314-4eb9-a035-7cf008e73be5") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_gda_id_auto_unknown_prefix() -> None:
    """Verify is_valid_gda_id in AUTO mode rejects unknown prefix format."""
    assert GDAReferenceManager.is_valid_gda_id("UNKNOWN-12345") is False


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_person() -> None:
    """Verify is_valid_gda_id matches person ID when entity_type is PERSON."""
    assert GDAReferenceManager.is_valid_gda_id("IND-00042", "PERSON") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_ind_alias() -> None:
    """Verify is_valid_gda_id matches person ID when entity_type is IND."""
    assert GDAReferenceManager.is_valid_gda_id("IND-00042", "ind") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_site_sid() -> None:
    """Verify is_valid_gda_id matches site ID when entity_type is SITE."""
    assert GDAReferenceManager.is_valid_gda_id("SID-00001", "SITE") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_site_alias() -> None:
    """Verify is_valid_gda_id matches site ID when entity_type is SID."""
    assert GDAReferenceManager.is_valid_gda_id("SID-00001", "sid") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_source() -> None:
    """Verify is_valid_gda_id matches source ID when entity_type is SOURCE."""
    assert GDAReferenceManager.is_valid_gda_id("SRC-00100", "SOURCE") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_src_alias() -> None:
    """Verify is_valid_gda_id matches source ID when entity_type is SRC."""
    assert GDAReferenceManager.is_valid_gda_id("SRC-00100", "src") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_note() -> None:
    """Verify is_valid_gda_id matches note ID when entity_type is NOTE."""
    assert GDAReferenceManager.is_valid_gda_id("NOT-00001", "NOTE") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_not_alias() -> None:
    """Verify is_valid_gda_id matches note ID when entity_type is NOT."""
    assert GDAReferenceManager.is_valid_gda_id("NOT-00001", "not") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_location() -> None:
    """Verify is_valid_gda_id matches location ID when entity_type is LOCATION."""
    assert GDAReferenceManager.is_valid_gda_id("LOC-00005", "LOCATION") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_loc_alias() -> None:
    """Verify is_valid_gda_id matches location ID when entity_type is LOC."""
    assert GDAReferenceManager.is_valid_gda_id("LOC-00005", "loc") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_is_valid_gda_id_explicit_guid() -> None:
    """Verify is_valid_gda_id matches fact GUID when entity_type is GUID."""
    assert GDAReferenceManager.is_valid_gda_id("c3b5d278-8314-4eb9-a035-7cf008e73be5", "GUID") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_gda_id_mismatched_type() -> None:
    """Verify is_valid_gda_id rejects person ID when expecting LOCATION."""
    assert GDAReferenceManager.is_valid_gda_id("IND-00042", "LOCATION") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_gda_id_unknown_entity_type() -> None:
    """Verify is_valid_gda_id returns False for unsupported entity_type."""
    assert GDAReferenceManager.is_valid_gda_id("IND-00042", "UNKNOWN_TYPE") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_gda_id_empty_entity_id() -> None:
    """Verify is_valid_gda_id returns False for empty entity_id."""
    assert GDAReferenceManager.is_valid_gda_id("") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_gda_id_none_entity_id() -> None:
    """Verify is_valid_gda_id returns False for None entity_id."""
    assert GDAReferenceManager.is_valid_gda_id(None) is False  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_gda_id_empty_entity_type() -> None:
    """Verify is_valid_gda_id returns False for empty entity_type."""
    assert GDAReferenceManager.is_valid_gda_id("IND-00042", "") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_valid_gda_id_none_entity_type() -> None:
    """Verify is_valid_gda_id returns False for None entity_type."""
    assert GDAReferenceManager.is_valid_gda_id("IND-00042", None) is False  # type: ignore[arg-type]


# ==============================================================================
# GROUP 7: Option A Compatibility Bridges (Deprecated)
# Note: Verification of transitional bridge methods for downstream callers
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_get_kinship_roles_bridge_content() -> None:
    """Verify get_kinship_roles bridge returns exact 15-token canonical set."""
    roles = GDAReferenceManager.get_kinship_roles()
    assert len(roles) == 15
    assert "FATH" in roles


@pytest.mark.unit
@pytest.mark.smoke
def test_get_kinship_roles_list_bridge_content() -> None:
    """Verify get_kinship_roles_list bridge returns exact 15-token list."""
    roles_list = GDAReferenceManager.get_kinship_roles_list()
    assert len(roles_list) == 15
    assert roles_list[0] == "FATH"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_union_statuses_bridge_content() -> None:
    """Verify get_union_statuses bridge returns exact 7-token canonical set."""
    statuses = GDAReferenceManager.get_union_statuses()
    assert len(statuses) == 7
    assert "MARRIED" in statuses


@pytest.mark.unit
@pytest.mark.smoke
def test_get_union_statuses_list_bridge_content() -> None:
    """Verify get_union_statuses_list bridge returns exact 7-token list."""
    statuses_list = GDAReferenceManager.get_union_statuses_list()
    assert len(statuses_list) == 7
    assert statuses_list[0] == "MARRIED"


# ==============================================================================
# GROUP 8: Reference Table Loading, Caching, and Colloquial State Resolution
# Note: Verification of static lookup persistence and state normalization
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_get_table_loads_file_content(mock_reference_sandbox: Path) -> None:
    """Verify get_table parses and loads JSON reference files from data/reference/."""
    payload: dict[str, Any] = {
        "_name": "jurisdictions.json",
        "mappings": {"US": "United States"},
    }
    (mock_reference_sandbox / "jurisdictions.json").write_text(json.dumps(payload), encoding="utf-8")
    result = GDAReferenceManager.get_table("jurisdictions")
    assert result["mappings"]["US"] == "United States"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_table_with_explicit_json_extension(mock_reference_sandbox: Path) -> None:
    """Verify get_table loads correctly when .json extension is explicitly supplied."""
    payload: dict[str, Any] = {"mappings": {"explicit": True}}
    (mock_reference_sandbox / "explicit.json").write_text(json.dumps(payload), encoding="utf-8")
    result = GDAReferenceManager.get_table("explicit.json")
    assert result["mappings"]["explicit"] is True


@pytest.mark.unit
@pytest.mark.regression
def test_get_table_in_memory_cache_hit(mock_reference_sandbox: Path) -> None:
    """Verify subsequent table requests return cached references without disk I/O."""
    payload = {"mappings": {"cached": True}}
    target_file = mock_reference_sandbox / "cached_sample.json"
    target_file.write_text(json.dumps(payload), encoding="utf-8")

    first_call = GDAReferenceManager.get_table("cached_sample")
    target_file.write_text(json.dumps({"mappings": {"cached": False}}), encoding="utf-8")
    second_call = GDAReferenceManager.get_table("cached_sample")

    assert second_call is first_call


@pytest.mark.unit
@pytest.mark.regression
def test_get_table_missing_file_raises_filenotfound(mock_reference_sandbox: Path) -> None:
    """Verify get_table raises FileNotFoundError when target table does not exist."""
    with pytest.raises(FileNotFoundError, match="Reference table 'ghost' not found"):
        GDAReferenceManager.get_table("ghost")


@pytest.mark.unit
@pytest.mark.regression
def test_get_table_malformed_json_raises_valueerror(mock_reference_sandbox: Path) -> None:
    """Verify get_table raises ValueError when encountering malformed JSON syntax."""
    target_file = mock_reference_sandbox / "bad_syntax.json"
    target_file.write_text("{malformed: json", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to parse reference table"):
        GDAReferenceManager.get_table("bad_syntax")


@pytest.mark.unit
@pytest.mark.smoke
def test_get_colloquial_states_returns_mappings_dict(mock_reference_sandbox: Path) -> None:
    """Verify get_colloquial_states extracts the inner mappings dictionary."""
    payload = {
        "mappings": {
            "penn": "Pennsylvania",
            "mass": "Massachusetts",
        }
    }
    (mock_reference_sandbox / "states_colloquial.json").write_text(json.dumps(payload), encoding="utf-8")
    states = GDAReferenceManager.get_colloquial_states()
    assert states["penn"] == "Pennsylvania"


@pytest.mark.unit
@pytest.mark.regression
def test_get_colloquial_states_missing_key_returns_empty_dict(
    mock_reference_sandbox: Path,
) -> None:
    """Verify get_colloquial_states returns empty dict when mappings key is absent."""
    payload: dict[str, Any] = {"version": "1.0.0"}
    (mock_reference_sandbox / "states_colloquial.json").write_text(json.dumps(payload), encoding="utf-8")

    GDAReferenceManager.clear_cache()
    assert GDAReferenceManager.get_colloquial_states() == {}


@pytest.mark.unit
@pytest.mark.regression
def test_get_colloquial_states_non_dict_mappings_returns_empty_dict(
    mock_reference_sandbox: Path,
) -> None:
    """Verify get_colloquial_states returns empty dict when mappings is not a mapping."""
    payload: dict[str, Any] = {"mappings": ["invalid", "list"]}
    (mock_reference_sandbox / "states_colloquial.json").write_text(json.dumps(payload), encoding="utf-8")

    GDAReferenceManager.clear_cache()
    assert GDAReferenceManager.get_colloquial_states() == {}


@pytest.mark.unit
@pytest.mark.smoke
def test_resolve_colloquial_state_successful_match(mock_reference_sandbox: Path) -> None:
    """Verify resolve_colloquial_state normalizes token and returns full state name."""
    payload = {"mappings": {"penn": "Pennsylvania", "nh": "New Hampshire"}}
    (mock_reference_sandbox / "states_colloquial.json").write_text(json.dumps(payload), encoding="utf-8")

    assert GDAReferenceManager.resolve_colloquial_state("  PENN  ") == "Pennsylvania"
    assert GDAReferenceManager.resolve_colloquial_state("nh") == "New Hampshire"


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_colloquial_state_unmatched_returns_none(mock_reference_sandbox: Path) -> None:
    """Verify resolve_colloquial_state returns None for unknown state candidate."""
    payload = {"mappings": {"penn": "Pennsylvania"}}
    (mock_reference_sandbox / "states_colloquial.json").write_text(json.dumps(payload), encoding="utf-8")

    assert GDAReferenceManager.resolve_colloquial_state("unknown_state") is None


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_colloquial_state_empty_or_non_string_returns_none() -> None:
    """Verify resolve_colloquial_state returns None for empty or non-string inputs."""
    assert GDAReferenceManager.resolve_colloquial_state("") is None
    assert GDAReferenceManager.resolve_colloquial_state("   ") is None
    assert GDAReferenceManager.resolve_colloquial_state(None) is None  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.regression
def test_clear_cache_evicts_cached_table(mock_reference_sandbox: Path) -> None:
    """Verify clear_cache forces subsequent table reads to reload from disk."""
    target_file = mock_reference_sandbox / "reloaded.json"
    target_file.write_text(json.dumps({"mappings": {"v": 1}}), encoding="utf-8")
    GDAReferenceManager.get_table("reloaded")

    target_file.write_text(json.dumps({"mappings": {"v": 2}}), encoding="utf-8")
    GDAReferenceManager.clear_cache()
    call_2 = GDAReferenceManager.get_table("reloaded")
    assert call_2["mappings"]["v"] == 2


@pytest.mark.unit
@pytest.mark.smoke
def test_reference_manager_introspectable_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify GDAReferenceManager inherits IntrospectableMixin and renders directory help."""
    GDAReferenceManager.help()
    captured = capsys.readouterr().out
    assert "=== GDAReferenceManager Public Directory ===" in captured