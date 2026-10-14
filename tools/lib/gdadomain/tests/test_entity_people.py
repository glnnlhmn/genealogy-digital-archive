# Name: test_entity_people.py
# Path: tools/lib/gdadomain/tests/test_entity_people.py
# Version: 1.0.0+build.r6

"""Unit test suite for the GDAPeople domain entity manager.

Operational Role:
    Validates IND-XXXXX monotonic minting, display name assembly,
    reciprocal association attributes, CRUD mutations, note collection
    subsystems, and atomic persistence using synthetic fixture baselines.

Test Structure & Protocol:
    - Atomized tests: 1:1 behavioral contract mapping per failure boundary.
    - Fully decorated: Strictly marked with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.regression.
    - Dependencies: Isolated pytest tmp_path fixtures and static golden/failure fixtures from conftest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from gdacore.util import GDAUtil
from gdadomain.people import GDAPeople


# ==============================================================================
# GROUP 1: Introspection, Initialization & Disk Loading
# Note: Verification of IntrospectableMixin, safe missing-file defaults,
# corrupt JSON rejection, context manager transactions, and reload/refresh logic.
# ==============================================================================


@pytest.mark.unit
def test_help_directory_generation(capsys: Any, tmp_path: Path) -> None:
    """Verify people.help() outputs all public members without listing private attributes."""
    pfile = tmp_path / "empty_people.json"
    mgr = GDAPeople(filepath=pfile, auto_load=False)
    mgr.help()

    captured = capsys.readouterr().out
    assert "add" in captured
    assert "edit" in captured
    assert "delete" in captured
    assert "save" in captured
    assert "link_kinship" in captured
    assert "unlink_kinship" in captured
    assert "add_union" in captured

    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    member_lines = [l for l in lines if l.startswith("-") or l.startswith("*")]
    for ml in member_lines:
        assert not ml.lstrip("- *").strip().startswith("_people")


@pytest.mark.smoke
@pytest.mark.unit
def test_help_member_signature(capsys: Any, tmp_path: Path) -> None:
    """Verify people.help('add') prints call signature, parameter types, and docstring."""
    pfile = tmp_path / "empty_people.json"
    mgr = GDAPeople(filepath=pfile, auto_load=False)
    mgr.help("add")

    captured = capsys.readouterr().out
    assert "add(" in captured
    assert "canonical_name" in captured
    assert "Register a new person" in captured


@pytest.mark.unit
def test_help_invalid_member(capsys: Any, tmp_path: Path) -> None:
    """Verify people.help() gracefully handles unknown member names without exceptions."""
    pfile = tmp_path / "empty_people.json"
    mgr = GDAPeople(filepath=pfile, auto_load=False)
    mgr.help("non_existent_method")

    captured = capsys.readouterr().out
    assert "not found" in captured or "No public member" in captured or "non_existent_method" in captured


@pytest.mark.smoke
@pytest.mark.unit
def test_init_missing_file_initializes_clean_state(tmp_path: Path) -> None:
    """Verify missing file initializes empty registry and flags is_dirty as False."""
    pfile = tmp_path / "missing_people.json"
    mgr = GDAPeople(filepath=pfile, auto_load=True)
    assert mgr.count == 0
    assert mgr.is_dirty is False


@pytest.mark.unit
def test_init_without_auto_load_does_not_populate(golden_people_file: Path) -> None:
    """Verify initializing GDAPeople with auto_load=False leaves memory empty until loaded."""
    mgr = GDAPeople(filepath=golden_people_file, auto_load=False)
    assert mgr.count == 0


@pytest.mark.regression
@pytest.mark.unit
def test_load_corrupted_json_raises_exception(failure_people_syntax: Path) -> None:
    """Verify malformed JSON payload raises an exception during instantiation."""
    with pytest.raises(Exception):
        GDAPeople(filepath=failure_people_syntax, auto_load=True)


@pytest.mark.regression
@pytest.mark.unit
def test_load_skips_empty_ids(failure_people_missing_id: Path) -> None:
    """Verify load skips records missing person_id payloads and hydrates subsequent records."""
    mgr = GDAPeople(filepath=failure_people_missing_id, auto_load=True)
    assert "" not in mgr
    assert mgr.count == 2
    assert "IND-00001" in mgr
    assert "IND-00002" in mgr


@pytest.mark.regression
@pytest.mark.unit
def test_load_envelope_and_schema_payload(failure_envelope_and_schema: Path) -> None:
    """Verify load successfully reads persons array from failed_envelope_and_schema fixture."""
    mgr = GDAPeople(filepath=failure_envelope_and_schema, auto_load=True)
    assert mgr.count == 62
    assert "IND-00000" in mgr
    assert "IND-00029" in mgr


@pytest.mark.regression
@pytest.mark.unit
def test_load_locations_and_redirects_fixture(failure_locations_and_redirects: Path) -> None:
    """Verify load parses persons from failed_locations_and_redirects fixture."""
    mgr = GDAPeople(filepath=failure_locations_and_redirects, auto_load=True)
    assert mgr.count == 62
    assert "IND-00043" in mgr


@pytest.mark.regression
@pytest.mark.unit
def test_load_topology_and_orphans_fixture(failure_topology_and_orphans: Path) -> None:
    """Verify load processes topology fixture containing orphaned edge pointers."""
    mgr = GDAPeople(filepath=failure_topology_and_orphans, auto_load=True)
    assert mgr.count == 62
    assert "IND-00083" in mgr


@pytest.mark.unit
def test_load_skips_non_dict_items_in_raw_list(tmp_path: Path) -> None:
    """Verify load ignores items in raw payload that are not dictionaries."""
    pfile = tmp_path / "non_dict_items.json"
    pfile.write_text(
        json.dumps({
            "schema_version": "1.0.0",
            "people": [
                "not_a_dictionary_item",
                {"person_id": "IND-00001", "canonical_name": {"given": "Valid"}},
            ],
        }),
        encoding="utf-8",
    )
    mgr = GDAPeople(filepath=pfile, auto_load=True)
    assert mgr.count == 1
    assert "IND-00001" in mgr


@pytest.mark.unit
def test_load_reads_metadata_envelope(tmp_path: Path) -> None:
    """Verify load preserves metadata fields and ignores non-standard envelope keys."""
    pfile = tmp_path / "meta_test.json"
    pfile.write_text(
        json.dumps({
            "_name": "meta_test.json",
            "_path": str(pfile),
            "$schema": "schemas/entities/person_registry.schema.json",
            "schema_version": "1.0.0",
            "created_at": "2026-01-01T00:00:00Z",
            "last_modified": "2026-01-02T00:00:00Z",
            "unrelated_metadata": 999,
            "people": [{"person_id": "IND-00001", "canonical_name": {"given": "Test"}}],
        }),
        encoding="utf-8",
    )
    mgr = GDAPeople(filepath=pfile, auto_load=True)
    assert mgr.count == 1
    assert mgr._registry_metadata["schema_version"] == "1.0.0"


@pytest.mark.unit
def test_load_raw_list_and_scalar_payload(tmp_path: Path) -> None:
    """Verify load populates partitions on list payloads and handles scalar JSON root."""
    pfile = tmp_path / "raw_list_people.json"
    pfile.write_text(
        json.dumps([
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "ActivePerson"},
                "is_deprecated": False,
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"given": "TombstonePerson"},
                "is_deprecated": True,
            },
        ]),
        encoding="utf-8",
    )
    mgr = GDAPeople(filepath=pfile, auto_load=True)
    assert mgr.count == 1
    assert "IND-00001" in mgr
    assert mgr.exists("IND-00002", include_graveyard=True) is True

    # Exercise line 277 fallback: data is valid JSON but neither dict nor list
    scalar_file = tmp_path / "scalar_people.json"
    scalar_file.write_text("12345", encoding="utf-8")
    scalar_mgr = GDAPeople(filepath=scalar_file, auto_load=True)
    assert scalar_mgr.count == 0


@pytest.mark.unit
def test_refresh_discards_unstaged_mutations(golden_people_file: Path) -> None:
    """Verify refresh discards uncommitted modifications and restores disk state."""
    mgr = GDAPeople(filepath=golden_people_file, auto_load=True)
    initial_count = mgr.count
    mgr.add(canonical_name={"given": "Draft"}, sex="M")
    assert mgr.is_dirty is True
    assert mgr.count == initial_count + 1

    mgr.refresh()
    assert mgr.is_dirty is False
    assert mgr.count == initial_count


@pytest.mark.unit
def test_reload_alias_method(golden_people_file: Path) -> None:
    """Verify reload() functions as a direct alias for refresh."""
    mgr = GDAPeople(filepath=golden_people_file, auto_load=True)
    initial_count = mgr.count
    mgr.add(canonical_name={"given": "Draft"}, sex="M")
    assert mgr.is_dirty is True
    mgr.reload()
    assert mgr.is_dirty is False
    assert mgr.count == initial_count


@pytest.mark.unit
def test_context_manager_commits_on_clean_exit(tmp_path: Path) -> None:
    """Verify context manager automatically commits dirty state upon clean exit."""
    pfile = tmp_path / "people_cm.json"
    with GDAPeople(filepath=pfile, auto_load=False) as mgr:
        mgr.add(canonical_name={"given": "ContextPerson"}, sex="M")
    reloaded = GDAPeople(filepath=pfile, auto_load=True)
    assert reloaded.count == 1


@pytest.mark.unit
def test_context_manager_suppresses_save_on_clean_exit_when_not_dirty(tmp_path: Path) -> None:
    """Verify context manager does not write to disk if no mutations occurred."""
    pfile = tmp_path / "people_clean_cm.json"
    with GDAPeople(filepath=pfile, auto_load=False):
        pass
    assert not pfile.exists()


@pytest.mark.unit
def test_context_manager_suppresses_save_on_exception(tmp_path: Path) -> None:
    """Verify context manager discards writes if an exception interrupts execution."""
    pfile = tmp_path / "people_cm_fail.json"
    try:
        with GDAPeople(filepath=pfile, auto_load=False) as mgr:
            mgr.add(canonical_name={"given": "FailPerson"}, sex="M")
            raise RuntimeError("Interrupting transaction")
    except RuntimeError:
        pass
    assert not pfile.exists()


# ==============================================================================
# GROUP 2: Collection Protocols & Subscript Ergonomics
# Note: Verification of sized count, iteration isolation, membership, and subscript.
# ==============================================================================


@pytest.mark.unit
def test_len_returns_active_count(golden_people_file: Path) -> None:
    """Verify len(people) returns the count of registered persons."""
    mgr = GDAPeople(filepath=golden_people_file, auto_load=True)
    assert len(mgr) == mgr.count


@pytest.mark.unit
def test_total_count_property_combines_active_and_graveyard(tmp_path: Path) -> None:
    """Verify total_count accurately returns the sum of active people and graveyard tombstones."""
    mgr = GDAPeople(filepath=tmp_path / "total_count.json", auto_load=False)
    p_active = mgr.add(canonical_name={"given": "Active"}, sex="M")
    p_defunct = mgr.add(canonical_name={"given": "Defunct"}, sex="F")
    mgr.delete(p_defunct, hard_delete=False)

    assert mgr.count == 1
    assert mgr.total_count == 2


@pytest.mark.unit
def test_existing_ids_property_returns_active_id_set(tmp_path: Path) -> None:
    """Verify existing_ids property returns the exact set of active canonical IDs."""
    mgr = GDAPeople(filepath=tmp_path / "existing_ids.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "One"}, sex="M")
    p2 = mgr.add(canonical_name={"given": "Two"}, sex="F")

    assert mgr.existing_ids == {p1, p2}
    mgr.delete(p2, hard_delete=False)
    assert mgr.existing_ids == {p1}


@pytest.mark.unit
def test_iter_yields_isolated_records(golden_people_file: Path) -> None:
    """Verify __iter__ traversal yields deep copies protecting internal state."""
    mgr = GDAPeople(filepath=golden_people_file, auto_load=True)
    pid = mgr.add(canonical_name={"given": "Original"}, sex="M")

    for person in mgr:
        if person["person_id"] == pid:
            person["display_name"] = "Mutated In Iteration"

    assert mgr[pid]["display_name"] != "Mutated In Iteration"


@pytest.mark.unit
def test_iter_empty_registry_yields_zero_items(tmp_path: Path) -> None:
    """Verify __iter__ traversal over an empty registry yields zero items."""
    mgr = GDAPeople(filepath=tmp_path / "empty.json", auto_load=False)
    assert list(mgr) == []


@pytest.mark.unit
def test_contains_active_membership(tmp_path: Path) -> None:
    """Verify 'in' operator returns True for registered person identifiers."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Registered"}, sex="M")
    assert (pid in mgr) is True


