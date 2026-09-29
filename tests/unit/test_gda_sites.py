# Name: test_gda_sites.py
# Path: tests/unit/test_gda_sites.py
# Version: 1.5.0+build.20260929.1

"""Unit test suite verifying GDASites master physical site registry manager.

Operational Role:
    Validates physical site additions, schema validations, auto-minting of
    identifiers, foreign key integrity against locations, exact/wildcard/fuzzy
    searches, alias management, stateful filtering, batch updates, and
    isolated scratch persistence to achieve >95% code coverage.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly marked with @pytest.mark.unit.
    - Dependencies: Hermetic tmp_path sandboxes without production disk I/O.
"""

from pathlib import Path
import pytest
from tools.lib.gda_core.GDASites import GDASites
from tools.lib.gda_core.GDAUtil import GDAUtil


@pytest.mark.unit
def test_gda_sites_mint_first_id(tmp_path: Path) -> None:
    """Verifies add() mints SITE-00001 when initializing an empty registry."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Carlisle Hospital", location_id="LOC-00006")
    assert sid == "SITE-00001"


@pytest.mark.unit
def test_gda_sites_mint_monotonic_sequence(tmp_path: Path) -> None:
    """Verifies add() calculates the next zero-padded monotonic ID from highest existing."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Site One", location_id="LOC-00001", site_id="SITE-00042")
    next_id = sites.add(site_type="FACILITY", name="Site Two", location_id="LOC-00001")
    assert next_id == "SITE-00043"


@pytest.mark.unit
def test_gda_sites_mint_skips_lower_index(tmp_path: Path) -> None:
    """Verifies _mint_next_id ignores lower IDs when a higher ID exists."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Site High", location_id="LOC-00001", site_id="SITE-00050")
    sites.add(site_type="FACILITY", name="Site Low", location_id="LOC-00001", site_id="SITE-00010")
    assert sites._mint_next_id() == "SITE-00051"


@pytest.mark.unit
def test_gda_sites_mint_id_ignores_malformed_keys() -> None:
    """Verifies _mint_next_id ignores non-standard site ID keys safely."""
    sites = GDASites(filepath=Path("mock.json"), auto_load=False)
    sites._sites["CUSTOM_SITE"] = {"site_id": "CUSTOM_SITE"}
    sites._sites["SITE-00003"] = {"site_id": "SITE-00003"}
    assert sites._mint_next_id() == "SITE-00004"


@pytest.mark.unit
def test_gda_sites_add_without_location_provider_skips_validation() -> None:
    """Verifies add() accepts valid LOC-XXXXX format without lookup if provider is None."""
    sites = GDASites(filepath=Path("mock.json"), auto_load=False, locations_provider=None)
    sid = sites.add(site_type="FACILITY", name="Clinic", location_id="LOC-00099")
    assert sid == "SITE-00001"


@pytest.mark.unit
def test_gda_sites_add_invalid_site_type_raises(tmp_path: Path) -> None:
    """Verifies add() rejects unregistered site types with ValueError."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    with pytest.raises(ValueError, match="Invalid site_type 'INVALID_TYPE'"):
        sites.add(site_type="INVALID_TYPE", name="Hospital", location_id="LOC-00001")


@pytest.mark.unit
def test_gda_sites_add_empty_name_raises(tmp_path: Path) -> None:
    """Verifies add() rejects empty name strings with ValueError."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    with pytest.raises(ValueError, match="Site name must not be empty"):
        sites.add(site_type="FACILITY", name="   ", location_id="LOC-00001")


@pytest.mark.unit
def test_gda_sites_add_malformed_location_id_raises(tmp_path: Path) -> None:
    """Verifies add() enforces regex pattern ^LOC-[0-9]{5}$ on location_id."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    with pytest.raises(ValueError, match="Malformed location_id pattern"):
        sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-99")


@pytest.mark.unit
def test_gda_sites_add_foreign_key_violation_raises(tmp_path: Path) -> None:
    """Verifies add() validates location existence against locations_provider when supplied."""
    reg_file = tmp_path / "sites.json"
    mock_loc = type("MockLocations", (), {"exists": lambda self, lid: False})()
    sites = GDASites(filepath=reg_file, auto_load=False, locations_provider=mock_loc)
    with pytest.raises(KeyError, match="Foreign key violation"):
        sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-00999")


