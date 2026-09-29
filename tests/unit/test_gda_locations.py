# Name: test_gda_locations.py
# Path: tests/unit/test_gda_locations.py
# Version: 1.4.0+build.20260929.1

"""Unit test suite verifying GDALocations master jurisdiction manager.

Operational Role:
    Validates civil jurisdiction normalization via 'us' package,
    canonical name construction, CRUD auto-minting, temporal validity,
    alias manipulation, stateful filtering, search filters, branch edge
    cases, and scratch persistence to achieve >95% code coverage.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly marked with @pytest.mark.unit.
    - Dependencies: Hermetic tmp_path sandboxes without production disk I/O.
"""

from pathlib import Path
import pytest
from tools.lib.gda_core.GDALocations import GDALocations
from tools.lib.gda_core.GDAUtil import GDAUtil


@pytest.mark.unit
def test_gda_locations_normalize_us_state_abbreviation() -> None:
    """Verifies normalize_state resolves two-letter USPS codes to full state names."""
    resolved = GDALocations.normalize_state("USA", "PA")
    assert resolved == "Pennsylvania"


@pytest.mark.unit
def test_gda_locations_normalize_us_state_case_insensitive() -> None:
    """Verifies normalize_state resolves case-insensitive state full names."""
    resolved = GDALocations.normalize_state("United States", "new hampshire")
    assert resolved == "New Hampshire"


@pytest.mark.unit
def test_gda_locations_normalize_us_state_none_input() -> None:
    """Verifies normalize_state returns None when state input is None."""
    resolved = GDALocations.normalize_state("USA", None)
    assert resolved is None


@pytest.mark.unit
def test_gda_locations_normalize_international_province_preserved() -> None:
    """Verifies normalize_state leaves non-US states or provinces unmutated."""
    resolved = GDALocations.normalize_state("Germany", "Bavaria")
    assert resolved == "Bavaria"


@pytest.mark.unit
def test_gda_locations_normalize_us_state_unknown_name() -> None:
    """Verifies normalize_state returns original string if lookup fails in USA."""
    resolved = GDALocations.normalize_state("USA", "NotAState")
    assert resolved == "NotAState"


@pytest.mark.unit
def test_gda_locations_build_canonical_name() -> None:
    """Verifies build_canonical_name formats hierarchical comma-separated representation."""
    c_name = GDALocations.build_canonical_name(
        country="USA",
        state_or_province="Pennsylvania",
        county="Cumberland",
        local_jurisdiction="Carlisle",
    )
    assert c_name == "Carlisle, Cumberland County, Pennsylvania, USA"


@pytest.mark.unit
def test_gda_locations_build_canonical_name_preserves_existing_county_suffix() -> None:
    """Verifies build_canonical_name does not duplicate County if already present."""
    c_name = GDALocations.build_canonical_name(
        country="USA",
        state_or_province="Pennsylvania",
        county="Cumberland County",
        local_jurisdiction="Carlisle",
    )
    assert c_name == "Carlisle, Cumberland County, Pennsylvania, USA"


@pytest.mark.unit
def test_gda_locations_canonical_name_bare_country() -> None:
    """Verifies build_canonical_name handles country-only entities."""
    c_name = GDALocations.build_canonical_name(country="Germany")
    assert c_name == "Germany"


@pytest.mark.unit
def test_gda_locations_mint_first_id(tmp_path: Path) -> None:
    """Verifies add() mints LOC-00001 when initializing an empty registry."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Carlisle")
    assert lid == "LOC-00001"


@pytest.mark.unit
def test_gda_locations_mint_monotonic_sequence(tmp_path: Path) -> None:
    """Verifies add() calculates next zero-padded monotonic ID from highest existing."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    loc.add(country="USA", state_or_province="PA", location_id="LOC-00010")
    next_id = loc.add(country="USA", state_or_province="PA")
    assert next_id == "LOC-00011"