@pytest.mark.unit
def test_contains_unregistered_and_non_string_returns_false(tmp_path: Path) -> None:
    """Verify 'in' operator returns False for unregistered IDs and non-string queries."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    assert ("IND-99999" in mgr) is False
    assert (12345 in mgr) is False
    assert (None in mgr) is False


@pytest.mark.unit
def test_getitem_active_retrieval(tmp_path: Path) -> None:
    """Verify subscript access retrieves expected active entity payload."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Jane", "surname": "Doe"}, sex="F")
    record = mgr[pid]
    assert record["person_id"] == pid
    assert record["display_name"] == "Jane Doe"


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_missing_raises_key_error(tmp_path: Path) -> None:
    """Verify subscript access for non-existent person ID raises KeyError."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    with pytest.raises(KeyError, match="IND-99999"):
        _ = mgr["IND-99999"]


@pytest.mark.unit
def test_getitem_transparent_graveyard_redirect(tmp_path: Path) -> None:
    """Verify subscript access transparently resolves tombstone redirect to successor."""
    mgr = GDAPeople(filepath=tmp_path / "redirect.json", auto_load=False)
    p_survivor = mgr.add(canonical_name={"given": "Survivor"}, sex="M")
    p_defunct = mgr.add(canonical_name={"given": "Defunct"}, sex="M")
    mgr.delete(p_defunct, hard_delete=False, superseded_by=p_survivor)

    assert mgr[p_defunct]["person_id"] == p_survivor


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_unredirected_tombstone_raises_key_error(tmp_path: Path) -> None:
    """Verify subscript access for tombstone without target raises KeyError."""
    mgr = GDAPeople(filepath=tmp_path / "tomb_no_target.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Tomb"}, sex="M")
    mgr.delete(pid, hard_delete=False, superseded_by=None)

    with pytest.raises(KeyError, match="not found in registry"):
        _ = mgr[pid]


# ==============================================================================
# GROUP 3: Entity Retrieval & Membership Queries
# Note: Verification of exists, get, get_by_id, and memory isolation.
# ==============================================================================


@pytest.mark.unit
def test_exists_boundary_returns_accurate_status(tmp_path: Path) -> None:
    """Verify exists distinguishes registered persons from unknown tokens."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Test"}, sex="M")
    assert mgr.exists(pid) is True
    assert mgr.exists("IND-99999") is False