@pytest.mark.unit
def test_gda_sites_add_foreign_key_provider_get_by_id_fallback(tmp_path: Path) -> None:
    """Verifies add() falls back to locations_provider.get_by_id when exists() is absent."""
    reg_file = tmp_path / "sites.json"
    mock_loc = type("MockLocations", (), {"get_by_id": lambda self, lid: None})()
    sites = GDASites(filepath=reg_file, auto_load=False, locations_provider=mock_loc)
    with pytest.raises(KeyError, match="Foreign key violation"):
        sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-00999")


@pytest.mark.unit
def test_gda_sites_add_foreign_key_provider_get_by_id_valid(tmp_path: Path) -> None:
    """Verifies add() accepts location if get_by_id fallback returns a record."""
    reg_file = tmp_path / "sites.json"
    mock_loc = type("MockLocations", (), {"get_by_id": lambda self, lid: {"location_id": lid}})()
    sites = GDASites(filepath=reg_file, auto_load=False, locations_provider=mock_loc)
    sid = sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-00001")
    assert sid == "SITE-00001"


@pytest.mark.unit
def test_gda_sites_add_duplicate_id_raises(tmp_path: Path) -> None:
    """Verifies add() rejects manual insertion of an existing primary key."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Hospital One", location_id="LOC-00001", site_id="SITE-00001")
    with pytest.raises(KeyError, match="Site identifier 'SITE-00001' already exists"):
        sites.add(site_type="FACILITY", name="Hospital Two", location_id="LOC-00001", site_id="SITE-00001")


@pytest.mark.unit
def test_gda_sites_add_malformed_site_id_raises(tmp_path: Path) -> None:
    """Verifies add() raises ValueError when manual site_id pattern is invalid."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    with pytest.raises(ValueError, match="Malformed site_id pattern"):
        sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-00001", site_id="BAD-ID")


@pytest.mark.unit
def test_gda_sites_add_coordinates_missing_lat_or_lon_raises(tmp_path: Path) -> None:
    """Verifies add() raises ValueError when coordinates lack latitude or longitude."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    with pytest.raises(ValueError, match="must specify both 'latitude' and 'longitude'"):
        sites.add(site_type="FACILITY", name="Clinic", location_id="LOC-00001", coordinates={"latitude": 40.20})


@pytest.mark.unit
def test_gda_sites_add_alias_success(tmp_path: Path) -> None:
    """Verifies add_alias appends a unique alias and marks registry dirty."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Carlisle Hospital", location_id="LOC-00006")
    result = sites.add_alias(sid, "Carlisle Hosp")
    assert result is True
    assert sites.is_dirty is True
    assert "Carlisle Hosp" in sites.get_by_id(sid)["aliases"]


@pytest.mark.unit
def test_gda_sites_add_alias_duplicate_returns_false(tmp_path: Path) -> None:
    """Verifies add_alias ignores existing alias string and returns False."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Carlisle Hospital", location_id="LOC-00006", aliases=["Carlisle Hosp"])
    result = sites.add_alias(sid, "Carlisle Hosp")
    assert result is False


@pytest.mark.unit
def test_gda_sites_add_alias_missing_site_raises(tmp_path: Path) -> None:
    """Verifies add_alias raises KeyError when site does not exist."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    with pytest.raises(KeyError, match="Site 'SITE-00999' does not exist"):
        sites.add_alias("SITE-00999", "Alias")


@pytest.mark.unit
def test_gda_sites_add_alias_empty_returns_false(tmp_path: Path) -> None:
    """Verifies add_alias returns False when alias is empty."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Carlisle Hospital", location_id="LOC-00006")
    assert sites.add_alias(sid, "   ") is False


@pytest.mark.unit
def test_gda_sites_remove_alias_success(tmp_path: Path) -> None:
    """Verifies remove_alias prunes an alias and marks registry dirty."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Carlisle Hospital", location_id="LOC-00006", aliases=["Carlisle Hosp", "Old Clinic"])
    result = sites.remove_alias(sid, "Old Clinic")
    assert result is True
    assert sites.is_dirty is True
    assert "Old Clinic" not in sites.get_by_id(sid)["aliases"]