@pytest.mark.unit
def test_gda_locations_mint_skips_lower_index(tmp_path: Path) -> None:
    """Verifies _mint_next_id ignores lower indices when a higher index exists."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    loc.add(country="USA", location_id="LOC-00020")
    loc.add(country="USA", location_id="LOC-00005")
    assert loc._mint_next_id() == "LOC-00021"


@pytest.mark.unit
def test_gda_locations_mint_id_ignores_malformed_keys() -> None:
    """Verifies _mint_next_id ignores non-standard key formats without throwing error."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc._locations["CUSTOM_KEY"] = {"location_id": "CUSTOM_KEY"}
    loc._locations["LOC-00005"] = {"location_id": "LOC-00005"}
    assert loc._mint_next_id() == "LOC-00006"


@pytest.mark.unit
def test_gda_locations_add_empty_country_raises(tmp_path: Path) -> None:
    """Verifies add() raises ValueError when country is empty."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    with pytest.raises(ValueError, match="Country must not be empty"):
        loc.add(country="   ")


@pytest.mark.unit
def test_gda_locations_add_malformed_location_id_raises(tmp_path: Path) -> None:
    """Verifies add() enforces regex pattern on location_id."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    with pytest.raises(ValueError, match="Malformed location_id pattern"):
        loc.add(country="USA", location_id="LOC-123")


@pytest.mark.unit
def test_gda_locations_add_duplicate_id_raises(tmp_path: Path) -> None:
    """Verifies add() raises KeyError when manually inserting an existing ID."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    loc.add(country="USA", location_id="LOC-00001")
    with pytest.raises(KeyError, match="Location identifier 'LOC-00001' already exists"):
        loc.add(country="USA", location_id="LOC-00001")


@pytest.mark.unit
def test_gda_locations_add_malformed_predecessor_id_raises(tmp_path: Path) -> None:
    """Verifies add() raises ValueError on malformed predecessor_location_id."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    with pytest.raises(ValueError, match="Malformed predecessor_location_id"):
        loc.add(country="USA", predecessor_location_id="BAD-ID")


@pytest.mark.unit
def test_gda_locations_add_malformed_successor_id_raises(tmp_path: Path) -> None:
    """Verifies add() raises ValueError on malformed successor_location_id."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    with pytest.raises(ValueError, match="Malformed successor_location_id"):
        loc.add(country="USA", successor_location_id="BAD-ID")


@pytest.mark.unit
def test_gda_locations_add_alias_success(tmp_path: Path) -> None:
    """Verifies add_alias appends unique string and marks registry dirty."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", state_or_province="PA", county="Dauphin", local_jurisdiction="Harrisburg")
    result = loc.add_alias(lid, "Hbg")
    assert result is True
    assert loc.is_dirty is True
    assert "Hbg" in loc.get_by_id(lid)["aliases"]


@pytest.mark.unit
def test_gda_locations_add_alias_duplicate_returns_false(tmp_path: Path) -> None:
    """Verifies add_alias ignores existing alias and returns False."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", state_or_province="PA", aliases=["Hbg"])
    result = loc.add_alias(lid, "Hbg")
    assert result is False


@pytest.mark.unit
def test_gda_locations_add_alias_missing_location_raises(tmp_path: Path) -> None:
    """Verifies add_alias raises KeyError when location does not exist."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    with pytest.raises(KeyError, match="Location 'LOC-00999' does not exist"):
        loc.add_alias("LOC-00999", "Alias")


@pytest.mark.unit
def test_gda_locations_add_alias_empty_returns_false(tmp_path: Path) -> None:
    """Verifies add_alias returns False when alias is empty whitespace."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", state_or_province="PA")
    assert loc.add_alias(lid, "   ") is False


@pytest.mark.unit
def test_gda_locations_remove_alias_success(tmp_path: Path) -> None:
    """Verifies remove_alias prunes existing alias and marks registry dirty."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", state_or_province="PA", aliases=["Hbg", "Harrisburg City"])
    result = loc.remove_alias(lid, "Hbg")
    assert result is True
    assert "Hbg" not in loc.get_by_id(lid)["aliases"]


