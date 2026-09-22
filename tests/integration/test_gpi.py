# Name: test_gpi.py
# Path: tests/integration/test_gpi.py

import json
import logging
from pathlib import Path
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops import gpi
from tools.ops.gpi import (
    stage_0_discovery,
    stage_1_validate_syntax,
    stage_2_verify_graph_topology,
    stage_3_deduplication_drift,
    stage_4_canonicalize_locations,
    stage_5_minting_and_rewrite,
    stage_6_atomic_commit,
    restore_quarantine,
)


@pytest.fixture
def mock_gpi_env(tmp_path, monkeypatch):
    """Sets up an isolated digital archive environment rebinding GDAConfig."""
    data_dir = tmp_path / "data"
    entities_dir = data_dir / "entities"
    indexes_dir = data_dir / "indexes"
    quarantine_dir = entities_dir / "quarantine"
    backups_dir = tmp_path / "backups"
    logs_dir = tmp_path / "logs"
    schemas_dir = tmp_path / "schemas" / "entities"
    defs_dir = tmp_path / "schemas" / "defs"

    entities_dir.mkdir(parents=True, exist_ok=True)
    indexes_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)
    defs_dir.mkdir(parents=True, exist_ok=True)

    mock_config = GDAConfig(root=tmp_path, manifest={})
    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.gpi.CONFIG", mock_config)

    # Populate canonical entity files
    loc_data = {
        "$schema": "schemas/entities/location_registry.schema.json",
        "schema_version": "1.0.0",
        "total_locations": 1,
        "locations": [
            {
                "location_id": "LOC-00001",
                "location_type": "JURISDICTION",
                "location": {
                    "standardized": "West Pennsboro Township, Cumberland County, Pennsylvania, USA",
                    "verbatim": "West Pennsboro, PA",
                    "details": {
                        "local_jurisdiction": "West Pennsboro Township",
                        "county": "Cumberland County",
                        "state_or_province": "Pennsylvania",
                        "country": "USA",
                    },
                },
            }
        ],
    }
    GDAUtil.save_json(mock_config.locations, loc_data)

    index_data = {
        "schema_version": "1.0.0",
        "redirects": {
            "west pennsboro, pa": {
                "location_id": "LOC-00001",
                "standardized": "West Pennsboro Township, Cumberland County, Pennsylvania, USA",
            }
        },
    }
    GDAUtil.save_json(mock_config.locations_index, index_data)

    people_data = {
        "schema_version": "1.0.2",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00000",
                "display_name": "Root Ancestor",
                "canonical_name": {"given": "Root", "surname": "Ancestor"},
                "associated_people": [{"person_id": "IND-00001", "role": "CHIL"}],
            },
            {
                "person_id": "IND-00001",
                "display_name": "Existing Parent",
                "canonical_name": {"given": "Existing", "surname": "Parent", "birth_year": {"year": 1800}},
                "associated_people": [{"person_id": "IND-00000", "role": "FATH"}],
            },
        ],
    }
    GDAUtil.save_json(mock_config.people, people_data)

    test_logger = logging.getLogger("gpi_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    return {
        "root": tmp_path,
        "config": mock_config,
        "entities_dir": entities_dir,
        "quarantine_dir": quarantine_dir,
        "backups_dir": backups_dir,
        "loc_data": loc_data,
        "index_data": index_data,
        "people_data": people_data,
        "logger": test_logger,
    }


def test_stage_0_discovery(mock_gpi_env):
    """Verifies discovery of staged pep-let files."""
    entities_dir = mock_gpi_env["entities_dir"]
    pep1 = entities_dir / "pep-let-001.json"
    pep2 = entities_dir / "pep-let-002.json"
    other = entities_dir / "factoid-001.json"

    pep1.write_text("{}", encoding="utf-8")
    pep2.write_text("{}", encoding="utf-8")
    other.write_text("{}", encoding="utf-8")

    discovered = stage_0_discovery(root_dir=mock_gpi_env["root"])
    assert len(discovered) == 2
    assert pep1 in discovered
    assert pep2 in discovered