@pytest.mark.unit
def test_gda_sites_remove_alias_missing_returns_false(tmp_path: Path) -> None:
    """Verifies remove_alias returns False when alias does not exist."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Carlisle Hospital", location_id="LOC-00006", aliases=["Carlisle Hosp"])
    result = sites.remove_alias(sid, "Nonexistent Alias")
    assert result is False


@pytest.mark.unit
def test_gda_sites_remove_alias_missing_site_raises(tmp_path: Path) -> None:
    """Verifies remove_alias raises KeyError when site does not exist."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    with pytest.raises(KeyError, match="Site 'SITE-00999' does not exist"):
        sites.remove_alias("SITE-00999", "Alias")


@pytest.mark.unit
def test_gda_sites_load_nonexistent_initializes_empty(tmp_path: Path) -> None:
    """Verifies load() initializes empty registry if target file is missing."""
    missing_file = tmp_path / "absent_sites.json"
    sites = GDASites(filepath=missing_file, auto_load=True)
    assert sites.count == 0
    assert sites.is_dirty is False


@pytest.mark.unit
def test_gda_sites_load_corrupt_file_raises(tmp_path: Path) -> None:
    """Verifies load() propagates exception when JSON payload is corrupt."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{bad", encoding="utf-8")
    with pytest.raises(Exception):
        GDASites(filepath=bad_file, auto_load=True)


@pytest.mark.unit
def test_gda_sites_load_existing_registry(tmp_path: Path) -> None:
    """Verifies load() populates sites registry from disk payload."""
    reg_file = tmp_path / "sites.json"
    payload = {
        "_name": "sites.json",
        "_path": "data/entities/sites.json",
        "schema_version": "1.0.0",
        "sites": [
            {
                "site_id": "SITE-00001",
                "site_type": "FACILITY",
                "name": "Carlisle Hospital",
                "aliases": ["Carlisle Hosp"],
                "location_id": "LOC-00006",
                "address": {"address_line_1": "402 W Louther St", "address_line_2": None, "postal_code": "17013", "coordinates": None},
                "notes": [],
                "last_updated": "2026-09-29T00:00:00Z"
            }
        ]
    }
    GDAUtil.save_json(reg_file, payload, create_backup=False)
    sites = GDASites(filepath=reg_file, auto_load=True)
    assert sites.count == 1
    assert sites.get_by_id("SITE-00001") is not None


@pytest.mark.unit
def test_gda_sites_refresh_discards_staged_mutations(tmp_path: Path) -> None:
    """Verifies refresh() reloads state from disk discarding in-memory changes."""
    reg_file = tmp_path / "sites.json"
    payload = {
        "_name": "sites.json",
        "sites": [{"site_id": "SITE-00001", "site_type": "FACILITY", "name": "Hospital", "location_id": "LOC-00001", "address": {}}]
    }
    GDAUtil.save_json(reg_file, payload, create_backup=False)
    sites = GDASites(filepath=reg_file, auto_load=True)
    sites.add(site_type="CHURCH", name="Zion", location_id="LOC-00001")
    assert sites.count == 2
    sites.refresh()
    assert sites.count == 1


@pytest.mark.unit
def test_gda_sites_get_by_id_missing_returns_none(tmp_path: Path) -> None:
    """Verifies get_by_id returns None for nonexistent IDs."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    assert sites.get_by_id("SITE-00999") is None


@pytest.mark.unit
def test_gda_sites_edit_updates_fields(tmp_path: Path) -> None:
    """Verifies edit() modifies name, site_type, address, and coordinates."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Carlisle Hospital", location_id="LOC-00006")
    sites.edit(sid, {
        "site_type": "CHURCH",
        "name": "Carlisle Regional Medical Center",
        "aliases": ["CRMC"],
        "location_id": "LOC-00006",
        "address": {
            "address_line_1": "361 Alexander Spring Rd",
            "address_line_2": "Suite 100",
            "postal_code": "17015",
            "coordinates": {"latitude": 40.1820, "longitude": -77.2105}
        },
        "notes": [{"note": "New facility built in 2006"}]
    })
    updated = sites.get_by_id(sid)
    assert updated["site_type"] == "CHURCH"
    assert updated["name"] == "Carlisle Regional Medical Center"
    assert updated["aliases"] == ["CRMC"]
    assert updated["address"]["address_line_2"] == "Suite 100"
    assert updated["address"]["coordinates"]["latitude"] == 40.1820
    assert len(updated["notes"]) == 1


@pytest.mark.unit
def test_gda_sites_edit_location_id_success(tmp_path: Path) -> None:
    """Verifies edit() successfully mutates location_id."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Clinic", location_id="LOC-00001")
    sites.edit(sid, {"location_id": "LOC-00002"})
    assert sites.get_by_id(sid)["location_id"] == "LOC-00002"


