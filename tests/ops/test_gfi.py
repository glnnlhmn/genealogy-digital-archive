# Name: test_gfi.py
# Path: tests/ops/test_gfi.py
# Version: 1.1.0+build.20261006.14

"""Comprehensive test harness for GFI (Genealogy Fact Intake Pipeline).

Operational Role:
    Validates staging discovery, referential integrity via GDAReferenceManager,
    ungrounded associated people tolerance, symmetrical union synchronization via
    GDAPeople, batch packaging, quarantine handling, Safe Backups, and CLI execution.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly classified with pytest markers.
    - Dependencies: Requires tools/ops/gfi.py, gdacore, gdadomain, and tmp_path.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List
import pytest

from gdacore.config import GDAConfig
from gdacore.util import GDAUtil
from gdadomain.facts import GDAFacts
from gdadomain.people import GDAPeople
from tools.ops import gfi
from tools.ops.gfi import (
    commit_fact_batches,
    discover_staged_factoids,
    main,
    process_intake_batch,
    quarantine_factoid,
    restore_quarantine,
    sync_unions_for_fact,
    validate_factoid,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_gfi_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Sets up an isolated digital archive environment rebinding GDAConfig and loading static fixtures."""
    data_dir = tmp_path / "data"
    entities_dir = data_dir / "entities"
    quarantine_dir = entities_dir / "quarantine"
    fact_new_dir = entities_dir / "fact-new"
    backups_dir = tmp_path / "backups"
    logs_dir = tmp_path / "logs"

    entities_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    mock_config = GDAConfig(root=tmp_path)
    monkeypatch.setattr("gdacore.config.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.gfi.CONFIG", mock_config)

    people_path = entities_dir / "people.json"
    facts_path = entities_dir / "facts.json"

    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
    golden_people = fixtures_dir / "people" / "golden" / "golden_people.json"
    golden_facts = fixtures_dir / "facts" / "golden" / "golden_facts.json"

    if golden_people.exists():
        GDAUtil.save_json(people_path, GDAUtil.load_json(golden_people))
    else:
        GDAUtil.save_json(
            people_path,
            {
                "schema_version": "1.0.0",
                "persons": [
                    {
                        "person_id": "IND-00000",
                        "display_name": "Arthur Sterling",
                        "canonical_name": {"given": "Arthur", "surname": "Sterling"},
                        "sex": "M",
                        "associated_people": [],
                        "unions": [],
                    },
                    {
                        "person_id": "IND-00019",
                        "display_name": "Mary Vance",
                        "canonical_name": {"given": "Mary", "surname": "Vance"},
                        "sex": "F",
                        "associated_people": [],
                        "unions": [],
                    },
                ],
            },
        )

    if golden_facts.exists():
        GDAUtil.save_json(facts_path, GDAUtil.load_json(golden_facts))
    else:
        GDAUtil.save_json(
            facts_path,
            {
                "schema_version": "1.0.0",
                "facts": [
                    {
                        "fact_id": "11111111-1111-4111-8111-111111111111",
                        "person_id": "IND-00000",
                        "fact_type": "Birth",
                        "date": {"date_start": "1850-01-01"},
                    }
                ],
            },
        )

    test_logger = logging.getLogger("gfi_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    people_mgr = GDAPeople(filepath=people_path)
    facts_mgr = GDAFacts(facts_path)

    all_pids = [p["person_id"] for p in list(people_mgr) if isinstance(p, dict) and "person_id" in p]
    pid_a = all_pids[0] if len(all_pids) > 0 else "IND-00000"
    pid_b = all_pids[1] if len(all_pids) > 1 else "IND-00019"

    return {
        "root": tmp_path,
        "config": mock_config,
        "entities_dir": entities_dir,
        "quarantine_dir": quarantine_dir,
        "fact_new_dir": fact_new_dir,
        "backups_dir": backups_dir,
        "people_path": people_path,
        "facts_path": facts_path,
        "people_mgr": people_mgr,
        "facts_mgr": facts_mgr,
        "pid_a": pid_a,
        "pid_b": pid_b,
        "logger": test_logger,
    }


# ==============================================================================
# 1. DISCOVERY & QUARANTINE RECOVERY (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_discover_staged_factoids_empty(mock_gfi_env: Dict[str, Any]) -> None:
    discovered = discover_staged_factoids(mock_gfi_env["entities_dir"])
    assert discovered == []


@pytest.mark.smoke
def test_discover_staged_factoids_finds_staged_files(mock_gfi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gfi_env["entities_dir"]
    (ent_dir / "factoid-001.json").write_text("{}", encoding="utf-8")
    (ent_dir / "factoid-002.json").write_text("{}", encoding="utf-8")
    (ent_dir / "other.json").write_text("{}", encoding="utf-8")

    discovered = discover_staged_factoids(ent_dir)
    assert len(discovered) == 2


@pytest.mark.regression
def test_discover_staged_factoids_missing_dir_returns_empty(mock_gfi_env: Dict[str, Any]) -> None:
    non_existent = mock_gfi_env["root"] / "non_existent"
    assert discover_staged_factoids(non_existent) == []


@pytest.mark.smoke
def test_restore_quarantine_recovers_files(mock_gfi_env: Dict[str, Any]) -> None:
    q_dir = mock_gfi_env["quarantine_dir"]
    target = q_dir / "20261006_120000_factoid-held.json"
    GDAUtil.save_json(target, {"fact_id": "some-id"})
    reason = q_dir / "20261006_120000_factoid-held.json.reason.txt"
    reason.write_text("Test reason", encoding="utf-8")

    count = restore_quarantine(
        logger=mock_gfi_env["logger"],
        quarantine_dir=q_dir,
        entities_dir=mock_gfi_env["entities_dir"],
    )
    assert count == 1
    assert (mock_gfi_env["entities_dir"] / "factoid-held.json").exists()
    assert not reason.exists()


@pytest.mark.regression
def test_restore_quarantine_missing_dir_returns_zero(mock_gfi_env: Dict[str, Any]) -> None:
    non_existent = mock_gfi_env["root"] / "non_existent_quarantine"
    assert restore_quarantine(logger=mock_gfi_env["logger"], quarantine_dir=non_existent) == 0


# ==============================================================================
# 2. VALIDATION RULES (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_validate_factoid_non_dict_rejected(mock_gfi_env: Dict[str, Any]) -> None:
    valid, reason = validate_factoid("not a dict", mock_gfi_env["people_mgr"])  # type: ignore[arg-type]
    assert valid is False
    assert "Payload is not a valid JSON dictionary" in reason


@pytest.mark.regression
def test_validate_factoid_missing_fact_id_rejected(mock_gfi_env: Dict[str, Any]) -> None:
    valid, reason = validate_factoid({"person_id": mock_gfi_env["pid_a"], "fact_type": "Birth"}, mock_gfi_env["people_mgr"])
    assert valid is False
    assert "Missing required fact_id" in reason


@pytest.mark.regression
def test_validate_factoid_invalid_uuid_rejected(mock_gfi_env: Dict[str, Any]) -> None:
    valid, reason = validate_factoid(
        {"fact_id": "NOT-A-UUID", "person_id": mock_gfi_env["pid_a"], "fact_type": "Birth"}, mock_gfi_env["people_mgr"]
    )
    assert valid is False
    assert "must be lowercase UUIDv4" in reason


@pytest.mark.regression
def test_validate_factoid_missing_person_id_rejected(mock_gfi_env: Dict[str, Any]) -> None:
    valid, reason = validate_factoid(
        {"fact_id": "22222222-2222-4222-8222-222222222222", "fact_type": "Birth"}, mock_gfi_env["people_mgr"]
    )
    assert valid is False
    assert "Missing required person_id" in reason


@pytest.mark.regression
def test_validate_factoid_malformed_person_id_rejected(mock_gfi_env: Dict[str, Any]) -> None:
    valid, reason = validate_factoid(
        {"fact_id": "22222222-2222-4222-8222-222222222222", "person_id": "BAD-ID", "fact_type": "Birth"},
        mock_gfi_env["people_mgr"],
    )
    assert valid is False
    assert "must conform to IND-XXXXX" in reason


@pytest.mark.regression
def test_validate_factoid_unregistered_person_id_rejected(mock_gfi_env: Dict[str, Any]) -> None:
    valid, reason = validate_factoid(
        {"fact_id": "22222222-2222-4222-8222-222222222222", "person_id": "IND-99999", "fact_type": "Birth"},
        mock_gfi_env["people_mgr"],
    )
    assert valid is False
    assert "not found in master people registry" in reason


@pytest.mark.regression
def test_validate_factoid_missing_fact_type_rejected(mock_gfi_env: Dict[str, Any]) -> None:
    valid, reason = validate_factoid(
        {"fact_id": "22222222-2222-4222-8222-222222222222", "person_id": mock_gfi_env["pid_a"]}, mock_gfi_env["people_mgr"]
    )
    assert valid is False
    assert "Missing required fact_type" in reason


@pytest.mark.regression
def test_validate_factoid_unrecognized_fact_type_rejected(mock_gfi_env: Dict[str, Any]) -> None:
    valid, reason = validate_factoid(
        {
            "fact_id": "22222222-2222-4222-8222-222222222222",
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "InvalidFactType",
        },
        mock_gfi_env["people_mgr"],
    )
    assert valid is False
    assert "Unrecognized fact_type" in reason


@pytest.mark.smoke
def test_validate_factoid_accepts_ungrounded_associated_person(mock_gfi_env: Dict[str, Any]) -> None:
    valid, _ = validate_factoid(
        {
            "fact_id": "22222222-2222-4222-8222-222222222222",
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "Birth",
            "associated_people": [{"name": "Rev. John Unindexed", "role": "Officiant"}],
        },
        mock_gfi_env["people_mgr"],
    )
    assert valid is True


@pytest.mark.unit
def test_validate_factoid_skips_non_dict_associated_person(mock_gfi_env: Dict[str, Any]) -> None:
    valid, _ = validate_factoid(
        {
            "fact_id": "22222222-2222-4222-8222-222222222222",
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "Birth",
            "associated_people": ["NotADictionary"],
        },
        mock_gfi_env["people_mgr"],
    )
    assert valid is True


@pytest.mark.regression
def test_validate_factoid_rejects_malformed_associated_person_id(mock_gfi_env: Dict[str, Any]) -> None:
    valid, reason = validate_factoid(
        {
            "fact_id": "22222222-2222-4222-8222-222222222222",
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "Marriage",
            "associated_people": [{"person_id": "BAD-PID", "role": "Spouse"}],
        },
        mock_gfi_env["people_mgr"],
    )
    assert valid is False
    assert "Invalid associated person_id format" in reason


@pytest.mark.regression
def test_validate_factoid_rejects_unregistered_associated_person_id(mock_gfi_env: Dict[str, Any]) -> None:
    valid, reason = validate_factoid(
        {
            "fact_id": "22222222-2222-4222-8222-222222222222",
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "Marriage",
            "associated_people": [{"person_id": "IND-99999", "role": "Spouse"}],
        },
        mock_gfi_env["people_mgr"],
    )
    assert valid is False
    assert "not found in master people registry" in reason


# ==============================================================================
# 3. UNION SYNCHRONIZATION (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_sync_unions_for_fact_marriage_updates_both_spouses(mock_gfi_env: Dict[str, Any]) -> None:
    fact = {
        "fact_id": "33333333-3333-4333-8333-333333333333",
        "person_id": mock_gfi_env["pid_a"],
        "fact_type": "Marriage",
        "date": {"date_start": "1875-06-15"},
        "associated_people": [{"person_id": mock_gfi_env["pid_b"], "role": "Spouse"}],
    }
    synced = sync_unions_for_fact(fact, mock_gfi_env["people_mgr"], mock_gfi_env["logger"])
    assert synced >= 1


@pytest.mark.regression
def test_sync_unions_for_fact_marriage_updates_existing_union_date(mock_gfi_env: Dict[str, Any]) -> None:
    initial_fact = {
        "fact_id": "33333333-3333-4333-8333-333333333333",
        "person_id": mock_gfi_env["pid_a"],
        "fact_type": "Marriage",
        "date": {"date_start": "1875-06-15"},
        "associated_people": [{"person_id": mock_gfi_env["pid_b"], "role": "Spouse"}],
    }
    sync_unions_for_fact(initial_fact, mock_gfi_env["people_mgr"], mock_gfi_env["logger"])

    updated_fact = {
        "fact_id": "33333333-3333-4333-8333-333333333334",
        "person_id": mock_gfi_env["pid_a"],
        "fact_type": "Marriage",
        "date": {"date_start": "1875-06-20"},
        "associated_people": [{"person_id": mock_gfi_env["pid_b"], "role": "Spouse"}],
    }
    synced = sync_unions_for_fact(updated_fact, mock_gfi_env["people_mgr"], mock_gfi_env["logger"])
    assert synced >= 1


@pytest.mark.regression
def test_sync_unions_for_fact_divorce_updates_existing_unions(mock_gfi_env: Dict[str, Any]) -> None:
    marr_fact = {
        "fact_id": "33333333-3333-4333-8333-333333333333",
        "person_id": mock_gfi_env["pid_a"],
        "fact_type": "Marriage",
        "date": {"date_start": "1875-06-15"},
        "associated_people": [{"person_id": mock_gfi_env["pid_b"], "role": "Spouse"}],
    }
    sync_unions_for_fact(marr_fact, mock_gfi_env["people_mgr"], mock_gfi_env["logger"])

    div_fact = {
        "fact_id": "33333333-3333-4333-8333-333333333335",
        "person_id": mock_gfi_env["pid_a"],
        "fact_type": "Divorce",
        "date": {"date_start": "1885-01-01"},
        "associated_people": [{"person_id": mock_gfi_env["pid_b"], "role": "Spouse"}],
    }
    synced = sync_unions_for_fact(div_fact, mock_gfi_env["people_mgr"], mock_gfi_env["logger"])
    assert synced >= 1


@pytest.mark.regression
def test_sync_unions_for_fact_divorce_without_date_updates_status_only(mock_gfi_env: Dict[str, Any]) -> None:
    marr_fact = {
        "fact_id": "33333333-3333-4333-8333-333333333333",
        "person_id": mock_gfi_env["pid_a"],
        "fact_type": "Marriage",
        "date": {"date_start": "1875-06-15"},
        "associated_people": [{"person_id": mock_gfi_env["pid_b"], "role": "Spouse"}],
    }
    sync_unions_for_fact(marr_fact, mock_gfi_env["people_mgr"], mock_gfi_env["logger"])

    div_nodate = {
        "fact_id": "33333333-3333-4333-8333-333333333336",
        "person_id": mock_gfi_env["pid_a"],
        "fact_type": "Divorce",
        "associated_people": [{"person_id": mock_gfi_env["pid_b"], "role": "Spouse"}],
    }
    synced = sync_unions_for_fact(div_nodate, mock_gfi_env["people_mgr"], mock_gfi_env["logger"])
    assert synced >= 1


@pytest.mark.regression
def test_sync_unions_for_fact_ignores_non_union_events(mock_gfi_env: Dict[str, Any]) -> None:
    fact = {
        "fact_id": "44444444-4444-4444-8444-444444444444",
        "person_id": mock_gfi_env["pid_a"],
        "fact_type": "Burial",
    }
    synced = sync_unions_for_fact(fact, mock_gfi_env["people_mgr"], mock_gfi_env["logger"])
    assert synced == 0


@pytest.mark.regression
def test_sync_unions_for_fact_missing_subject_returns_zero(mock_gfi_env: Dict[str, Any]) -> None:
    fact = {
        "fact_id": "44444444-4444-4444-8444-444444444445",
        "person_id": "IND-99999",
        "fact_type": "Marriage",
        "associated_people": [{"person_id": mock_gfi_env["pid_b"], "role": "Spouse"}],
    }
    synced = sync_unions_for_fact(fact, mock_gfi_env["people_mgr"], mock_gfi_env["logger"])
    assert synced == 0


@pytest.mark.regression
def test_sync_unions_for_fact_skips_when_associated_spouse_is_ungrounded(mock_gfi_env: Dict[str, Any]) -> None:
    fact = {
        "fact_id": "55555555-5555-4555-8555-555555555555",
        "person_id": mock_gfi_env["pid_a"],
        "fact_type": "Marriage",
        "associated_people": [{"name": "Ungrounded Spouse"}],
    }
    synced = sync_unions_for_fact(fact, mock_gfi_env["people_mgr"], mock_gfi_env["logger"])
    assert synced == 0


# ==============================================================================
# 4. INTAKE BATCHING & MASTER COMMIT (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_process_intake_batch_quarantines_corrupt_json(mock_gfi_env: Dict[str, Any]) -> None:
    bad_file = mock_gfi_env["entities_dir"] / "factoid-bad.json"
    bad_file.write_text("{ corrupt json }", encoding="utf-8")

    res = process_intake_batch(
        staged_files=[bad_file],
        facts_mgr=mock_gfi_env["facts_mgr"],
        people_mgr=mock_gfi_env["people_mgr"],
        logger=mock_gfi_env["logger"],
        quarantine_dir=mock_gfi_env["quarantine_dir"],
    )
    assert res["quarantined"] == 1
    assert len(list(mock_gfi_env["quarantine_dir"].glob("*factoid-bad.json"))) == 1


@pytest.mark.regression
def test_process_intake_batch_dry_run_does_not_quarantine(mock_gfi_env: Dict[str, Any]) -> None:
    bad_file = mock_gfi_env["entities_dir"] / "factoid-dry-bad.json"
    bad_file.write_text("{ corrupt json }", encoding="utf-8")

    res = process_intake_batch(
        staged_files=[bad_file],
        facts_mgr=mock_gfi_env["facts_mgr"],
        people_mgr=mock_gfi_env["people_mgr"],
        logger=mock_gfi_env["logger"],
        quarantine_dir=mock_gfi_env["quarantine_dir"],
        dry_run=True,
    )
    assert res["quarantined"] == 1
    assert len(list(mock_gfi_env["quarantine_dir"].glob("*factoid-dry-bad.json"))) == 0


@pytest.mark.regression
def test_process_intake_batch_quarantines_duplicate_fact_id(mock_gfi_env: Dict[str, Any]) -> None:
    existing_id = list(mock_gfi_env["facts_mgr"].existing_ids)[0]
    dup_file = mock_gfi_env["entities_dir"] / "factoid-dup.json"
    GDAUtil.save_json(
        dup_file,
        {
            "fact_id": existing_id,
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "Burial",
        },
    )

    res = process_intake_batch(
        staged_files=[dup_file],
        facts_mgr=mock_gfi_env["facts_mgr"],
        people_mgr=mock_gfi_env["people_mgr"],
        logger=mock_gfi_env["logger"],
        quarantine_dir=mock_gfi_env["quarantine_dir"],
    )
    assert res["quarantined"] == 1


@pytest.mark.regression
def test_process_intake_batch_duplicate_in_dry_run_does_not_quarantine(mock_gfi_env: Dict[str, Any]) -> None:
    existing_id = list(mock_gfi_env["facts_mgr"].existing_ids)[0]
    dup_file = mock_gfi_env["entities_dir"] / "factoid-dup-dry.json"
    GDAUtil.save_json(
        dup_file,
        {
            "fact_id": existing_id,
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "Burial",
        },
    )

    res = process_intake_batch(
        staged_files=[dup_file],
        facts_mgr=mock_gfi_env["facts_mgr"],
        people_mgr=mock_gfi_env["people_mgr"],
        logger=mock_gfi_env["logger"],
        quarantine_dir=mock_gfi_env["quarantine_dir"],
        dry_run=True,
    )
    assert res["quarantined"] == 1
    assert len(list(mock_gfi_env["quarantine_dir"].glob("*factoid-dup-dry.json"))) == 0


@pytest.mark.smoke
def test_process_intake_batch_creates_batch_containers(mock_gfi_env: Dict[str, Any]) -> None:
    valid_file = mock_gfi_env["entities_dir"] / "factoid-valid.json"
    GDAUtil.save_json(
        valid_file,
        {
            "fact_id": "66666666-6666-4666-8666-666666666666",
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "Residence",
        },
    )

    res = process_intake_batch(
        staged_files=[valid_file],
        facts_mgr=mock_gfi_env["facts_mgr"],
        people_mgr=mock_gfi_env["people_mgr"],
        logger=mock_gfi_env["logger"],
        fact_new_dir=mock_gfi_env["fact_new_dir"],
    )
    assert res["accepted"] == 1
    assert res["batches_created"] == 1
    assert (mock_gfi_env["fact_new_dir"] / "batch-0001" / "factoids-0001.json").exists()


@pytest.mark.smoke
def test_commit_fact_batches_appends_and_cleans_up(mock_gfi_env: Dict[str, Any]) -> None:
    new_fact = {
        "fact_id": "77777777-7777-4777-8777-777777777777",
        "person_id": mock_gfi_env["pid_a"],
        "fact_type": "Occupation",
    }
    staged_file = mock_gfi_env["entities_dir"] / "factoid-commit.json"
    staged_file.write_text("{}", encoding="utf-8")
    missing_phantom = mock_gfi_env["entities_dir"] / "phantom-absent.json"

    res = commit_fact_batches(
        facts_mgr=mock_gfi_env["facts_mgr"],
        people_mgr=mock_gfi_env["people_mgr"],
        logger=mock_gfi_env["logger"],
        accepted_facts=[new_fact],
        accepted_files=[staged_file, missing_phantom],
    )
    assert res["committed"] == 1
    assert not staged_file.exists()

    reloaded_facts = GDAFacts(mock_gfi_env["facts_path"])
    assert "77777777-7777-4777-8777-777777777777" in reloaded_facts


@pytest.mark.smoke
def test_commit_fact_batches_from_staged_directory(mock_gfi_env: Dict[str, Any]) -> None:
    b_dir = mock_gfi_env["fact_new_dir"] / "batch-0001"
    b_dir.mkdir(parents=True, exist_ok=True)
    GDAUtil.save_json(
        b_dir / "factoids-0001.json",
        {
            "facts": [
                {
                    "fact_id": "12345678-1234-4234-8234-123456789abc",
                    "person_id": mock_gfi_env["pid_a"],
                    "fact_type": "Military",
                }
            ]
        },
    )

    res = commit_fact_batches(
        facts_mgr=mock_gfi_env["facts_mgr"],
        people_mgr=mock_gfi_env["people_mgr"],
        logger=mock_gfi_env["logger"],
        fact_new_dir=mock_gfi_env["fact_new_dir"],
    )
    assert res["committed"] == 1
    assert not mock_gfi_env["fact_new_dir"].exists()


@pytest.mark.regression
def test_commit_fact_batches_empty_noop(mock_gfi_env: Dict[str, Any]) -> None:
    res = commit_fact_batches(
        facts_mgr=mock_gfi_env["facts_mgr"],
        people_mgr=mock_gfi_env["people_mgr"],
        logger=mock_gfi_env["logger"],
        accepted_facts=[],
    )
    assert res["committed"] == 0


@pytest.mark.regression
def test_commit_fact_batches_no_arguments_and_missing_dir_returns_zero(mock_gfi_env: Dict[str, Any]) -> None:
    non_existent = mock_gfi_env["root"] / "non_existent_fact_new"
    res = commit_fact_batches(
        facts_mgr=mock_gfi_env["facts_mgr"],
        people_mgr=mock_gfi_env["people_mgr"],
        logger=mock_gfi_env["logger"],
        fact_new_dir=non_existent,
    )
    assert res["committed"] == 0


# ==============================================================================
# 5. CLI PIPELINE INTEGRATION (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_gfi_cli_no_staged_factoids_exits_zero(mock_gfi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["gfi.py"])
    assert main() == 0


@pytest.mark.smoke
def test_gfi_cli_intake_mode(mock_gfi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    staged = mock_gfi_env["entities_dir"] / "factoid-intake.json"
    GDAUtil.save_json(
        staged,
        {
            "fact_id": "99999999-9999-4999-8999-000000000001",
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "Census",
        },
    )

    monkeypatch.setattr("sys.argv", ["gfi.py", "--intake"])
    assert main() == 0
    assert (mock_gfi_env["fact_new_dir"] / "batch-0001").exists()


@pytest.mark.smoke
def test_gfi_cli_restore_flag_recovers_files(mock_gfi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    held = mock_gfi_env["quarantine_dir"] / "20261006_000000_factoid-cli.json"
    GDAUtil.save_json(held, {"fact_id": "cli-id"})

    monkeypatch.setattr("sys.argv", ["gfi.py", "--restore"])
    assert main() == 0
    assert (mock_gfi_env["entities_dir"] / "factoid-cli.json").exists()


@pytest.mark.smoke
def test_gfi_cli_dry_run_preserves_staging_file(mock_gfi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    staged = mock_gfi_env["entities_dir"] / "factoid-dry.json"
    GDAUtil.save_json(
        staged,
        {
            "fact_id": "88888888-8888-4888-8888-888888888888",
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "Census",
        },
    )

    monkeypatch.setattr("sys.argv", ["gfi.py", "--append", "--dry-run"])
    assert main() == 0
    assert staged.exists()


@pytest.mark.smoke
def test_gfi_cli_append_from_existing_batches(mock_gfi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    b_dir = mock_gfi_env["fact_new_dir"] / "batch-0001"
    b_dir.mkdir(parents=True, exist_ok=True)
    GDAUtil.save_json(
        b_dir / "factoids-0001.json",
        {
            "facts": [
                {
                    "fact_id": "99999999-9999-4999-8999-000000000002",
                    "person_id": mock_gfi_env["pid_a"],
                    "fact_type": "Probate",
                }
            ]
        },
    )

    monkeypatch.setattr("sys.argv", ["gfi.py", "--append"])
    assert main() == 0


@pytest.mark.smoke
def test_gfi_cli_append_from_existing_batches_dry_run(mock_gfi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    b_dir = mock_gfi_env["fact_new_dir"] / "batch-0001"
    b_dir.mkdir(parents=True, exist_ok=True)
    GDAUtil.save_json(
        b_dir / "factoids-0001.json",
        {
            "facts": [
                {
                    "fact_id": "99999999-9999-4999-8999-000000000003",
                    "person_id": mock_gfi_env["pid_a"],
                    "fact_type": "Probate",
                }
            ]
        },
    )

    monkeypatch.setattr("sys.argv", ["gfi.py", "--append", "--dry-run"])
    assert main() == 0
    assert (b_dir / "factoids-0001.json").exists()


@pytest.mark.integration
def test_gfi_cli_full_append_workflow(mock_gfi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    staged = mock_gfi_env["entities_dir"] / "factoid-e2e.json"
    GDAUtil.save_json(
        staged,
        {
            "fact_id": "99999999-9999-4999-8999-999999999999",
            "person_id": mock_gfi_env["pid_a"],
            "fact_type": "Marriage",
            "date": {"date_start": "1880-01-01"},
            "associated_people": [{"person_id": mock_gfi_env["pid_b"], "role": "Spouse"}],
        },
    )

    monkeypatch.setattr("sys.argv", ["gfi.py", "--append", "--verbose"])
    assert main() == 0
    assert not staged.exists()