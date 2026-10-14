# Name: test_entity_locations.py
# Path: tools/lib/gdadomain/tests/test_entity_locations.py
# Version: 1.0.0+build.r1

"""Unit test suite validating GDALocations initialization, protocols, retrieval, mutation, and persistence.

Operational Role:
    Executes hermetic verification across all 7 functional groups for GDALocations (v1.2.0):
    - Group 1: IntrospectableMixin directory generation, public member inspection,
      safe missing-file defaults, corrupt JSON rejection, partitioned loading, and refresh discard logic.
    - Group 2: Collection protocols, active sized count, subscript retrieval,
      deep-copy memory isolation, and transparent graveyard redirection.
    - Group 3: Entity membership, multi-hop redirect resolution, circular loop guards,
      predecessor/successor navigation, and temporal date boundary validity.
    - Group 4: Record creation, strictly system-minted sequential LOC-XXXXX allocation
      via monotonic high-water mark, US state normalization, and canonical name building.
    - Group 5: Record updates, property validation, note addition/removal,
      and idempotent alias management.
    - Group 6: Deprecation, soft deletion, graveyard pointers, consolidation (merge), and site cascading.
    - Group 7: Multi-field search, fuzzy matching, structural auditing, and atomic save.

Test Structure & Protocol:
    - Atomized tests: 1:1 assertion mapping isolating individual contract rules.
    - Fully decorated: Explicit markers applied (smoke, unit, regression, integration).
    - Dependencies: Isolated pytest tmp_path fixtures and static golden/failure fixtures from conftest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from gdadomain.locations import GDALocations


# ==============================================================================
# GROUP 1: Introspection, Initialization & Disk Loading
# Note: Verification of IntrospectableMixin, safe missing-file handling, and loading
# ==============================================================================


@pytest.mark.unit
def test_help_directory_generation(capsys: Any, tmp_path: Path) -> None:
    """Verify locations.help() outputs all public members without listing private attributes."""
    empty_file = tmp_path / "empty_loc.json"
    locs = GDALocations(filepath=empty_file)
    locs.help()

    captured = capsys.readouterr().out
    assert "add" in captured
    assert "edit" in captured
    assert "delete" in captured
    assert "search" in captured
    assert "save" in captured
    assert "graveyard" in captured
    assert "resolve_id" in captured

    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    member_lines = [l for l in lines if l.startswith("-") or l.startswith("*")]
    for ml in member_lines:
        assert not ml.lstrip("- *").strip().startswith("_locations")
        assert not ml.lstrip("- *").strip().startswith("_graveyard")


@pytest.mark.smoke
@pytest.mark.unit
def test_help_member_signature(capsys: Any, tmp_path: Path) -> None:
    """Verify locations.help('add') prints call signature, parameter types, and docstring."""
    empty_file = tmp_path / "empty_loc.json"
    locs = GDALocations(filepath=empty_file)
    locs.help("add")

    captured = capsys.readouterr().out
    assert "add(" in captured
    assert "country" in captured
    assert "Add a new civil location entity" in captured


@pytest.mark.unit
def test_help_invalid_member(capsys: Any, tmp_path: Path) -> None:
    """Verify locations.help() gracefully handles unknown member names without exceptions."""
    empty_file = tmp_path / "empty_loc.json"
    locs = GDALocations(filepath=empty_file)
    locs.help("non_existent_method")

    captured = capsys.readouterr().out
    assert "not found" in captured or "No public member" in captured or "non_existent_method" in captured


@pytest.mark.unit
def test_init_missing_file_initializes_clean_state(tmp_path: Path) -> None:
    """Verify missing file initializes empty partitions and flags is_dirty as True."""
    non_existent = tmp_path / "missing_loc.json"
    locs = GDALocations(filepath=non_existent)

    assert len(locs) == 0
    assert len(locs.graveyard) == 0
    assert locs.total_count == 0
    assert locs.is_dirty is True


@pytest.mark.regression
@pytest.mark.unit
def test_load_corrupt_json_raises_exception(failure_fixture_syntax: Path) -> None:
    """Verify malformed JSON payload raises an exception during instantiation."""
    with pytest.raises(Exception):
        GDALocations(filepath=failure_fixture_syntax)


@pytest.mark.regression
@pytest.mark.unit
def test_load_corrupt_json_logs_error(failure_fixture_syntax: Path) -> None:
    """Verify malformed JSON payload logs error via GDALogger during instantiation."""
    with patch("gdadomain.locations.GDALogger.get_logger") as mock_logger_getter:
        mock_logger = mock_logger_getter.return_value
        with pytest.raises(Exception):
            GDALocations(filepath=failure_fixture_syntax)
        mock_logger.error.assert_called()


@pytest.mark.unit
def test_load_partitioning_active_and_graveyard(golden_fixture_file: Path) -> None:
    """Verify load partitions active records into _locations and graveyard tombstones."""
    locs = GDALocations(filepath=golden_fixture_file)

    assert locs.count == 40
    assert "LOC-00006" in locs
    assert "LOC-00101" in locs
    assert len(locs.graveyard) == 5
    assert "LOC-01300" in locs.graveyard
    assert "LOC-01301" in locs.graveyard
    assert "LOC-01302" in locs.graveyard
    assert "LOC-01303" in locs.graveyard
    assert "LOC-01304" in locs.graveyard
    assert locs.total_count == 45


@pytest.mark.regression
@pytest.mark.unit
def test_load_skips_empty_ids(failure_fixture_missing_id: Path) -> None:
    """Verify load skips records missing location_id payloads."""
    locs = GDALocations(filepath=failure_fixture_missing_id)
    assert "" not in locs
    assert "" not in locs.graveyard
    assert locs.count == 1
    assert "LOC-00006" in locs


@pytest.mark.unit
def test_refresh_discards_unstaged_mutations(golden_fixture_file: Path) -> None:
    """Verify refresh discards unstaged in-memory mutations and restores clean disk state."""
    locs = GDALocations(filepath=golden_fixture_file)
    initial_count = locs.count

    locs.add(country="USA", state_or_province="PA", local_jurisdiction="Temporary Borough")
    assert locs.is_dirty is True
    assert locs.count == initial_count + 1

    locs.refresh()
    assert locs.is_dirty is False
    assert locs.count == initial_count


@pytest.mark.unit
def test_refresh_discards_unstaged_deletions(golden_fixture_file: Path) -> None:
    """Verify refresh discards unstaged deletions and restores active records."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert "LOC-00006" in locs

    locs.delete("LOC-00006", hard_delete=True)
    assert "LOC-00006" not in locs
    assert locs.is_dirty is True

    locs.refresh()
    assert locs.is_dirty is False
    assert "LOC-00006" in locs


# ==============================================================================
# GROUP 2: Collection Protocols & Subscript Ergonomics
# Note: Verification of sized count, iteration isolation, membership, and subscript
# ==============================================================================


@pytest.mark.unit
def test_len_returns_active_count_only(golden_fixture_file: Path) -> None:
    """Verify len(locations) returns count of active locations, excluding graveyard tombstones."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert len(locs) == 40
    assert locs.total_count == 45


@pytest.mark.unit
def test_iter_yields_active_only_with_memory_isolation(golden_fixture_file: Path) -> None:
    """Verify __iter__ traversal yields only active records and enforces deep-copy isolation."""
    locs = GDALocations(filepath=golden_fixture_file)
    yielded_ids = []

    for loc in locs:
        yielded_ids.append(loc["location_id"])
        if loc["location_id"] == "LOC-00006":
            loc["canonical_name"] = "Mutated In Iteration"

    assert "LOC-00006" in yielded_ids
    assert "LOC-01300" not in yielded_ids
    assert len(yielded_ids) == 40
    assert locs["LOC-00006"]["canonical_name"] != "Mutated In Iteration"


@pytest.mark.unit
def test_iter_empty_registry_yields_zero_items(tmp_path: Path) -> None:
    """Verify __iter__ traversal over an empty registry yields zero items."""
    locs = GDALocations(filepath=tmp_path / "empty.json")
    items = list(locs)
    assert len(items) == 0


@pytest.mark.unit
def test_contains_active_membership(golden_fixture_file: Path) -> None:
    """Verify 'in' operator returns True for active registered locations."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert "LOC-00006" in locs