@pytest.mark.unit
def test_gda_sites_edit_noop_returns_false(tmp_path: Path) -> None:
    """Verifies edit() returns False when updates match existing attributes."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Clinic", location_id="LOC-00001", aliases=["C"])
    modified = sites.edit(sid, {"site_type": "FACILITY", "name": "Clinic", "location_id": "LOC-00001", "aliases": ["C"]})
    assert modified is False


@pytest.mark.unit
def test_gda_sites_edit_address_noop_leaves_clean() -> None:
    """Verifies edit() does not mark dirty when address attributes are identical."""
    sites = GDASites(filepath=Path("mock.json"), auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Clinic", location_id="LOC-00001", address_line_1="100 Main")
    sites._is_dirty = False
    modified = sites.edit(sid, {"address": {"address_line_1": "100 Main"}})
    assert modified is False
    assert sites.is_dirty is False


@pytest.mark.unit
def test_gda_sites_edit_overwrite_none_address(tmp_path: Path) -> None:
    """Verifies edit() clears address properties when overwrite_none is True."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Clinic", location_id="LOC-00001", address_line_1="100 Main")
    sites.edit(sid, {"address": {"address_line_1": None}}, overwrite_none=True)
    assert sites.get_by_id(sid)["address"]["address_line_1"] is None


@pytest.mark.unit
def test_gda_sites_edit_missing_site_raises(tmp_path: Path) -> None:
    """Verifies edit() raises KeyError when site does not exist."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    with pytest.raises(KeyError, match="Site 'SITE-00999' does not exist"):
        sites.edit("SITE-00999", {"name": "Name"})


@pytest.mark.unit
def test_gda_sites_edit_empty_name_raises(tmp_path: Path) -> None:
    """Verifies edit() raises ValueError when name is set to empty string."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Clinic", location_id="LOC-00001")
    with pytest.raises(ValueError, match="Site name must not be empty"):
        sites.edit(sid, {"name": "   "})


@pytest.mark.unit
def test_gda_sites_edit_invalid_type_raises(tmp_path: Path) -> None:
    """Verifies edit() raises ValueError when site_type is invalid."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Clinic", location_id="LOC-00001")
    with pytest.raises(ValueError, match="Invalid site_type 'INVALID'"):
        sites.edit(sid, {"site_type": "INVALID"})


@pytest.mark.unit
def test_gda_sites_delete_removes_entity(tmp_path: Path) -> None:
    """Verifies delete() unlinks site from memory and updates filtered subset."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid = sites.add(site_type="CEMETERY", name="Rolling Green Cemetery", location_id="LOC-00005")
    sites.set_filter(site_type="CEMETERY")
    deleted = sites.delete(sid)
    assert deleted is True
    assert sites.count == 0
    assert sites.filtered_count == 0


@pytest.mark.unit
def test_gda_sites_delete_when_id_not_in_active_filter() -> None:
    """Verifies delete() succeeds on an entity outside the currently active filter."""
    sites = GDASites(filepath=Path("mock.json"), auto_load=False)
    sid1 = sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-00001")
    sid2 = sites.add(site_type="CEMETERY", name="Cemetery", location_id="LOC-00001")
    sites.set_filter(site_type="FACILITY")
    deleted = sites.delete(sid2)
    assert deleted is True
    assert sid2 not in sites._sites


@pytest.mark.unit
def test_gda_sites_delete_nonexistent_returns_false(tmp_path: Path) -> None:
    """Verifies delete() returns False when site does not exist."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    assert sites.delete("SITE-00999") is False


@pytest.mark.unit
def test_gda_sites_search_with_location_and_type_filters(tmp_path: Path) -> None:
    """Verifies search() restricts by location_id and site_type simultaneously."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Harrisburg Hospital", location_id="LOC-00020")
    sites.add(site_type="FACILITY", name="Harrisburg State Hospital", location_id="LOC-00065")
    sites.add(site_type="CEMETERY", name="Harrisburg Cemetery", location_id="LOC-00020")

    matches = sites.search(query=None, location_id="LOC-00020", site_type="FACILITY")
    assert len(matches) == 1
    assert matches[0]["name"] == "Harrisburg Hospital"