@pytest.mark.unit
def test_exists_include_graveyard_boundary(tmp_path: Path) -> None:
    """Verify exists accurately queries active and graveyard partitions."""
    mgr = GDAPeople(filepath=tmp_path / "grave_exists.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "GraveTest"}, sex="M")
    mgr.delete(pid, hard_delete=False)

    assert mgr.exists(pid, include_graveyard=False) is False
    assert mgr.exists(pid, include_graveyard=True) is True


@pytest.mark.unit
def test_get_by_id_memory_isolation(tmp_path: Path) -> None:
    """Verify modifying record returned by get_by_id does not leak into internal memory."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Safe"}, sex="M")
    rec = mgr.get_by_id(pid)
    assert rec is not None
    rec["display_name"] = "Leaked Name"

    fresh_rec = mgr.get_by_id(pid)
    assert fresh_rec is not None
    assert fresh_rec["display_name"] != "Leaked Name"


@pytest.mark.unit
def test_get_method_alias(tmp_path: Path) -> None:
    """Verify get() functions as an alias for get_by_id."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Aliased"}, sex="M")
    assert mgr.get(pid) == mgr.get_by_id(pid)
    assert mgr.get("IND-99999") is None


@pytest.mark.unit
def test_resolve_id_single_and_multihop(tmp_path: Path) -> None:
    """Verify resolve_id traces multi-hop deprecation chains through graveyard."""
    mgr = GDAPeople(filepath=tmp_path / "resolve.json", auto_load=False)
    p_survivor = mgr.add(canonical_name={"given": "A"}, sex="M")
    p_mid = mgr.add(canonical_name={"given": "B"}, sex="M")
    p_old = mgr.add(canonical_name={"given": "C"}, sex="M")

    mgr.delete(p_mid, hard_delete=False, superseded_by=p_survivor)
    mgr.delete(p_old, hard_delete=False, superseded_by=p_mid)

    assert mgr.resolve_id(p_old) == p_survivor
    assert mgr.resolve_id(p_mid) == p_survivor


@pytest.mark.regression
@pytest.mark.unit
def test_resolve_id_dead_end_in_graveyard_returns_none(tmp_path: Path) -> None:
    """Verify resolve_id returns None if target points to defunct ID outside active store."""
    mgr = GDAPeople(filepath=tmp_path / "dead_end.json", auto_load=False)
    mgr._graveyard["IND-00001"] = {
        "person_id": "IND-00001",
        "is_deprecated": True,
        "superseded_by": "IND-00002",
    }
    assert mgr.resolve_id("IND-00001") is None


@pytest.mark.regression
@pytest.mark.unit
def test_resolve_id_circular_loop_returns_none(tmp_path: Path) -> None:
    """Verify resolve_id safely detects circular redirect loops without stack overflow."""
    mgr = GDAPeople(filepath=tmp_path / "circular.json", auto_load=False)
    mgr._graveyard["IND-00001"] = {"person_id": "IND-00001", "is_deprecated": True, "superseded_by": "IND-00002"}
    mgr._graveyard["IND-00002"] = {"person_id": "IND-00002", "is_deprecated": True, "superseded_by": "IND-00001"}

    assert mgr.resolve_id("IND-00001") is None


