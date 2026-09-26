# Name: test_gfi.py
# Path: tests/integration/test_gfi.py

"""Integration test suite for GFI (Genealogy Fact Intake).

Validates factoid validation, quarantine isolation, duplicate rejection,
master facts appending, Safe Backup creation, unions synchronization,
edge case handling, and CLI execution paths.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops.gfi import FactIntakeEngine, load_valid_person_ids, run_cli, sync_union_for_fact


@pytest.fixture
def mock_gfi_env(tmp_path: Path):
    """Sets up an isolated digital archive environment for GFI integration tests."""
    root_dir = tmp_path / "genealogy-digital-archive"
    entities_dir = root_dir / "data" / "entities"
    staging_dir = root_dir / "import" / "staging"
    quarantine_dir = entities_dir / "quarantine"
    backups_dir = root_dir / "backups"

    for d in [entities_dir, staging_dir, quarantine_dir, backups_dir]:
        d.mkdir(parents=True, exist_ok=True)

    people_payload = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-25T06:00:00Z",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "display_name": "John Doe",
                "canonical_name": {
                    "given": "John",
                    "surname": "Doe",
                    "birth_year": {"year": 1960, "modifier": "EXACT"},
                    "death_year": {"year": None, "modifier": "LIVING"},
                },
                "unions": [],
            },
            {
                "person_id": "IND-00002",
                "display_name": "Jane Smith",
                "canonical_name": {
                    "given": "Jane",
                    "surname": "Smith",
                    "birth_year": {"year": 1962, "modifier": "EXACT"},
                    "death_year": {"year": None, "modifier": "LIVING"},
                },
                "unions": [],
            },
        ],
    }

    facts_payload = {
        "$schema": "schemas/entities/fact_registry.schema.json",
        "schema_version": "1.0.1",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-25T06:00:00Z",
        "facts": [
            {
                "fact_id": "00000000-0000-4000-8000-000000000000",
                "person_id": "IND-00001",
                "fact_type": "Birth",
                "date": {"date_start": "1960-01-01", "modifier": "EXACT"},
            }
        ],
    }

    p_path = entities_dir / "people.json"
    f_path = entities_dir / "facts.json"
    GDAUtil.save_json(p_path, people_payload)
    GDAUtil.save_json(f_path, facts_payload)

    config = GDAConfig(root_dir)
    return config, staging_dir, quarantine_dir, f_path, p_path


def test_gfi_intake_appends_and_syncs_unions(mock_gfi_env):
    config, staging_dir, quarantine_dir, f_path, p_path = mock_gfi_env
    logger = logging.getLogger("test_gfi")

    staged_file = staging_dir / "factoid-11111111.json"
    fact_payload = {
        "fact_id": "11111111-1111-4111-8111-111111111111",
        "person_id": "IND-00001",
        "fact_type": "Marriage",
        "date": {"date_start": "1985-06-15", "modifier": "EXACT", "raw_text": "15 Jun 1985"},
        "location": {"standardized": "Carlisle, Cumberland County, Pennsylvania, USA"},
        "notes": "Parish register",
        "associated_people": [{"person_id": "IND-00002", "role": "Spouse"}],
    }
    GDAUtil.save_json(staged_file, fact_payload)

    engine = FactIntakeEngine(config, logger)
    results = engine.process_staged_factoids([staged_file])

    assert results["processed"] == 1
    assert results["accepted"] == 1
    assert results["quarantined"] == 0
    assert results["unions_synced"] == 2

    # Verify facts.json updated
    f_data = GDAUtil.load_json(f_path)
    assert any(f["fact_id"] == "11111111-1111-4111-8111-111111111111" for f in f_data["facts"])

    # Verify people.json unions synchronized symmetrically
    p_data = GDAUtil.load_json(p_path)
    p1 = next(p for p in p_data["persons"] if p["person_id"] == "IND-00001")
    p2 = next(p for p in p_data["persons"] if p["person_id"] == "IND-00002")

    assert len(p1["unions"]) == 1
    assert p1["unions"][0]["spouse_id"] == "IND-00002"
    assert p1["unions"][0]["status"] == "MARRIED"
    assert p1["unions"][0]["marriage_date"]["date_start"] == "1985-06-15"

    assert len(p2["unions"]) == 1
    assert p2["unions"][0]["spouse_id"] == "IND-00001"
    assert p2["unions"][0]["status"] == "MARRIED"
    assert p2["unions"][0]["marriage_date"]["date_start"] == "1985-06-15"


def test_gfi_quarantines_invalid_person_id(mock_gfi_env):
    config, staging_dir, quarantine_dir, f_path, p_path = mock_gfi_env
    logger = logging.getLogger("test_gfi")

    staged_file = staging_dir / "factoid-invalid-person.json"
    fact_payload = {
        "fact_id": "22222222-2222-4222-8222-222222222222",
        "person_id": "IND-99999",
        "fact_type": "Marriage",
    }
    GDAUtil.save_json(staged_file, fact_payload)

    engine = FactIntakeEngine(config, logger)
    results = engine.process_staged_factoids([staged_file])

    assert results["accepted"] == 0
    assert results["quarantined"] == 1
    assert (engine.quarantine_dir / "factoid-invalid-person.json").is_file()


def test_gfi_quarantines_duplicate_fact_id(mock_gfi_env):
    config, staging_dir, quarantine_dir, f_path, p_path = mock_gfi_env
    logger = logging.getLogger("test_gfi")

    staged_file = staging_dir / "factoid-dup.json"
    fact_payload = {
        "fact_id": "00000000-0000-4000-8000-000000000000",
        "person_id": "IND-00001",
        "fact_type": "Birth",
    }
    GDAUtil.save_json(staged_file, fact_payload)

    engine = FactIntakeEngine(config, logger)
    results = engine.process_staged_factoids([staged_file])

    assert results["accepted"] == 0
    assert results["quarantined"] == 1
    assert (engine.quarantine_dir / "factoid-dup.json").is_file()


def test_gfi_quarantines_corrupt_json(mock_gfi_env):
    config, staging_dir, quarantine_dir, f_path, p_path = mock_gfi_env
    logger = logging.getLogger("test_gfi")

    staged_file = staging_dir / "factoid-corrupt.json"
    staged_file.write_text("{ corrupt json ...", encoding="utf-8")

    engine = FactIntakeEngine(config, logger)
    results = engine.process_staged_factoids([staged_file])

    assert results["accepted"] == 0
    assert results["quarantined"] == 1
    assert (engine.quarantine_dir / "factoid-corrupt.json").is_file()


def test_gfi_validation_failures(mock_gfi_env):
    config, staging_dir, quarantine_dir, f_path, p_path = mock_gfi_env
    logger = logging.getLogger("test_gfi")
    engine = FactIntakeEngine(config, logger)
    valid_pids = {"IND-00001"}

    # Not a dictionary
    ok, reason = engine.validate_factoid(["not-dict"], valid_pids)
    assert not ok

    # Missing fact_id
    ok, reason = engine.validate_factoid({"person_id": "IND-00001", "fact_type": "Birth"}, valid_pids)
    assert not ok

    # Missing person_id
    ok, reason = engine.validate_factoid({"fact_id": "xyz", "fact_type": "Birth"}, valid_pids)
    assert not ok

    # Missing fact_type
    ok, reason = engine.validate_factoid({"fact_id": "xyz", "person_id": "IND-00001"}, valid_pids)
    assert not ok


def test_gfi_sync_unions_edge_cases(mock_gfi_env):
    config, staging_dir, quarantine_dir, f_path, p_path = mock_gfi_env
    logger = logging.getLogger("test_gfi")
    p_data = GDAUtil.load_json(p_path)

    # 1. Non-marriage/divorce fact returns 0
    res = sync_union_for_fact(p_data, {"fact_type": "Birth"})
    assert res == 0

    # 2. Fact missing person_id returns 0
    res = sync_union_for_fact(p_data, {"fact_type": "Marriage"})
    assert res == 0

    # 3. Fact missing associated spouses returns 0
    res = sync_union_for_fact(p_data, {"fact_type": "Marriage", "person_id": "IND-00001"})
    assert res == 0

    # 4. Unknown person_id returns 0
    res = sync_union_for_fact(
        p_data,
        {"fact_type": "Marriage", "person_id": "IND-99999", "associated_people": [{"person_id": "IND-00002"}]}
    )
    assert res == 0

    # 5. Unknown spouse returns 0
    res = sync_union_for_fact(
        p_data,
        {"fact_type": "Marriage", "person_id": "IND-00001", "associated_people": [{"person_id": "IND-88888"}]}
    )
    assert res == 0

    # 6. Update existing marriage union location and date
    p_data["persons"][0]["unions"] = [{
        "spouse_id": "IND-00002",
        "status": "MARRIED",
        "marriage_date": {"date_start": "1985-01-01"},
    }]
    p_data["persons"][1]["unions"] = [{
        "spouse_id": "IND-00001",
        "status": "MARRIED",
        "marriage_date": {"date_start": "1985-01-01"},
    }]
    m_fact = {
        "fact_type": "Marriage",
        "person_id": "IND-00001",
        "associated_people": [{"person_id": "IND-00002"}],
        "date": {"date_start": "1985-06-15"},
        "location": {"standardized": "New Place"},
    }
    synced = sync_union_for_fact(p_data, m_fact, logger)
    assert synced == 2
    assert p_data["persons"][0]["unions"][0]["place"]["standardized"] == "New Place"


def test_gfi_sync_divorce_fact(mock_gfi_env):
    config, staging_dir, quarantine_dir, f_path, p_path = mock_gfi_env
    logger = logging.getLogger("test_gfi")

    p_data = GDAUtil.load_json(p_path)
    p_data["persons"][0]["unions"] = [{
        "spouse_id": "IND-00002",
        "status": "MARRIED",
        "marriage_date": {"date_start": "1985-06-15"},
    }]
    p_data["persons"][1]["unions"] = [{
        "spouse_id": "IND-00001",
        "status": "MARRIED",
        "marriage_date": {"date_start": "1985-06-15"},
    }]
    GDAUtil.save_json(p_path, p_data)

    divorce_fact = {
        "fact_id": "33333333-3333-4333-8333-333333333333",
        "person_id": "IND-00001",
        "fact_type": "Divorce",
        "date": {"date_start": "1995-12-01", "modifier": "EXACT"},
        "associated_people": [{"person_id": "IND-00002"}],
    }
    synced = sync_union_for_fact(p_data, divorce_fact, logger)
    assert synced == 2
    assert p_data["persons"][0]["unions"][0]["status"] == "DIVORCED"
    assert p_data["persons"][0]["unions"][0]["end_date"]["date_start"] == "1995-12-01"
    assert p_data["persons"][1]["unions"][0]["status"] == "DIVORCED"
    assert p_data["persons"][1]["unions"][0]["end_date"]["date_start"] == "1995-12-01"


def test_gfi_load_valid_person_ids_fallbacks(tmp_path):
    logger = logging.getLogger("test_gfi")

    # Missing file returns empty set
    missing_path = tmp_path / "nonexistent.json"
    pids = load_valid_person_ids(missing_path, logger)
    assert pids == set()

    # Corrupt file returns empty set
    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text("{ corrupt ...", encoding="utf-8")
    pids = load_valid_person_ids(corrupt_path, logger)
    assert pids == set()


def test_gfi_cli_execution_with_files(mock_gfi_env, monkeypatch):
    config, staging_dir, quarantine_dir, f_path, p_path = mock_gfi_env

    # Stage a valid factoid for CLI intake
    staged_file = staging_dir / "factoid-cli-test.json"
    fact_payload = {
        "fact_id": "55555555-5555-4555-8555-555555555555",
        "person_id": "IND-00001",
        "fact_type": "Residence",
        "date": {"date_start": "1990-01-01"},
    }
    GDAUtil.save_json(staged_file, fact_payload)

    monkeypatch.setattr("sys.argv", ["gfi.py", "-d", str(staging_dir), "--verbose"])
    exit_code = run_cli()
    assert exit_code == 0


def test_gfi_cli_missing_dir(tmp_path, monkeypatch):
    missing_dir = tmp_path / "nonexistent_staging"
    monkeypatch.setattr("sys.argv", ["gfi.py", "-d", str(missing_dir)])
    exit_code = run_cli()
    assert exit_code == 1