@pytest.mark.unit
def test_contains_graveyard_returns_false(golden_fixture_file: Path) -> None:
    """Verify 'in' operator returns False for graveyard tombstones."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert "LOC-01300" not in locs


@pytest.mark.unit
def test_contains_unregistered_and_non_string_returns_false(golden_fixture_file: Path) -> None:
    """Verify 'in' operator returns False for unregistered IDs and non-string queries."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert ("LOC-99999" in locs) is False
    assert (12345 in locs) is False
    assert (None in locs) is False


@pytest.mark.unit
def test_getitem_active_retrieval_returns_isolated_record(golden_fixture_file: Path) -> None:
    """Verify subscript access retrieves expected active entity payload."""
    locs = GDALocations(filepath=golden_fixture_file)
    record = locs["LOC-00006"]
    assert record["location_id"] == "LOC-00006"
    assert "Carlisle" in record["canonical_name"]


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_transparent_graveyard_redirect(golden_fixture_file: Path) -> None:
    """Verify subscript access transparently resolves single-hop graveyard redirect."""
    locs = GDALocations(filepath=golden_fixture_file)
    record = locs["LOC-01300"]
    assert record["location_id"] == "LOC-00006"
    assert "Carlisle" in record["canonical_name"]


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_transparent_multihop_graveyard_redirect(golden_fixture_file: Path) -> None:
    """Verify subscript access transparently resolves two-hop graveyard redirect."""
    locs = GDALocations(filepath=golden_fixture_file)
    record = locs["LOC-01304"]
    assert record["location_id"] == "LOC-00205"
    assert "Richmond" in record["canonical_name"]


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_missing_raises_key_error(golden_fixture_file: Path) -> None:
    """Verify subscript access for non-existent location ID raises KeyError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(KeyError) as exc_info:
        _ = locs["LOC-99999"]
    assert "LOC-99999" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_defunct_without_replacement_raises_key_error(golden_fixture_file: Path) -> None:
    """Verify subscript access on terminal defunct tombstone without replacement raises KeyError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(KeyError) as exc_info:
        _ = locs["LOC-01301"]
    assert "LOC-01301" in str(exc_info.value)


# ==============================================================================
# GROUP 3: Entity Retrieval, Membership & Graveyard Traversal
# Note: Verification of exists, get_by_id, redirects, temporal validity, and lineage
# ==============================================================================


@pytest.mark.unit
def test_exists_boundary_modes(golden_fixture_file: Path) -> None:
    """Verify exists distinguishes active and graveyard records under explicit flags."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.exists("LOC-00006", include_graveyard=False) is True
    assert locs.exists("LOC-01300", include_graveyard=False) is False
    assert locs.exists("LOC-01300", include_graveyard=True) is True
    assert locs.exists("LOC-99999", include_graveyard=True) is False


@pytest.mark.unit
def test_get_by_id_memory_isolation(golden_fixture_file: Path) -> None:
    """Verify modifying record returned by get_by_id does not leak into internal manager memory."""
    locs = GDALocations(filepath=golden_fixture_file)
    record = locs.get_by_id("LOC-00006")
    assert record is not None
    record["canonical_name"] = "Leaked Carlisle"

    fresh_record = locs.get_by_id("LOC-00006")
    assert fresh_record is not None
    assert "Leaked Carlisle" not in fresh_record["canonical_name"]


@pytest.mark.unit
def test_get_by_id_graveyard_unresolved_returns_tombstone(golden_fixture_file: Path) -> None:
    """Verify get_by_id returns raw graveyard record when redirection is disabled."""
    locs = GDALocations(filepath=golden_fixture_file)
    tombstone = locs.get_by_id("LOC-01300", include_graveyard=True, resolve_redirects=False)
    assert tombstone is not None
    assert tombstone["location_id"] == "LOC-01300"
    assert tombstone["superseded_by"] == "LOC-00006"


@pytest.mark.unit
def test_iter_graveyard_yields_all_tombstones(golden_fixture_file: Path) -> None:
    """Verify iter_graveyard yields only soft-deleted tombstones."""
    locs = GDALocations(filepath=golden_fixture_file)
    graveyard_ids = {item["location_id"] for item in locs.iter_graveyard()}
    assert graveyard_ids == {"LOC-01300", "LOC-01301", "LOC-01302", "LOC-01303", "LOC-01304"}


@pytest.mark.unit
def test_iter_all_yields_complete_registry(golden_fixture_file: Path) -> None:
    """Verify iter_all yields combined active and graveyard inventory."""
    locs = GDALocations(filepath=golden_fixture_file)
    all_ids = {item["location_id"] for item in locs.iter_all()}
    assert len(all_ids) == 45
    assert "LOC-00006" in all_ids
    assert "LOC-01300" in all_ids


@pytest.mark.unit
def test_resolve_id_single_hop(golden_fixture_file: Path) -> None:
    """Verify resolve_id traces single-hop deprecation chains."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.resolve_id("LOC-01300") == "LOC-00006"
    assert locs.resolve_id("LOC-01302") == "LOC-00312"


@pytest.mark.regression
@pytest.mark.unit
def test_resolve_id_transitive_multihop(golden_fixture_file: Path) -> None:
    """Verify resolve_id traces two-hop deprecation chain."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.resolve_id("LOC-01304") == "LOC-00205"


@pytest.mark.regression
@pytest.mark.unit
def test_resolve_id_circular_protection(failure_fixture_circular_graveyard: Path) -> None:
    """Verify resolve_id detects circular graveyard loops safely and returns None."""
    locs = GDALocations(filepath=failure_fixture_circular_graveyard)
    assert locs.resolve_id("LOC-03000") is None
    assert locs.resolve_id("LOC-03001") is None


@pytest.mark.unit
def test_resolve_id_terminal_defunct_without_replacement_returns_none(golden_fixture_file: Path) -> None:
    """Verify resolve_id returns None when a tombstone lacks a superseded_by pointer."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.resolve_id("LOC-01301") is None


@pytest.mark.unit
def test_resolve_id_nonexistent_returns_none(golden_fixture_file: Path) -> None:
    """Verify resolve_id returns None for an unregistered ID."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.resolve_id("LOC-99999") is None


@pytest.mark.unit
def test_get_predecessor_and_successor_retrieval(tmp_path: Path) -> None:
    """Verify get_predecessor and get_successor traverse temporal validity links."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    p_id = locs.add(country="USA", state_or_province="PA", county="Chester")
    c_id = locs.add(country="USA", state_or_province="PA", county="Lancaster", predecessor_location_id=p_id)
    s_id = locs.add(country="USA", state_or_province="PA", county="Cumberland")
    locs.edit(c_id, {"temporal_validity": {"successor_location_id": s_id}})

    pred = locs.get_predecessor(c_id)
    succ = locs.get_successor(c_id)

    assert pred is not None and pred["location_id"] == p_id
    assert succ is not None and succ["location_id"] == s_id
    assert locs.get_predecessor("LOC-99999") is None
    assert locs.get_successor("LOC-99999") is None


@pytest.mark.unit
def test_is_valid_at_date_before_established_returns_false(golden_fixture_file: Path) -> None:
    """Verify is_valid_at_date returns False when query date is prior to establishment."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.is_valid_at_date("LOC-00006", "1740") is False


@pytest.mark.unit
def test_is_valid_at_date_within_active_boundaries_returns_true(golden_fixture_file: Path) -> None:
    """Verify is_valid_at_date returns True when query date falls within valid range."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.is_valid_at_date("LOC-00006", "1760-05-12") is True