@pytest.mark.regression
@pytest.mark.unit
def test_resolve_id_recursion_error_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_id catches RecursionError and returns None."""
    mgr = GDAPeople(filepath=tmp_path / "recursion.json", auto_load=False)
    mgr._graveyard["IND-00001"] = {
        "person_id": "IND-00001",
        "is_deprecated": True,
        "superseded_by": "IND-00002",
    }

    def _mock_resolve(*args: Any, **kwargs: Any) -> Any:
        raise RecursionError("Mocked cyclic depth exceeded")

    monkeypatch.setattr(GDAUtil, "resolve_superseded_id", _mock_resolve)
    assert mgr.resolve_id("IND-00001") is None


# ==============================================================================
# GROUP 4: Record Creation (add) & Monotonic Minting
# Note: Verification of sequential allocation, display name assembly, and validation.
# ==============================================================================

@pytest.mark.unit
def test_validate_person_schema_non_list_relations(tmp_path: Path) -> None:
    """Verify validate_person_schema flags non-list associated_people and unions containers."""
    mgr = GDAPeople(filepath=tmp_path / "val_non_list.json", auto_load=False)

    # 1. assoc and unions are None (exercises branches 358->374 and 375->387)
    errors_none = mgr.validate_person_schema({
        "person_id": "IND-00001",
        "associated_people": None,
        "unions": None,
    })
    assert errors_none == []

    # 2. assoc and unions are not lists (exercises line 360 and line 377)
    errors_invalid = mgr.validate_person_schema({
        "person_id": "IND-00001",
        "associated_people": "not-a-list",
        "unions": "not-a-list",
    })
    assert "'associated_people' must be a list." in errors_invalid
    assert "'unions' must be a list." in errors_invalid


@pytest.mark.unit
def test_add_payload_dictionary_invocation(tmp_path: Path) -> None:
    """Verify add accepts an existing full person record dictionary as canonical_name."""
    mgr = GDAPeople(filepath=tmp_path / "dict_payload.json", auto_load=False)
    record_payload = {
        "person_id": "IND-00055",
        "canonical_name": {"given": "Positional", "surname": "Record"},
        "sex": "F",
        "associated_people": [{"person_id": "IND-00001", "role": "FATH"}],
        "unions": [{"spouse_id": "IND-00002", "status": "MARRIED"}],
        "notes": [{"text": "Ingested via payload dictionary"}],
        "custom_attribute": "arbitrary_value",
    }

    # Exercise lines 508-529 (isinstance(canonical_name, dict) and "canonical_name" in canonical_name)
    pid = mgr.add(record_payload, caller_override_field="extra_val")

    assert pid == "IND-00055"
    assert mgr[pid]["sex"] == "F"
    assert mgr[pid]["canonical_name"]["given"] == "Positional"
    assert mgr[pid]["custom_attribute"] == "arbitrary_value"
    assert mgr[pid]["caller_override_field"] == "extra_val"
    assert len(mgr[pid]["associated_people"]) == 1
    assert len(mgr[pid]["unions"]) == 1
    assert len(mgr[pid]["notes"]) == 1

@pytest.mark.unit
def test_mint_initial_id_empty_registry(tmp_path: Path) -> None:
    """Verify auto-minting assigns IND-00001 when registry is empty."""
    mgr = GDAPeople(filepath=tmp_path / "empty.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "First", "surname": "Person"}, sex="M")
    assert pid == "IND-00001"


@pytest.mark.unit
def test_mint_next_id_incremental(tmp_path: Path) -> None:
    """Verify sequential calls to add increment monotonic high-water mark."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    mgr.add(canonical_name={"given": "A"}, sex="M", person_id="IND-00008")
    mgr.add(canonical_name={"given": "B"}, sex="F", person_id="IND-00003")
    assert mgr.mint_next_person_id() == "IND-00009"


@pytest.mark.unit
def test_mint_next_id_when_max_person_num_zero_triggers_rescan(tmp_path: Path) -> None:
    """Verify _mint_next_id calls find_max_numeric_id when _max_person_num is 0."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    mgr._people["IND-00012"] = {"person_id": "IND-00012", "canonical_name": {"given": "Existing"}}
    mgr._max_person_num = 0
    new_id = mgr._mint_next_id()
    assert new_id == "IND-00013"


@pytest.mark.unit
def test_mint_skips_irregular_id_format(tmp_path: Path) -> None:
    """Verify monotonic calculation ignores non-conforming identifier strings."""
    mgr = GDAPeople(filepath=tmp_path / "irregular.json", auto_load=False)
    mgr._people["IND-CUSTOM"] = {"person_id": "IND-CUSTOM"}
    assert mgr._mint_next_id() == "IND-00001"


@pytest.mark.unit
def test_build_display_name_combinations() -> None:
    """Verify build_display_name standardizes various component combinations."""
    name_full = {"given": "Jacob", "middle": "B.", "surname": "Lehman", "suffix": "Sr."}
    assert GDAPeople.build_display_name(name_full) == "Jacob B Lehman Sr"

    name_dots = {"given": "J.B.", "middle": "D.", "surname": "Lehman"}
    assert GDAPeople.build_display_name(name_dots) == "JB D Lehman"

    name_raw = {"raw_name": "Old Pioneer"}
    assert GDAPeople.build_display_name(name_raw) == "Old Pioneer"

    assert GDAPeople.build_display_name(None) == "UNKNOWN"
    assert GDAPeople.build_display_name("not a dict") == "UNKNOWN"
    assert GDAPeople.build_display_name({}) == "UNKNOWN"
    assert GDAPeople.build_display_name({"given": "   ", "raw_name": "   "}) == "UNKNOWN"


@pytest.mark.unit
def test_add_explicit_valid_id(tmp_path: Path) -> None:
    """Verify add registers explicit valid identifier token."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Anna"}, sex="F", person_id="IND-00025")
    assert pid == "IND-00025"
    assert pid in mgr


@pytest.mark.regression
@pytest.mark.unit
def test_add_malformed_id_raises_value_error(tmp_path: Path) -> None:
    """Verify non-conforming person_id pattern raises ValueError."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    with pytest.raises(ValueError, match="Malformed person_id pattern"):
        mgr.add(canonical_name={"given": "Anna"}, sex="F", person_id="INVALID-ID")


@pytest.mark.regression
@pytest.mark.unit
def test_add_duplicate_id_raises_key_error(tmp_path: Path) -> None:
    """Verify adding person with existing identifier raises KeyError."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    mgr.add(canonical_name={"given": "Anna"}, sex="F", person_id="IND-00010")
    with pytest.raises(KeyError, match="already exists in registry"):
        mgr.add(canonical_name={"given": "Mary"}, sex="F", person_id="IND-00010")


@pytest.mark.unit
def test_add_normalizes_sex_token(tmp_path: Path) -> None:
    """Verify add normalizes whitespace and defaults invalid sex tokens."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid1 = mgr.add(canonical_name={"given": "David"}, sex="  m  ")
    pid2 = mgr.add(canonical_name={"given": "Child"}, sex=None)
    assert mgr[pid1]["sex"] == "M"
    assert mgr[pid2]["sex"] == "U"


@pytest.mark.unit
def test_add_input_memory_isolation(tmp_path: Path) -> None:
    """Verify mutating caller inputs after add() does not affect internal store."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    assoc = [{"person_id": "IND-00001", "role": "FATH"}]
    unions = [{"spouse_id": "IND-00002", "status": "MARRIED"}]
    notes = [{"text": "Original Note"}]

    pid = mgr.add(
        canonical_name={"given": "Connected"},
        sex="M",
        associated_people=assoc,
        unions=unions,
        notes=notes,
    )

    assoc.append({"person_id": "IND-00003", "role": "MOTH"})
    unions[0]["status"] = "DIVORCED"
    notes[0]["text"] = "Mutated Note"

    stored = mgr[pid]
    assert len(stored["associated_people"]) == 1
    assert stored["unions"][0]["status"] == "MARRIED"
    assert stored["notes"][0]["note_text"] == "Original Note"


