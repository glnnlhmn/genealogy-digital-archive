# Name: test_entity_sites.py
# Path: tools/lib/gdadomain/tests/test_entity_sites.py
# Version: 1.0.0+build.r1

"""Unit test suite validating GDASites initialization, protocols, retrieval, mutation, and persistence.

Operational Role:
    Executes hermetic verification across all 7 functional groups for GDASites (v1.2.0):
    - Group 1: IntrospectableMixin directory generation, public member inspection,
      mandatory locations_provider validation, missing file fallback, corrupt JSON
      rejection, partitioned loading, and refresh discard logic.
    - Group 2: Collection protocols, active sized count, subscript retrieval,
      deep-copy memory isolation, and transparent graveyard redirection.
    - Group 3: Entity membership, multi-hop redirect resolution, circular loop guards,
      spatial jurisdiction queries, and dedicated graveyard iterators.
    - Group 4: Record creation, strictly system-minted sequential SID-XXXXX allocation
      via monotonic high-water mark, note validation, and foreign key verification.
    - Group 5: Record updates, property validation, note addition/removal,
      and idempotent alias management.
    - Group 6: Deprecation, soft deletion, graveyard pointers, and foreign key cascading.
    - Group 7: Multi-field search, fuzzy matching, coordinate filtering, and atomic save.

Test Structure & Protocol:
    - Atomized tests: 1:1 assertion mapping isolating individual contract rules.
    - Fully decorated: Explicit markers applied (smoke, unit, regression, integration).
    - Dependencies: Isolated pytest tmp_path fixtures, mock_loc stub, and static golden/failure fixtures from conftest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from gdadomain.sites import GDASites


# ==============================================================================
# GROUP 1: Introspection, Initialization & Disk Loading
# Note: Verifies IntrospectableMixin directory generation, public signatures,
# safe missing-file defaults, mutation rollbacks, and mandatory locations_provider.
# ==============================================================================


@pytest.mark.unit
def test_help_directory_generation(capsys: Any, tmp_path: Path, mock_loc: Any) -> None:
    """Verify sites.help() outputs all public members without listing private attributes."""
    empty_file = tmp_path / "empty_sites.json"
    sites = GDASites(locations_provider=mock_loc, filepath=empty_file)
    sites.help()

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
        assert not ml.lstrip("- *").strip().startswith("_sites")
        assert not ml.lstrip("- *").strip().startswith("_graveyard")


@pytest.mark.smoke
@pytest.mark.unit
def test_help_member_signature(capsys: Any, tmp_path: Path, mock_loc: Any) -> None:
    """Verify sites.help('add') prints call signature, parameter types, and docstring."""
    empty_file = tmp_path / "empty_sites.json"
    sites = GDASites(locations_provider=mock_loc, filepath=empty_file)
    sites.help("add")

    captured = capsys.readouterr().out
    assert "add(" in captured
    assert "site_type" in captured
    assert "Add a new physical site entity" in captured


@pytest.mark.unit
def test_help_invalid_member(capsys: Any, tmp_path: Path, mock_loc: Any) -> None:
    """Verify sites.help() gracefully handles unknown member names without exceptions."""
    empty_file = tmp_path / "empty_sites.json"
    sites = GDASites(locations_provider=mock_loc, filepath=empty_file)
    sites.help("non_existent_method")

    captured = capsys.readouterr().out
    assert "not found" in captured or "No public member" in captured or "non_existent_method" in captured


@pytest.mark.regression
@pytest.mark.unit
def test_init_missing_locations_provider_raises_error(tmp_path: Path) -> None:
    """Verify initializing GDASites without locations_provider raises ValueError."""
    empty_file = tmp_path / "empty_sites.json"
    with pytest.raises(ValueError) as exc_info:
        GDASites(locations_provider=None, filepath=empty_file)
    assert "requires a valid locations_provider" in str(exc_info.value)


@pytest.mark.unit
def test_init_missing_file(tmp_path: Path, mock_loc: Any) -> None:
    """Verify missing file initializes empty partitions and flags is_dirty as True."""
    non_existent = tmp_path / "missing_sites.json"
    sites = GDASites(locations_provider=mock_loc, filepath=non_existent)

    assert len(sites) == 0
    assert len(sites.graveyard) == 0
    assert sites.total_count == 0
    assert sites.is_dirty is True


@pytest.mark.regression
@pytest.mark.unit
def test_load_corrupt_json(failure_sites_syntax: Path, mock_loc: Any) -> None:
    """Verify malformed JSON payload raises an exception during instantiation."""
    with pytest.raises(Exception):
        GDASites(locations_provider=mock_loc, filepath=failure_sites_syntax)


@pytest.mark.regression
@pytest.mark.unit
def test_load_corrupt_json_logs_error(failure_sites_syntax: Path, mock_loc: Any) -> None:
    """Verify malformed JSON payload logs error via GDALogger during instantiation."""
    with patch("gdadomain.sites.GDALogger.get_logger") as mock_logger_getter:
        mock_logger = mock_logger_getter.return_value
        with pytest.raises(Exception):
            GDASites(locations_provider=mock_loc, filepath=failure_sites_syntax)
        mock_logger.error.assert_called()


@pytest.mark.unit
def test_load_partitioning(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify load partitions active records into _sites and deprecated records into _graveyard."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)

    assert sites.count == 15
    assert "SID-00001" in sites
    assert "SID-00003" in sites
    assert len(sites.graveyard) == 2
    assert "SID-00002" in sites.graveyard
    assert "SID-00015" in sites.graveyard
    assert sites.total_count == 17


@pytest.mark.regression
@pytest.mark.unit
def test_load_skips_empty_ids(failure_sites_missing_id: Path, mock_loc: Any) -> None:
    """Verify load skips records missing site_id payloads."""
    sites = GDASites(locations_provider=mock_loc, filepath=failure_sites_missing_id)
    assert "" not in sites
    assert "" not in sites.graveyard
    assert sites.count == 1
    assert "SID-00001" in sites


@pytest.mark.unit
def test_load_clean_state(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify is_dirty initializes to False after loading a valid dataset."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.is_dirty is False


@pytest.mark.unit
def test_refresh_discards_mutations(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify refresh discards unstaged in-memory mutations and restores clean disk state."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)

    sites.add(
        name="Temporary Landmark",
        site_type="LANDMARK",
        location_id="LOC-00042",
    )
    assert sites.is_dirty is True
    assert sites.count == 16

    sites.refresh()

    assert sites.is_dirty is False
    assert sites.count == 15
    assert "Temporary Landmark" not in [s["name"] for s in sites]


@pytest.mark.unit
def test_refresh_discards_deletions(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify refresh discards unstaged soft-deletions and restores active records."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert "SID-00001" in sites

    sites.delete("SID-00001")
    assert "SID-00001" not in sites
    assert sites.is_dirty is True

    sites.refresh()
    assert sites.is_dirty is False
    assert "SID-00001" in sites


# ==============================================================================
# GROUP 2: Collection Protocols & Subscript Ergonomics
# Note: Validates container interfaces on active sites and transparent graveyard
# redirection without in-memory state leakage.
# ==============================================================================


@pytest.mark.unit
def test_len_returns_active_count(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify len(sites) returns count of active sites, excluding graveyard tombstones."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert len(sites) == 15


@pytest.mark.unit
def test_total_count_property(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify total_count accurately sums active records and graveyard tombstones."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.total_count == 17


@pytest.mark.unit
def test_iter_yields_active_only(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify __iter__ traversal yields only active site records."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    yielded_ids = [s["site_id"] for s in sites]

    assert "SID-00001" in yielded_ids
    assert "SID-00002" not in yielded_ids
    assert "SID-00015" not in yielded_ids
    assert len(yielded_ids) == 15


@pytest.mark.unit
def test_iter_empty_registry_yields_zero_items(tmp_path: Path, mock_loc: Any) -> None:
    """Verify __iter__ traversal over an empty registry yields zero items."""
    empty_file = tmp_path / "empty_sites.json"
    sites = GDASites(locations_provider=mock_loc, filepath=empty_file)
    assert list(sites) == []


@pytest.mark.unit
def test_iter_memory_isolation(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify in-place mutation of iterated entity dictionary does not leak into manager memory."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    for site in sites:
        if site["site_id"] == "SID-00001":
            if site.get("address"):
                site["address"]["postal_code"] = "99999"

    retrieved = sites["SID-00001"]
    assert retrieved["address"]["postal_code"] == "19801"


@pytest.mark.unit
def test_contains_active_id(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify 'in' container operator returns True for active site identifiers."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert "SID-00001" in sites


@pytest.mark.unit
def test_contains_graveyard_id_returns_false(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify 'in' container operator returns False for soft-deleted graveyard identifiers."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert "SID-00002" not in sites
    assert "SID-00015" not in sites


@pytest.mark.unit
def test_contains_non_existent_id_returns_false(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify 'in' container operator returns False for unregistered identifier."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert ("SID-99999" in sites) is False


@pytest.mark.unit
def test_contains_non_string_returns_false(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify 'in' container operator returns False for non-string queries without raising TypeError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert (12345 in sites) is False
    assert (None in sites) is False


@pytest.mark.unit
def test_getitem_active_retrieval(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify subscript access retrieves expected active entity payload."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    record = sites["SID-00003"]
    assert record["name"] == "Gettysburg National Cemetery"
    assert record["site_type"] == "CEMETERY"


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_graveyard_redirect(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify subscript access on superseded tombstone transparently redirects to canonical active replacement."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    record = sites["SID-00002"]
    assert record["site_id"] == "SID-00001"
    assert record["name"] == "First Evangelical Lutheran Church"


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_missing_raises_key_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify subscript access for non-existent site ID raises KeyError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(KeyError) as exc_info:
        _ = sites["SID-99999"]
    assert "SID-99999" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_defunct_without_replacement_raises_key_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify subscript access on terminal defunct tombstone without replacement raises KeyError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(KeyError) as exc_info:
        _ = sites["SID-00015"]
    assert "SID-00015" in str(exc_info.value)


# ==============================================================================
# GROUP 3: Entity Retrieval, Membership & Graveyard Traversal
# Note: Validates multi-hop redirects, cyclic guards, and spatial association queries.
# ==============================================================================


@pytest.mark.unit
def test_find_max_site_id_skips_non_conforming_tokens(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify max numeric ID calculation ignores malformed IDs that do not match SID-XXXXX."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    sites._sites["CUSTOM-ID-123"] = {"site_id": "CUSTOM-ID-123"}
    all_ids = list(sites._sites.keys()) + list(sites._graveyard.keys())
    max_id = sites._max_site_num
    assert max_id == 17


@pytest.mark.unit
def test_find_max_site_id_empty_store_returns_zero(tmp_path: Path, mock_loc: Any) -> None:
    """Verify max numeric ID evaluates to 0 when store has zero records."""
    empty_file = tmp_path / "empty_sites.json"
    sites = GDASites(locations_provider=mock_loc, filepath=empty_file)
    assert sites._max_site_num == 0


@pytest.mark.unit
def test_exists_active_site(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify exists returns True for active site identifier."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.exists("SID-00001") is True


@pytest.mark.unit
def test_exists_graveyard_default_false(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify exists returns False by default for soft-deleted graveyard tombstones."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.exists("SID-00002", include_graveyard=False) is False


@pytest.mark.unit
def test_exists_graveyard_explicit_true(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify exists returns True for graveyard tombstones when include_graveyard=True."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.exists("SID-00002", include_graveyard=True) is True


@pytest.mark.unit
def test_exists_unknown_id_returns_false(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify exists returns False for unknown site identifiers under all search modes."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.exists("SID-99999", include_graveyard=True) is False


@pytest.mark.unit
def test_get_by_id_active_returns_record(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify get_by_id returns canonical active record."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    record = sites.get_by_id("SID-00003")
    assert record is not None
    assert record["name"] == "Gettysburg National Cemetery"
    assert record["site_type"] == "CEMETERY"


@pytest.mark.unit
def test_get_by_id_memory_isolation(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify modifying record returned by get_by_id does not leak into internal manager memory."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    record = sites.get_by_id("SID-00003")
    assert record is not None
    record["address"]["postal_code"] = "99999"

    fresh_record = sites.get_by_id("SID-00003")
    assert fresh_record is not None
    assert fresh_record["address"]["postal_code"] == "17325"


@pytest.mark.regression
@pytest.mark.unit
def test_get_by_id_resolves_redirect_to_active(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify get_by_id follows graveyard redirect to active replacement record."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    record = sites.get_by_id("SID-00002", resolve_redirects=True)
    assert record is not None
    assert record["site_id"] == "SID-00001"
    assert record["name"] == "First Evangelical Lutheran Church"


@pytest.mark.unit
def test_get_by_id_graveyard_direct_tombstone(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify get_by_id returns raw graveyard tombstone when redirection is disabled."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    tombstone = sites.get_by_id("SID-00002", include_graveyard=True, resolve_redirects=False)
    assert tombstone is not None
    assert tombstone["site_id"] == "SID-00002"
    assert tombstone["is_deprecated"] is True
    assert tombstone["superseded_by"] == "SID-00001"


@pytest.mark.unit
def test_get_by_id_graveyard_without_include_returns_none(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify get_by_id returns None for unredirected tombstone when include_graveyard=False."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    result = sites.get_by_id("SID-00015", include_graveyard=False, resolve_redirects=False)
    assert result is None


@pytest.mark.unit
def test_get_by_id_unknown_returns_none(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify get_by_id returns None for non-existent identifier."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.get_by_id("SID-99999") is None


@pytest.mark.unit
def test_resolve_id_direct_link(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify resolve_id traces single-hop deprecation link to canonical active ID."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.resolve_id("SID-00002") == "SID-00001"


@pytest.mark.regression
@pytest.mark.unit
def test_resolve_id_transitive_multihop(failure_sites_transitive_graveyard: Path, mock_loc: Any) -> None:
    """Verify resolve_id traces multi-hop deprecation chains to canonical active ID."""
    sites = GDASites(locations_provider=mock_loc, filepath=failure_sites_transitive_graveyard)
    assert sites.resolve_id("SID-00020") == "SID-00001"


@pytest.mark.regression
@pytest.mark.unit
def test_resolve_id_circular_guard(failure_sites_circular_graveyard: Path, mock_loc: Any) -> None:
    """Verify resolve_id catches circular redirects and returns None without recursion error."""
    sites = GDASites(locations_provider=mock_loc, filepath=failure_sites_circular_graveyard)
    assert sites.resolve_id("SID-00030") is None


@pytest.mark.unit
def test_resolve_id_terminal_defunct_returns_none(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify resolve_id returns None for defunct tombstones lacking a superseded_by target."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.resolve_id("SID-00015") is None


@pytest.mark.unit
def test_resolve_id_unknown_returns_none(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify resolve_id returns None for an unregistered ID."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.resolve_id("SID-99999") is None


@pytest.mark.unit
def test_get_by_location_active_only(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify get_by_location returns active sites for location_id, excluding graveyard by default."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    loc_sites = sites.get_by_location("LOC-00042", include_graveyard=False)
    ids = [s["site_id"] for s in loc_sites]
    assert ids == ["SID-00001"]


@pytest.mark.unit
def test_get_by_location_including_graveyard(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify get_by_location returns both active and graveyard sites when include_graveyard=True."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    loc_sites = sites.get_by_location("LOC-00042", include_graveyard=True)
    ids = [s["site_id"] for s in loc_sites]
    assert "SID-00001" in ids
    assert "SID-00002" in ids
    assert len(ids) == 2


@pytest.mark.unit
def test_get_by_location_unmatched_returns_empty(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify get_by_location returns empty list when no sites anchor to target location."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.get_by_location("LOC-99999", include_graveyard=True) == []


@pytest.mark.unit
def test_iter_graveyard_yields_tombstones_only(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify iter_graveyard generator yields all soft-deleted records."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    graveyard_ids = {s["site_id"] for s in sites.iter_graveyard()}
    assert graveyard_ids == {"SID-00002", "SID-00015"}


@pytest.mark.unit
def test_iter_all_yields_entire_registry(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify iter_all generator yields combined active and graveyard inventory."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    all_sites = list(sites.iter_all())
    assert len(all_sites) == 17
    all_ids = {s["site_id"] for s in all_sites}
    assert "SID-00001" in all_ids
    assert "SID-00002" in all_ids
    assert "SID-00015" in all_ids


# ==============================================================================
# GROUP 4: Record Creation (add) & Sequential Minting
# Note: Physical site creation enforces sequential SID-XXXXX allocation, foreign-key
# validation, schema-validated notes, and deep-copy input isolation.
# ==============================================================================


@pytest.mark.unit
def test_add_auto_mint_initial_id(tmp_path: Path, mock_loc: Any) -> None:
    """Verify auto-minting assigns SID-00001 on an empty registry."""
    empty_file = tmp_path / "empty_sites.json"
    sites = GDASites(locations_provider=mock_loc, filepath=empty_file)
    new_id = sites.add(
        name="Valley Forge Encampment",
        site_type="LANDMARK",
        location_id="LOC-00042",
    )
    assert new_id == "SID-00001"
    assert new_id in sites


@pytest.mark.unit
def test_add_auto_mint_increments_monotonic(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify sequential calls to add increment monotonic high-water mark without full rescans."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    id_1 = sites.add(
        name="Pickett's Charge High Water Mark",
        site_type="LANDMARK",
        location_id="LOC-00101",
    )
    id_2 = sites.add(
        name="Culp's Hill",
        site_type="LANDMARK",
        location_id="LOC-00101",
    )
    assert id_1 == "SID-00018"
    assert id_2 == "SID-00019"
    assert id_1 in sites
    assert id_2 in sites


@pytest.mark.regression
@pytest.mark.unit
def test_add_empty_name_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify adding a site with an empty or whitespace name raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="   ",
            site_type="LANDMARK",
            location_id="LOC-00101",
        )
    assert "Site 'name' must be a non-empty string" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_add_invalid_site_type_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify non-conforming site_type raises ValueError with allowed vocabulary enumerated."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Invalid Type Site",
            site_type="NON_EXISTENT_TYPE",
            location_id="LOC-00101",
        )
    assert "Invalid site_type 'NON_EXISTENT_TYPE'" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_add_foreign_key_location_failure(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify adding site with missing location_id fails foreign key check."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Unanchored Landmark",
            site_type="LANDMARK",
            location_id="LOC-99999",
        )
    assert "Foreign key validation failed: location_id 'LOC-99999' not found" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_add_invalid_operational_status_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify non-conforming operational_status raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Invalid Status Site",
            site_type="LANDMARK",
            location_id="LOC-00101",
            operational_status="ABANDONED_STATUS",
        )
    assert "Invalid operational_status 'ABANDONED_STATUS'" in str(exc_info.value)


@pytest.mark.unit
def test_add_normalizes_and_validates_notes(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify notes payload auto-formats note_id sequentially if missing."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    new_id = sites.add(
        name="Noted Facility",
        site_type="FACILITY",
        location_id="LOC-00101",
        notes=[
            {"note_text": "First primary note."},
            {"note_text": "Second primary note.", "note_type": "HISTORICAL"},
        ],
    )
    record = sites[new_id]
    notes = record["notes"]
    assert len(notes) == 2
    assert notes[0]["note_id"] == "NOT-00001"
    assert notes[0]["note_text"] == "First primary note."
    assert notes[0]["note_type"] == "RESEARCH"
    assert "modified_date" in notes[0] or "created_at" in notes[0]
    assert notes[1]["note_id"] == "NOT-00002"
    assert notes[1]["note_text"] == "Second primary note."


@pytest.mark.regression
@pytest.mark.unit
def test_add_empty_note_text_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify adding notes with empty or invalid text raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Faulty Note Site",
            site_type="LANDMARK",
            location_id="LOC-00101",
            notes=[{"note_text": "   "}],
        )
    assert "non-empty string" in str(exc_info.value).lower()


@pytest.mark.regression
@pytest.mark.unit
def test_add_notes_non_list_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify passing a non-list object as notes raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Malformed Notes Site",
            site_type="LANDMARK",
            location_id="LOC-00101",
            notes="invalid_string_notes",  # type: ignore[arg-type]
        )
    assert "must be a list" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_add_notes_entry_not_dict_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify passing a non-dict entry within the notes list raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Malformed Note Entry Site",
            site_type="LANDMARK",
            location_id="LOC-00101",
            notes=["not_a_dictionary"],  # type: ignore[list-item]
        )
    assert "must be a dictionary" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_add_address_non_dict_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify passing a non-dictionary object as address raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Malformed Address Site",
            site_type="LANDMARK",
            location_id="LOC-00101",
            address="invalid_string_address",  # type: ignore[arg-type]
        )
    assert "Address payload must be a dictionary" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_add_address_disallowed_keys_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify passing unsupported keys in address dictionary raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Extra Key Address Site",
            site_type="LANDMARK",
            location_id="LOC-00101",
            address={"address_line_1": "123 Main St", "unsupported_field": "disallowed"},
        )
    assert "Disallowed properties in address dictionary" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_add_address_coords_non_dict_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify passing non-dictionary coordinates raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Bad Coords Type Site",
            site_type="LANDMARK",
            location_id="LOC-00101",
            address={"coordinates": "40.0,-77.0"},  # type: ignore[dict-item]
        )
    assert "Address coordinates must be a dictionary" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_add_address_coords_extra_keys_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify passing unexpected keys inside coordinates dictionary raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Extra Coords Keys Site",
            site_type="LANDMARK",
            location_id="LOC-00101",
            address={"coordinates": {"latitude": 40.0, "longitude": -77.0, "altitude": 500.0}},
        )
    assert "Disallowed properties in coordinates dictionary" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_add_address_non_numeric_coordinates_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify passing non-numeric latitude or longitude raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add(
            name="Non-Numeric Coords Site",
            site_type="LANDMARK",
            location_id="LOC-00101",
            address={"coordinates": {"latitude": "north_40", "longitude": -77.0}},  # type: ignore[dict-item]
        )
    assert "must contain numeric 'latitude' and 'longitude'" in str(exc_info.value)


@pytest.mark.unit
def test_add_address_integer_coordinates_normalized_to_float(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify integer coordinates normalize safely to floating-point representation."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    sid = sites.add(
        name="Integer Coords Site",
        site_type="LANDMARK",
        location_id="LOC-00101",
        address={"coordinates": {"latitude": 40, "longitude": -77}},
    )
    coords = sites[sid]["address"]["coordinates"]
    assert isinstance(coords["latitude"], float)
    assert isinstance(coords["longitude"], float)
    assert coords["latitude"] == 40.0
    assert coords["longitude"] == -77.0


@pytest.mark.unit
def test_add_address_without_coordinates_normalizes_to_none(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify address payload without coordinates normalizes coordinates field to None."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    sid = sites.add(
        name="No Coords Facility",
        site_type="FACILITY",
        location_id="LOC-00042",
        address={"address_line_1": "100 Rural Route", "postal_code": "17013"},
    )
    assert sites[sid]["address"]["coordinates"] is None


@pytest.mark.unit
def test_add_input_memory_isolation(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify mutating caller input dictionaries/lists after add() does not alter internal state."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    addr_payload = {
        "address_line_1": "123 Old Post Road",
        "address_line_2": None,
        "postal_code": "17325",
        "coordinates": {"latitude": 39.8, "longitude": -77.2},
    }
    notes_payload = [{"note_text": "Initial note"}]
    aliases_payload = ["Old Alias"]

    new_id = sites.add(
        name="Isolated Input Site",
        site_type="LANDMARK",
        location_id="LOC-00101",
        aliases=aliases_payload,
        address=addr_payload,
        notes=notes_payload,
    )

    addr_payload["postal_code"] = "00000"
    addr_payload["coordinates"]["latitude"] = 0.0
    notes_payload[0]["note_text"] = "Mutated note"
    aliases_payload.append("Injected Alias")

    stored = sites[new_id]
    assert stored["address"]["postal_code"] == "17325"
    assert stored["address"]["coordinates"]["latitude"] == 39.8
    assert stored["notes"][0]["note_text"] == "Initial note"
    assert stored["aliases"] == ["Old Alias"]


@pytest.mark.unit
def test_add_sets_default_lifecycle_fields(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify newly added sites initialize with non-deprecated active lifecycle defaults."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    new_id = sites.add(
        name="Lifecycle Default Site",
        site_type="LANDMARK",
        location_id="LOC-00101",
    )
    record = sites[new_id]
    assert record["is_deprecated"] is False
    assert record["superseded_by"] is None
    assert record["dissolution_date"] is None
    assert record["operational_status"] == "ACTIVE"


@pytest.mark.unit
def test_add_flags_dirty_state(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify is_dirty transitions from False to True upon adding a record."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.is_dirty is False

    sites.add(
        name="Dirty Flag Site",
        site_type="LANDMARK",
        location_id="LOC-00101",
    )
    assert sites.is_dirty is True


# ==============================================================================
# GROUP 5: Record Updates, Note Operations & Alias Management
# Note: Physical site modifications enforce property boundaries, foreign key
# synchronization, note addition/removal, and idempotent alias tracking.
# ==============================================================================


@pytest.mark.unit
def test_edit_active_record_fields(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify updating standard scalar fields updates record and marks manager dirty."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    success = sites.edit("SID-00001", {"name": "First Evangelical Lutheran Church of Carlisle"})
    assert success is True
    assert sites["SID-00001"]["name"] == "First Evangelical Lutheran Church of Carlisle"
    assert sites.is_dirty is True


@pytest.mark.unit
def test_edit_identical_values_returns_false(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify editing a record with identical values returns False and leaves is_dirty unchanged."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    cur_name = sites["SID-00001"]["name"]
    success = sites.edit("SID-00001", {"name": cur_name})
    assert success is False
    assert sites.is_dirty is False


@pytest.mark.regression
@pytest.mark.unit
def test_edit_missing_site_raises_key_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify editing a non-existent site ID raises KeyError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(KeyError) as exc_info:
        sites.edit("SID-99999", {"name": "Ghost Site"})
    assert "SID-99999" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_edit_graveyard_site_raises_key_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify editing a deprecated site residing in the graveyard raises KeyError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(KeyError) as exc_info:
        sites.edit("SID-00002", {"name": "Resurrected Site"})
    assert "Cannot edit deprecated site 'SID-00002'" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_edit_disallowed_property_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify attempting to edit unapproved or schema-disallowed properties raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.edit("SID-00001", {"invalid_property_key": "injected_value"})
    assert "Disallowed property updates for site" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_edit_invalid_vocabulary_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify updating site_type to a non-conforming vocabulary token raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.edit("SID-00001", {"site_type": "NON_EXISTENT_TYPE"})
    assert "Invalid site_type 'NON_EXISTENT_TYPE'" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_edit_invalid_operational_status_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify updating operational_status to a non-conforming token raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.edit("SID-00001", {"operational_status": "DISMANTLED_STATUS"})
    assert "Invalid operational_status 'DISMANTLED_STATUS'" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_edit_location_foreign_key_validation(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify editing location_id validates against locations provider."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.edit("SID-00001", {"location_id": "LOC-99999"})
    assert "Foreign key validation failed: location_id 'LOC-99999' not found" in str(exc_info.value)


@pytest.mark.unit
def test_edit_valid_site_type_status_and_location(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify edit updates site_type, operational_status, and location_id when valid."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    success = sites.edit(
        "SID-00001",
        {
            "site_type": "LANDMARK",
            "operational_status": "HISTORICAL",
            "location_id": "LOC-00101",
        },
    )
    assert success is True
    record = sites["SID-00001"]
    assert record["site_type"] == "LANDMARK"
    assert record["operational_status"] == "HISTORICAL"
    assert record["location_id"] == "LOC-00101"
    assert sites.is_dirty is True


@pytest.mark.unit
def test_edit_updates_address_and_name_fields(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify edit updates normalized address dictionary and stripped name string."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    new_addr = {
        "address_line_1": "500 Heritage Way",
        "postal_code": "17013",
        "coordinates": {"latitude": 40.123, "longitude": -77.456},
    }
    success = sites.edit(
        "SID-00001",
        {
            "name": "  Trimmed Name Church  ",
            "address": new_addr,
        },
    )
    assert success is True
    record = sites["SID-00001"]
    assert record["name"] == "Trimmed Name Church"
    assert record["address"]["address_line_1"] == "500 Heritage Way"
    assert record["address"]["coordinates"]["latitude"] == 40.123


@pytest.mark.unit
def test_edit_ignores_protected_site_id(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify edit() skips mutation of protected site_id attribute."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    success = sites.edit(
        "SID-00001",
        {
            "site_id": "SID-99999",
            "name": "Preserved ID Church",
        },
    )
    assert success is True
    record = sites["SID-00001"]
    assert record["site_id"] == "SID-00001"
    assert record["name"] == "Preserved ID Church"


@pytest.mark.unit
def test_edit_mutates_notes_and_aliases_subobjects(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify edit() normalizes notes and aliases sub-objects directly."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    new_notes = [{"note_text": "Freshly audited deed records."}]
    new_aliases = ["St. John's Chapel"]

    success = sites.edit(
        "SID-00001",
        {
            "notes": new_notes,
            "aliases": new_aliases,
        },
    )
    assert success is True
    record = sites["SID-00001"]
    assert record["notes"][0]["note_text"] == "Freshly audited deed records."
    assert "St. John's Chapel" in record["aliases"]


@pytest.mark.unit
def test_edit_overwrite_none_clears_optional_fields(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify overwrite_none=True clears fields set to None, while overwrite_none=False preserves them."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites["SID-00001"]["address"] is not None

    sites.edit("SID-00001", {"address": None}, overwrite_none=False)
    assert sites["SID-00001"]["address"] is not None

    sites.edit("SID-00001", {"address": None}, overwrite_none=True)
    assert sites["SID-00001"]["address"] is None


@pytest.mark.unit
def test_edit_inline_deprecation_dispatch(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify setting is_deprecated=True in edit updates dispatches to delete with graveyard transition."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    sites.edit("SID-00001", {"is_deprecated": True, "superseded_by": "SID-00003"})
    assert "SID-00001" not in sites
    assert "SID-00001" in sites.graveyard
    assert sites.graveyard["SID-00001"]["superseded_by"] == "SID-00003"


@pytest.mark.unit
def test_add_note_ergonomics_and_minting(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify add_note appends note with auto-minted sequential NOT-XXXXX and valid timestamp."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    minted_id = sites.add_note("SID-00003", "Verified historical monument records on site.", note_type="RESEARCH")
    record = sites["SID-00003"]
    assert minted_id.startswith("NOT-")
    assert record["notes"][-1]["note_id"] == minted_id
    assert record["notes"][-1]["note_text"] == "Verified historical monument records on site."
    assert "created_at" in record["notes"][-1] or "modified_date" in record["notes"][-1]
    assert sites.is_dirty is True


@pytest.mark.unit
def test_add_note_defaults_unrecognized_type(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify add_note defaults to RESEARCH when an unregistered note_type is supplied."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    minted_id = sites.add_note("SID-00003", "A note with unregistered type.", note_type="UNREGISTERED_TYPE")
    record = sites["SID-00003"]
    assert record["notes"][-1]["note_id"] == minted_id
    assert record["notes"][-1]["note_type"] == "RESEARCH"


@pytest.mark.regression
@pytest.mark.unit
def test_add_note_missing_site_raises_key_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify calling add_note on a non-existent site ID raises KeyError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(KeyError) as exc_info:
        sites.add_note("SID-99999", "Floating note.")
    assert "SID-99999" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_add_note_empty_text_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify calling add_note with empty or whitespace text raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.add_note("SID-00003", "   ")
    assert "non-empty string" in str(exc_info.value).lower()


@pytest.mark.unit
def test_remove_note_lifecycle(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify remove_note evicts matching note by ID and returns boolean status."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    minted_id = sites.add_note("SID-00003", "Temporary note to be purged.")
    assert any(n["note_id"] == minted_id for n in sites["SID-00003"]["notes"])

    removed = sites.remove_note("SID-00003", minted_id)
    assert removed is True
    assert not any(n["note_id"] == minted_id for n in sites["SID-00003"]["notes"])

    assert sites.remove_note("SID-00003", "NOT-99999") is False


@pytest.mark.regression
@pytest.mark.unit
def test_remove_note_missing_site_raises_key_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify calling remove_note on a non-existent site ID raises KeyError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(KeyError) as exc_info:
        sites.remove_note("SID-99999", "NOT-00001")
    assert "SID-99999" in str(exc_info.value)


@pytest.mark.unit
def test_alias_management_lifecycle(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify add_alias and remove_alias correctly manage alias collections without duplication."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    novel_alias = "National Cemetery at Gettysburg"

    added = sites.add_alias("SID-00003", novel_alias)
    assert added is True
    assert novel_alias in sites["SID-00003"]["aliases"]

    assert sites.add_alias("SID-00003", novel_alias) is False

    removed = sites.remove_alias("SID-00003", novel_alias)
    assert removed is True
    assert novel_alias not in sites["SID-00003"]["aliases"]

    assert sites.remove_alias("SID-00003", "Unlisted Alias") is False


@pytest.mark.regression
@pytest.mark.unit
def test_add_alias_missing_site_raises_key_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify add_alias on non-existent site ID raises KeyError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(KeyError) as exc_info:
        sites.add_alias("SID-99999", "Phantom Alias")
    assert "SID-99999" in str(exc_info.value)


@pytest.mark.unit
def test_add_alias_empty_string_returns_false(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify add_alias with empty or whitespace string returns False."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.add_alias("SID-00003", "   ") is False


@pytest.mark.regression
@pytest.mark.unit
def test_remove_alias_missing_site_raises_key_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify remove_alias on non-existent site ID raises KeyError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(KeyError) as exc_info:
        sites.remove_alias("SID-99999", "Any Alias")
    assert "SID-99999" in str(exc_info.value)


@pytest.mark.unit
def test_remove_alias_empty_or_non_string_returns_false(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify remove_alias with empty or non-string argument safely returns False."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.remove_alias("SID-00003", "   ") is False
    assert sites.remove_alias("SID-00003", None) is False  # type: ignore[arg-type]


# ==============================================================================
# GROUP 6: Deprecation (delete), Graveyard Management & Foreign Key Cascading
# Note: Soft-deletion transitions entities to the graveyard partition, enforces
# valid syntax and existence for superseded_by pointers, and repoints foreign keys.
# ==============================================================================


@pytest.mark.unit
def test_delete_missing_site_returns_false(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify deleting a non-existent site ID returns False."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.delete("SID-99999") is False


@pytest.mark.unit
def test_delete_soft_transitions_to_graveyard(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify soft-delete moves active site to graveyard with DEFUNCT status and is_deprecated True."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    initial_active_len = len(sites)
    initial_total_len = sites.total_count

    success = sites.delete("SID-00001", hard_delete=False)
    assert success is True
    assert "SID-00001" not in sites
    assert "SID-00001" in sites.graveyard
    assert len(sites) == initial_active_len - 1
    assert sites.total_count == initial_total_len

    tombstone = sites.graveyard["SID-00001"]
    assert tombstone["is_deprecated"] is True
    assert tombstone["operational_status"] == "DEFUNCT"
    assert tombstone["superseded_by"] is None
    assert sites.is_dirty is True


@pytest.mark.unit
def test_delete_soft_with_valid_superseded_by(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify soft-delete attaches valid superseded_by pointer on the graveyard record."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    success = sites.delete("SID-00001", superseded_by="SID-00003")
    assert success is True
    assert sites.graveyard["SID-00001"]["superseded_by"] == "SID-00003"


@pytest.mark.regression
@pytest.mark.unit
def test_delete_invalid_superseded_syntax_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify non-conforming superseded_by identifier syntax raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.delete("SID-00001", superseded_by="INVALID-ID-FORMAT")
    assert "must conform to '^SID-\\d{5}$'" in str(exc_info.value)


@pytest.mark.regression
@pytest.mark.unit
def test_delete_unregistered_superseded_target_raises_key_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify superseded_by target pointing to non-existent site ID raises KeyError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(KeyError) as exc_info:
        sites.delete("SID-00001", superseded_by="SID-99999")
    assert "Target superseded_by site_id 'SID-99999' not found" in str(exc_info.value)


@pytest.mark.unit
def test_delete_already_graveyard_updates_pointer(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify calling delete on an existing tombstone updates its superseded_by target."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.graveyard["SID-00015"]["superseded_by"] is None

    success = sites.delete("SID-00015", superseded_by="SID-00003")
    assert success is True
    assert sites.graveyard["SID-00015"]["superseded_by"] == "SID-00003"
    assert sites.is_dirty is True


@pytest.mark.unit
def test_delete_already_graveyard_without_superseded_returns_true(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify calling delete on an existing tombstone without replacement target is a safe no-op returning True."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert "SID-00002" in sites.graveyard
    success = sites.delete("SID-00002", hard_delete=False, superseded_by=None)
    assert success is True


@pytest.mark.unit
def test_delete_hard_purges_permanently(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify hard_delete=True permanently removes record from both active and graveyard sets."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    initial_total = sites.total_count

    success = sites.delete("SID-00001", hard_delete=True)
    assert success is True
    assert "SID-00001" not in sites
    assert "SID-00001" not in sites.graveyard
    assert sites.total_count == initial_total - 1
    assert sites.is_dirty is True


@pytest.mark.unit
def test_delete_hard_purges_graveyard_tombstone(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify hard_delete=True permanently removes tombstone residing only in the graveyard."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert "SID-00015" in sites.graveyard
    initial_total = sites.total_count

    success = sites.delete("SID-00015", hard_delete=True)
    assert success is True
    assert "SID-00015" not in sites.graveyard
    assert sites.total_count == initial_total - 1


@pytest.mark.regression
@pytest.mark.unit
def test_repoint_locations_target_failure_raises_value_error(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify repointing to a non-existent new_location_id raises ValueError."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    with pytest.raises(ValueError) as exc_info:
        sites.repoint_locations("LOC-99999", ["LOC-00042"])
    assert "Foreign key validation failed: new_location_id 'LOC-99999' not found" in str(exc_info.value)


@pytest.mark.unit
def test_repoint_locations_cascades_active_and_graveyard(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify repointing updates location_id across both active sites and graveyard tombstones."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    repointed = sites.repoint_locations("LOC-00101", ["LOC-00042"])
    assert repointed == 2
    assert sites["SID-00001"]["location_id"] == "LOC-00101"
    assert sites.graveyard["SID-00002"]["location_id"] == "LOC-00101"
    assert sites.is_dirty is True


@pytest.mark.unit
def test_repoint_locations_with_set_collection(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify repoint_locations accepts a set of old location IDs."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    repointed = sites.repoint_locations("LOC-00101", {"LOC-00042"})
    assert repointed == 2
    assert sites["SID-00001"]["location_id"] == "LOC-00101"


@pytest.mark.unit
def test_repoint_locations_unmatched_noop(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify repointing with unmatched old_location_ids returns 0 and leaves manager clean."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    repointed = sites.repoint_locations("LOC-00101", ["LOC-88888"])
    assert repointed == 0
    assert sites.is_dirty is False


# ==============================================================================
# GROUP 7: Search Engine, Spatial Filtering & Atomic Persistence (save)
# Note: Multi-field fuzzy matching queries active and graveyard records across
# names, aliases, types, and coordinates, while save enforces the Safe Backup
# Protocol and JSON sorting invariants.
# ==============================================================================


@pytest.mark.unit
def test_search_exact_name_match(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search returns exact substring match on site name."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    results = sites.search(query="Gettysburg")
    assert len(results) >= 1
    assert any(s["site_id"] == "SID-00003" for s in results)


@pytest.mark.unit
def test_search_alias_match(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search matches query against alias array entries."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    results = sites.search(query="Soldiers' National Cemetery")
    assert len(results) >= 1
    assert any(s["site_id"] == "SID-00003" for s in results)


@pytest.mark.unit
def test_search_fuzzy_matching(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search finds matching sites despite typographical variations when fuzzy enabled."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    results = sites.search(query="Gettisburg Nationl Cemetry", use_fuzzy=True, fuzzy_threshold=0.70)
    assert len(results) >= 1
    assert any(s["site_id"] == "SID-00003" for s in results)


@pytest.mark.unit
def test_search_fuzzy_alias_match_threshold(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search matches fuzzy threshold against alias even when name ratio falls short."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    results = sites.search(query="Soldyers Nationel Cemetary", use_fuzzy=True, fuzzy_threshold=0.75)
    assert len(results) >= 1
    assert any(s["site_id"] == "SID-00003" for s in results)


@pytest.mark.unit
def test_search_site_type_filter(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search strictly isolates records matching specified site_type."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    results = sites.search(site_type="CHURCH")
    assert len(results) > 0
    assert all(s["site_type"] == "CHURCH" for s in results)


@pytest.mark.unit
def test_search_location_id_filter(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search isolates records matching specified location_id."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    results = sites.search(location_id="LOC-00042")
    assert len(results) > 0
    assert all(s["location_id"] == "LOC-00042" for s in results)


@pytest.mark.unit
def test_search_has_coordinates_filter(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search filters records by coordinate presence."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)

    sites.add(
        name="Unmapped Historic Marker",
        site_type="LANDMARK",
        location_id="LOC-00042",
        address=None,
    )

    with_coords = sites.search(has_coordinates=True)
    without_coords = sites.search(has_coordinates=False)

    assert len(with_coords) > 0
    assert len(without_coords) > 0
    assert all(s.get("address", {}).get("coordinates") is not None for s in with_coords)
    assert any(s["name"] == "Unmapped Historic Marker" for s in without_coords)


@pytest.mark.unit
def test_search_has_coordinates_non_dict_coords(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify _has_coords returns False when address is a dict but coordinates is None/non-dict."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    sites.add(
        name="Address Without Coords Object",
        site_type="LANDMARK",
        location_id="LOC-00042",
        address={"address_line_1": "123 Main St", "postal_code": "17013"},
    )
    without_coords = sites.search(has_coordinates=False)
    assert any(s["name"] == "Address Without Coords Object" for s in without_coords)


@pytest.mark.unit
def test_search_multiple_exact_matches_cycles_loop(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search processes multiple sequential matches to cycle the loop edge."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    sites.add(name="Repeated Keystone Alpha", site_type="LANDMARK", location_id="LOC-00042")
    sites.add(name="Repeated Keystone Beta", site_type="LANDMARK", location_id="LOC-00042")

    results = sites.search(query="Repeated Keystone")
    assert len(results) >= 2
    names = [s["name"] for s in results]
    assert "Repeated Keystone Alpha" in names
    assert "Repeated Keystone Beta" in names


@pytest.mark.unit
def test_search_use_fuzzy_disabled_skips_fuzzy_evaluation(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search with use_fuzzy=False skips fuzzy evaluation and returns empty when exact match fails."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    results = sites.search(query="Gettisburg Nationl Cemetry", use_fuzzy=False)
    assert len(results) == 0


@pytest.mark.unit
def test_search_query_none_returns_all_candidates(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search with query=None returns all candidate records."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    results = sites.search(query=None)
    assert len(results) == 15


@pytest.mark.unit
def test_search_graveyard_inclusion(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify search excludes graveyard by default but includes tombstones when requested."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    tombstone = sites.graveyard["SID-00015"]
    target_name = tombstone["name"]

    excluded = sites.search(query=target_name, include_graveyard=False)
    included = sites.search(query=target_name, include_graveyard=True)

    assert not any(s["site_id"] == "SID-00015" for s in excluded)
    assert any(s["site_id"] == "SID-00015" for s in included)


@pytest.mark.unit
def test_find_one_resolution(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify find_one resolves single top record or None when threshold unsatisfied."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    top_match = sites.find_one(query="Gettysburg National Cemetery")
    assert top_match is not None
    assert top_match["site_id"] == "SID-00003"


@pytest.mark.unit
def test_find_one_no_match_returns_none(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify find_one returns None when no records satisfy criteria."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    result = sites.find_one(query="Completely Non-Existent Entity Name", fuzzy_threshold=0.99)
    assert result is None


@pytest.mark.unit
def test_save_clean_state_skips_write(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify save returns False and avoids disk writes when manager is not dirty."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.is_dirty is False
    saved = sites.save()
    assert saved is False


@pytest.mark.unit
def test_save_force_persists_clean_state(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify save with force=True executes disk persistence even when is_dirty is False."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert sites.is_dirty is False
    saved = sites.save(force=True, create_backup=False)
    assert saved is True


@pytest.mark.integration
def test_save_dirty_state_persists_and_cleans(tmp_path: Path, mock_loc: Any) -> None:
    """Verify save serializes mutated records, sorts by site_id, and clears is_dirty."""
    target_file = tmp_path / "entities" / "sites.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(json.dumps({"sites": []}), encoding="utf-8")

    sites = GDASites(locations_provider=mock_loc, filepath=target_file)
    sites.add(name="Site Bravo", site_type="LANDMARK", location_id="LOC-00042")
    sites.add(name="Site Alpha", site_type="LANDMARK", location_id="LOC-00042")

    assert sites.is_dirty is True
    saved = sites.save(create_backup=False)
    assert saved is True
    assert sites.is_dirty is False


@pytest.mark.integration
def test_save_sorts_active_and_graveyard_records(golden_sites_file: Path, tmp_path: Path, mock_loc: Any) -> None:
    """Verify save serializes and sorts both active and graveyard records together."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    assert len(sites.graveyard) > 0
    sites.add(name="Zeta Historical Site", site_type="LANDMARK", location_id="LOC-00042")
    sites.add(name="Omega Historical Site", site_type="LANDMARK", location_id="LOC-00042")

    target_file = tmp_path / "combined_sorted_sites.json"
    saved = sites.save(output_path=target_file, create_backup=False)
    assert saved is True

    payload = json.loads(target_file.read_text(encoding="utf-8"))
    ids = [s["site_id"] for s in payload["sites"]]
    assert ids == sorted(ids)
    assert "SID-00002" in ids


@pytest.mark.integration
def test_save_custom_output_path(golden_sites_file: Path, tmp_path: Path, mock_loc: Any) -> None:
    """Verify save persists to an explicit output_path without overwriting the default filepath."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    custom_target = tmp_path / "custom_sites_output.json"

    sites.add(name="Brand New Site", site_type="LANDMARK", location_id="LOC-00042")
    saved = sites.save(output_path=custom_target, create_backup=False)

    assert saved is True
    assert custom_target.exists()
    assert sites.is_dirty is False

    custom_payload = json.loads(custom_target.read_text(encoding="utf-8"))
    assert any(s["name"] == "Brand New Site" for s in custom_payload["sites"])


@pytest.mark.unit
def test_save_io_exception_propagates(golden_sites_file: Path, mock_loc: Any) -> None:
    """Verify save raises exception when GDAUtil encounters an unhandled IO error."""
    sites = GDASites(locations_provider=mock_loc, filepath=golden_sites_file)
    sites.add(name="Faulty Persistence Site", site_type="LANDMARK", location_id="LOC-00042")
    with patch("gdadomain.sites.GDAUtil.save_json", side_effect=IOError("Simulated disk write failure")):
        with pytest.raises(IOError, match="Simulated disk write failure"):
            sites.save()