@pytest.mark.unit
def test_gda_sites_search_has_coordinates_filter(tmp_path: Path) -> None:
    """Verifies search() filters by presence of coordinates."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Hospital With Coords", location_id="LOC-00001", coordinates={"latitude": 40.0, "longitude": -77.0})
    sites.add(site_type="FACILITY", name="Hospital Without Coords", location_id="LOC-00001")

    with_coords = sites.search(has_coordinates=True)
    assert len(with_coords) == 1
    assert with_coords[0]["name"] == "Hospital With Coords"


@pytest.mark.unit
def test_gda_sites_search_has_coordinates_false_filter(tmp_path: Path) -> None:
    """Verifies search() filters by absence of coordinates."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Hospital With Coords", location_id="LOC-00001", coordinates={"latitude": 40.0, "longitude": -77.0})
    sites.add(site_type="FACILITY", name="Hospital Without Coords", location_id="LOC-00001")

    without_coords = sites.search(has_coordinates=False)
    assert len(without_coords) == 1
    assert without_coords[0]["name"] == "Hospital Without Coords"


@pytest.mark.unit
def test_gda_sites_find_one_returns_highest_match(tmp_path: Path) -> None:
    """Verifies find_one returns the top-scoring entity dictionary."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Polyclinic Hospital", location_id="LOC-00020")
    match = sites.find_one("Polyclinic")
    assert match is not None
    assert match["site_id"] == "SITE-00001"


@pytest.mark.unit
def test_gda_sites_find_one_no_match_returns_none(tmp_path: Path) -> None:
    """Verifies find_one returns None when no entities match."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    assert sites.find_one("Nonexistent") is None


@pytest.mark.unit
def test_gda_sites_search_wildcard_matching(tmp_path: Path) -> None:
    """Verifies search() resolves glob patterns across site names."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Harrisburg Hospital", location_id="LOC-00020")
    sites.add(site_type="FACILITY", name="Harrisburg State Hospital", location_id="LOC-00065")
    matches = sites.search(query="*State*", use_fuzzy=False)
    assert len(matches) == 1
    assert matches[0]["site_id"] == "SITE-00002"


@pytest.mark.unit
def test_gda_sites_search_fuzzy_tolerance(tmp_path: Path) -> None:
    """Verifies search() identifies typo variations via SequenceMatcher ratio."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Polyclinic Hospital", location_id="LOC-00020")
    matches = sites.search(query="Polyclinc Hosptl", use_fuzzy=True, fuzzy_threshold=0.75)
    assert len(matches) == 1
    assert matches[0]["name"] == "Polyclinic Hospital"


@pytest.mark.unit
def test_gda_sites_set_filter_and_clear_filter(tmp_path: Path) -> None:
    """Verifies set_filter and clear_filter manage active view states."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Hospital A", location_id="LOC-00001")
    sites.add(site_type="CEMETERY", name="Cemetery B", location_id="LOC-00001")
    sites.set_filter(site_type="CEMETERY")
    assert sites.filtered_count == 1
    sites.clear_filter()
    assert sites.filtered_count == 2


@pytest.mark.unit
def test_gda_sites_set_filter_location_id(tmp_path: Path) -> None:
    """Verifies set_filter filters by location_id."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Hospital A", location_id="LOC-00001")
    sites.add(site_type="FACILITY", name="Hospital B", location_id="LOC-00002")
    sites.set_filter(location_id="LOC-00002")
    assert sites.filtered_count == 1
    assert sites.get_filtered()[0]["name"] == "Hospital B"


