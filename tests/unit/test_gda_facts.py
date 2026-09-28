# Name: test_gda_facts.py
# Path: tests/unit/test_gda_facts.py
# Version: 1.0.5+build.20260928.1

"""Unit test suite for the GDAFacts core facts registry container.

Operational Role:
    Validates in-memory indexing, query resolution, dirty state tracking,
    person cross-referencing (_person_xref), Safe Backup Protocol triggers,
    mutation methods (add, remove, replace), and defensive null-safety paths.

Test Structure & Protocol:
    - Atomized tests: 1:1 assertion mapping isolating single behaviors and boundaries.
    - Fully decorated: Explicitly marked with @pytest.mark.unit, @pytest.mark.regression,
      and @pytest.mark.smoke.
    - Dependencies: tests/fixtures/people/golden/golden_people.json,
                   tests/fixtures/facts/golden/golden_facts.json,
                   tmp_path hermetic sandbox.
"""

import json
import logging
import pytest
from pathlib import Path

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAFacts import GDAFacts
from tools.lib.gda_core.GDAUtil import GDAUtil


@pytest.fixture
def mock_facts_env(tmp_path, monkeypatch):
    """Sets up an isolated filesystem environment using tests/fixtures/[Subject]/golden/."""
    backups_dir = tmp_path / "backups"
    reports_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"
    entities_dir = tmp_path / "data" / "entities"

    backups_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    entities_dir.mkdir(parents=True, exist_ok=True)

    mock_config = GDAConfig(root=tmp_path, manifest={})

    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAFacts.CONFIG", mock_config)

    test_logger = logging.getLogger("gda_facts_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"

    golden_people_path = fixtures_dir / "people" / "golden" / "golden_people.json"
    golden_people_data = GDAUtil.load_json(golden_people_path)
    GDAUtil.save_json(mock_config.people, golden_people_data)

    golden_facts_path = fixtures_dir / "facts" / "golden" / "golden_facts.json"
    golden_facts_data = GDAUtil.load_json(golden_facts_path)
    GDAUtil.save_json(mock_config.facts, golden_facts_data)

    return {
        "root": tmp_path,
        "config": mock_config,
        "facts_file": mock_config.facts,
        "people_file": mock_config.people,
        "backups_dir": mock_config.backups,
        "fixtures_dir": fixtures_dir,
        "logger": test_logger,
    }


# -----------------------------------------------------------------------------
# Unit & Smoke Tests: Core Invariants, Iteration & Query Interface
# -----------------------------------------------------------------------------

@pytest.mark.smoke
@pytest.mark.unit
def test_gda_facts_len(mock_facts_env):
    """Verifies that GDAFacts initializes cleanly and reports correct record count."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    assert len(facts) == 100


@pytest.mark.unit
def test_gda_facts_iter(mock_facts_env):
    """Verifies iteration directly over GDAFacts yields fact dictionaries."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    items = list(facts)
    assert len(items) == 100
    assert items[0]["fact_id"] == "00000000-0000-4000-8000-000000000001"


@pytest.mark.unit
def test_gda_facts_existing_ids_property(mock_facts_env):
    """Verifies existing_ids property returns all indexed fact IDs."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    ids = facts.existing_ids
    assert len(ids) == 100
    assert "00000000-0000-4000-8000-000000000001" in ids


@pytest.mark.unit
def test_gda_facts_initial_dirty_state(mock_facts_env):
    """Verifies that GDAFacts initializes with a clean dirty state."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    assert not facts.is_dirty


@pytest.mark.smoke
@pytest.mark.unit
def test_gda_facts_get_exact(mock_facts_env):
    """Verifies retrieval interface resolves a fact record via full canonical UUID."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    exact = facts.get("00000000-0000-4000-8000-000000000001")
    assert exact is not None
    assert exact["fact_type"] == "Birth"


@pytest.mark.unit
def test_gda_facts_get_prefix_single_match(mock_facts_env):
    """Verifies resolution of a fact record via unique prefix match."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    match = facts.get("00000000-0000-4000-8000-000000000032")
    assert match is not None
    assert match["person_id"] == "IND-00019"


@pytest.mark.unit
def test_gda_facts_get_prefix_under_eight_chars(mock_facts_env):
    """Verifies get returns None immediately when query identifier is shorter than 8 characters."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    assert facts.get("0000") is None


@pytest.mark.unit
def test_gda_facts_get_prefix_ambiguous_returns_none(mock_facts_env):
    """Verifies short prefix matching multiple records logs warning and returns None."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    ambiguous = facts.get("00000000-0000")
    assert ambiguous is None


@pytest.mark.unit
def test_gda_facts_get_missing_returns_none(mock_facts_env):
    """Verifies get returns None when an 8+ char identifier has zero matches."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    assert facts.get("ffffffff-ffff-4000-8000-ffffffffffff") is None


@pytest.mark.smoke
@pytest.mark.unit
def test_gda_facts_get_by_person_count(mock_facts_env):
    """Verifies person cross-reference interface returns expected fact count for a person."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    person_facts = facts.get_by_person("IND-00000")
    assert len(person_facts) == 8


@pytest.mark.unit
def test_gda_facts_get_by_person_missing(mock_facts_env):
    """Verifies person cross-reference returns empty list for unindexed person."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    assert facts.get_by_person("IND-99999") == []


@pytest.mark.unit
def test_gda_facts_mark_dirty(mock_facts_env):
    """Verifies marking an existing record dirty records its ID in dirty_ids."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    target_id = "00000000-0000-4000-8000-000000000001"
    facts.mark_dirty(target_id)
    assert facts.is_dirty
    assert target_id in facts.dirty_ids


@pytest.mark.unit
def test_gda_facts_mark_dirty_nonexistent_ignored(mock_facts_env):
    """Verifies marking a non-existent ID dirty is ignored without error."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    facts.mark_dirty("non-existent-id")
    assert not facts.is_dirty


# -----------------------------------------------------------------------------
# Unit & Smoke Tests: Mutations (replace, add, remove)
# -----------------------------------------------------------------------------

@pytest.mark.smoke
@pytest.mark.unit
def test_gda_facts_replace_in_place(mock_facts_env):
    """Verifies replacement interface updates record in-place and marks session dirty."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    target_id = "00000000-0000-4000-8000-000000000001"
    existing = facts.get(target_id)
    assert existing is not None

    replacement = dict(existing)
    replacement["description"] = "Completely Replaced Description"

    success = facts.replace(target_id, replacement)
    assert success is True
    assert facts.get(target_id)["description"] == "Completely Replaced Description"
    assert target_id in facts.dirty_ids


@pytest.mark.unit
def test_gda_facts_replace_rebinds_person_xref(mock_facts_env):
    """Verifies replace updates _person_xref when person_id changes."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    target_id = "00000000-0000-4000-8000-000000000001"
    existing = facts.get(target_id)
    assert existing["person_id"] == "IND-00000"

    replacement = dict(existing)
    replacement["person_id"] = "IND-00019"

    facts.replace(target_id, replacement)
    p0_ids = [f["fact_id"] for f in facts.get_by_person("IND-00000")]
    p19_ids = [f["fact_id"] for f in facts.get_by_person("IND-00019")]
    assert target_id not in p0_ids
    assert target_id in p19_ids


@pytest.mark.unit
def test_gda_facts_replace_from_no_person_to_person(mock_facts_env):
    """Verifies replace binds to _person_xref when old fact had no person_id."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    new_unlinked = {
        "fact_id": "77777777-7777-4777-8777-777777777777",
        "fact_type": "Other"
    }
    facts.add(new_unlinked)

    replacement = dict(new_unlinked)
    replacement["person_id"] = "IND-00000"
    facts.replace("77777777-7777-4777-8777-777777777777", replacement)

    p0_ids = [f["fact_id"] for f in facts.get_by_person("IND-00000")]
    assert "77777777-7777-4777-8777-777777777777" in p0_ids


