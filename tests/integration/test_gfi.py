# Name: test_gfi.py
# Path: tests/integration/test_gfi.py

"""Integration test suite for GFI (Genealogy Fact Intake).

Validates:
- Fact semantic normalization and validation rules
- Batch chunking and automated quarantine routing
- Master append, de-duplication, dual safe backup generation, and workspace cleanup
- Quarantine restoration workflow
"""

import json
import logging
from pathlib import Path
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops import gfi
from tools.ops.gfi import (
    load_valid_person_ids,
    normalize_and_validate_fact,
    intake_and_batch,
    append_and_cleanup,
    restore_quarantine_files,
)


@pytest.fixture
def mock_gfi_env(tmp_path, monkeypatch):
    """Sets up an isolated digital archive environment by rebinding GDAConfig[cite: 8]."""
    data_dir = tmp_path / "data"
    entities_dir = data_dir / "entities"
    quarantine_dir = entities_dir / "quarantine"
    backups_dir = tmp_path / "backups"
    logs_dir = tmp_path / "logs"

    entities_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    mock_config = GDAConfig(root=tmp_path, manifest={})
    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.gfi.CONFIG", mock_config)

    # Populate baseline people registry
    people_payload = {
        "persons": [
            {"person_id": "IND-00001", "display_name": "John Doe"},
            {"person_id": "IND-00002", "display_name": "Jane Doe"},
        ]
    }
    GDAUtil.save_json(mock_config.people, people_payload)

    # Populate baseline facts registry
    facts_payload = {
        "$schema": "schemas/entities/fact_registry.schema.json",
        "schema_version": "1.0.1",
        "total_facts": 1,
        "facts": [
            {
                "fact_id": "EXISTING-FACT-001",
                "person_id": "IND-00001",
                "fact_type": "Birth",
                "description": "Original birth assertion",
                "source_urn": "urn:cite:RECORD:001",
            }
        ],
    }
    GDAUtil.save_json(mock_config.facts, facts_payload)

    test_logger = logging.getLogger("gfi_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    return {
        "root": tmp_path,
        "config": mock_config,
        "entities_dir": entities_dir,
        "quarantine_dir": quarantine_dir,
        "backups_dir": backups_dir,
        "people_path": mock_config.people,
        "facts_path": mock_config.facts,
        "logger": test_logger,
    }


def test_normalize_and_validate_fact():
    """Verifies semantic validation and place mapping."""
    valid_ids = {"IND-00001", "IND-00002"}

    # 1. Valid fact with citations
    raw_fact = {
        "person_id": "IND-00001",
        "fact_type": "Census",
        "description": "1900 US Census Record",
        "place": "Cumberland, PA",
        "citations": [{"publication_code": "CENSUS", "publication_date": "1900-06-01", "media_file": "PAGE1"}],
    }
    is_valid, msg, norm = normalize_and_validate_fact(raw_fact, valid_ids)
    assert is_valid is True
    assert "location" in norm
    assert "place" not in norm
    assert norm["source_urn"] == "urn:cite:CENSUS:19000601:PAGE1"

    # 2. Self-referencing loop violation
    loop_fact = {
        "person_id": "IND-00001",
        "display_name": "John Doe",
        "fact_type": "Marriage",
        "description": "Marriage assertion",
        "source_urn": "urn:cite:GEN:1",
        "associated_people": [{"person_id": "IND-00001", "name": "Different Person", "role": "SPOUSE"}],
    }
    is_valid_loop, msg_loop, _ = normalize_and_validate_fact(loop_fact, valid_ids)
    assert is_valid_loop is False
    assert "Self-referencing loop" in msg_loop