@pytest.mark.unit
def test_is_valid_at_date_unregistered_location_returns_false(golden_fixture_file: Path) -> None:
    """Verify is_valid_at_date returns False for an unregistered location ID."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.is_valid_at_date("LOC-99999", "1800") is False


@pytest.mark.unit
def test_is_valid_at_date_dissolved_boundary(tmp_path: Path) -> None:
    """Verify is_valid_at_date respects dissolution boundary when present."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    lid = locs.add(
        country="USA",
        state_or_province="PA",
        date_established="1750",
        date_dissolved="1800",
    )
    assert locs.is_valid_at_date(lid, "1775") is True
    assert locs.is_valid_at_date(lid, "1825") is False


@pytest.mark.unit
def test_is_valid_at_date_without_established_or_dissolved(tmp_path: Path) -> None:
    """Verify is_valid_at_date returns True when record has no dates recorded."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    lid = locs.add(country="USA", state_or_province="PA", local_jurisdiction="Undated Settlement")
    assert locs.is_valid_at_date(lid, "1800") is True


@pytest.mark.unit
def test_is_valid_at_date_unparseable_target_date_returns_true(tmp_path: Path) -> None:
    """Verify is_valid_at_date returns True when target date string cannot yield a year."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    lid = locs.add(country="USA", state_or_province="PA", date_established="1750")
    assert locs.is_valid_at_date(lid, "circa early spring") is True


# ==============================================================================
# GROUP 4: Record Creation (add) & Monotonic Minting
# Note: Verification of auto-minting, US state normalization, canonical names, and validation
# ==============================================================================


@pytest.mark.unit
def test_add_auto_mint_initial_and_monotonic_increment(tmp_path: Path) -> None:
    """Verify auto-minting allocates LOC-00001 initially and increments monotonically."""
    locs = GDALocations(filepath=tmp_path / "empty_loc.json")
    id1 = locs.add(country="USA", state_or_province="PA", local_jurisdiction="Carlisle")
    id2 = locs.add(country="USA", state_or_province="PA", local_jurisdiction="Harrisburg")

    assert id1 == "LOC-00001"
    assert id2 == "LOC-00002"
    assert id1 in locs
    assert id2 in locs


@pytest.mark.unit
def test_add_auto_mint_monotonic_from_golden_high_water_mark(golden_fixture_file: Path) -> None:
    """Verify auto-minting continues beyond highest ID in golden registry."""
    locs = GDALocations(filepath=golden_fixture_file)
    new_id = locs.add(country="USA", state_or_province="PA", local_jurisdiction="Mechanicsburg")
    assert new_id == "LOC-01305"
    assert new_id in locs


@pytest.mark.regression
@pytest.mark.unit
def test_add_empty_country_raises_value_error(tmp_path: Path) -> None:
    """Verify adding a location with empty country string raises ValueError."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    with pytest.raises(ValueError, match="Country must not be empty"):
        locs.add(country="   ")


@pytest.mark.regression
@pytest.mark.unit
def test_add_invalid_operational_status_raises_value_error(tmp_path: Path) -> None:
    """Verify adding a location with invalid operational_status raises ValueError."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    with pytest.raises(ValueError, match="Invalid operational_status"):
        locs.add(country="USA", operational_status="NON_EXISTENT_STATUS")


@pytest.mark.regression
@pytest.mark.unit
def test_add_malformed_predecessor_id_raises_value_error(tmp_path: Path) -> None:
    """Verify malformed predecessor identifier raises ValueError."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    with pytest.raises(ValueError, match="Malformed predecessor_location_id"):
        locs.add(country="USA", predecessor_location_id="INVALID-PRED")


@pytest.mark.regression
@pytest.mark.unit
def test_add_malformed_successor_id_raises_value_error(tmp_path: Path) -> None:
    """Verify malformed successor identifier raises ValueError."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    with pytest.raises(ValueError, match="Malformed successor_location_id"):
        locs.add(country="USA", successor_location_id="INVALID-SUCC")


@pytest.mark.unit
def test_normalize_state_non_us_and_unknown() -> None:
    """Verify normalize_state handles international and unrecognized regions."""
    assert GDALocations.normalize_state("Germany", "Bavaria") == "Bavaria"
    assert GDALocations.normalize_state("USA", "UnknownTerritory") == "UnknownTerritory"
    assert GDALocations.normalize_state("USA", None) is None


@pytest.mark.unit
def test_build_canonical_name_combinations() -> None:
    """Verify build_canonical_name handles varied component subsets."""
    res1 = GDALocations.build_canonical_name(country="USA", county="Cumberland County")
    assert res1 == "Cumberland County, USA"

    res2 = GDALocations.build_canonical_name(country="", local_jurisdiction="Carlisle")
    assert res2 == "Carlisle"


@pytest.mark.unit
def test_build_canonical_name_all_empty_parts_returns_empty_string() -> None:
    """Verify build_canonical_name returns empty string when all parts are empty."""
    assert GDALocations.build_canonical_name(country="", state_or_province=None, county=None, local_jurisdiction=None) == ""


@pytest.mark.unit
def test_add_input_memory_isolation(tmp_path: Path) -> None:
    """Verify mutating caller inputs after add() does not affect internal store."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    aliases = ["Initial Alias"]
    notes = [{"text": "Original note text"}]

    lid = locs.add(country="USA", state_or_province="PA", aliases=aliases, notes=notes)
    aliases.append("Injected Alias")
    notes[0]["text"] = "Mutated note text"

    record = locs[lid]
    assert record["aliases"] == ["Initial Alias"]
    assert record["notes"][0]["note_text"] == "Original note text"


@pytest.mark.regression
@pytest.mark.unit
def test_add_omitted_boundaries_and_non_string_aliases(tmp_path: Path) -> None:
    """Verify add handles non-string elements in aliases and omitted boundary strings."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    lid = locs.add(
        country="USA",
        county=None,
        local_jurisdiction=None,
        canonical_name="Explicit Unique Name",
        aliases=["Valid Alias", "  ", 1234, None],  # type: ignore[list-item]
        predecessor_location_id=None,
        successor_location_id=None,
    )
    rec = locs[lid]
    assert rec["canonical_name"] == "Explicit Unique Name"
    assert rec["aliases"] == ["Valid Alias"]
    assert rec["jurisdiction"]["county"] is None
    assert rec["jurisdiction"]["local_jurisdiction"] is None
    assert rec["temporal_validity"]["predecessor_location_id"] is None
    assert rec["temporal_validity"]["successor_location_id"] is None


@pytest.mark.unit
def test_add_with_valid_successor_and_whitespace_boundaries(tmp_path: Path) -> None:
    """Verify add successfully links valid successor_location_id and ignores whitespace boundaries."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    target_id = locs.add(country="USA", state_or_province="PA")
    lid = locs.add(
        country="USA",
        county="   ",
        local_jurisdiction="   ",
        successor_location_id=target_id,
    )
    rec = locs[lid]
    assert rec["jurisdiction"]["county"] is None
    assert rec["jurisdiction"]["local_jurisdiction"] is None
    assert rec["temporal_validity"]["successor_location_id"] == target_id


# ==============================================================================
# GROUP 5: Record Updates, Note Operations & Alias Management
# Note: Verification of edit mutations, dirty state, notes, and aliases
# ==============================================================================


@pytest.mark.unit
def test_edit_scalar_fields_and_dirty_flag(golden_fixture_file: Path) -> None:
    """Verify editing scalar fields updates record and marks manager dirty."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.is_dirty is False

    modified = locs.edit("LOC-00006", {"operational_status": "HISTORICAL"})
    assert modified is True
    assert locs["LOC-00006"]["operational_status"] == "HISTORICAL"
    assert locs.is_dirty is True