@pytest.mark.unit
def test_gda_facts_replace_from_person_to_no_person(mock_facts_env):
    """Verifies replace clears person from _person_xref when replacement lacks person_id."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    target_id = "00000000-0000-4000-8000-000000000001"
    existing = facts.get(target_id)
    assert existing["person_id"] == "IND-00000"

    replacement = dict(existing)
    del replacement["person_id"]
    facts.replace(target_id, replacement)

    p0_ids = [f["fact_id"] for f in facts.get_by_person("IND-00000")]
    assert target_id not in p0_ids


@pytest.mark.unit
def test_gda_facts_replace_both_without_person(mock_facts_env):
    """Verifies replace succeeds when neither old nor new fact has a person_id."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    new_unlinked = {
        "fact_id": "88888888-8888-4888-8888-888888888888",
        "fact_type": "Other"
    }
    facts.add(new_unlinked)

    replacement = dict(new_unlinked)
    replacement["description"] = "Updated unlinked fact"
    facts.replace("88888888-8888-4888-8888-888888888888", replacement)

    assert facts.get("88888888-8888-4888-8888-888888888888")["description"] == "Updated unlinked fact"


@pytest.mark.unit
def test_gda_facts_replace_same_person_refreshes_xref(mock_facts_env):
    """Verifies replace updates object pointer in _person_xref when person_id is unchanged."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    target_id = "00000000-0000-4000-8000-000000000001"
    existing = facts.get(target_id)

    replacement = dict(existing)
    replacement["description"] = "Refreshed Description"
    facts.replace(target_id, replacement)

    p0_facts = facts.get_by_person("IND-00000")
    matching = next(f for f in p0_facts if f["fact_id"] == target_id)
    assert matching["description"] == "Refreshed Description"


@pytest.mark.smoke
@pytest.mark.unit
def test_gda_facts_add_success(mock_facts_env):
    """Verifies adding a new valid fact record indexes and marks dirty."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    new_record = {
        "fact_id": "33333333-3333-4333-8333-333333333333",
        "person_id": "IND-00000",
        "fact_type": "Award",
        "description": "Civic honor"
    }
    assert facts.add(new_record) is True
    assert len(facts) == 101
    assert facts.get("33333333-3333-4333-8333-333333333333") is not None
    assert "33333333-3333-4333-8333-333333333333" in facts.dirty_ids
    assert any(f["fact_id"] == new_record["fact_id"] for f in facts.get_by_person("IND-00000"))