@pytest.mark.unit
def test_gda_sites_set_filter_name_pattern_and_predicate(tmp_path: Path) -> None:
    """Verifies set_filter filters by name glob pattern and custom predicate."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Carlisle General Hospital", location_id="LOC-00001")
    sites.add(site_type="FACILITY", name="Harrisburg Hospital", location_id="LOC-00002")

    cnt = sites.set_filter(name_pattern="*Carlisle*", predicate=lambda s: s["location_id"] == "LOC-00001")
    assert cnt == 1
    assert sites.get_filtered()[0]["name"] == "Carlisle General Hospital"


@pytest.mark.unit
def test_gda_sites_set_filter_alias_glob_matching() -> None:
    """Verifies set_filter matches name_pattern against aliases."""
    sites = GDASites(filepath=Path("mock.json"), auto_load=False)
    sites.add(site_type="FACILITY", name="Main Facility", location_id="LOC-00001", aliases=["Old County Asylum"])
    cnt = sites.set_filter(name_pattern="*Asylum*")
    assert cnt == 1
    assert sites.filtered_count == 1


@pytest.mark.unit
def test_gda_sites_update_filtered_batch(tmp_path: Path) -> None:
    """Verifies update_filtered modifies attributes across all active filter items."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sid1 = sites.add(site_type="CEMETERY", name="Cemetery One", location_id="LOC-00001")
    sid2 = sites.add(site_type="CEMETERY", name="Cemetery Two", location_id="LOC-00001")
    sites.add(site_type="FACILITY", name="Hospital Three", location_id="LOC-00001")
    sites.set_filter(site_type="CEMETERY")
    modified_count = sites.update_filtered({"location_id": "LOC-00050"})
    assert modified_count == 2
    assert sites.get_by_id(sid1)["location_id"] == "LOC-00050"
    assert sites.get_by_id(sid2)["location_id"] == "LOC-00050"


@pytest.mark.unit
def test_gda_sites_update_filtered_bypass_location_validation() -> None:
    """Verifies update_filtered accepts location update without validation when flag is False."""
    sites = GDASites(filepath=Path("mock.json"), auto_load=False)
    sid = sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-00001")
    sites.update_filtered({"location_id": "LOC-00099"}, validate_location=False)
    assert sites.get_by_id(sid)["location_id"] == "LOC-00099"


@pytest.mark.unit
def test_gda_sites_update_filtered_empty_returns_zero(tmp_path: Path) -> None:
    """Verifies update_filtered returns 0 when no records match filter."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-00001")
    sites.set_filter(site_type="CEMETERY")
    assert sites.update_filtered({"name": "Unmodified"}) == 0


@pytest.mark.unit
def test_gda_sites_dunder_protocols(tmp_path: Path) -> None:
    """Verifies __len__, __contains__, and __iter__ behaviors."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-00001")
    assert len(sites) == 1
    assert "SITE-00001" in sites
    assert "SITE-00099" not in sites
    items = list(sites)
    assert len(items) == 1
    assert items[0]["name"] == "Hospital"


@pytest.mark.unit
def test_gda_sites_dunder_iter_with_filter(tmp_path: Path) -> None:
    """Verifies __iter__ yields only items matching active filter."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-00001")
    sites.add(site_type="CEMETERY", name="Cemetery", location_id="LOC-00001")
    sites.set_filter(site_type="CEMETERY")
    items = list(sites)
    assert len(items) == 1
    assert items[0]["name"] == "Cemetery"


@pytest.mark.unit
def test_gda_sites_save_resets_dirty_state(tmp_path: Path) -> None:
    """Verifies save() to canonical path sets is_dirty to False."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    sites.add(site_type="FACILITY", name="Hospital", location_id="LOC-00001")
    assert sites.is_dirty is True
    sites.save(force=True, create_backup=False)
    assert sites.is_dirty is False


@pytest.mark.unit
def test_gda_sites_save_skips_when_clean_and_not_forced(tmp_path: Path) -> None:
    """Verifies save() returns False without writing when is_dirty is False and force is False."""
    reg_file = tmp_path / "sites.json"
    sites = GDASites(filepath=reg_file, auto_load=False)
    assert sites.save(force=False) is False


@pytest.mark.unit
def test_gda_sites_save_to_scratch_output_path(tmp_path: Path) -> None:
    """Verifies save(output_path=...) persists to scratch file leaving canonical path clean."""
    canonical_file = tmp_path / "canonical_sites.json"
    scratch_file = tmp_path / "scratch_sites.json"
    sites = GDASites(filepath=canonical_file, auto_load=False)
    sites.add(site_type="LANDMARK", name="Historic Depot", location_id="LOC-00010")
    sites.save(output_path=scratch_file, force=True)
    assert scratch_file.exists()
    assert not canonical_file.exists()