@pytest.mark.unit
def test_gda_locations_remove_alias_missing_returns_false(tmp_path: Path) -> None:
    """Verifies remove_alias returns False when alias is not found."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", state_or_province="PA", aliases=["Hbg"])
    assert loc.remove_alias(lid, "Other") is False


@pytest.mark.unit
def test_gda_locations_remove_alias_missing_location_raises(tmp_path: Path) -> None:
    """Verifies remove_alias raises KeyError when location does not exist."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    with pytest.raises(KeyError, match="Location 'LOC-00999' does not exist"):
        loc.remove_alias("LOC-00999", "Alias")


@pytest.mark.unit
def test_gda_locations_load_nonexistent_initializes_empty(tmp_path: Path) -> None:
    """Verifies load() gracefully handles missing file by creating empty state."""
    missing_file = tmp_path / "absent.json"
    loc = GDALocations(filepath=missing_file, auto_load=True)
    assert loc.count == 0
    assert loc.is_dirty is False


@pytest.mark.unit
def test_gda_locations_load_corrupt_file_raises(tmp_path: Path) -> None:
    """Verifies load() propagates exception when JSON is corrupt."""
    corrupt_file = tmp_path / "bad.json"
    corrupt_file.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(Exception):
        GDALocations(filepath=corrupt_file, auto_load=True)


@pytest.mark.unit
def test_gda_locations_load_existing_registry(tmp_path: Path) -> None:
    """Verifies load() populates registry from JSON file on disk."""
    reg_file = tmp_path / "locations.json"
    payload = {
        "_name": "locations.json",
        "_path": "data/entities/locations.json",
        "schema_version": "1.0.0",
        "locations": [
            {
                "location_id": "LOC-00001",
                "canonical_name": "Carlisle, Cumberland County, Pennsylvania, USA",
                "aliases": ["Carlisle"],
                "jurisdiction": {"country": "USA", "state_or_province": "Pennsylvania", "county": "Cumberland", "local_jurisdiction": "Carlisle"},
                "temporal_validity": {},
                "notes": [],
                "last_updated": "2026-09-29T00:00:00Z"
            }
        ]
    }
    GDAUtil.save_json(reg_file, payload, create_backup=False)
    loc = GDALocations(filepath=reg_file, auto_load=True)
    assert loc.count == 1
    assert loc.exists("LOC-00001") is True


@pytest.mark.unit
def test_gda_locations_refresh_discards_unsaved_state(tmp_path: Path) -> None:
    """Verifies refresh() reloads state from disk and clears in-memory edits."""
    reg_file = tmp_path / "locations.json"
    payload = {
        "_name": "locations.json",
        "locations": [{"location_id": "LOC-00001", "canonical_name": "Disk State", "jurisdiction": {"country": "USA"}}]
    }
    GDAUtil.save_json(reg_file, payload, create_backup=False)
    loc = GDALocations(filepath=reg_file, auto_load=True)
    loc.add(country="Germany", local_jurisdiction="Munich")
    assert loc.count == 2
    loc.refresh()
    assert loc.count == 1


@pytest.mark.unit
def test_gda_locations_edit_success(tmp_path: Path) -> None:
    """Verifies edit() modifies canonical name, jurisdiction, and marks dirty."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", state_or_province="PA", local_jurisdiction="Carlisle")
    loc.edit(lid, {
        "canonical_name": "Carlisle Borough, PA",
        "aliases": ["Carlisle"],
        "jurisdiction": {"local_jurisdiction": "Carlisle Borough", "county": "Cumberland"},
        "temporal_validity": {"date_established": "1751-01-27", "predecessor_location_id": "LOC-00000"},
        "notes": [{"note": "County seat"}]
    })
    updated = loc.get_by_id(lid)
    assert updated["canonical_name"] == "Carlisle Borough, PA"
    assert updated["aliases"] == ["Carlisle"]
    assert updated["jurisdiction"]["local_jurisdiction"] == "Carlisle Borough"
    assert updated["temporal_validity"]["date_established"] == "1751-01-27"
    assert len(updated["notes"]) == 1


@pytest.mark.unit
def test_gda_locations_edit_noop_returns_false(tmp_path: Path) -> None:
    """Verifies edit() returns False when updates match existing values."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", canonical_name="Name", aliases=["Alias"])
    modified = loc.edit(lid, {"canonical_name": "Name", "aliases": ["Alias"]})
    assert modified is False