@pytest.mark.unit
def test_gda_facts_add_without_person_id(mock_facts_env):
    """Verifies adding a fact without person_id succeeds and skips person_xref."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    new_record = {
        "fact_id": "44444444-4444-4444-8444-444444444444",
        "fact_type": "Other",
        "description": "General archive event"
    }
    assert facts.add(new_record) is True
    assert facts.get("44444444-4444-4444-8444-444444444444") is not None


@pytest.mark.unit
def test_gda_facts_remove_success(mock_facts_env):
    """Verifies removing a fact deletes it from indices and marks dirty."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    target_id = "00000000-0000-4000-8000-000000000001"
    assert facts.remove(target_id) is True
    assert len(facts) == 99
    assert facts.get(target_id) is None
    assert target_id in facts.dirty_ids
    assert not any(f["fact_id"] == target_id for f in facts.get_by_person("IND-00000"))


@pytest.mark.unit
def test_gda_facts_remove_fact_without_person_id(mock_facts_env):
    """Verifies removing a fact that has no person_id succeeds."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    new_record = {
        "fact_id": "55555555-5555-4555-8555-555555555555",
        "fact_type": "Other"
    }
    facts.add(new_record)
    assert facts.remove("55555555-5555-4555-8555-555555555555") is True
    assert facts.get("55555555-5555-4555-8555-555555555555") is None


@pytest.mark.unit
def test_gda_facts_remove_nonexistent_returns_false(mock_facts_env):
    """Verifies removing a non-existent fact returns False."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    assert facts.remove("nonexistent-uuid") is False


# -----------------------------------------------------------------------------
# Unit Tests: Lifecycle, Context Manager, Commit & Rollback Operations
# -----------------------------------------------------------------------------