@pytest.mark.unit
def test_edit_canonical_name_updates_record_and_flags_dirty(golden_fixture_file: Path) -> None:
    """Verify edit updates canonical_name directly."""
    locs = GDALocations(filepath=golden_fixture_file)
    novel_name = "Historic Borough of Carlisle, Cumberland County, Pennsylvania, USA"
    modified = locs.edit("LOC-00006", {"canonical_name": novel_name})
    assert modified is True
    assert locs["LOC-00006"]["canonical_name"] == novel_name


@pytest.mark.regression
@pytest.mark.unit
def test_edit_missing_and_graveyard_records_raises_key_error(golden_fixture_file: Path) -> None:
    """Verify editing non-existent or graveyard records raises KeyError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(KeyError, match="does not exist in registry"):
        locs.edit("LOC-99999", {"canonical_name": "Ghost"})

    with pytest.raises(KeyError, match="Cannot edit deprecated location"):
        locs.edit("LOC-01300", {"canonical_name": "Resurrected"})


@pytest.mark.regression
@pytest.mark.unit
def test_edit_empty_canonical_name_raises_value_error(golden_fixture_file: Path) -> None:
    """Verify editing with empty canonical_name raises ValueError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(ValueError, match="canonical_name must not be empty"):
        locs.edit("LOC-00006", {"canonical_name": "   "})


@pytest.mark.regression
@pytest.mark.unit
def test_edit_invalid_operational_status_raises_value_error(golden_fixture_file: Path) -> None:
    """Verify editing with invalid operational_status raises ValueError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(ValueError, match="Invalid operational_status"):
        locs.edit("LOC-00006", {"operational_status": "BAD_STATUS"})


@pytest.mark.regression
@pytest.mark.unit
def test_edit_disallowed_property_raises_value_error(golden_fixture_file: Path) -> None:
    """Verify attempting to edit disallowed property raises ValueError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(ValueError, match="Disallowed property updates for location"):
        locs.edit("LOC-00006", {"unauthorized_field": "disallowed_value"})


@pytest.mark.unit
def test_edit_partial_updates_omitting_aliases(golden_fixture_file: Path) -> None:
    """Verify edit payload omitting aliases executes safely."""
    locs = GDALocations(filepath=golden_fixture_file)
    success = locs.edit("LOC-00006", {"notes": [{"note_text": "Freshly audited records."}]})
    assert success is True
    assert locs["LOC-00006"]["notes"][0]["note_text"] == "Freshly audited records."


@pytest.mark.unit
def test_edit_aliases_with_empty_list_clears_aliases(tmp_path: Path) -> None:
    """Verify edit with aliases=[] clears existing aliases on record."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    lid = locs.add(country="USA", aliases=["Alias One", "Alias Two"])
    assert len(locs[lid]["aliases"]) == 2

    modified = locs.edit(lid, {"aliases": []})
    assert modified is True
    assert locs[lid]["aliases"] == []


@pytest.mark.unit
def test_edit_operational_status_same_value_does_not_mutate(tmp_path: Path) -> None:
    """Verify editing operational_status with identical value evaluates to no modification."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    lid = locs.add(country="USA", operational_status="ACTIVE")
    modified = locs.edit(lid, {"operational_status": "ACTIVE"})
    assert modified is False


@pytest.mark.unit
def test_edit_jurisdiction_partial_components_preserves_state(golden_fixture_file: Path) -> None:
    """Verify edit jurisdiction updates partial keys preserving others."""
    locs = GDALocations(filepath=golden_fixture_file)
    success = locs.edit("LOC-00006", {"jurisdiction": {"local_jurisdiction": "New Borough"}})
    assert success is True
    rec = locs["LOC-00006"]
    assert rec["jurisdiction"]["local_jurisdiction"] == "New Borough"
    assert rec["jurisdiction"]["county"] == "Cumberland"
    assert rec["jurisdiction"]["state_or_province"] == "Pennsylvania"


@pytest.mark.unit
def test_edit_jurisdiction_normalizes_us_state(tmp_path: Path) -> None:
    """Verify editing jurisdiction normalizes state abbreviation to full name."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    lid = locs.add(country="USA", state_or_province="Virginia")
    success = locs.edit(lid, {"jurisdiction": {"state_or_province": "PA"}})
    assert success is True
    assert locs[lid]["jurisdiction"]["state_or_province"] == "Pennsylvania"


@pytest.mark.unit
def test_edit_jurisdiction_and_temporal_subobjects(golden_fixture_file: Path) -> None:
    """Verify editing jurisdiction and temporal fields mutates correctly."""
    locs = GDALocations(filepath=golden_fixture_file)
    success = locs.edit(
        "LOC-00006",
        {
            "jurisdiction": {"country": "USA", "county": "Cumberland", "local_jurisdiction": "Carlisle Town"},
            "temporal_validity": {"date_established": "1751-01-27"},
            "operational_status": "HISTORICAL",
            "aliases": ["Carlisle Borough", "Letort"],
            "notes": [{"note_text": "Fresh survey records."}],
        },
    )
    assert success is True
    rec = locs["LOC-00006"]
    assert rec["jurisdiction"]["local_jurisdiction"] == "Carlisle Town"
    assert rec["temporal_validity"]["date_established"] == "1751-01-27"
    assert rec["operational_status"] == "HISTORICAL"
    assert "Letort" in rec["aliases"]
    assert rec["notes"][0]["note_text"] == "Fresh survey records."


@pytest.mark.unit
def test_edit_overwrite_none_behavior(golden_fixture_file: Path) -> None:
    """Verify overwrite_none=True clears fields, whereas overwrite_none=False preserves them."""
    locs = GDALocations(filepath=golden_fixture_file)
    locs.edit("LOC-00006", {"jurisdiction": {"local_jurisdiction": None, "state_or_province": None}}, overwrite_none=False)
    assert locs["LOC-00006"]["jurisdiction"]["local_jurisdiction"] is not None
    assert locs["LOC-00006"]["jurisdiction"]["state_or_province"] is not None

    locs.edit("LOC-00006", {"jurisdiction": {"local_jurisdiction": None}}, overwrite_none=True)
    assert locs["LOC-00006"]["jurisdiction"]["local_jurisdiction"] is None


@pytest.mark.unit
def test_edit_temporal_validity_overwrite_none_clears_existing_value(tmp_path: Path) -> None:
    """Verify edit clears temporal validity property when value is None and overwrite_none=True."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    lid = locs.add(country="USA", date_established="1750")
    assert locs[lid]["temporal_validity"]["date_established"] == "1750"

    modified = locs.edit(lid, {"temporal_validity": {"date_established": None}}, overwrite_none=True)
    assert modified is True
    assert locs[lid]["temporal_validity"]["date_established"] is None


@pytest.mark.unit
def test_edit_identical_values_returns_false(golden_fixture_file: Path) -> None:
    """Verify editing with identical field values returns False without marking manager dirty."""
    locs = GDALocations(filepath=golden_fixture_file)
    current_name = locs["LOC-00006"]["canonical_name"]
    modified = locs.edit("LOC-00006", {"canonical_name": current_name})
    assert modified is False


@pytest.mark.unit
def test_edit_inline_deprecation_dispatch(golden_fixture_file: Path) -> None:
    """Verify passing is_deprecated=True in edit updates dispatches to soft deletion."""
    locs = GDALocations(filepath=golden_fixture_file)
    locs.edit("LOC-00006", {"is_deprecated": True, "superseded_by": "LOC-00101"})
    assert "LOC-00006" not in locs
    assert "LOC-00006" in locs.graveyard
    assert locs.graveyard["LOC-00006"]["superseded_by"] == "LOC-00101"