@pytest.mark.unit
def test_gda_locations_edit_temporal_validity_noop_leaves_clean() -> None:
    """Verifies edit() does not mark dirty when temporal fields match existing."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    lid = loc.add(country="USA", date_established="1800-01-01")
    loc._is_dirty = False
    modified = loc.edit(lid, {"temporal_validity": {"date_established": "1800-01-01"}})
    assert modified is False
    assert loc.is_dirty is False


@pytest.mark.unit
def test_gda_locations_edit_overwrite_none(tmp_path: Path) -> None:
    """Verifies edit() clears jurisdiction fields when overwrite_none is True."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", county="Cumberland")
    loc.edit(lid, {"jurisdiction": {"county": None}}, overwrite_none=True)
    assert loc.get_by_id(lid)["jurisdiction"]["county"] is None


@pytest.mark.unit
def test_gda_locations_edit_temporal_validity_overwrite_none(tmp_path: Path) -> None:
    """Verifies edit() clears temporal fields when overwrite_none is True."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", date_established="1800-01-01")
    loc.edit(lid, {"temporal_validity": {"date_established": None}}, overwrite_none=True)
    assert loc.get_by_id(lid)["temporal_validity"]["date_established"] is None


@pytest.mark.unit
def test_gda_locations_edit_missing_location_raises(tmp_path: Path) -> None:
    """Verifies edit() raises KeyError when editing nonexistent location."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    with pytest.raises(KeyError, match="Location 'LOC-00999' does not exist"):
        loc.edit("LOC-00999", {"canonical_name": "New Name"})


@pytest.mark.unit
def test_gda_locations_edit_empty_canonical_name_raises(tmp_path: Path) -> None:
    """Verifies edit() raises ValueError when canonical_name is empty."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA")
    with pytest.raises(ValueError, match="canonical_name must not be empty"):
        loc.edit(lid, {"canonical_name": "   "})


@pytest.mark.unit
def test_gda_locations_delete_success(tmp_path: Path) -> None:
    """Verifies delete() removes location and updates filtered views."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    lid = loc.add(country="USA", local_jurisdiction="Carlisle")
    loc.set_filter(country="USA")
    deleted = loc.delete(lid)
    assert deleted is True
    assert loc.count == 0
    assert loc.filtered_count == 0
    assert loc.get_by_id(lid) is None


@pytest.mark.unit
def test_gda_locations_delete_when_id_not_in_active_filter() -> None:
    """Verifies delete() removes entity from master registry even if excluded from active filter."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    lid1 = loc.add(country="USA", location_id="LOC-00001")
    lid2 = loc.add(country="Germany", location_id="LOC-00002")
    loc.set_filter(country="USA")
    deleted = loc.delete(lid2)
    assert deleted is True
    assert "LOC-00002" not in loc._locations


@pytest.mark.unit
def test_gda_locations_delete_nonexistent_returns_false(tmp_path: Path) -> None:
    """Verifies delete() returns False when location does not exist."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    assert loc.delete("LOC-00999") is False


@pytest.mark.unit
def test_gda_locations_temporal_validity_extant() -> None:
    """Verifies is_valid_at_date returns True when ISO date is within established/dissolved range."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(
        country="USA",
        state_or_province="PA",
        local_jurisdiction="Frankford Township",
        date_established="1795-01-01",
        date_dissolved="1882-06-30",
    )
    assert loc.is_valid_at_date("LOC-00001", "1850-07-04") is True


@pytest.mark.unit
def test_gda_locations_temporal_validity_pre_establishment() -> None:
    """Verifies is_valid_at_date returns False when ISO date is prior to date_established."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(
        country="USA",
        state_or_province="PA",
        local_jurisdiction="Frankford Township",
        date_established="1795-01-01",
    )
    assert loc.is_valid_at_date("LOC-00001", "1750-01-01") is False