@pytest.mark.unit
def test_validate_person_schema_diagnostics(tmp_path: Path) -> None:
    """Verify validate_person_schema exercises all branch boundaries in person payloads."""
    mgr = GDAPeople(filepath=tmp_path / "val.json", auto_load=False)
    assert "Person payload must be a dictionary." in mgr.validate_person_schema("not-a-dict")

    payload = {
        "person_id": "BAD-ID",
        "sex": "INVALID-SEX",
        "associated_people": [
            "not-a-dict",
            {"person_id": "BAD-APID", "role": "INVALID-ROLE"},
            {"person_id": "IND-00001", "role": "FATH"},
            {"person_id": None, "role": None},
            {},
        ],
        "unions": [
            "not-a-dict",
            {"spouse_id": "BAD-SP"},
            {"spouse_id": "IND-00002", "status": "MARRIED"},
            {"spouse_id": None},
            {},
        ],
        "notes": "not-a-list",
    }
    errors = mgr.validate_person_schema(payload)
    assert any("Invalid person_id format" in e for e in errors)
    assert any("associated_people[0] must be a dictionary" in e for e in errors)
    assert any("Invalid person_id 'BAD-APID'" in e for e in errors)
    assert any("unions[0] must be a dictionary" in e for e in errors)
    assert any("Invalid spouse_id 'BAD-SP'" in e for e in errors)
    assert any("'notes' must be a list" in e for e in errors)


@pytest.mark.regression
@pytest.mark.unit
def test_add_schema_validation_failure_raises_value_error(tmp_path: Path) -> None:
    """Verify add raises ValueError when payload triggers schema validation violations."""
    mgr = GDAPeople(filepath=tmp_path / "add_val_err.json", auto_load=False)
    with pytest.raises(ValueError, match="Person schema validation failed"):
        mgr.add(
            canonical_name={"given": "ErrorPerson"},
            associated_people=["not-a-dictionary"],
        )


# ==============================================================================
# GROUP 5: Record Updates, Property Validation & Note Operations
# Note: Verification of scalar edits, note collection methods, and dirty flagging.
# ==============================================================================

@pytest.mark.unit
def test_mark_dirty_stages_active_and_graveyard_records(tmp_path: Path) -> None:
    """Verify mark_dirty stages active and tombstone identifiers and flags manager dirty."""
    mgr = GDAPeople(filepath=tmp_path / "mark_dirty.json", auto_load=False)
    p_active = mgr.add(canonical_name={"given": "Active"}, sex="M")
    p_tomb = mgr.add(canonical_name={"given": "Tomb"}, sex="F")
    mgr.delete(p_tomb, hard_delete=False)
    mgr.save(force=True, create_backup=False)
    assert mgr.is_dirty is False
    mgr.dirty_ids.clear()

    # Mark active ID as dirty (exercises lines 474-476 active branch)
    mgr.mark_dirty(p_active)
    assert p_active in mgr.dirty_ids
    assert mgr.is_dirty is True

    # Mark graveyard ID as dirty (exercises lines 474-476 graveyard branch)
    mgr.mark_dirty(p_tomb)
    assert p_tomb in mgr.dirty_ids

    # Unregistered ID is ignored without flagging dirty
    mgr.dirty_ids.clear()
    mgr._is_dirty = False
    mgr.mark_dirty("IND-99999")
    assert "IND-99999" not in mgr.dirty_ids
    assert mgr.is_dirty is False

@pytest.mark.unit
def test_edit_scalar_fields_and_dirty_flag(tmp_path: Path) -> None:
    """Verify editing scalar fields updates record and marks manager dirty."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Jake"}, sex="M")
    assert mgr.is_dirty is True
    mgr.save(force=True, create_backup=False)
    assert mgr.is_dirty is False

    modified = mgr.edit(pid, {"canonical_name": {"given": "Jacob", "surname": "Lehman"}})
    assert modified is True
    assert mgr[pid]["display_name"] == "Jacob Lehman"
    assert mgr.is_dirty is True


@pytest.mark.regression
@pytest.mark.unit
def test_edit_missing_person_raises_key_error(tmp_path: Path) -> None:
    """Verify editing non-existent person ID raises KeyError."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    with pytest.raises(KeyError, match="does not exist in registry"):
        mgr.edit("IND-99999", {"sex": "F"})


@pytest.mark.regression
@pytest.mark.unit
def test_edit_graveyard_person_raises_key_error(tmp_path: Path) -> None:
    """Verify editing deprecated person in graveyard raises KeyError."""
    mgr = GDAPeople(filepath=tmp_path / "grave_edit.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Tomb"}, sex="M")
    mgr.delete(pid, hard_delete=False)
    with pytest.raises(KeyError, match="Cannot edit deprecated person"):
        mgr.edit(pid, {"sex": "F"})


@pytest.mark.regression
@pytest.mark.unit
def test_edit_immutable_person_id_raises_value_error(tmp_path: Path) -> None:
    """Verify attempting to alter person_id raises ValueError."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Subject"}, sex="M")
    with pytest.raises(ValueError, match="person_id is immutable"):
        mgr.edit(pid, {"person_id": "IND-00999"})


@pytest.mark.regression
@pytest.mark.unit
def test_edit_schema_violation_raises_value_error(tmp_path: Path) -> None:
    """Verify passing invalid structural attributes in edit raises ValueError on schema check."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Subject"}, sex="M")
    with pytest.raises(ValueError, match="Person schema validation failed"):
        mgr.edit(pid, {"associated_people": ["not-a-dictionary"]})


@pytest.mark.unit
def test_edit_deprecation_flag_delegates_to_soft_delete(tmp_path: Path) -> None:
    """Verify edit with is_deprecated=True routes to soft delete with superseded redirection."""
    mgr = GDAPeople(filepath=tmp_path / "edit_deprecate.json", auto_load=False)
    p_survivor = mgr.add(canonical_name={"given": "Survivor"}, sex="M")
    p_defunct = mgr.add(canonical_name={"given": "Defunct"}, sex="F")

    modified = mgr.edit(
        p_defunct,
        {"is_deprecated": True, "superseded_by": p_survivor},
    )

    assert modified is True
    assert p_defunct not in mgr
    assert mgr.exists(p_defunct, include_graveyard=True) is True
    assert mgr.graveyard[p_defunct]["superseded_by"] == p_survivor


@pytest.mark.unit
def test_edit_same_person_id_passes_silently(tmp_path: Path) -> None:
    """Verify passing matching person_id in edit passes without mutating."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Subject"}, sex="M")
    assert mgr.edit(pid, {"person_id": pid}) is False


@pytest.mark.unit
def test_edit_notes_list_subobject(tmp_path: Path) -> None:
    """Verify edit normalizes and modifies notes via GDANoteCollection."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Subject"}, sex="M")

    new_notes = [{"text": "Fresh census finding", "note_type": "RESEARCH"}]
    modified = mgr.edit(pid, {"notes": new_notes})
    assert modified is True
    assert len(mgr[pid]["notes"]) == 1
    assert mgr[pid]["notes"][0]["note_text"] == "Fresh census finding"

    assert mgr.edit(pid, {"notes": new_notes}) is False


