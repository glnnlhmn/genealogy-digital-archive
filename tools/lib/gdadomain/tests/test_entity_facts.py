# Name: test_entity_facts.py
# Path: tools/lib/gdadomain/tests/test_entity_facts.py
# Version: 1.0.0+build.r1

"""Unit and integration test suite validating GDAFacts initialization, protocols, mutations, and persistence.

Operational Role:
    Executes hermetic verification across all 7 functional groups for GDAFacts (v1.0.0):
    - Group 1: IntrospectableMixin directory generation, public member inspection,
      safe missing-file defaults, corrupt JSON rejection, and partitioned loading.
    - Group 2: Collection protocols, active sized count, subscript retrieval,
      deep-copy memory isolation, and transparent graveyard redirection.
    - Group 3: Entity membership, exact UUID retrieval, multi-hop redirect resolution,
      and circular loop guards.
    - Group 4: Record creation (add), UUIDv4 auto-minting, and strict schema validation.
    - Group 5: Record updates (edit), immutability, and secondary indexing (person, location, type).
    - Group 6: Deprecation (delete), in-place tombstoning, and reciprocal kinship verification.
    - Group 7: Persistence (save), reload reset, and context manager transaction bounds.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per behavioral boundary.
    - Fully decorated: Strictly marked with @pytest.mark.unit, @pytest.mark.smoke, and @pytest.mark.integration.
    - Dependencies: Isolated tmp_path sandboxes and GDAConfig topology.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import pytest

from gdacore.config import GDAConfig
from gdacore.util import GDAUtil
from gdadomain.facts import GDAFacts


@pytest.fixture
def facts_sandbox(tmp_path: Path) -> GDAConfig:
    """Fixture providing isolated GDAConfig topology and empty fact registries."""
    root = tmp_path / "gda_root"
    root.mkdir(parents=True, exist_ok=True)
    cfg = GDAConfig(root=root)
    cfg.entities.mkdir(parents=True, exist_ok=True)
    cfg.backups.mkdir(parents=True, exist_ok=True)
    cfg.logs.mkdir(parents=True, exist_ok=True)
    return cfg


# ==============================================================================
# GROUP 1: Introspection, Initialization & Disk Loading
# Note: Verification of IntrospectableMixin, safe missing-file handling, and loading
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_help_directory_generation(capsys: Any) -> None:
    """Verify IntrospectableMixin generates public directory output without private members."""
    GDAFacts.help()
    captured = capsys.readouterr().out
    assert "add" in captured
    assert "edit" in captured
    assert "delete" in captured
    assert "verify_reciprocal_facts" in captured
    assert "save" in captured

    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    member_lines = [l for l in lines if l.startswith("-") or l.startswith("*")]
    for ml in member_lines:
        assert not ml.lstrip("- *").strip().startswith("_facts")
        assert not ml.lstrip("- *").strip().startswith("_graveyard")


@pytest.mark.smoke
@pytest.mark.unit
def test_help_member_signature(capsys: Any) -> None:
    """Verify GDAFacts.help('add') prints call signature and docstring."""
    GDAFacts.help("add")
    captured = capsys.readouterr().out
    assert "add(" in captured
    assert "fact_data" in captured
    assert "Add a new fact assertion" in captured


@pytest.mark.unit
def test_help_invalid_member(capsys: Any) -> None:
    """Verify GDAFacts.help() gracefully handles unknown member names without exceptions."""
    GDAFacts.help("non_existent_method")
    captured = capsys.readouterr().out
    assert "not found" in captured or "No public member" in captured or "non_existent_method" in captured


@pytest.mark.unit
@pytest.mark.smoke
def test_init_missing_file_initializes_clean_state(facts_sandbox: GDAConfig) -> None:
    """Verify initialization when facts.json does not yet exist on disk."""
    facts_path = facts_sandbox.entities / "missing_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    assert len(mgr) == 0
    assert len(mgr.graveyard) == 0
    assert mgr.total_count == 0
    assert mgr.is_dirty is True
    assert mgr.facts_path == facts_path


@pytest.mark.regression
@pytest.mark.unit
def test_load_corrupt_json_raises_exception(facts_sandbox: GDAConfig) -> None:
    """Verify malformed JSON payload raises an exception during instantiation."""
    facts_path = facts_sandbox.entities / "corrupt_facts.json"
    facts_path.write_text("INVALID-JSON-PAYLOAD{", encoding="utf-8")
    with pytest.raises(Exception):
        GDAFacts(filepath=facts_path, auto_commit=False)


@pytest.mark.unit
def test_load_partitioning_active_and_graveyard(facts_sandbox: GDAConfig) -> None:
    """Verify load partitions active records and tombstoned records into separate stores."""
    facts_path = facts_sandbox.entities / "partition_facts.json"
    raw_payload = {
        "facts": [
            {"fact_id": "9b1deb4d-3b7d-4bad-8bdd-2b0d7b3dcb6d", "person_id": "IND-00001", "fact_type": "Birth"},
            {
                "fact_id": "a1b2c3d4-e5f6-4789-8012-34567890abcd",
                "person_id": "IND-00002",
                "fact_type": "Death",
                "is_deprecated": True,
                "superseded_by": "9b1deb4d-3b7d-4bad-8bdd-2b0d7b3dcb6d",
            },
        ]
    }
    GDAUtil.save_json(facts_path, raw_payload, create_backup=False)
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    assert len(mgr) == 1
    assert "9b1deb4d-3b7d-4bad-8bdd-2b0d7b3dcb6d" in mgr
    assert len(mgr.graveyard) == 1
    assert "a1b2c3d4-e5f6-4789-8012-34567890abcd" in mgr.graveyard
    assert mgr.total_count == 2


@pytest.mark.regression
@pytest.mark.unit
def test_load_skips_empty_ids(facts_sandbox: GDAConfig) -> None:
    """Verify load skips records that lack fact_id across loop iterations."""
    facts_path = facts_sandbox.entities / "skip_facts.json"
    raw_payload = {
        "facts": [
            {"notes": ["missing fact_id"]},
            {"fact_id": "", "person_id": "IND-00001", "fact_type": "Birth"},
            {"fact_id": "9b1deb4d-3b7d-4bad-8bdd-2b0d7b3dcb6d", "person_id": "IND-00001", "fact_type": "Birth"},
            {"fact_id": "a1b2c3d4-e5f6-4789-8012-34567890abcd", "person_id": "IND-00002", "fact_type": "Death"},
        ]
    }
    GDAUtil.save_json(facts_path, raw_payload, create_backup=False)
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    assert len(mgr) == 2
    assert "9b1deb4d-3b7d-4bad-8bdd-2b0d7b3dcb6d" in mgr
    assert "a1b2c3d4-e5f6-4789-8012-34567890abcd" in mgr


@pytest.mark.unit
def test_refresh_discards_unstaged_mutations(facts_sandbox: GDAConfig) -> None:
    """Verify refresh discards unstaged in-memory mutations and restores clean disk state."""
    facts_path = facts_sandbox.entities / "refresh_facts.json"
    raw_payload = {"facts": [{"fact_id": "9b1deb4d-3b7d-4bad-8bdd-2b0d7b3dcb6d", "person_id": "IND-00001", "fact_type": "Birth"}]}
    GDAUtil.save_json(facts_path, raw_payload, create_backup=False)
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)

    mgr.add({"person_id": "IND-00002", "fact_type": "Death"})
    assert len(mgr) == 2
    assert mgr.is_dirty is True

    mgr.refresh()
    assert len(mgr) == 1
    assert mgr.is_dirty is False


@pytest.mark.unit
def test_load_raw_list_payload(raw_list_facts_file: Path) -> None:
    """Verify load processes a top-level list payload from disk."""
    mgr = GDAFacts(filepath=raw_list_facts_file, auto_commit=False)
    assert len(mgr) == 1
    assert "9b1deb4d-3b7d-4bad-8bdd-2b0d7b3dcb6d" in mgr


@pytest.mark.regression
@pytest.mark.unit
def test_load_non_dict_non_list_payload_initializes_empty(failure_facts_scalar: Path) -> None:
    """Verify load initializes an empty registry when JSON root is neither dict nor list."""
    mgr = GDAFacts(filepath=failure_facts_scalar, auto_commit=False)
    assert len(mgr) == 0
    assert len(mgr.graveyard) == 0


# ==============================================================================
# GROUP 2: Collection Protocols & Subscript Ergonomics
# Note: Verification of sized count, iteration isolation, membership, and subscript
# ==============================================================================


@pytest.mark.unit
def test_len_returns_active_count_only(facts_sandbox: GDAConfig) -> None:
    """Verify len(mgr) returns count of active facts, excluding graveyard tombstones."""
    facts_path = facts_sandbox.entities / "len_facts.json"
    raw_payload = {
        "facts": [
            {"fact_id": "9b1deb4d-3b7d-4bad-8bdd-2b0d7b3dcb6d", "person_id": "IND-00001", "fact_type": "Birth"},
            {"fact_id": "a1b2c3d4-e5f6-4789-8012-34567890abcd", "person_id": "IND-00002", "fact_type": "Death", "is_deprecated": True},
        ]
    }
    GDAUtil.save_json(facts_path, raw_payload, create_backup=False)
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    assert len(mgr) == 1
    assert mgr.total_count == 2
    assert mgr.existing_ids == {"9b1deb4d-3b7d-4bad-8bdd-2b0d7b3dcb6d"}


@pytest.mark.unit
def test_iter_yields_active_only_with_memory_isolation(facts_sandbox: GDAConfig) -> None:
    """Verify __iter__ traversal yields only active records and enforces deep-copy isolation."""
    facts_path = facts_sandbox.entities / "iter_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({
        "person_id": "IND-00001",
        "fact_type": "Marriage",
        "associated_people": [{"person_id": "IND-00002", "role": "SPOU"}],
    })

    yielded_facts = list(mgr)
    assert len(yielded_facts) == 1
    yielded_facts[0]["associated_people"][0]["role"] = "MUTATED_ROLE"

    stored = mgr[fid]
    assert stored["associated_people"][0]["role"] == "SPOU"


@pytest.mark.unit
def test_iter_empty_registry_yields_zero_items(facts_sandbox: GDAConfig) -> None:
    """Verify __iter__ traversal over an empty registry yields zero items."""
    facts_path = facts_sandbox.entities / "empty_iter_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    assert list(mgr) == []


@pytest.mark.unit
def test_contains_active_membership(facts_sandbox: GDAConfig) -> None:
    """Verify 'in' operator returns True for active registered facts."""
    facts_path = facts_sandbox.entities / "contains_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    assert (fid in mgr) is True


@pytest.mark.unit
def test_contains_graveyard_returns_false(facts_sandbox: GDAConfig) -> None:
    """Verify 'in' operator returns False for graveyard tombstones."""
    facts_path = facts_sandbox.entities / "graveyard_contains.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    mgr.delete(fid, hard_delete=False)
    assert (fid in mgr) is False


@pytest.mark.unit
def test_contains_unregistered_and_non_string_returns_false(facts_sandbox: GDAConfig) -> None:
    """Verify 'in' operator returns False for unregistered IDs and non-string queries."""
    facts_path = facts_sandbox.entities / "contains_types.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    assert ("00000000-0000-4000-8000-000000000000" in mgr) is False
    assert (12345 in mgr) is False
    assert (None in mgr) is False


@pytest.mark.unit
def test_getitem_active_retrieval(facts_sandbox: GDAConfig) -> None:
    """Verify subscript access retrieves expected active entity payload."""
    facts_path = facts_sandbox.entities / "getitem_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    record = mgr[fid]
    assert record["fact_id"] == fid
    assert record["fact_type"] == "Birth"


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_transparent_graveyard_redirect(facts_sandbox: GDAConfig) -> None:
    """Verify subscript access transparently resolves graveyard redirect to successor."""
    facts_path = facts_sandbox.entities / "redirect_getitem.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid_survivor = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    fid_absorbed = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    mgr.delete(fid_absorbed, superseded_by=fid_survivor)

    record = mgr[fid_absorbed]
    assert record["fact_id"] == fid_survivor


@pytest.mark.regression
@pytest.mark.unit
def test_getitem_missing_raises_key_error(facts_sandbox: GDAConfig) -> None:
    """Verify subscript access for non-existent fact ID raises KeyError."""
    facts_path = facts_sandbox.entities / "missing_getitem.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    with pytest.raises(KeyError, match="not found in active registry"):
        _ = mgr["00000000-0000-4000-8000-000000000000"]


# ==============================================================================
# GROUP 3: Entity Retrieval, Membership & Graveyard Traversal
# Note: Verification of exact exists, get, resolve_id, and redirect tracing
# ==============================================================================


@pytest.mark.unit
def test_exists_boundary_modes(facts_sandbox: GDAConfig) -> None:
    """Verify exists distinguishes active and graveyard records under explicit flags."""
    facts_path = facts_sandbox.entities / "exists_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    assert mgr.exists(fid, include_graveyard=False) is True

    mgr.delete(fid, hard_delete=False)
    assert mgr.exists(fid, include_graveyard=False) is False
    assert mgr.exists(fid, include_graveyard=True) is True
    assert mgr.exists("00000000-0000-4000-8000-000000000000", include_graveyard=True) is False


@pytest.mark.unit
def test_get_graveyard_defunct_without_replacement(facts_sandbox: GDAConfig) -> None:
    """Verify get returns raw tombstone when resolve_redirects is True but superseded_by is None."""
    facts_path = facts_sandbox.entities / "defunct_graveyard.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    mgr.delete(fid, superseded_by=None)

    res = mgr.get(fid, include_graveyard=True, resolve_redirects=True)
    assert res is not None
    assert res["fact_id"] == fid
    assert res["is_deprecated"] is True

    assert mgr.get(fid, include_graveyard=False, resolve_redirects=True) is None


@pytest.mark.unit
def test_resolve_id_single_and_multihop(facts_sandbox: GDAConfig) -> None:
    """Verify resolve_id traces single and transitive deprecation chains."""
    facts_path = facts_sandbox.entities / "multihop_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    f_survivor = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    f_step1 = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    f_step2 = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})

    mgr.delete(f_step1, superseded_by=f_survivor)
    mgr.delete(f_step2, superseded_by=f_step1)

    assert mgr.resolve_id(f_step1) == f_survivor
    assert mgr.resolve_id(f_step2) == f_survivor


@pytest.mark.regression
@pytest.mark.unit
def test_resolve_id_circular_protection(facts_sandbox: GDAConfig) -> None:
    """Verify resolve_id detects circular graveyard loops safely and returns None."""
    facts_path = facts_sandbox.entities / "circular_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    f1 = "a1b2c3d4-1111-4789-8012-34567890abcd"
    f2 = "a1b2c3d4-2222-4789-8012-34567890abcd"
    mgr._graveyard[f1] = {"fact_id": f1, "is_deprecated": True, "superseded_by": f2}
    mgr._graveyard[f2] = {"fact_id": f2, "is_deprecated": True, "superseded_by": f1}

    assert mgr.resolve_id(f1) is None
    assert mgr.resolve_id(f2) is None


@pytest.mark.unit
def test_resolve_id_golden_chains_traverse_to_active_records(golden_facts_file: Path) -> None:
    """Verify resolve_id successfully resolves single, two-hop, and 8-hop chains in golden_facts."""
    mgr = GDAFacts(filepath=golden_facts_file, auto_commit=False)
    assert len(mgr) == 100
    assert len(mgr.graveyard) == 23
    assert mgr.total_count == 123

    # Single-hop verification (0101 -> 0001)
    assert mgr.resolve_id("00000000-0000-4000-8000-000000000101") == "00000000-0000-4000-8000-000000000001"

    # Two-hop verification (0201 -> 0101 -> 0001)
    assert mgr.resolve_id("00000000-0000-4000-8000-000000000201") == "00000000-0000-4000-8000-000000000001"

    # 8-hop chain verification (0801 -> 0802 -> ... -> 0808 -> 0086)
    assert mgr.resolve_id("00000000-0000-4000-8000-000000000801") == "00000000-0000-4000-8000-000000000086"


@pytest.mark.regression
@pytest.mark.unit
def test_resolve_id_chain_target_not_in_active_facts_returns_none(golden_facts_file: Path) -> None:
    """Verify resolve_id returns None when a chain terminates at a record missing from active facts."""
    mgr = GDAFacts(filepath=golden_facts_file, auto_commit=False)
    active_target = "00000000-0000-4000-8000-000000000086"

    # Confirm the 8-hop chain resolves initially
    assert mgr.resolve_id("00000000-0000-4000-8000-000000000801") == active_target

    # Remove the target fact from active memory so target in self._facts evaluates to False
    mgr._facts.pop(active_target)

    assert mgr.resolve_id("00000000-0000-4000-8000-000000000801") is None


# ==============================================================================
# GROUP 4: Record Creation (add) & Schema Validation
# Note: Verification of auto-minting, UUIDv4 validation, and schema constraints
# ==============================================================================


@pytest.mark.unit
def test_add_auto_mints_uuid(facts_sandbox: GDAConfig) -> None:
    """Verify add() automatically mints a lowercase UUIDv4 when fact_id is omitted."""
    facts_path = facts_sandbox.entities / "add_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00100", "fact_type": "Birth"})
    assert fid is not None
    assert fid in mgr
    assert mgr.is_dirty is True
    assert len(mgr) == 1


@pytest.mark.unit
def test_add_duplicate_raises_value_error(facts_sandbox: GDAConfig) -> None:
    """Verify add raises ValueError if the fact_id is already registered."""
    facts_path = facts_sandbox.entities / "dup_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fact_payload = {"fact_id": "a1b2c3d4-e5f6-4789-8012-34567890abcd", "person_id": "IND-00100", "fact_type": "Birth"}
    mgr.add(fact_payload)
    with pytest.raises(ValueError, match="already exists"):
        mgr.add(fact_payload)


@pytest.mark.unit
def test_add_invalid_schema_raises_value_error(facts_sandbox: GDAConfig) -> None:
    """Verify add raises ValueError when fact payload fails schema validation."""
    facts_path = facts_sandbox.entities / "add_invalid_schema.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    invalid_payload = {"person_id": "INVALID-PID", "fact_type": "Birth"}
    with pytest.raises(ValueError, match="Fact schema validation failed"):
        mgr.add(invalid_payload)


@pytest.mark.unit
def test_schema_validation_diagnostics(facts_sandbox: GDAConfig) -> None:
    """Verify validate_fact_schema flags invalid payloads, IDs, and vocabularies."""
    facts_path = facts_sandbox.entities / "diag_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)

    assert "Fact payload must be a dictionary." in mgr.validate_fact_schema("invalid-string")
    assert any("Invalid fact_id format" in e for e in mgr.validate_fact_schema({"fact_id": "BAD-UUID"}))
    assert any("missing required 'person_id'" in e for e in mgr.validate_fact_schema({"fact_type": "Birth"}))
    assert any("Invalid person_id format" in e for e in mgr.validate_fact_schema({"person_id": "BAD-ID", "fact_type": "Birth"}))
    assert any("missing required 'fact_type'" in e for e in mgr.validate_fact_schema({"person_id": "IND-00001"}))
    assert any("Invalid fact_type" in e for e in mgr.validate_fact_schema({"person_id": "IND-00001", "fact_type": "NonexistentType"}))
    assert any("'associated_people' must be a list." in e for e in mgr.validate_fact_schema({
        "person_id": "IND-00001", "fact_type": "Birth", "associated_people": "not-a-list"
    }))
    assert any("must be a dictionary" in e for e in mgr.validate_fact_schema({
        "person_id": "IND-00001", "fact_type": "Birth", "associated_people": ["not-a-dict"]
    }))
    assert any("Invalid person_id 'BAD-ID'" in e for e in mgr.validate_fact_schema({
        "person_id": "IND-00001", "fact_type": "Birth", "associated_people": [{"person_id": "BAD-ID"}]
    }))
    assert len(mgr.validate_fact_schema({
        "person_id": "IND-00001", "fact_type": "Birth", "associated_people": [
            {"person_id": "IND-00002", "role": "WITN"},
            {"role": "NO_PID"},
        ]
    })) == 0
    assert len(mgr.validate_fact_schema({
        "person_id": "IND-00001", "fact_type": "Birth", "associated_people": None
    })) == 0
    assert len(mgr.validate_fact_schema({
        "person_id": "IND-00001", "fact_type": "Birth"
    })) == 0


# ==============================================================================
# GROUP 5: Record Updates (edit) & Secondary Index Queries
# Note: Verification of in-place edit, immutability, dirty state, and query cross-references
# ==============================================================================


@pytest.mark.unit
def test_edit_success(facts_sandbox: GDAConfig) -> None:
    """Verify edit updates assertion in-place and marks manager dirty."""
    facts_path = facts_sandbox.entities / "edit_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    updated = {"fact_id": fid, "person_id": "IND-00002", "fact_type": "Death"}
    assert mgr.edit(fid, updated) is True
    assert mgr.get(fid)["fact_type"] == "Death"
    assert mgr.is_dirty is True


@pytest.mark.unit
def test_edit_graveyard_fact_raises_key_error(facts_sandbox: GDAConfig) -> None:
    """Verify edit raises KeyError when attempting to mutate a tombstone."""
    facts_path = facts_sandbox.entities / "edit_grave_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    mgr.delete(fid)
    with pytest.raises(KeyError, match="Cannot edit deprecated fact"):
        mgr.edit(fid, {"fact_id": fid, "person_id": "IND-00002", "fact_type": "Death"})


@pytest.mark.unit
def test_edit_nonexistent_returns_false(facts_sandbox: GDAConfig) -> None:
    """Verify edit returns False when target ID is not found."""
    facts_path = facts_sandbox.entities / "edit_nonexist_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    assert mgr.edit("00000000-0000-4000-8000-000000000000", {"fact_id": "00000000-0000-4000-8000-000000000000"}) is False


@pytest.mark.unit
def test_edit_mismatched_id_raises(facts_sandbox: GDAConfig) -> None:
    """Verify edit forbids altering canonical fact_id."""
    facts_path = facts_sandbox.entities / "edit_mismatch_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    with pytest.raises(ValueError, match="fact_id is immutable"):
        mgr.edit(fid, {"fact_id": "9b1deb4d-3b7d-4bad-8bdd-2b0d7b3dcb6d", "person_id": "IND-00001", "fact_type": "Birth"})


@pytest.mark.unit
def test_edit_missing_fact_id_raises(facts_sandbox: GDAConfig) -> None:
    """Verify edit raises ValueError when replacement payload omits fact_id."""
    facts_path = facts_sandbox.entities / "edit_missing_id.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    with pytest.raises(ValueError, match="must contain a valid 'fact_id'"):
        mgr.edit(fid, {"person_id": "IND-00001", "fact_type": "Birth"})


@pytest.mark.unit
def test_edit_invalid_schema_raises_value_error(facts_sandbox: GDAConfig) -> None:
    """Verify edit raises ValueError when replacement payload fails schema validation."""
    facts_path = facts_sandbox.entities / "edit_invalid_schema.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    invalid_replacement = {"fact_id": fid, "person_id": "INVALID-PID", "fact_type": "Birth"}
    with pytest.raises(ValueError, match="Replacement fact schema validation failed"):
        mgr.edit(fid, invalid_replacement)


@pytest.mark.unit
def test_edit_with_is_deprecated_dispatches_to_delete(facts_sandbox: GDAConfig) -> None:
    """Verify setting is_deprecated=True inside edit dispatches to delete."""
    facts_path = facts_sandbox.entities / "edit_deprecate_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    f_survivor = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})

    assert mgr.edit(fid, {"fact_id": fid, "person_id": "IND-00001", "fact_type": "Birth", "is_deprecated": True, "superseded_by": f_survivor}) is True
    assert fid not in mgr
    assert fid in mgr.graveyard
    assert mgr.graveyard[fid]["superseded_by"] == f_survivor


@pytest.mark.unit
def test_secondary_index_lookups(facts_sandbox: GDAConfig) -> None:
    """Verify secondary indexing across person_id, associated_people, location_id, and fact_type."""
    facts_path = facts_sandbox.entities / "index_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid1 = mgr.add({
        "person_id": "IND-00001",
        "fact_type": "Marriage",
        "location_id": "LOC-00010",
        "associated_people": [
            {"person_id": "IND-00001", "role": "SELF"},
            {"person_id": "IND-00002", "role": "SPOU"},
        ],
    })
    fid2 = mgr.add({
        "person_id": "IND-00002",
        "fact_type": "Death",
        "location_id": "LOC-00020",
    })

    mgr._facts[fid1]["associated_people"].insert(0, "not-a-dict")
    mgr._facts[fid1]["associated_people"].insert(1, {"role": "missing-person-id"})
    mgr._facts[fid1]["associated_people"].insert(2, {"person_id": ""})
    mgr._facts[fid2]["associated_people"] = "not-a-list"
    mgr._rebuild_indices()

    assert len(mgr.get_facts_for_person("IND-00001", include_roles=False)) == 1
    assert len(mgr.get_facts_for_person("IND-00002", include_roles=False)) == 1
    assert len(mgr.get_facts_for_person("IND-00002", include_roles=True)) == 2

    assert len(mgr.get_facts_by_location("LOC-00010")) == 1
    assert len(mgr.get_facts_by_location("LOC-99999")) == 0

    assert len(mgr.get_facts_by_type("Marriage")) == 1
    assert len(mgr.get_facts_by_type("Burial")) == 0


@pytest.mark.unit
def test_rebuild_indices_skips_missing_attributes(facts_sandbox: GDAConfig) -> None:
    """Verify _rebuild_indices gracefully bypasses records lacking person_id or fact_type."""
    facts_path = facts_sandbox.entities / "index_missing_attrs.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({
        "person_id": "IND-00001",
        "fact_type": "Birth",
        "location_id": "LOC-00010",
    })

    # Clear attributes directly in active memory to exercise missing branch paths
    mgr._facts[fid]["person_id"] = None
    mgr._facts[fid]["fact_type"] = None
    mgr._facts[fid]["location_id"] = None

    mgr._rebuild_indices()

    assert len(mgr.get_facts_for_person("IND-00001", include_roles=False)) == 0
    assert len(mgr.get_facts_by_type("Birth")) == 0
    assert len(mgr.get_facts_by_location("LOC-00010")) == 0


@pytest.mark.unit
def test_mark_dirty_lifecycle(facts_sandbox: GDAConfig) -> None:
    """Verify mark_dirty stages known active fact ID."""
    facts_path = facts_sandbox.entities / "dirty_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    mgr.dirty_ids.clear()
    mgr._is_dirty = False
    assert not mgr.is_dirty

    mgr.mark_dirty(fid)
    assert mgr.is_dirty

    mgr.mark_dirty("00000000-0000-4000-8000-000000000000")


# ==============================================================================
# GROUP 6: Deprecation (delete), In-Place Tombstoning & Kinship Reciprocity
# Note: Verification of soft-deletes, graveyard pointers, and reciprocal kinship
# ==============================================================================


@pytest.mark.unit
def test_delete_soft_transitions_to_graveyard(facts_sandbox: GDAConfig) -> None:
    """Verify soft-delete moves active fact to graveyard with is_deprecated=True."""
    facts_path = facts_sandbox.entities / "del_soft_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})

    success = mgr.delete(fid, hard_delete=False)
    assert success is True
    assert fid not in mgr
    assert fid in mgr.graveyard
    assert mgr.graveyard[fid]["is_deprecated"] is True
    assert mgr.is_dirty is True


@pytest.mark.unit
def test_delete_hard_purges_permanently(facts_sandbox: GDAConfig) -> None:
    """Verify hard_delete=True permanently removes fact from active and graveyard stores."""
    facts_path = facts_sandbox.entities / "del_hard_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})

    success = mgr.delete(fid, hard_delete=True)
    assert success is True
    assert fid not in mgr
    assert fid not in mgr.graveyard
    assert mgr.total_count == 0


@pytest.mark.unit
def test_delete_invalid_and_unregistered_superseded_by(facts_sandbox: GDAConfig) -> None:
    """Verify delete validates syntax and registry existence for superseded_by targets."""
    facts_path = facts_sandbox.entities / "del_invalid_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})

    with pytest.raises(ValueError, match="must be a lowercase UUIDv4"):
        mgr.delete(fid, superseded_by="INVALID-UUID")

    with pytest.raises(KeyError, match="not found in registry"):
        mgr.delete(fid, superseded_by="00000000-0000-4000-8000-000000000000")


@pytest.mark.unit
def test_delete_graveyard_record_updates_superseded_by_and_noop(facts_sandbox: GDAConfig) -> None:
    """Verify delete on existing tombstone updates superseded_by target or acts as safe no-op."""
    facts_path = facts_sandbox.entities / "del_tomb_update.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    f_survivor = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    f_tomb = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    mgr.delete(f_tomb)

    assert mgr.delete(f_tomb, superseded_by=f_survivor) is True
    assert mgr.graveyard[f_tomb]["superseded_by"] == f_survivor
    assert mgr.delete(f_tomb, superseded_by=None) is True


@pytest.mark.unit
def test_delete_nonexistent_returns_false(facts_sandbox: GDAConfig) -> None:
    """Verify delete returns False when target fact ID is not found in registry."""
    facts_path = facts_sandbox.entities / "del_nonexist_facts.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    assert mgr.delete("00000000-0000-4000-8000-000000000000") is False


@pytest.mark.unit
def test_reciprocal_kinship_verification_and_addition(facts_sandbox: GDAConfig) -> None:
    """Verify reciprocal kinship discovery and auto-addition for associated spouses and children."""
    facts_path = facts_sandbox.entities / "recip_kinship.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    f_parent = mgr.add({
        "person_id": "IND-00001",
        "fact_type": "Parentage",
        "associated_people": [
            {"person_id": "IND-00002", "role": "CHIL"},
        ],
    })

    mgr._facts[f_parent]["associated_people"].insert(0, "raw-non-dict-entry")

    with pytest.raises(KeyError, match="not found"):
        mgr.verify_reciprocal_facts("00000000-0000-4000-8000-000000000000")

    mgr.add({"person_id": "IND-00002", "fact_type": "Birth"})

    is_recip, missing = mgr.verify_reciprocal_facts(f_parent)
    assert is_recip is False
    assert len(missing) == 1

    minted_ids = mgr.add_reciprocal_facts(f_parent)
    assert len(minted_ids) == 1
    assert mgr.verify_reciprocal_facts(f_parent)[0] is True
    assert mgr.add_reciprocal_facts(f_parent) == []


@pytest.mark.unit
def test_verify_reciprocal_facts_evaluates_mismatched_roles_and_people(facts_sandbox: GDAConfig) -> None:
    """Verify verify_reciprocal_facts evaluates diverse associated roles and partner facts."""
    facts_path = facts_sandbox.entities / "recip_mismatch.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    f_parent = mgr.add({
        "person_id": "IND-00001",
        "fact_type": "Parentage",
        "associated_people": [
            {"person_id": "IND-00002", "role": "CHIL"},
        ],
    })

    f_partner1 = mgr.add({"person_id": "IND-00002", "fact_type": "Parentage"})
    mgr._facts[f_partner1]["associated_people"] = "not-a-list"

    f_partner2 = mgr.add({
        "person_id": "IND-00002",
        "fact_type": "Parentage",
        "associated_people": [
            {"person_id": "IND-00003", "role": "FATH"},
            {"person_id": "IND-00001", "role": "WITN"},
        ],
    })
    mgr._facts[f_partner2]["associated_people"].insert(0, "not-a-dict")

    is_recip, missing = mgr.verify_reciprocal_facts(f_parent)
    assert is_recip is False
    assert len(missing) == 1

    mgr.add({
        "person_id": "IND-00002",
        "fact_type": "Parentage",
        "associated_people": [{"person_id": "IND-00001", "role": "FATH"}],
    })
    assert mgr.verify_reciprocal_facts(f_parent)[0] is True


@pytest.mark.unit
def test_verify_reciprocal_facts_empty_primary_pid_returns_true(facts_sandbox: GDAConfig) -> None:
    """Verify verify_reciprocal_facts returns True immediately if person_id is missing or empty."""
    facts_path = facts_sandbox.entities / "recip_empty.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    fid = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    mgr._facts[fid]["person_id"] = None
    assert mgr.verify_reciprocal_facts(fid)[0] is True

    mgr._facts[fid]["person_id"] = "IND-00001"
    mgr._facts[fid]["associated_people"] = None
    assert mgr.verify_reciprocal_facts(fid)[0] is True
    mgr._facts[fid]["associated_people"] = []
    assert mgr.verify_reciprocal_facts(fid)[0] is True


@pytest.mark.unit
@pytest.mark.regression
def test_verify_reciprocal_facts_skips_unmapped_roles_and_missing_ids(tmp_path: Path) -> None:
    """Verify verify_reciprocal_facts skips associated entries missing person_id or mapping."""
    facts_file = tmp_path / "facts.json"
    facts_mgr = GDAFacts(filepath=facts_file, auto_commit=False)

    fact_payload = {
        "fact_id": "a0000000-0000-4000-8000-000000000001",
        "person_id": "IND-00001",
        "fact_type": "Birth",
        "associated_people": [
            {"role": "FATH"},
            {"person_id": "IND-00002", "role": "WITN"},
            {"person_id": "IND-00003", "role": "FATH"},
        ],
    }
    fid = facts_mgr.add(fact_payload)

    is_recip, missing = facts_mgr.verify_reciprocal_facts(fid)

    assert is_recip is False
    assert len(missing) == 1
    assert missing[0]["person_id"] == "IND-00003"
    assert missing[0]["associated_people"][0]["role"] == "CHIL"


@pytest.mark.unit
@pytest.mark.regression
def test_add_reciprocal_facts_early_return_when_already_reciprocated(tmp_path: Path) -> None:
    """Verify add_reciprocal_facts returns empty list when all facts are already reciprocated."""
    facts_file = tmp_path / "facts.json"
    facts_mgr = GDAFacts(filepath=facts_file, auto_commit=False)

    fact1 = {
        "fact_id": "b0000000-0000-4000-8000-000000000001",
        "person_id": "IND-00001",
        "fact_type": "Marriage",
        "associated_people": [{"person_id": "IND-00002", "role": "SPOU"}],
    }
    fact2 = {
        "fact_id": "b0000000-0000-4000-8000-000000000002",
        "person_id": "IND-00002",
        "fact_type": "Marriage",
        "associated_people": [{"person_id": "IND-00001", "role": "SPOU"}],
    }
    fid1 = facts_mgr.add(fact1)
    facts_mgr.add(fact2)

    created_ids = facts_mgr.add_reciprocal_facts(fid1)
    assert created_ids == []


# ==============================================================================
# GROUP 7: Persistence (save), Reloading & Context Management
# Note: Verification of Safe Backup Protocol serialization, resets, and context manager
# ==============================================================================


@pytest.mark.integration
def test_save_persists_active_and_graveyard_records(facts_sandbox: GDAConfig) -> None:
    """Verify save serializes both active and graveyard records under Safe Backup Protocol."""
    facts_path = facts_sandbox.entities / "save_persist.json"
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    f_active = mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
    f_dead = mgr.add({"person_id": "IND-00002", "fact_type": "Death"})
    mgr.delete(f_dead, superseded_by=f_active)

    saved = mgr.save(create_backup=False)
    assert saved is True
    assert mgr.is_dirty is False

    reloaded = GDAFacts(filepath=facts_path, auto_commit=False)
    assert len(reloaded) == 1
    assert f_active in reloaded
    assert len(reloaded.graveyard) == 1
    assert f_dead in reloaded.graveyard


@pytest.mark.unit
def test_save_clean_state_skips_write_unless_forced(facts_sandbox: GDAConfig) -> None:
    """Verify save returns False when manager has no uncommitted changes, and True when forced."""
    facts_path = facts_sandbox.entities / "save_clean.json"
    GDAUtil.save_json(facts_path, {"facts": []}, create_backup=False)
    mgr = GDAFacts(filepath=facts_path, auto_commit=False)
    mgr._is_dirty = False
    mgr.dirty_ids.clear()
    assert not mgr.is_dirty
    assert mgr.save(force=False) is False
    assert mgr.save(force=True, create_backup=False) is True


@pytest.mark.unit
def test_save_clean_state_skips_write_and_returns_false(golden_facts_file: Path) -> None:
    """Verify save returns False and skips disk write when clean and unforced."""
    mgr = GDAFacts(filepath=golden_facts_file, auto_commit=False)
    assert not mgr.is_dirty
    assert len(mgr.dirty_ids) == 0

    saved = mgr.save(force=False)
    assert saved is False


@pytest.mark.unit
def test_save_clean_state_forced_persists_and_returns_true(golden_facts_file: Path) -> None:
    """Verify save commits clean state to disk when force is True."""
    mgr = GDAFacts(filepath=golden_facts_file, auto_commit=False)
    assert not mgr.is_dirty

    saved = mgr.save(force=True, create_backup=False)
    assert saved is True
    assert not mgr.is_dirty


@pytest.mark.integration
def test_context_manager_commits_on_clean_exit(facts_sandbox: GDAConfig) -> None:
    """Verify context manager automatically commits staged mutations upon normal exit."""
    facts_path = facts_sandbox.entities / "ctx_clean.json"
    with GDAFacts(filepath=facts_path, auto_commit=True) as mgr:
        mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})

    reloaded = GDAFacts(filepath=facts_path, auto_commit=False)
    assert len(reloaded) == 1


@pytest.mark.integration
def test_context_manager_suppresses_save_on_exception(facts_sandbox: GDAConfig) -> None:
    """Verify context manager suppresses automated commit when an unhandled exception occurs."""
    facts_path = facts_sandbox.entities / "ctx_exception.json"
    try:
        with GDAFacts(filepath=facts_path, auto_commit=True) as mgr:
            mgr.add({"person_id": "IND-00001", "fact_type": "Birth"})
            raise RuntimeError("Intentional error during context manager")
    except RuntimeError:
        pass

    reloaded = GDAFacts(filepath=facts_path, auto_commit=False)
    assert len(reloaded) == 0