@pytest.mark.unit
def test_gda_locations_temporal_validity_post_dissolution() -> None:
    """Verifies is_valid_at_date returns False when ISO date is after date_dissolved."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(
        country="USA",
        state_or_province="PA",
        local_jurisdiction="Frankford Township",
        date_established="1795-01-01",
        date_dissolved="1882-06-30",
    )
    assert loc.is_valid_at_date("LOC-00001", "1900-01-01") is False


@pytest.mark.unit
def test_gda_locations_temporal_validity_dissolved_only() -> None:
    """Verifies is_valid_at_date evaluates entities that have only a date_dissolved."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    lid = loc.add(country="USA", date_dissolved="1880-01-01")
    assert loc.is_valid_at_date(lid, "1850-01-01") is True
    assert loc.is_valid_at_date(lid, "1900-01-01") is False


@pytest.mark.unit
def test_gda_locations_temporal_validity_open_boundaries_returns_true() -> None:
    """Verifies is_valid_at_date returns True when established and dissolved dates are None."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA")
    assert loc.is_valid_at_date("LOC-00001", "1950-01-01") is True


@pytest.mark.unit
def test_gda_locations_temporal_validity_missing_record_returns_false() -> None:
    """Verifies is_valid_at_date returns False when location does not exist."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    assert loc.is_valid_at_date("LOC-00999", "1850-01-01") is False


@pytest.mark.unit
def test_gda_locations_get_predecessor_and_successor() -> None:
    """Verifies get_predecessor and get_successor resolve linked entities."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", local_jurisdiction="Old Frankford", location_id="LOC-00001", successor_location_id="LOC-00002")
    loc.add(country="USA", local_jurisdiction="Upper Frankford", location_id="LOC-00002", predecessor_location_id="LOC-00001")

    pred = loc.get_predecessor("LOC-00002")
    succ = loc.get_successor("LOC-00001")
    assert pred["location_id"] == "LOC-00001"
    assert succ["location_id"] == "LOC-00002"


@pytest.mark.unit
def test_gda_locations_get_predecessor_missing_link_returns_none() -> None:
    """Verifies get_predecessor returns None when predecessor_location_id is absent."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", location_id="LOC-00001")
    assert loc.get_predecessor("LOC-00001") is None


@pytest.mark.unit
def test_gda_locations_get_predecessor_unregistered_id_returns_none() -> None:
    """Verifies get_predecessor returns None when predecessor ID is not in registry."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", location_id="LOC-00001", predecessor_location_id="LOC-00999")
    assert loc.get_predecessor("LOC-00001") is None


@pytest.mark.unit
def test_gda_locations_get_predecessor_missing_entity_returns_none() -> None:
    """Verifies get_predecessor returns None when queried location does not exist."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    assert loc.get_predecessor("LOC-00999") is None


@pytest.mark.unit
def test_gda_locations_get_successor_missing_link_returns_none() -> None:
    """Verifies get_successor returns None when successor_location_id is absent."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", location_id="LOC-00001")
    assert loc.get_successor("LOC-00001") is None


@pytest.mark.unit
def test_gda_locations_get_successor_unregistered_id_returns_none() -> None:
    """Verifies get_successor returns None when successor ID is not in registry."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", location_id="LOC-00001", successor_location_id="LOC-00999")
    assert loc.get_successor("LOC-00001") is None


@pytest.mark.unit
def test_gda_locations_get_successor_missing_entity_returns_none() -> None:
    """Verifies get_successor returns None when queried location does not exist."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    assert loc.get_successor("LOC-00999") is None


@pytest.mark.unit
def test_gda_locations_find_by_jurisdiction_match() -> None:
    """Verifies find_by_jurisdiction locates exact matching civil components."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Carlisle")
    match = loc.find_by_jurisdiction(country="USA", state_or_province="Pennsylvania", county="Cumberland County", local_jurisdiction="Carlisle")
    assert match is not None
    assert match["location_id"] == "LOC-00001"