def test_intake_and_batch_quarantines_and_chunks(mock_gfi_env):
    """Verifies chunking of valid factoids and isolation of invalid records[cite: 7]."""
    entities_dir = mock_gfi_env["entities_dir"]
    quarantine_dir = mock_gfi_env["quarantine_dir"]

    # Valid factoid
    valid_file = entities_dir / "factoid-valid.json"
    GDAUtil.save_json(valid_file, {
        "fact_id": "FCT-NEW-001",
        "person_id": "IND-00001",
        "fact_type": "Residence",
        "description": "Living in Carlisle",
        "source_urn": "urn:cite:TEST:1",
    })

    # Invalid factoid (unknown person_id)
    invalid_file = entities_dir / "factoid-invalid.json"
    GDAUtil.save_json(invalid_file, {
        "fact_id": "FCT-NEW-002",
        "person_id": "IND-99999",
        "fact_type": "Residence",
        "description": "Living elsewhere",
        "source_urn": "urn:cite:TEST:2",
    })

    batched_count = intake_and_batch(
        batch_size=75,
        entities_dir=entities_dir,
        people_path=mock_gfi_env["people_path"],
        quarantine_dir=quarantine_dir,
        verbose=False,
        logger=mock_gfi_env["logger"],
    )

    assert batched_count == 1

    # Verify batch envelope was created
    fact_new = entities_dir / "fact-new"
    batches = list(fact_new.glob("factoids-*.json"))
    assert len(batches) == 1

    # Verify invalid file moved to quarantine
    assert not invalid_file.exists()
    assert (quarantine_dir / "factoid-invalid.json").exists()


def test_append_and_cleanup_merges_and_purges_staging(mock_gfi_env):
    """Verifies master append, de-duplication, backup creation, and staging purge[cite: 10]."""
    entities_dir = mock_gfi_env["entities_dir"]
    facts_path = mock_gfi_env["facts_path"]
    backups_dir = mock_gfi_env["backups_dir"]
    fact_new = entities_dir / "fact-new"
    fact_new.mkdir(parents=True, exist_ok=True)

    # Create staging batch with 1 duplicate and 1 novel fact
    batch_envelope = {
        "$schema": "schemas/entities/fact_registry.schema.json",
        "schema_version": "1.0.1",
        "total_facts": 2,
        "facts": [
            {
                "fact_id": "EXISTING-FACT-001",  # Duplicate ID
                "person_id": "IND-00001",
                "fact_type": "Birth",
                "description": "Duplicate assertion",
                "source_urn": "urn:cite:RECORD:001",
            },
            {
                "fact_id": "NEW-FACT-002",  # Novel ID
                "person_id": "IND-00002",
                "fact_type": "Death",
                "description": "Novel death assertion",
                "source_urn": "urn:cite:RECORD:002",
            },
        ],
    }
    batch_file = fact_new / "factoids-0001.json"
    GDAUtil.save_json(batch_file, batch_envelope)

    append_and_cleanup(
        batch_size=75,
        entities_dir=entities_dir,
        master_facts_path=facts_path,
        backups_dir=backups_dir,
        quarantine_dir=mock_gfi_env["quarantine_dir"],
        verbose=True,
        logger=mock_gfi_env["logger"],
    )

    # 1. Verify merged master facts
    updated_master = GDAUtil.load_json(facts_path)
    assert updated_master["total_facts"] == 2
    fids = [f["fact_id"] for f in updated_master["facts"]]
    assert "EXISTING-FACT-001" in fids
    assert "NEW-FACT-002" in fids

    # 2. Verify staging directory purged
    assert not fact_new.exists()

    # 3. Verify paired backups created
    master_backups = list(backups_dir.glob("facts.json.*.bk"))
    ingest_backups = list(backups_dir.glob("factoids_ingested_*.bk"))
    assert len(master_backups) == 1
    assert len(ingest_backups) == 1


def test_restore_quarantine_files(mock_gfi_env):
    """Verifies restoration of quarantined factoid files back to staging entities[cite: 7]."""
    entities_dir = mock_gfi_env["entities_dir"]
    quarantine_dir = mock_gfi_env["quarantine_dir"]

    quarantined = quarantine_dir / "factoid-recovered.json"
    GDAUtil.save_json(quarantined, {"fact_id": "FCT-RECOVERED"})

    restore_quarantine_files(
        entities_dir=entities_dir,
        quarantine_dir=quarantine_dir,
        verbose=False,
        logger=mock_gfi_env["logger"],
    )

    assert not quarantined.exists()
    restored = entities_dir / "factoid-recovered.json"
    assert restored.exists()
    assert GDAUtil.load_json(restored)["fact_id"] == "FCT-RECOVERED"