@pytest.mark.unit
def test_add_and_remove_note_lifecycle(golden_fixture_file: Path) -> None:
    """Verify add_note auto-mints note_id, removes by note_id, and renumbers sequentially."""
    locs = GDALocations(filepath=golden_fixture_file)
    minted_id_1 = locs.add_note("LOC-00006", "First note.")
    minted_id_2 = locs.add_note("LOC-00006", "Second note.")
    assert minted_id_1 == "NOT-00001"
    assert minted_id_2 == "NOT-00002"

    removed = locs.remove_note("LOC-00006", minted_id_1)
    assert removed is True
    notes = locs["LOC-00006"]["notes"]
    assert len(notes) == 1
    assert notes[0]["note_id"] == "NOT-00001"
    assert notes[0]["note_text"] == "Second note."


@pytest.mark.unit
def test_add_note_invalid_type_raises_error(golden_fixture_file: Path) -> None:
    """Verify add_note rejects unapproved note_type strings."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(ValueError, match="Invalid note_type"):
        locs.add_note("LOC-00006", "Valid note text", note_type="INVALID_VOCAB_TYPE")


@pytest.mark.regression
@pytest.mark.unit
def test_remove_note_unregistered_location_raises_key_error(golden_fixture_file: Path) -> None:
    """Verify calling remove_note on an unregistered location raises KeyError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(KeyError, match="Active location ID 'LOC-99999' not found"):
        locs.remove_note("LOC-99999", "NOT-00001")


@pytest.mark.unit
def test_remove_note_missing_id_returns_false(golden_fixture_file: Path) -> None:
    """Verify remove_note on an unrecorded note_id returns False."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.remove_note("LOC-00006", "NOT-99999") is False


@pytest.mark.regression
@pytest.mark.unit
def test_add_note_missing_location_raises_key_error(golden_fixture_file: Path) -> None:
    """Verify calling add_note on missing location ID raises KeyError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(KeyError):
        locs.add_note("LOC-99999", "Some note text")


@pytest.mark.regression
@pytest.mark.unit
def test_add_note_empty_text_raises_value_error(golden_fixture_file: Path) -> None:
    """Verify calling add_note with empty text raises ValueError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(ValueError, match="non-empty string"):
        locs.add_note("LOC-00006", "   ")


@pytest.mark.unit
def test_alias_management_lifecycle(golden_fixture_file: Path) -> None:
    """Verify add_alias and remove_alias manage alternate names idempotently."""
    locs = GDALocations(filepath=golden_fixture_file)
    novel_alias = "County Seat of Cumberland"

    assert locs.add_alias("LOC-00006", novel_alias) is True
    assert novel_alias in locs["LOC-00006"]["aliases"]
    assert locs.add_alias("LOC-00006", novel_alias) is False

    assert locs.remove_alias("LOC-00006", novel_alias) is True
    assert novel_alias not in locs["LOC-00006"]["aliases"]


@pytest.mark.regression
@pytest.mark.unit
def test_add_alias_unregistered_location_raises_key_error(golden_fixture_file: Path) -> None:
    """Verify add_alias on an unregistered location raises KeyError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(KeyError, match="Location 'LOC-99999' does not exist"):
        locs.add_alias("LOC-99999", "Valid Alias")


@pytest.mark.regression
@pytest.mark.unit
def test_remove_alias_unregistered_location_raises_key_error(golden_fixture_file: Path) -> None:
    """Verify remove_alias on an unregistered location raises KeyError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(KeyError, match="Location 'LOC-99999' does not exist"):
        locs.remove_alias("LOC-99999", "Valid Alias")


@pytest.mark.unit
def test_remove_alias_unlisted_alias_returns_false(golden_fixture_file: Path) -> None:
    """Verify remove_alias on an unlisted alias returns False."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.remove_alias("LOC-00006", "Unlisted Alias") is False


@pytest.mark.unit
def test_alias_invalid_values_return_false(golden_fixture_file: Path) -> None:
    """Verify empty or non-string aliases return False safely."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.add_alias("LOC-00006", "   ") is False
    assert locs.remove_alias("LOC-00006", "   ") is False


# ==============================================================================
# GROUP 6: Deprecation (delete), Consolidation (merge) & Cascading
# Note: Verification of soft-deletes, graveyard pointers, merge logic, and cascading
# ==============================================================================


@pytest.mark.unit
def test_delete_nonexistent_location_returns_false(golden_fixture_file: Path) -> None:
    """Verify delete returns False when target location does not exist."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.delete("LOC-99999") is False


@pytest.mark.unit
def test_delete_soft_transitions_to_graveyard(golden_fixture_file: Path) -> None:
    """Verify soft delete moves active location to graveyard partition."""
    locs = GDALocations(filepath=golden_fixture_file)
    initial_active = locs.count
    initial_total = locs.total_count

    success = locs.delete("LOC-00006", hard_delete=False)
    assert success is True
    assert "LOC-00006" not in locs
    assert "LOC-00006" in locs.graveyard
    assert locs.count == initial_active - 1
    assert locs.total_count == initial_total


@pytest.mark.regression
@pytest.mark.unit
def test_delete_invalid_superseded_by_syntax_raises_value_error(golden_fixture_file: Path) -> None:
    """Verify non-conforming superseded_by format raises ValueError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(ValueError, match="must conform to"):
        locs.delete("LOC-00006", superseded_by="INVALID-ID-PATTERN")


@pytest.mark.regression
@pytest.mark.unit
def test_delete_unregistered_superseded_target_raises_key_error(golden_fixture_file: Path) -> None:
    """Verify superseded_by target pointing to non-existent ID raises KeyError."""
    locs = GDALocations(filepath=golden_fixture_file)
    with pytest.raises(KeyError, match="Target superseded_by location_id .* not found"):
        locs.delete("LOC-00006", superseded_by="LOC-99999")


@pytest.mark.unit
def test_delete_already_graveyard_updates_pointer(golden_fixture_file: Path) -> None:
    """Verify calling delete on an existing tombstone updates its superseded_by pointer."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.graveyard["LOC-01301"]["superseded_by"] is None

    success = locs.delete("LOC-01301", superseded_by="LOC-00006")
    assert success is True
    assert locs.graveyard["LOC-01301"]["superseded_by"] == "LOC-00006"
    assert locs.is_dirty is True


@pytest.mark.unit
def test_delete_existing_tombstone_without_superseded_by_noop(golden_fixture_file: Path) -> None:
    """Verify calling delete on existing tombstone without new target is safe no-op returning True."""
    locs = GDALocations(filepath=golden_fixture_file)
    success = locs.delete("LOC-01301", hard_delete=False, superseded_by=None)
    assert success is True


@pytest.mark.unit
def test_delete_hard_purges_permanently(golden_fixture_file: Path) -> None:
    """Verify hard_delete=True permanently evicts location from memory."""
    locs = GDALocations(filepath=golden_fixture_file)
    initial_total = locs.total_count

    success = locs.delete("LOC-00006", hard_delete=True)
    assert success is True
    assert "LOC-00006" not in locs
    assert "LOC-00006" not in locs.graveyard
    assert locs.total_count == initial_total - 1


@pytest.mark.unit
def test_merge_locations_consolidates_records_and_cascades_sites(
    golden_fixture_file: Path, mock_sites: Any
) -> None:
    """Verify merge_locations moves secondaries to graveyard and repoints sites."""
    locs = GDALocations(filepath=golden_fixture_file)
    lid_p = "LOC-00006"
    lid_s1 = locs.add(country="USA", state_or_province="PA", county="Cumberland", canonical_name="Old Carlisle Borough")
    lid_s2 = locs.add(country="USA", state_or_province="PA", local_jurisdiction="Carlisle", canonical_name="Borough of Carlisle")

    merged = locs.merge_locations(lid_p, lid_s1, lid_s2, sites_provider=mock_sites, keep_secondary_aliases=True)

    assert merged["location_id"] == lid_p
    assert "Old Carlisle Borough" in merged["aliases"]
    assert "Borough of Carlisle" in merged["aliases"]
    assert lid_s1 not in locs
    assert lid_s2 not in locs
    assert lid_s1 in locs.graveyard
    assert lid_s2 in locs.graveyard
    assert locs.graveyard[lid_s1]["superseded_by"] == lid_p
    assert locs.graveyard[lid_s2]["superseded_by"] == lid_p

    assert len(mock_sites.repointed_calls) == 1
    assert mock_sites.repointed_calls[0] == (lid_p, [lid_s1, lid_s2])