@pytest.mark.unit
def test_gda_facts_commit_when_clean_is_noop(mock_facts_env):
    """Verifies commit does nothing and returns True if no changes were made."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    assert facts.commit() is True
    backups = list(mock_facts_env["backups_dir"].glob("facts.json.*.bk"))
    assert len(backups) == 0


@pytest.mark.unit
def test_gda_facts_commit_single_backup(mock_facts_env):
    """Verifies commit triggers Safe Backup Protocol once when records are dirty."""
    facts_file = mock_facts_env["facts_file"]
    backups_dir = mock_facts_env["backups_dir"]

    with GDAFacts(facts_path=facts_file, auto_commit=True) as mgr:
        fact = mgr.get("00000000-0000-4000-8000-000000000001")
        assert fact is not None
        fact["description"] = "Updated Description"
        mgr.mark_dirty(fact["fact_id"])

    backups = list(backups_dir.glob("facts.json.*.bk"))
    assert len(backups) == 1


@pytest.mark.unit
def test_gda_facts_rollback_in_memory_reset(mock_facts_env):
    """Verifies rollback restores initial in-memory state without disk mutation."""
    facts_file = mock_facts_env["facts_file"]

    mgr = GDAFacts(facts_path=facts_file, auto_commit=False)
    fact = mgr.get("00000000-0000-4000-8000-000000000001")
    assert fact is not None
    fact["fact_type"] = "TemporaryMutatedType"
    mgr.mark_dirty(fact["fact_id"])

    mgr.rollback()
    assert not mgr.is_dirty
    restored = mgr.get("00000000-0000-4000-8000-000000000001")
    assert restored is not None
    assert restored["fact_type"] == "Birth"


@pytest.mark.unit
def test_gda_facts_context_manager_exception_aborts_commit(mock_facts_env):
    """Verifies that an unhandled exception inside a context block prevents commit."""
    facts_file = mock_facts_env["facts_file"]
    backups_dir = mock_facts_env["backups_dir"]

    with pytest.raises(RuntimeError):
        with GDAFacts(facts_path=facts_file, auto_commit=True) as mgr:
            fact = mgr.get("00000000-0000-4000-8000-000000000001")
            fact["description"] = "Uncommitted due to crash"
            mgr.mark_dirty(fact["fact_id"])
            raise RuntimeError("Simulated crash")

    backups = list(backups_dir.glob("facts.json.*.bk"))
    assert len(backups) == 0


# -----------------------------------------------------------------------------
# Regression Tests: Defensive Boundaries & Validation Failures
# -----------------------------------------------------------------------------

@pytest.mark.regression
def test_gda_facts_load_nonexistent_file(tmp_path):
    """Verifies defensive handling of missing registry by initializing empty payload."""
    missing_file = tmp_path / "nonexistent_facts.json"
    facts = GDAFacts(facts_path=missing_file)
    assert len(facts) == 0


@pytest.mark.regression
def test_gda_facts_load_corrupt_bad_json(mock_facts_env):
    """Verifies JSONDecodeError raised when loading malformed JSON syntax."""
    corrupt_file = mock_facts_env["fixtures_dir"] / "facts" / "failure" / "corrupt_facts_bad_json.json"
    with pytest.raises(json.JSONDecodeError):
        GDAFacts(facts_path=corrupt_file)


@pytest.mark.regression
def test_gda_facts_load_invalid_structure_handles_list(mock_facts_env):
    """Verifies defensive fallback when root JSON payload is a raw list."""
    invalid_struct = mock_facts_env["fixtures_dir"] / "facts" / "failure" / "corrupt_facts_invalid_structure.json"
    facts = GDAFacts(facts_path=invalid_struct)
    assert len(facts) == 5


@pytest.mark.regression
def test_gda_facts_load_invalid_primitive_handles_empty(tmp_path):
    """Verifies defensive fallback when root JSON payload is a primitive integer."""
    prim_file = tmp_path / "primitive.json"
    GDAUtil.save_json(prim_file, 12345)
    facts = GDAFacts(facts_path=prim_file)
    assert len(facts) == 0


@pytest.mark.regression
def test_gda_facts_replace_not_found(mock_facts_env):
    """Verifies replace returns False if target ID does not exist."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    assert facts.replace("missing-id", {"fact_id": "missing-id"}) is False


@pytest.mark.regression
def test_gda_facts_replace_missing_id_raises(mock_facts_env):
    """Verifies replace raises ValueError if replacement fact lacks fact_id."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    target_id = "00000000-0000-4000-8000-000000000001"
    with pytest.raises(ValueError, match="must contain a valid 'fact_id'"):
        facts.replace(target_id, {"description": "Missing ID"})


@pytest.mark.regression
def test_gda_facts_replace_mutating_fact_id_raises(mock_facts_env):
    """Verifies replace raises ValueError if caller attempts to mutate immutable fact_id."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    target_id = "00000000-0000-4000-8000-000000000001"
    tampered = {"fact_id": "99999999-9999-4999-8999-999999999999", "description": "Tampered ID"}
    with pytest.raises(ValueError, match="fact_id is immutable"):
        facts.replace(target_id, tampered)


@pytest.mark.regression
def test_gda_facts_add_missing_id_raises(mock_facts_env):
    """Verifies add raises ValueError if fact record lacks fact_id."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    with pytest.raises(ValueError, match="must contain a valid 'fact_id'"):
        facts.add({"description": "No ID"})


@pytest.mark.regression
def test_gda_facts_add_duplicate_id_raises(mock_facts_env):
    """Verifies add raises ValueError if fact ID already exists in registry."""
    facts = GDAFacts(facts_path=mock_facts_env["facts_file"])
    existing_id = "00000000-0000-4000-8000-000000000001"
    with pytest.raises(ValueError, match="already exists"):
        facts.add({"fact_id": existing_id, "description": "Duplicate"})