@pytest.mark.unit
def test_update_alias_method(tmp_path: Path) -> None:
    """Verify update() executes as alias for edit."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Subject"}, sex="M")
    assert mgr.update(pid, {"sex": "F"}) is True
    assert mgr[pid]["sex"] == "F"


@pytest.mark.unit
def test_edit_overwrite_none_behavior(tmp_path: Path) -> None:
    """Verify overwrite_none=True clears fields, whereas overwrite_none=False preserves them."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Subject"}, sex="M")

    mgr.edit(pid, {"sex": None}, overwrite_none=False)
    assert mgr[pid]["sex"] == "M"

    mgr.edit(pid, {"sex": None}, overwrite_none=True)
    assert mgr[pid]["sex"] is None


@pytest.mark.unit
def test_edit_identical_or_empty_values_returns_false(tmp_path: Path) -> None:
    """Verify editing with identical values or empty payload returns False."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Subject"}, sex="M")
    assert mgr.edit(pid, {}) is False
    assert mgr.edit(pid, {"sex": "M"}) is False


@pytest.mark.unit
def test_add_and_remove_note_lifecycle(tmp_path: Path) -> None:
    """Verify add_note appends sequential note and remove_note excises by note_id."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Subject"}, sex="M")

    note_id = mgr.add_note(pid, "Archival birth record audited.", note_type="RESEARCH")
    assert note_id == "NOT-00001"
    assert mgr[pid]["notes"][0]["note_text"] == "Archival birth record audited."

    removed = mgr.remove_note(pid, note_id)
    assert removed is True
    assert len(mgr[pid]["notes"]) == 0
    assert mgr.remove_note(pid, "NOT-99999") is False


@pytest.mark.regression
@pytest.mark.unit
def test_note_operations_unregistered_person_raises_key_error(tmp_path: Path) -> None:
    """Verify note operations on missing person ID raise KeyError."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    with pytest.raises(KeyError):
        mgr.add_note("IND-99999", "Floating note")
    with pytest.raises(KeyError):
        mgr.remove_note("IND-99999", "NOT-00001")


# ==============================================================================
# GROUP 6: Kinship Relations, Unions & Deletion
# Note: Verification of reciprocal associations, union pairings, and cascade cleanup.
# ==============================================================================


@pytest.mark.unit
def test_delete_lifecycle_and_reciprocal_cleanup(tmp_path: Path) -> None:
    """Verify delete removes person and cleans reciprocal edges on related entities."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "Parent"}, sex="M")
    p2 = mgr.add(canonical_name={"given": "Child"}, sex="F")
    mgr.link_kinship(p1, p2, "FATH")

    assert mgr.delete(p1) is True
    assert p1 not in mgr
    assert len(mgr[p2]["associated_people"]) == 0
    assert mgr.delete("IND-99999") is False