@pytest.mark.unit
def test_merge_locations_backfills_missing_jurisdiction_temporal_and_notes(tmp_path: Path) -> None:
    """Verify merge_locations backfills missing primary jurisdiction/temporal fields and copies notes."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    primary_id = locs.add(country="USA")
    secondary_notes = [{"text": "Copied historical note", "type": "HISTORICAL"}]
    secondary_id = locs.add(
        country="USA",
        state_or_province="PA",
        county="Franklin",
        local_jurisdiction="Chambersburg",
        date_established="1764",
        notes=secondary_notes,
    )

    merged = locs.merge_locations(primary_id, secondary_id)
    assert merged["jurisdiction"]["county"] == "Franklin"
    assert merged["jurisdiction"]["local_jurisdiction"] == "Chambersburg"
    assert merged["temporal_validity"]["date_established"] == "1764"
    assert any(n["note_text"] == "Copied historical note" for n in merged["notes"])


@pytest.mark.unit
def test_merge_locations_secondary_note_unlisted_type_defaults_to_research(tmp_path: Path) -> None:
    """Verify merge_locations defaults secondary notes with unapproved types to RESEARCH."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    p_id = locs.add(country="USA", state_or_province="PA", local_jurisdiction="Primary Place")
    s_notes = [{"text": "Field record note", "type": "UNAPPROVED_CUSTOM_CATEGORY"}]
    s_id = locs.add(country="USA", state_or_province="PA", local_jurisdiction="Secondary Place", notes=s_notes)

    merged = locs.merge_locations(p_id, s_id)
    transferred = [n for n in merged["notes"] if n["note_text"] == "Field record note"]
    assert len(transferred) == 1
    assert transferred[0]["note_type"] == "RESEARCH"


@pytest.mark.unit
def test_merge_locations_discards_secondary_aliases_when_flag_false(golden_fixture_file: Path) -> None:
    """Verify merge_locations with keep_secondary_aliases=False does not copy secondary aliases."""
    locs = GDALocations(filepath=golden_fixture_file)
    lid_p = "LOC-00006"
    lid_s = locs.add(
        country="USA",
        state_or_province="PA",
        aliases=["Disposable Secondary Alias"],
        canonical_name="Old Town Name",
    )

    merged = locs.merge_locations(lid_p, lid_s, keep_secondary_aliases=False)
    assert "Disposable Secondary Alias" not in merged["aliases"]
    assert "Old Town Name" in merged["aliases"]


@pytest.mark.unit
def test_merge_locations_filters_existing_primary_aliases_and_names(tmp_path: Path) -> None:
    """Verify merge_locations skips secondary aliases if already on primary or matches primary canonical name."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    p_id = locs.add(country="USA", canonical_name="Primary Town", aliases=["Shared Alias"])
    s_id = locs.add(country="USA", canonical_name="Primary Town", aliases=["Shared Alias", "Novel Alias"])

    merged = locs.merge_locations(p_id, s_id, keep_secondary_aliases=True)
    assert merged["aliases"].count("Shared Alias") == 1
    assert "Novel Alias" in merged["aliases"]


@pytest.mark.unit
def test_merge_locations_secondary_alias_equals_primary_canonical_name(tmp_path: Path) -> None:
    """Verify merge_locations skips secondary alias matching primary canonical name."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    p_id = locs.add(country="USA", canonical_name="Primary Fortress")
    s_id = locs.add(country="USA", canonical_name="Old Fortress", aliases=["Primary Fortress"])

    merged = locs.merge_locations(p_id, s_id, keep_secondary_aliases=True)
    assert merged["aliases"].count("Primary Fortress") == 0


@pytest.mark.unit
def test_merge_locations_graceful_fallback_without_repoint_method(golden_fixture_file: Path) -> None:
    """Verify merge_locations succeeds gracefully when sites_provider lacks repoint_locations."""
    locs = GDALocations(filepath=golden_fixture_file)
    lid_p = "LOC-00006"
    lid_s = locs.add(country="USA", state_or_province="PA", canonical_name="Secondary Place")

    class IncompleteProvider:
        pass

    merged = locs.merge_locations(lid_p, lid_s, sites_provider=IncompleteProvider())
    assert merged["location_id"] == lid_p
    assert lid_s in locs.graveyard


@pytest.mark.regression
@pytest.mark.unit
def test_merge_locations_invalid_arguments_raises_error(tmp_path: Path) -> None:
    """Verify merge_locations raises appropriate errors on invalid inputs."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    lid = locs.add(country="USA")

    with pytest.raises(KeyError, match="Primary location .* not found"):
        locs.merge_locations("LOC-99999", lid)

    with pytest.raises(ValueError, match="At least one secondary location_id must be provided"):
        locs.merge_locations(lid)

    with pytest.raises(ValueError, match="Cannot merge primary location .* into itself"):
        locs.merge_locations(lid, lid)

    with pytest.raises(KeyError, match="Secondary location .* not found"):
        locs.merge_locations(lid, "LOC-99999")


# ==============================================================================
# GROUP 7: Search Engine, Auditing & Atomic Persistence (save)
# Note: Verification of exact/fuzzy searches, validation checks, and persistence
# ==============================================================================


@pytest.mark.unit
def test_search_and_find_by_jurisdiction(golden_fixture_file: Path) -> None:
    """Verify search and find_by_jurisdiction accurately locate target entities."""
    locs = GDALocations(filepath=golden_fixture_file)
    results = locs.search(query="Carlisle")
    assert len(results) >= 1
    assert any("Carlisle" in r["canonical_name"] for r in results)

    jur_match = locs.find_by_jurisdiction(
        country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Carlisle"
    )
    assert jur_match is not None
    assert "Carlisle" in jur_match["canonical_name"]


@pytest.mark.unit
def test_find_by_jurisdiction_mismatches_all_boundaries(golden_fixture_file: Path) -> None:
    """Verify find_by_jurisdiction returns None when country, state, county, or local mismatches."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.find_by_jurisdiction(country="Canada") is None
    assert locs.find_by_jurisdiction(country="USA", state_or_province="California", local_jurisdiction="Carlisle") is None
    assert locs.find_by_jurisdiction(country="USA", state_or_province="PA", county="Lancaster", local_jurisdiction="Carlisle") is None
    assert locs.find_by_jurisdiction(country="USA", state_or_province="PA", county="Cumberland", local_jurisdiction="Mechanicsburg") is None


@pytest.mark.regression
@pytest.mark.unit
def test_find_by_jurisdiction_with_sparse_records(tmp_path: Path) -> None:
    """Verify find_by_jurisdiction against records missing state, county, or local fields."""
    locs = GDALocations(filepath=tmp_path / "loc.json")
    lid = locs.add(country="USA")
    assert locs.find_by_jurisdiction(country="USA", state_or_province="PA") is None
    assert locs.find_by_jurisdiction(country="USA", county="Cumberland") is None
    assert locs.find_by_jurisdiction(country="USA", local_jurisdiction="Carlisle") is None
    res = locs.find_by_jurisdiction(country="USA")
    assert res is not None and res["location_id"] == lid