@pytest.mark.unit
def test_gda_locations_find_by_jurisdiction_no_match_returns_none() -> None:
    """Verifies find_by_jurisdiction returns None when jurisdiction does not match."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Carlisle")
    assert loc.find_by_jurisdiction(country="USA", state_or_province="NH") is None


@pytest.mark.unit
def test_gda_locations_find_by_jurisdiction_county_mismatch_returns_none() -> None:
    """Verifies find_by_jurisdiction returns None when county does not match."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Carlisle")
    assert loc.find_by_jurisdiction(country="USA", state_or_province="PA", county="Dauphin") is None


@pytest.mark.unit
def test_gda_locations_find_by_jurisdiction_local_mismatch_returns_none() -> None:
    """Verifies find_by_jurisdiction returns None when local jurisdiction mismatches."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Carlisle")
    assert loc.find_by_jurisdiction(country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Mechanicsburg") is None


@pytest.mark.unit
def test_gda_locations_search_with_jurisdiction_filters() -> None:
    """Verifies search() applies country, state, and county filters concurrently."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Carlisle")
    loc.add(country="USA", state_or_province="PA", county="Dauphin", local_jurisdiction="Harrisburg")
    loc.add(country="USA", state_or_province="NH", county="Merrimack", local_jurisdiction="Bow")

    results = loc.search(query=None, country="USA", state_or_province="PA", county="Cumberland")
    assert len(results) == 1
    assert results[0]["location_id"] == "LOC-00001"


@pytest.mark.unit
def test_gda_locations_search_county_and_local_candidate_matching() -> None:
    """Verifies search() matches query directly on county or local jurisdiction."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Carlisle")
    results = loc.search(query="Cumberland", use_fuzzy=False)
    assert len(results) == 1
    assert results[0]["location_id"] == "LOC-00001"


@pytest.mark.unit
def test_gda_locations_search_alias_wildcard_matching() -> None:
    """Verifies search() resolves glob wildcards against aliases."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", canonical_name="Harrisburg City", aliases=["Hbg Borough"])
    results = loc.search(query="*Hbg*")
    assert len(results) == 1
    assert results[0]["location_id"] == "LOC-00001"


@pytest.mark.unit
def test_gda_locations_search_fuzzy_below_threshold_returns_empty() -> None:
    """Verifies search() rejects query when fuzzy score is below threshold."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", local_jurisdiction="Carlisle")
    assert len(loc.search(query="Zzzzzzz", use_fuzzy=True, fuzzy_threshold=0.8)) == 0


@pytest.mark.unit
def test_gda_locations_find_one_returns_top_scoring_result() -> None:
    """Verifies find_one returns highest matching result or None."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", state_or_province="PA", local_jurisdiction="Harrisburg")
    top = loc.find_one("Harisburg")
    assert top is not None
    assert top["location_id"] == "LOC-00001"


@pytest.mark.unit
def test_gda_locations_find_one_no_match_returns_none() -> None:
    """Verifies find_one returns None when no entities match."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    assert loc.find_one("Nonexistent") is None


@pytest.mark.unit
def test_gda_locations_set_filter_and_clear_filter() -> None:
    """Verifies set_filter restricts active set and clear_filter restores full set."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", state_or_province="PA", local_jurisdiction="Carlisle")
    loc.add(country="USA", state_or_province="NH", local_jurisdiction="Bow")
    loc.add(country="Germany", local_jurisdiction="Munich")

    cnt = loc.set_filter(country="USA", state_or_province="PA")
    assert cnt == 1
    assert loc.filtered_count == 1
    loc.clear_filter()
    assert loc.filtered_count == 3