def test_stage_1_syntax_validation(mock_gpi_env):
    """Verifies schema validation and syntax checking."""
    schema_file = mock_gpi_env["config"].person_schema
    minimal_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["person_id", "display_name", "canonical_name"],
        "properties": {
            "person_id": {"type": "string"},
            "display_name": {"type": "string"},
            "canonical_name": {"type": "object"},
        },
    }
    GDAUtil.save_json(schema_file, minimal_schema)

    valid_pep = mock_gpi_env["entities_dir"] / "pep-let-001.json"
    GDAUtil.save_json(valid_pep, {
        "person_id": "TMP-00001",
        "display_name": "Test Child",
        "canonical_name": {"given": "Test", "surname": "Child"},
    })

    invalid_pep = mock_gpi_env["entities_dir"] / "pep-let-invalid.json"
    GDAUtil.save_json(invalid_pep, {
        "person_id": "TMP-99999",
    })

    records, files = stage_1_validate_syntax(
        [valid_pep, invalid_pep],
        verbose=False,
        logger=mock_gpi_env["logger"],
        person_schema_path=schema_file,
        quarantine_dir=mock_gpi_env["quarantine_dir"],
    )

    assert len(records) == 1
    assert records[0]["person_id"] == "TMP-00001"
    assert len(files) == 1

    # Verify invalid file quarantined
    assert not invalid_pep.exists()
    assert (mock_gpi_env["quarantine_dir"] / "pep-let-invalid.json").exists()


def test_stage_2_graph_topology(mock_gpi_env):
    """Verifies topological connection to root IND-00000."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    entities_dir = mock_gpi_env["entities_dir"]

    connected_record = {
        "person_id": "TMP-00002",
        "display_name": "Linked Child",
        "canonical_name": {"given": "Linked", "surname": "Child"},
        "associated_people": [{"person_id": "IND-00001", "role": "FATH"}],
    }
    f1 = entities_dir / "pep-let-linked.json"
    GDAUtil.save_json(f1, connected_record)

    orphan_record = {
        "person_id": "TMP-00003",
        "display_name": "Orphan Child",
        "canonical_name": {"given": "Orphan", "surname": "Child"},
    }
    f2 = entities_dir / "pep-let-orphan.json"
    GDAUtil.save_json(f2, orphan_record)

    records, files = stage_2_verify_graph_topology(
        [connected_record, orphan_record],
        [f1, f2],
        existing_people,
        verbose=False,
        logger=mock_gpi_env["logger"],
        quarantine_dir=mock_gpi_env["quarantine_dir"],
    )

    assert len(records) == 1
    assert records[0]["person_id"] == "TMP-00002"
    assert not f2.exists()
    assert (mock_gpi_env["quarantine_dir"] / "pep-let-orphan.json").exists()


def test_stage_3_deduplication(mock_gpi_env):
    """Verifies candidate duplicate identification and quarantine routing."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    dup_record = {
        "person_id": "TMP-00004",
        "display_name": "Existing Parent",
        "canonical_name": {"given": "Existing", "surname": "Parent", "birth_year": {"year": 1800}},
    }
    f1 = mock_gpi_env["entities_dir"] / "pep-let-dup.json"
    GDAUtil.save_json(f1, dup_record)

    records, files = stage_3_deduplication_drift(
        [dup_record],
        [f1],
        existing_people,
        verbose=False,
        logger=mock_gpi_env["logger"],
        quarantine_dir=mock_gpi_env["quarantine_dir"],
    )

    assert len(records) == 0
    assert not f1.exists()
    assert (mock_gpi_env["quarantine_dir"] / "pep-let-dup.json").exists()