@pytest.mark.unit
def test_search_single_char_wildcard_matching(golden_fixture_file: Path) -> None:
    """Verify search processes single-character wildcard ? patterns."""
    locs = GDALocations(filepath=golden_fixture_file)
    wildcard_res = locs.search(query="Carl*")
    assert len(wildcard_res) >= 1
    assert any("Carlisle" in r["canonical_name"] for r in wildcard_res)

    question_res = locs.search(query="Carlis?e")
    assert len(question_res) >= 1

    no_match_wildcard = locs.search(query="*NonexistentLocation*")
    assert len(no_match_wildcard) == 0


@pytest.mark.unit
def test_search_glob_character_set_matching(golden_fixture_file: Path) -> None:
    """Verify search processes glob character set patterns like [A-Z]."""
    locs = GDALocations(filepath=golden_fixture_file)
    results = locs.search(query="C[a-z]rlisle")
    assert len(results) >= 1
    assert any("Carlisle" in r["canonical_name"] for r in results)


@pytest.mark.unit
def test_search_fuzzy_ratio_match(golden_fixture_file: Path) -> None:
    """Verify search executes fuzzy SequenceMatcher scoring when ratio exceeds threshold."""
    locs = GDALocations(filepath=golden_fixture_file)
    results = locs.search(query="Carlisl", use_fuzzy=True, fuzzy_threshold=0.85)
    assert len(results) >= 1
    assert any("Carlisle" in r["canonical_name"] for r in results)


@pytest.mark.unit
def test_search_county_filter_mismatch_skips_candidate(golden_fixture_file: Path) -> None:
    """Verify search skips candidate when county parameter does not match."""
    locs = GDALocations(filepath=golden_fixture_file)
    results = locs.search(query="Carlisle", county="Nonexistent County")
    assert len(results) == 0


@pytest.mark.unit
def test_search_none_query_returns_all_candidates_scored_one(golden_fixture_file: Path) -> None:
    """Verify search with query=None returns all candidates with maximum score."""
    locs = GDALocations(filepath=golden_fixture_file)
    results = locs.search(query=None)
    assert len(results) == 40


@pytest.mark.unit
def test_search_substring_length_ratio_scoring(golden_fixture_file: Path) -> None:
    """Verify search scores substring matches by length ratio."""
    locs = GDALocations(filepath=golden_fixture_file)
    results = locs.search(query="Carlisle", use_fuzzy=False)
    assert len(results) >= 1
    assert any("Carlisle" in r["canonical_name"] for r in results)


@pytest.mark.unit
def test_search_filters_by_country_state_and_county(golden_fixture_file: Path) -> None:
    """Verify search filters isolate records by administrative boundaries."""
    locs = GDALocations(filepath=golden_fixture_file)
    pa_results = locs.search(country="USA", state_or_province="PA")
    assert len(pa_results) > 0
    assert all(r["jurisdiction"]["state_or_province"] == "Pennsylvania" for r in pa_results)

    cumb_results = locs.search(county="Cumberland")
    assert len(cumb_results) > 0
    assert all("Cumberland" in str(r["jurisdiction"]["county"]) for r in cumb_results)


@pytest.mark.unit
def test_search_fuzzy_disabled_returns_empty_on_typo(golden_fixture_file: Path) -> None:
    """Verify search with use_fuzzy=False skips fuzzy matches and returns empty on misspelled queries."""
    locs = GDALocations(filepath=golden_fixture_file)
    results = locs.search(query="Carlilse Borough", use_fuzzy=False)
    assert len(results) == 0


@pytest.mark.unit
def test_search_graveyard_inclusion_filter(golden_fixture_file: Path) -> None:
    """Verify search excludes graveyard by default and includes when requested."""
    locs = GDALocations(filepath=golden_fixture_file)
    excluded = locs.search(query="Old Carlisle District", include_graveyard=False)
    included = locs.search(query="Old Carlisle District", include_graveyard=True)

    assert not any(l["location_id"] == "LOC-01300" for l in excluded)
    assert any(l["location_id"] == "LOC-01300" for l in included)


@pytest.mark.unit
def test_find_one_resolution(golden_fixture_file: Path) -> None:
    """Verify find_one resolves closest single matching record or None."""
    locs = GDALocations(filepath=golden_fixture_file)
    match = locs.find_one(query="Carlisle")
    assert match is not None
    assert "Carlisle" in match["canonical_name"]
    assert locs.find_one(query="Completely Nonexistent Name", fuzzy_threshold=0.99) is None
    assert locs.find_one(query="   ") is None


@pytest.mark.unit
def test_validate_location_missing_or_bad_id_format(golden_fixture_file: Path) -> None:
    """Verify validate_location flags missing, None, or invalid ID tokens."""
    locs = GDALocations(filepath=golden_fixture_file)
    violations1 = locs.validate_location({"location_id": "", "canonical_name": "T", "jurisdiction": {"country": "USA"}})
    assert any("Invalid or missing location_id" in v for v in violations1)

    violations2 = locs.validate_location({"location_id": "BAD-PREFIX-01", "canonical_name": "T", "jurisdiction": {"country": "USA"}})
    assert any("Invalid or missing location_id" in v for v in violations2)


@pytest.mark.unit
def test_validate_location_non_string_canonical_name(golden_fixture_file: Path) -> None:
    """Verify validate_location flags non-string canonical_name."""
    locs = GDALocations(filepath=golden_fixture_file)
    violations = locs.validate_location({
        "location_id": "LOC-00001",
        "canonical_name": None,
        "jurisdiction": {"country": "USA"},
    })
    assert any("canonical_name must be a non-empty string" in v for v in violations)


@pytest.mark.unit
def test_validate_location_non_dict_jurisdiction_flags_violation(golden_fixture_file: Path) -> None:
    """Verify validate_location flags jurisdiction when payload is not a dictionary."""
    locs = GDALocations(filepath=golden_fixture_file)
    violations = locs.validate_location({
        "location_id": "LOC-00001",
        "canonical_name": "Test Location",
        "jurisdiction": "not-a-dictionary",
    })
    assert any("jurisdiction must be a dictionary" in v for v in violations)


@pytest.mark.unit
def test_validate_location_non_list_aliases_flags_violation(golden_fixture_file: Path) -> None:
    """Verify validate_location flags aliases when payload is not a list."""
    locs = GDALocations(filepath=golden_fixture_file)
    violations = locs.validate_location({
        "location_id": "LOC-00001",
        "canonical_name": "Test Location",
        "jurisdiction": {"country": "USA"},
        "aliases": "invalid-string-alias-collection",
    })
    assert any("Aliases must be a list of strings" in v for v in violations)


@pytest.mark.unit
def test_validate_location_predecessor_and_successor_defects(golden_fixture_file: Path) -> None:
    """Verify validate_location catches malformed predecessor and successor links."""
    locs = GDALocations(filepath=golden_fixture_file)
    payload_bad_pred = {
        "location_id": "LOC-00001",
        "canonical_name": "Test Place",
        "jurisdiction": {"country": "USA"},
        "temporal_validity": {"predecessor_location_id": "BAD-PRED-SYNTAX"},
    }
    assert any("Invalid predecessor_location_id" in v for v in locs.validate_location(payload_bad_pred))

    payload_bad_succ = {
        "location_id": "LOC-00001",
        "canonical_name": "Test Place",
        "jurisdiction": {"country": "USA"},
        "temporal_validity": {"successor_location_id": "BAD-SUCC-SYNTAX"},
    }
    assert any("Invalid successor_location_id" in v for v in locs.validate_location(payload_bad_succ))


@pytest.mark.unit
def test_validate_location_self_referential_predecessor_detected(golden_fixture_file: Path) -> None:
    """Verify validate_location flags when predecessor_location_id references own location_id."""
    locs = GDALocations(filepath=golden_fixture_file)
    payload = {
        "location_id": "LOC-00006",
        "canonical_name": "Carlisle",
        "jurisdiction": {"country": "USA"},
        "temporal_validity": {"predecessor_location_id": "LOC-00006"},
    }
    violations = locs.validate_location(payload)
    assert any("predecessor_location_id cannot reference own location_id" in v for v in violations)