@pytest.mark.unit
def test_gda_locations_set_filter_with_predicate_and_county() -> None:
    """Verifies set_filter handles custom predicates and county patterns."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Carlisle")
    loc.add(country="USA", state_or_province="PA", county="Dauphin", local_jurisdiction="Harrisburg")

    cnt = loc.set_filter(county="Cumberland", predicate=lambda x: "Carlisle" in x["canonical_name"])
    assert cnt == 1
    assert loc.filtered_count == 1


@pytest.mark.unit
def test_gda_locations_set_filter_name_pattern() -> None:
    """Verifies set_filter filters by wildcard name pattern."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", local_jurisdiction="Carlisle")
    loc.add(country="USA", local_jurisdiction="Bow")

    cnt = loc.set_filter(name_pattern="*Carlisle*")
    assert cnt == 1
    assert loc.get_filtered()[0]["jurisdiction"]["local_jurisdiction"] == "Carlisle"


@pytest.mark.unit
def test_gda_locations_update_filtered_modifies_active_set() -> None:
    """Verifies update_filtered applies atomic changes to records in the active filter."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    lid1 = loc.add(country="USA", state_or_province="PA", local_jurisdiction="Town A")
    lid2 = loc.add(country="USA", state_or_province="PA", local_jurisdiction="Town B")
    loc.add(country="USA", state_or_province="NH", local_jurisdiction="Town C")

    loc.set_filter(state_or_province="PA")
    modified = loc.update_filtered({"jurisdiction": {"county": "Perry"}})
    assert modified == 2
    assert loc.get_by_id(lid1)["jurisdiction"]["county"] == "Perry"
    assert loc.get_by_id(lid2)["jurisdiction"]["county"] == "Perry"


@pytest.mark.unit
def test_gda_locations_update_filtered_empty_returns_zero() -> None:
    """Verifies update_filtered returns 0 when no items pass filter."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA")
    loc.set_filter(country="Canada")
    assert loc.update_filtered({"notes": []}) == 0


@pytest.mark.unit
def test_gda_locations_dunder_protocols() -> None:
    """Verifies __len__, __contains__, and __iter__ behaviors."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", local_jurisdiction="Carlisle", location_id="LOC-00001")
    assert len(loc) == 1
    assert "LOC-00001" in loc
    assert "LOC-00002" not in loc
    items = list(loc)
    assert len(items) == 1
    assert items[0]["location_id"] == "LOC-00001"


@pytest.mark.unit
def test_gda_locations_dunder_iter_with_filter() -> None:
    """Verifies __iter__ yields only items passing active filter."""
    loc = GDALocations(filepath=Path("mock.json"), auto_load=False)
    loc.add(country="USA", location_id="LOC-00001")
    loc.add(country="Germany", location_id="LOC-00002")
    loc.set_filter(country="Germany")
    items = list(loc)
    assert len(items) == 1
    assert items[0]["location_id"] == "LOC-00002"


@pytest.mark.unit
def test_gda_locations_save_resets_dirty_state(tmp_path: Path) -> None:
    """Verifies save() to canonical path sets is_dirty to False."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    loc.add(country="USA")
    assert loc.is_dirty is True
    loc.save(force=True, create_backup=False)
    assert loc.is_dirty is False


@pytest.mark.unit
def test_gda_locations_save_skips_when_clean_and_not_forced(tmp_path: Path) -> None:
    """Verifies save() returns False without writing when is_dirty is False and force is False."""
    reg_file = tmp_path / "locations.json"
    loc = GDALocations(filepath=reg_file, auto_load=False)
    assert loc.save(force=False) is False


@pytest.mark.unit
def test_gda_locations_save_to_scratch_output_path(tmp_path: Path) -> None:
    """Verifies save() persists to custom output_path leaving canonical file untouched."""
    canonical_file = tmp_path / "canonical.json"
    scratch_file = tmp_path / "scratch.json"
    loc = GDALocations(filepath=canonical_file, auto_load=False)
    loc.add(country="USA", state_or_province="PA", county="Perry")
    loc.save(output_path=scratch_file, force=True)
    assert scratch_file.exists()
    assert not canonical_file.exists()