def test_stage_4_location_canonicalization(mock_gpi_env):
    """Verifies place resolution against canonical authority and index."""
    locations_entity = mock_gpi_env["loc_data"]
    location_index = mock_gpi_env["index_data"]

    record = {
        "person_id": "TMP-00005",
        "display_name": "Loc Test",
        "canonical_name": {"given": "Loc", "surname": "Test"},
        "vitals": {
            "birth": {
                "place": {
                    "standardized": "West Pennsboro, PA",
                    "verbatim": "West Pennsboro, PA",
                }
            }
        },
    }
    f1 = mock_gpi_env["entities_dir"] / "pep-let-loc.json"
    GDAUtil.save_json(f1, record)

    records, files = stage_4_canonicalize_locations(
        [record],
        [f1],
        locations_entity,
        location_index,
        verbose=False,
        logger=mock_gpi_env["logger"],
        quarantine_dir=mock_gpi_env["quarantine_dir"],
    )

    assert len(records) == 1
    resolved_place = records[0]["vitals"]["birth"]["place"]["standardized"]
    assert resolved_place == "West Pennsboro Township, Cumberland County, Pennsylvania, USA"


def test_stage_5_minting_and_rewrite():
    """Verifies sequential master identifier generation and reciprocal link rewriting."""
    staged = [
        {
            "person_id": "TMP-00001",
            "display_name": "Son",
            "canonical_name": {"given": "Son", "surname": "Lehman"},
            "associated_people": [{"person_id": "TMP-00002", "role": "FATH"}],
        },
        {
            "person_id": "TMP-00002",
            "display_name": "Father",
            "canonical_name": {"given": "Father", "surname": "Lehman"},
            "associated_people": [{"person_id": "TMP-00001", "role": "CHIL"}],
        },
    ]
    existing = [
        {
            "person_id": "IND-00010",
            "display_name": "Old",
            "canonical_name": {"given": "Old", "surname": "Lehman"},
        }
    ]

    minted, _ = stage_5_minting_and_rewrite(staged, existing)

    assert minted[0]["person_id"] == "IND-00011"
    assert minted[1]["person_id"] == "IND-00012"
    assert minted[0]["associated_people"][0]["person_id"] == "IND-00012"
    assert minted[1]["associated_people"][0]["person_id"] == "IND-00011"


def test_stage_6_atomic_commit_and_backup(mock_gpi_env):
    """Verifies atomic commit, Safe Backup creation, and staging file unlinking."""
    people_file = mock_gpi_env["config"].people
    staged_record = {
        "person_id": "IND-00002",
        "display_name": "New Child",
        "canonical_name": {"given": "New", "surname": "Child"},
    }
    staged_file = mock_gpi_env["entities_dir"] / "pep-let-002.json"
    GDAUtil.save_json(staged_file, staged_record)

    existing = mock_gpi_env["people_data"]["persons"]

    success = stage_6_atomic_commit(
        new_records=[staged_record],
        updated_existing=existing,
        staged_files=[staged_file],
        verbose=True,
        logger=mock_gpi_env["logger"],
        people_path=people_file,
    )

    assert success is True
    assert not staged_file.exists()

    committed_data = GDAUtil.load_json(people_file)
    assert committed_data["total_persons"] == 3
    assert any(p["person_id"] == "IND-00002" for p in committed_data["persons"])

    backups = list(mock_gpi_env["backups_dir"].glob("people.json.*.bk"))
    assert len(backups) == 1


def test_restore_quarantine(mock_gpi_env):
    """Verifies restoring quarantined pep-let records back to staging."""
    q_dir = mock_gpi_env["quarantine_dir"]
    ent_dir = mock_gpi_env["entities_dir"]

    held_file = q_dir / "pep-let-held.json"
    GDAUtil.save_json(held_file, {"person_id": "TMP-HELD"})

    restore_quarantine(
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
        entities_dir=ent_dir,
    )

    assert not held_file.exists()
    restored_file = ent_dir / "pep-let-held.json"
    assert restored_file.exists()
    assert GDAUtil.load_json(restored_file)["person_id"] == "TMP-HELD"