@pytest.mark.unit
def test_validate_location_self_referential_successor_detected(golden_fixture_file: Path) -> None:
    """Verify validate_location flags when successor_location_id references own location_id."""
    locs = GDALocations(filepath=golden_fixture_file)
    payload = {
        "location_id": "LOC-00006",
        "canonical_name": "Carlisle",
        "jurisdiction": {"country": "USA"},
        "temporal_validity": {"successor_location_id": "LOC-00006"},
    }
    violations = locs.validate_location(payload)
    assert any("successor_location_id cannot reference own location_id" in v for v in violations)


@pytest.mark.unit
def test_validate_location_temporal_inversion(golden_fixture_file: Path) -> None:
    """Verify validate_location flags date_established later than date_dissolved."""
    locs = GDALocations(filepath=golden_fixture_file)
    payload = {
        "location_id": "LOC-00001",
        "canonical_name": "Inverted Dates Place",
        "jurisdiction": {"country": "USA"},
        "temporal_validity": {
            "date_established": "1900",
            "date_dissolved": "1800",
        },
    }
    violations = locs.validate_location(payload)
    assert any("cannot be later than date_dissolved" in v for v in violations)


@pytest.mark.regression
@pytest.mark.unit
def test_validate_location_temporal_validity_without_dates(golden_fixture_file: Path) -> None:
    """Verify validate_location passes when temporal_validity dict has no dates set."""
    locs = GDALocations(filepath=golden_fixture_file)
    payload = {
        "location_id": "LOC-00001",
        "canonical_name": "Undated Boundary Place",
        "jurisdiction": {"country": "USA"},
        "temporal_validity": {},
    }
    violations = locs.validate_location(payload)
    assert len(violations) == 0


@pytest.mark.unit
def test_validate_location_fully_valid_rich_record(golden_fixture_file: Path) -> None:
    """Verify validate_location returns empty list when all fields, lineage, and dates are valid."""
    locs = GDALocations(filepath=golden_fixture_file)
    payload = {
        "location_id": "LOC-00001",
        "canonical_name": "Exemplary Borough",
        "jurisdiction": {"country": "USA", "state_or_province": "Pennsylvania"},
        "temporal_validity": {
            "date_established": "1750",
            "date_dissolved": "1850",
            "predecessor_location_id": "LOC-00002",
            "successor_location_id": "LOC-00003",
        },
        "aliases": ["Valid Alias One", "Valid Alias Two"],
    }
    violations = locs.validate_location(payload)
    assert violations == []


@pytest.mark.unit
def test_validate_location_non_dict_temporal_validity(golden_fixture_file: Path) -> None:
    """Verify validate_location flags temporal_validity when not a dictionary."""
    locs = GDALocations(filepath=golden_fixture_file)
    payload = {
        "location_id": "LOC-00001",
        "canonical_name": "Bad Temporal Place",
        "jurisdiction": {"country": "USA"},
        "temporal_validity": "not-a-dict",
    }
    violations = locs.validate_location(payload)
    assert any("temporal_validity must be a dictionary" in v for v in violations)


@pytest.mark.unit
def test_validate_location_blank_alias_entry_flags_error(golden_fixture_file: Path) -> None:
    """Verify validate_location flags empty or whitespace alias entries."""
    locs = GDALocations(filepath=golden_fixture_file)
    violations = locs.validate_location({
        "location_id": "LOC-00001",
        "canonical_name": "Valid Name",
        "jurisdiction": {"country": "USA"},
        "aliases": ["Valid Alias", "   "],
    })
    assert any("All alias entries must be non-empty strings" in v for v in violations)


@pytest.mark.unit
def test_validate_location_non_dict_payload(golden_fixture_file: Path) -> None:
    """Verify passing non-dict to validate_location returns immediate error list."""
    locs = GDALocations(filepath=golden_fixture_file)
    violations = locs.validate_location("string_payload")  # type: ignore[arg-type]
    assert violations == ["Location payload must be a dictionary."]


@pytest.mark.unit
def test_validate_location_empty_country_in_jurisdiction(golden_fixture_file: Path) -> None:
    """Verify validate_location catches empty or whitespace country strings."""
    locs = GDALocations(filepath=golden_fixture_file)
    violations = locs.validate_location({
        "location_id": "LOC-00001",
        "canonical_name": "Valid Name",
        "jurisdiction": {"country": "   "},
    })
    assert any("country must be a non-empty string" in v for v in violations)


@pytest.mark.unit
def test_validate_all_finds_injected_defects(failure_fixture_schema_violations: Path) -> None:
    """Verify validate_all scans entire active store and aggregates defects."""
    locs = GDALocations(filepath=failure_fixture_schema_violations)
    defects = locs.validate_all()
    assert "LOC-00006" in defects
    assert any("canonical_name must be a non-empty string" in d for d in defects["LOC-00006"])
    assert "LOC-00042" in defects
    assert any("country must be a non-empty string" in d for d in defects["LOC-00042"])


@pytest.mark.regression
@pytest.mark.unit
def test_save_clean_state_skips_write(golden_fixture_file: Path) -> None:
    """Verify save returns False when manager has no uncommitted changes."""
    locs = GDALocations(filepath=golden_fixture_file)
    assert locs.is_dirty is False
    assert locs.save(force=False) is False


@pytest.mark.regression
@pytest.mark.unit
def test_save_io_exception_handling(golden_fixture_file: Path) -> None:
    """Verify save raises exception when GDAUtil encounters an unhandled IO error."""
    locs = GDALocations(filepath=golden_fixture_file)
    locs.add(country="USA", state_or_province="PA", local_jurisdiction="FaultyVille")
    with patch("gdadomain.locations.GDAUtil.save_json", side_effect=IOError("Simulated disk error")):
        with pytest.raises(IOError, match="Simulated disk error"):
            locs.save()


@pytest.mark.integration
def test_save_force_and_custom_output_path(golden_fixture_file: Path, tmp_path: Path) -> None:
    """Verify save persists cleanly with force=True and explicit output_path."""
    locs = GDALocations(filepath=golden_fixture_file)
    custom_path = tmp_path / "custom_locations_export.json"

    saved = locs.save(output_path=custom_path, force=True, create_backup=False)
    assert saved is True
    assert custom_path.exists()

    payload = json.loads(custom_path.read_text(encoding="utf-8"))
    assert payload["total_locations"] == 45
    assert len(payload["locations"]) == 45


@pytest.mark.integration
def test_save_force_default_path(tmp_path: Path) -> None:
    """Verify save persists to default filepath when force=True and output_path is None."""
    target_file = tmp_path / "entities" / "locations.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(json.dumps({"locations": []}), encoding="utf-8")

    locs = GDALocations(filepath=target_file)
    saved = locs.save(force=True, create_backup=False)
    assert saved is True
    assert target_file.exists()


@pytest.mark.integration
def test_save_dirty_record_serializes_and_clears_dirty_flag(tmp_path: Path) -> None:
    """Verify save serializes dirty records, clears is_dirty, and reloads reliably."""
    target_file = tmp_path / "entities" / "locations.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(json.dumps({"locations": []}), encoding="utf-8")

    locs = GDALocations(filepath=target_file)
    locs.add(country="USA", state_or_province="PA", local_jurisdiction="Testville")
    assert locs.is_dirty is True

    saved = locs.save(create_backup=False)
    assert saved is True
    assert locs.is_dirty is False

    reloaded = GDALocations(filepath=target_file)
    assert reloaded.count == 1
    assert any("Testville" in l["canonical_name"] for l in reloaded)