@pytest.mark.unit
def test_delete_soft_transitions_to_graveyard(tmp_path: Path) -> None:
    """Verify delete with hard_delete=False creates tombstone record."""
    mgr = GDAPeople(filepath=tmp_path / "soft_del.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "Survivor"}, sex="M")
    p2 = mgr.add(canonical_name={"given": "Defunct"}, sex="M")

    assert mgr.delete(p2, hard_delete=False, superseded_by=p1) is True
    assert p2 not in mgr
    assert mgr.exists(p2, include_graveyard=True) is True
    assert mgr.graveyard[p2]["superseded_by"] == p1


@pytest.mark.unit
def test_delete_graveyard_record_updates_superseded_by(tmp_path: Path) -> None:
    """Verify delete on an existing tombstone updates its superseded_by target."""
    mgr = GDAPeople(filepath=tmp_path / "del_update_tomb.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "InitialTarget"}, sex="M")
    p2 = mgr.add(canonical_name={"given": "NewTarget"}, sex="M")
    p_tomb = mgr.add(canonical_name={"given": "Tomb"}, sex="M")

    mgr.delete(p_tomb, hard_delete=False, superseded_by=p1)
    assert mgr.graveyard[p_tomb]["superseded_by"] == p1

    assert mgr.delete(p_tomb, hard_delete=False, superseded_by=p2) is True
    assert mgr.graveyard[p_tomb]["superseded_by"] == p2


@pytest.mark.unit
def test_delete_existing_tombstone_without_successor_returns_true(tmp_path: Path) -> None:
    """Verify calling delete on an existing tombstone without a successor returns True without changes."""
    mgr = GDAPeople(filepath=tmp_path / "tomb_no_new_target.json", auto_load=False)
    p_initial = mgr.add(canonical_name={"given": "InitialTarget"}, sex="M")
    p_tomb = mgr.add(canonical_name={"given": "Tomb"}, sex="M")

    mgr.delete(p_tomb, hard_delete=False, superseded_by=p_initial)
    assert mgr.graveyard[p_tomb]["superseded_by"] == p_initial

    assert mgr.delete(p_tomb, hard_delete=False, superseded_by=None) is True
    assert mgr.graveyard[p_tomb]["superseded_by"] == p_initial


@pytest.mark.regression
@pytest.mark.unit
def test_delete_invalid_and_unregistered_superseded_by(tmp_path: Path) -> None:
    """Verify delete validates superseded_by syntax and existence."""
    mgr = GDAPeople(filepath=tmp_path / "del_err.json", auto_load=False)
    pid = mgr.add(canonical_name={"given": "Test"}, sex="M")

    with pytest.raises(ValueError, match="must follow IND-XXXXX"):
        mgr.delete(pid, hard_delete=False, superseded_by="INVALID-ID")

    with pytest.raises(KeyError, match="not found in registry"):
        mgr.delete(pid, hard_delete=False, superseded_by="IND-99999")


@pytest.mark.regression
@pytest.mark.unit
def test_link_kinship_missing_target_or_source_raises_key_error(tmp_path: Path) -> None:
    """Verify link_kinship raises KeyError if either person is unregistered."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "A"}, sex="M")
    with pytest.raises(KeyError, match="Both persons must exist"):
        mgr.link_kinship(p1, "IND-99999", "FATH")
    with pytest.raises(KeyError, match="Both persons must exist"):
        mgr.link_kinship("IND-99999", p1, "FATH")


@pytest.mark.unit
def test_link_kinship_reciprocal_gendered_mappings(tmp_path: Path) -> None:
    """Verify link_kinship resolves gendered reciprocal roles correctly."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    p_mom = mgr.add(canonical_name={"given": "Mom"}, sex="F")
    p_dad = mgr.add(canonical_name={"given": "Dad"}, sex="M")
    p_unk = mgr.add(canonical_name={"given": "Parent"}, sex="U")
    p_child = mgr.add(canonical_name={"given": "Child"}, sex="M")

    mgr.link_kinship(p_mom, p_child, "MOTH")
    assert mgr[p_child]["associated_people"][0]["role"] == "CHIL"

    mgr.link_kinship(p_child, p_dad, "CHIL")
    assert mgr[p_dad]["associated_people"][0]["role"] == "FATH"

    mgr.link_kinship(p_child, p_unk, "CHIL")
    assert mgr[p_unk]["associated_people"][0]["role"] == "PARENT"


@pytest.mark.unit
def test_link_kinship_updates_existing_edge(tmp_path: Path) -> None:
    """Verify linking kinship between existing edges updates reciprocal role in-place."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "A"}, sex="M")
    p2 = mgr.add(canonical_name={"given": "B"}, sex="F")

    mgr.link_kinship(p1, p2, "WITN")
    assert mgr[p1]["associated_people"][0]["role"] == "WITN"

    mgr.link_kinship(p1, p2, "SPOU")
    assert mgr[p1]["associated_people"][0]["role"] == "SPOU"
    assert mgr[p2]["associated_people"][0]["role"] == "SPOU"

    mgr.link_kinship(p1, p2, "SIBL")
    assert mgr[p1]["associated_people"][0]["role"] == "SIBL"
    assert mgr[p2]["associated_people"][0]["role"] == "SIBL"


@pytest.mark.unit
def test_link_kinship_unreciprocated_role_skips_target_edge(tmp_path: Path) -> None:
    """Verify linking an unreciprocated role (e.g. WITN) leaves target associated_people empty."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "Witness"}, sex="M")
    p2 = mgr.add(canonical_name={"given": "Subject"}, sex="F")

    mgr.link_kinship(p1, p2, "WITN")
    assert mgr[p1]["associated_people"][0]["role"] == "WITN"
    assert len(mgr[p2]["associated_people"]) == 0


@pytest.mark.regression
@pytest.mark.unit
def test_kinship_unknown_role_fixture_detection(failure_kinship_unknown_role: Path) -> None:
    """Verify schema validator identifies unknown kinship roles in failed_kinship_unknown_role."""
    raw = GDAUtil.load_json(failure_kinship_unknown_role)
    mgr = GDAPeople(filepath=failure_kinship_unknown_role, auto_load=False)
    target_person = next(p for p in raw["persons"] if p["person_id"] == "IND-00037")
    errors = mgr.validate_person_schema(target_person)
    assert any("Invalid role 'GODPARENT'" in e for e in errors)


@pytest.mark.regression
@pytest.mark.unit
def test_kinship_and_unions_fixture_loading(failure_kinship_and_unions: Path) -> None:
    """Verify failed_kinship_and_unions fixture hydrates and identifies unreciprocated union."""
    mgr = GDAPeople(filepath=failure_kinship_and_unions, auto_load=True)
    assert mgr.count == 62
    assert len(mgr["IND-00000"]["unions"]) == 2


@pytest.mark.regression
@pytest.mark.unit
def test_dedup_and_drift_fixture_detects_duplicate_ids(failure_dedup_and_drift: Path) -> None:
    """Verify failed_dedup_and_drift fixture flags duplicate identity collisions."""
    raw = GDAUtil.load_json(failure_dedup_and_drift)
    pids = [p["person_id"] for p in raw["persons"] if "person_id" in p]
    assert "IND-00000" in pids
    assert "IND-99999" in pids
    duplicate_names = [p for p in raw["persons"] if p.get("display_name") == "Arthur Pendelton Sterling"]
    assert len(duplicate_names) >= 2


@pytest.mark.regression
@pytest.mark.unit
def test_vital_sync_death_fixture_data_integrity(failure_vital_sync_death: Path) -> None:
    """Verify failed_vital_sync_death fixture hydrates without unhandled exception."""
    mgr = GDAPeople(filepath=failure_vital_sync_death, auto_load=True)
    assert "IND-00019" in mgr
    assert mgr["IND-00019"]["display_name"] == "Garrison Montgomery Sterling III"


@pytest.mark.regression
@pytest.mark.unit
def test_biological_chronology_fixture_data_integrity(failure_biological_chronology: Path) -> None:
    """Verify failed_biological_chronology fixture hydrates without unhandled exception."""
    mgr = GDAPeople(filepath=failure_biological_chronology, auto_load=True)
    assert "IND-00037" in mgr
    assert mgr["IND-00037"]["display_name"] == "Julian Sinclair Sterling"


@pytest.mark.unit
def test_unlink_kinship_lifecycle(tmp_path: Path) -> None:
    """Verify unlink_kinship purges mutual associations and exits safely on missing IDs."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "A"}, sex="M")
    p2 = mgr.add(canonical_name={"given": "B"}, sex="F")
    mgr.link_kinship(p1, p2, "SPOU")

    mgr.unlink_kinship(p1, p2)
    assert len(mgr[p1]["associated_people"]) == 0
    assert len(mgr[p2]["associated_people"]) == 0

    mgr.unlink_kinship(p1, "IND-99999")
    mgr.unlink_kinship("IND-99999", p2)
    mgr.unlink_kinship("IND-99998", "IND-99999")


@pytest.mark.unit
def test_add_union_pairs_reciprocally_and_links_spou(tmp_path: Path) -> None:
    """Verify add_union establishes mutual union records and links SPOU kinship."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "Husband"}, sex="M")
    p2 = mgr.add(canonical_name={"given": "Wife"}, sex="F")

    mgr.add_union(p1, p2, status="MARRIED", marriage_date="1986-03-22")
    assert mgr[p1]["unions"][0]["spouse_id"] == p2
    assert mgr[p2]["unions"][0]["spouse_id"] == p1
    assert mgr[p1]["associated_people"][0]["role"] == "SPOU"
    assert mgr[p2]["associated_people"][0]["role"] == "SPOU"


@pytest.mark.unit
def test_add_union_updates_existing_record(tmp_path: Path) -> None:
    """Verify add_union updates existing union between same spouses."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "Husband"}, sex="M")
    p2 = mgr.add(canonical_name={"given": "Wife"}, sex="F")

    mgr.add_union(p1, p2, status="MARRIED")
    mgr.add_union(p1, p2, status="DIVORCED")
    assert mgr[p1]["unions"][0]["status"] == "DIVORCED"
    assert mgr[p2]["unions"][0]["status"] == "DIVORCED"


@pytest.mark.regression
@pytest.mark.unit
def test_add_union_missing_parties_raises_key_error(tmp_path: Path) -> None:
    """Verify add_union raises KeyError if either party is unregistered."""
    mgr = GDAPeople(filepath=tmp_path / "p.json", auto_load=False)
    p1 = mgr.add(canonical_name={"given": "A"}, sex="M")
    with pytest.raises(KeyError, match="Both persons must exist"):
        mgr.add_union(p1, "IND-99999")
    with pytest.raises(KeyError, match="Both persons must exist"):
        mgr.add_union("IND-99999", p1)


# ==============================================================================
# GROUP 7: Persistence & Safe Backups (save)
# Note: Verification of atomic save, sorting invariants, force overrides, and backups.
# ==============================================================================


@pytest.mark.regression
@pytest.mark.unit
def test_save_sorts_nonconforming_ids_from_fixture(failure_people_nonconforming_ids: Path) -> None:
    """Verify save fallback sort key orders non-conforming IDs after conforming numeric IDs."""
    mgr = GDAPeople(filepath=failure_people_nonconforming_ids, auto_load=True)

    assert mgr.save(force=True, create_backup=False) is True

    payload = json.loads(failure_people_nonconforming_ids.read_text(encoding="utf-8"))
    saved_ids = [p["person_id"] for p in payload["people"]]

    assert saved_ids == ["IND-00001", "IND-00002", "CUSTOM-ALPHA", "CUSTOM-ZED"]


@pytest.mark.unit
def test_save_clean_state_without_force_returns_false(tmp_path: Path) -> None:
    """Verify save returns False when manager has no uncommitted changes."""
    mgr = GDAPeople(filepath=tmp_path / "clean.json", auto_load=False)
    assert mgr.save(force=False) is False


@pytest.mark.unit
def test_save_clean_state_with_force_returns_true(tmp_path: Path) -> None:
    """Verify save with force=True commits clean state to disk."""
    pfile = tmp_path / "force_save.json"
    mgr = GDAPeople(filepath=pfile, auto_load=False)
    assert mgr.save(force=True, create_backup=False) is True
    assert pfile.exists()


@pytest.mark.integration
def test_save_persists_modifications_and_clears_dirty_flag(tmp_path: Path) -> None:
    """Verify save serializes mutated records, clears is_dirty, and reloads reliably."""
    pfile = tmp_path / "people_save.json"
    mgr = GDAPeople(filepath=pfile, auto_load=False)
    mgr.add(canonical_name={"given": "Persisted"}, sex="M")
    assert mgr.is_dirty is True

    saved = mgr.save(create_backup=False)
    assert saved is True
    assert mgr.is_dirty is False

    reloaded = GDAPeople(filepath=pfile, auto_load=True)
    assert reloaded.count == 1


@pytest.mark.integration
def test_save_custom_output_path_preserves_dirty_flag(tmp_path: Path) -> None:
    """Verify save to custom output_path preserves dirty flag on main manager."""
    orig = tmp_path / "orig.json"
    custom = tmp_path / "custom.json"
    mgr = GDAPeople(filepath=orig, auto_load=False)
    mgr.add(canonical_name={"given": "CustomTarget"}, sex="M")

    mgr.save(output_path=custom, force=True, create_backup=False)
    assert mgr.is_dirty is True
    assert custom.exists()


@pytest.mark.integration
def test_save_sorts_records_numerically(tmp_path: Path) -> None:
    """Verify save serializes people sorted strictly by numeric sequence."""
    pfile = tmp_path / "sorted_save.json"
    mgr = GDAPeople(filepath=pfile, auto_load=False)
    mgr.add(canonical_name={"given": "Two"}, sex="M", person_id="IND-00002")
    mgr.add(canonical_name={"given": "One"}, sex="M", person_id="IND-00001")
    mgr._people["IND-CUSTOM"] = {"person_id": "IND-CUSTOM", "canonical_name": {"given": "Custom"}}

    assert mgr.save(create_backup=False) is True
    payload = json.loads(pfile.read_text(encoding="utf-8"))
    ids = [p["person_id"] for p in payload["people"]]
    assert ids == ["IND-00001", "IND-00002", "IND-CUSTOM"]


@pytest.mark.unit
def test_save_with_default_backup_flag_evaluates_target_match(tmp_path: Path) -> None:
    """Verify save evaluates create_backup=True on default configured filepath."""
    pfile = tmp_path / "people_default_save.json"
    mgr = GDAPeople(filepath=pfile, auto_load=False)
    mgr.add(canonical_name={"given": "SavedWithBackup"}, sex="M")
    assert mgr.save(create_backup=True) is True
    assert mgr.is_dirty is False


@pytest.mark.unit
def test_save_to_default_filepath_with_backup_disabled(tmp_path: Path) -> None:
    """Verify save evaluates create_backup=False when targeting default filepath."""
    pfile = tmp_path / "people_no_backup.json"
    mgr = GDAPeople(filepath=pfile, auto_load=False)
    mgr.add(canonical_name={"given": "NoBackupPerson"}, sex="M")
    assert mgr.save(output_path=None, create_backup=False) is True
    assert mgr.is_dirty is False


@pytest.mark.regression
@pytest.mark.unit
def test_save_sorts_nonconforming_ids_fallback(tmp_path: Path) -> None:
    """Verify save fallback sort key orders non-conforming IDs after conforming numeric IDs."""
    pfile = tmp_path / "fallback_sort_test.json"
    mgr = GDAPeople(filepath=pfile, auto_load=False)

    mgr.add(canonical_name={"given": "Second"}, sex="M", person_id="IND-00002")
    mgr.add(canonical_name={"given": "First"}, sex="M", person_id="IND-00001")

    mgr._people["CUSTOM-ZED"] = {
        "person_id": "CUSTOM-ZED",
        "canonical_name": {"given": "Zed"},
        "sex": "U",
        "display_name": "Custom Zed",
        "is_deprecated": False,
    }
    mgr._people["CUSTOM-ALPHA"] = {
        "person_id": "CUSTOM-ALPHA",
        "canonical_name": {"given": "Alpha"},
        "sex": "U",
        "display_name": "Custom Alpha",
        "is_deprecated": False,
    }

    assert mgr.save(force=True, create_backup=False) is True

    payload = json.loads(pfile.read_text(encoding="utf-8"))
    saved_ids = [p["person_id"] for p in payload["people"]]

    assert saved_ids == ["IND-00001", "IND-00002", "CUSTOM-ALPHA", "CUSTOM-ZED"]


@pytest.mark.unit
def test_save_target_filepath_with_backup_disabled_branch(tmp_path: Path) -> None:
    """Verify save correctly sets should_backup to False when create_backup is False."""
    pfile = tmp_path / "nobackup_branch.json"
    mgr = GDAPeople(filepath=pfile, auto_load=False)
    mgr.add(canonical_name={"given": "NoBackupBranch"}, sex="M")
    assert mgr.save(output_path=pfile, force=True, create_backup=False) is True
    assert mgr.is_dirty is False