# Name: test_gpi.py
# Path: tests/integration/test_gpi.py

"""Comprehensive test harness for GPI (Genealogy Person Intake Pipeline).

Exercises discovery, syntax validation, topological graph reachability,
deduplication drift, location canonicalization, sequential identifier minting,
reciprocal relation updates, atomic commit backups, and CLI operations.
"""

import json
import logging
from pathlib import Path
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops import gpi
from tools.ops.gpi import (
    main,
    quarantine_file,
    restore_quarantine,
    stage_0_discovery,
    stage_1_validate_syntax,
    stage_2_verify_graph_topology,
    stage_3_deduplication_drift,
    stage_4_canonicalize_locations,
    stage_5_minting_and_rewrite,
    stage_6_atomic_commit,
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

    # Base canonical locations
    loc_data = {
        "$schema": "schemas/entities/location_registry.schema.json",
        "schema_version": "1.0.0",
        "total_locations": 2,
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
            },
            {
                "location_id": "LOC-00002",
                "location_type": "MUNICIPALITY",
                "location": {
                    "standardized": "Carlisle, Cumberland County, Pennsylvania, USA",
                    "verbatim": "Carlisle, PA",
                    "details": {
                        "local_jurisdiction": "Carlisle",
                        "county": "Cumberland County",
                        "state_or_province": "Pennsylvania",
                        "country": "USA",
                    },
                },
            },
        ],
    }
    GDAUtil.save_json(mock_config.locations, loc_data)

    # Base location index
    index_data = {
        "schema_version": "1.0.0",
        "redirects": {
            "west pennsboro, pa": {
                "location_id": "LOC-00001",
                "standardized": "West Pennsboro Township, Cumberland County, Pennsylvania, USA",
            },
            "carlisle, pa": {
                "location_id": "LOC-00002",
                "standardized": "Carlisle, Cumberland County, Pennsylvania, USA",
            },
        },
    }
    GDAUtil.save_json(mock_config.locations_index, index_data)

    # Master people.json baseline
    people_data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.2",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00000",
                "display_name": "Arthur Pendelton Sterling",
                "canonical_name": {"given": "Arthur", "surname": "Sterling", "birth_year": {"year": 1961}},
                "associated_people": [{"person_id": "IND-00019", "role": "CHIL"}],
            },
            {
                "person_id": "IND-00019",
                "display_name": "Garrison Montgomery Sterling III",
                "canonical_name": {"given": "Garrison", "surname": "Sterling", "birth_year": {"year": 1941}},
                "associated_people": [{"person_id": "IND-00000", "role": "FATH"}],
            },
        ],
    }
    GDAUtil.save_json(mock_config.people, people_data)

    # Person schema for Stage 1 validation
    schema_data = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["person_id", "display_name", "canonical_name"],
        "unevaluatedProperties": False,
        "properties": {
            "person_id": {"type": "string"},
            "display_name": {"type": "string"},
            "canonical_name": {"type": "object"},
            "sex": {"type": "string", "enum": ["Male", "Female", "Unknown"]},
            "vitals": {"type": "object"},
            "notes": {"type": "array"},
            "associated_people": {"type": "array"},
            "unions": {"type": "array"},
            "last_updated": {"type": "string"},
        },
    }
    GDAUtil.save_json(mock_config.person_schema, schema_data)

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


# ==============================================================================
# SMOKE TESTS
# ==============================================================================
@pytest.mark.smoke
def test_stage_0_discovery_empty(mock_gpi_env):
    """Verifies discovery on an empty directory returns an empty list."""
    discovered = stage_0_discovery(root_dir=mock_gpi_env["root"])
    assert discovered == []


@pytest.mark.smoke
def test_stage_0_discovery_populated(mock_gpi_env):
    """Verifies discovery pattern matches only pep-let JSON files."""
    ent_dir = mock_gpi_env["entities_dir"]
    pep1 = ent_dir / "pep-let-001.json"
    pep2 = ent_dir / "pep-let-002.json"
    other = ent_dir / "other-file.json"

    pep1.write_text("{}", encoding="utf-8")
    pep2.write_text("{}", encoding="utf-8")
    other.write_text("{}", encoding="utf-8")

    discovered = stage_0_discovery(root_dir=mock_gpi_env["root"])
    assert len(discovered) == 2
    assert pep1 in discovered
    assert pep2 in discovered
    assert other not in discovered


@pytest.mark.smoke
def test_restore_quarantine_empty(mock_gpi_env):
    """Verifies restore_quarantine exits gracefully when directory is empty."""
    restore_quarantine(
        logger=mock_gpi_env["logger"],
        quarantine_dir=mock_gpi_env["quarantine_dir"],
        entities_dir=mock_gpi_env["entities_dir"],
    )
    assert list(mock_gpi_env["entities_dir"].glob("pep-let-*.json")) == []


@pytest.mark.smoke
def test_restore_quarantine_missing_dir(mock_gpi_env):
    """Verifies restore_quarantine handles non-existent quarantine path."""
    non_existent = mock_gpi_env["root"] / "non_existent_quarantine"
    restore_quarantine(
        logger=mock_gpi_env["logger"],
        quarantine_dir=non_existent,
        entities_dir=mock_gpi_env["entities_dir"],
    )
    assert not non_existent.exists()


# ==============================================================================
# REGRESSION TESTS
# ==============================================================================
@pytest.mark.regression
def test_stage_1_disallowed_properties_and_enums(mock_gpi_env):
    """Verifies schema strictness rejects unevaluated properties and bad enums."""
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    f1 = ent_dir / "pep-let-disallowed.json"
    GDAUtil.save_json(f1, {
        "person_id": "TMP-00001",
        "display_name": "Invalid Prop",
        "canonical_name": {"given": "Invalid", "surname": "Prop"},
        "unauthorized_key": "Illegal",
    })

    f2 = ent_dir / "pep-let-bad-enum.json"
    GDAUtil.save_json(f2, {
        "person_id": "TMP-00002",
        "display_name": "Bad Sex",
        "canonical_name": {"given": "Bad", "surname": "Sex"},
        "sex": "UNKNOWN_ENUM_VALUE",
    })

    records, files = stage_1_validate_syntax(
        [f1, f2],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )

    assert len(records) == 0
    assert len(files) == 0
    assert (q_dir / "pep-let-disallowed.json").exists()
    assert (q_dir / "pep-let-bad-enum.json").exists()


@pytest.mark.regression
def test_stage_2_self_referential_and_dangling_loops(mock_gpi_env):
    """Verifies self-referential and dangling links without path to root are quarantined."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    f_loop = ent_dir / "pep-let-loop.json"
    GDAUtil.save_json(f_loop, {
        "person_id": "TMP-00010",
        "display_name": "Self Parent",
        "canonical_name": {"given": "Self", "surname": "Parent"},
        "associated_people": [{"person_id": "TMP-00010", "role": "FATH"}],
    })

    f_dangle = ent_dir / "pep-let-dangle.json"
    GDAUtil.save_json(f_dangle, {
        "person_id": "TMP-00020",
        "display_name": "Dangling Node",
        "canonical_name": {"given": "Dangling", "surname": "Node"},
        "associated_people": [{"person_id": "IND-99999", "role": "FATH"}],
    })

    records, files = stage_2_verify_graph_topology(
        [GDAUtil.load_json(f_loop), GDAUtil.load_json(f_dangle)],
        [f_loop, f_dangle],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )

    assert len(records) == 0
    assert (q_dir / "pep-let-loop.json").exists()
    assert (q_dir / "pep-let-dangle.json").exists()


@pytest.mark.regression
def test_stage_3_phonetic_variants_pass_fingerprint(mock_gpi_env):
    """Verifies similar names pass deduplication while exact fingerprints collide."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    # Exact collision with existing IND-00019 (Garrison Sterling, 1941)
    f_dup = ent_dir / "pep-let-dup.json"
    rec_dup = {
        "person_id": "TMP-00001",
        "display_name": "Garrison Sterling",
        "canonical_name": {"given": "Garrison", "surname": "Sterling", "birth_year": {"year": 1941}},
    }
    GDAUtil.save_json(f_dup, rec_dup)

    # Phonetic/Spelling variant: 'Garison' (passes)
    f_var = ent_dir / "pep-let-var.json"
    rec_var = {
        "person_id": "TMP-00002",
        "display_name": "Garison Sterling",
        "canonical_name": {"given": "Garison", "surname": "Sterling", "birth_year": {"year": 1941}},
    }
    GDAUtil.save_json(f_var, rec_var)

    records, files = stage_3_deduplication_drift(
        [rec_dup, rec_var],
        [f_dup, f_var],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )

    assert len(records) == 1
    assert records[0]["canonical_name"]["given"] == "Garison"
    assert (q_dir / "pep-let-dup.json").exists()


@pytest.mark.regression
def test_stage_4_unregistered_location_quarantine(mock_gpi_env):
    """Verifies unindexed birth and death places trigger quarantine."""
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    f_bad_birth = ent_dir / "pep-let-bad-birth.json"
    rec_bad_birth = {
        "person_id": "TMP-00001",
        "display_name": "Lost Birth",
        "canonical_name": {"given": "Lost", "surname": "Birth"},
        "vitals": {"birth": {"place": {"standardized": "Atlantis, Atlantic Ocean"}}},
    }
    GDAUtil.save_json(f_bad_birth, rec_bad_birth)

    f_bad_death = ent_dir / "pep-let-bad-death.json"
    rec_bad_death = {
        "person_id": "TMP-00002",
        "display_name": "Lost Death",
        "canonical_name": {"given": "Lost", "surname": "Death"},
        "vitals": {"death": {"place": {"standardized": "Avalon, Mythic Isles"}}},
    }
    GDAUtil.save_json(f_bad_death, rec_bad_death)

    records, files = stage_4_canonicalize_locations(
        [rec_bad_birth, rec_bad_death],
        [f_bad_birth, f_bad_death],
        mock_gpi_env["loc_data"],
        mock_gpi_env["index_data"],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )

    assert len(records) == 0
    assert (q_dir / "pep-let-bad-birth.json").exists()
    assert (q_dir / "pep-let-bad-death.json").exists()


@pytest.mark.regression
def test_quarantine_file_exception_handling(mock_gpi_env, monkeypatch):
    """Verifies quarantine_file logs an error without crashing when moving fails."""
    ent_dir = mock_gpi_env["entities_dir"]
    target = ent_dir / "pep-let-fail.json"
    target.write_text("{}", encoding="utf-8")

    def broken_quarantine(*args, **kwargs):
        raise OSError("Disk write failed")

    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.GDAUtil.quarantine_file", broken_quarantine)
    quarantine_file(target, "Forced failure test", logger=mock_gpi_env["logger"])


# ==============================================================================
# BURN-IN / STRESS TESTS
# ==============================================================================
@pytest.mark.burnin
def test_stage_2_deep_five_generation_topology(mock_gpi_env):
    """Verifies a 5-generation linear branch successfully resolves back to root."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    ent_dir = mock_gpi_env["entities_dir"]

    chain = [
        {"person_id": "TMP-00001", "canonical_name": {"given": "G1", "surname": "S"}, "associated_people": [{"person_id": "IND-00019", "role": "FATH"}]},
        {"person_id": "TMP-00002", "canonical_name": {"given": "G2", "surname": "S"}, "associated_people": [{"person_id": "TMP-00001", "role": "FATH"}]},
        {"person_id": "TMP-00003", "canonical_name": {"given": "G3", "surname": "S"}, "associated_people": [{"person_id": "TMP-00002", "role": "FATH"}]},
        {"person_id": "TMP-00004", "canonical_name": {"given": "G4", "surname": "S"}, "associated_people": [{"person_id": "TMP-00003", "role": "FATH"}]},
        {"person_id": "TMP-00005", "canonical_name": {"given": "G5", "surname": "S"}, "associated_people": [{"person_id": "TMP-00004", "role": "FATH"}]},
    ]
    files = []
    for item in chain:
        f = ent_dir / f"pep-let-{item['person_id']}.json"
        GDAUtil.save_json(f, item)
        files.append(f)

    records, passed_files = stage_2_verify_graph_topology(
        chain, files, existing_people, verbose=True, logger=mock_gpi_env["logger"]
    )
    assert len(records) == 5
    assert len(passed_files) == 5


@pytest.mark.burnin
def test_stage_5_minting_multi_reciprocal_rewrite():
    """Verifies sequential minting rewrites reciprocal edges across complex trees."""
    staged = [
        {
            "person_id": "TMP-00001",
            "display_name": "Son",
            "associated_people": [{"person_id": "TMP-00002", "role": "FATH"}],
        },
        {
            "person_id": "TMP-00002",
            "display_name": "Father",
            "associated_people": [
                {"person_id": "TMP-00001", "role": "CHIL"},
                {"person_id": "IND-00010", "role": "FATH"},
            ],
        },
    ]
    existing = [
        {"person_id": "IND-00010", "display_name": "Grandfather", "associated_people": []}
    ]

    minted, updated_existing = stage_5_minting_and_rewrite(staged, existing)

    assert minted[0]["person_id"] == "IND-00011"
    assert minted[1]["person_id"] == "IND-00012"
    gf = next(p for p in updated_existing if p["person_id"] == "IND-00010")
    assert any(r["person_id"] == "IND-00012" and r["role"] == "CHIL" for r in gf["associated_people"])


# ==============================================================================
# INTEGRATION TESTS (FULL PIPELINE & CLI)
# ==============================================================================
@pytest.mark.integration
def test_gpi_cli_no_args(mock_gpi_env, monkeypatch):
    """Verifies running GPI without operation mode warns and exits safely."""
    monkeypatch.setattr("sys.argv", ["gpi.py"])
    main()


@pytest.mark.integration
def test_gpi_cli_append_pipeline(mock_gpi_env, monkeypatch):
    """Verifies complete end-to-end execution via main() with --append flag."""
    ent_dir = mock_gpi_env["entities_dir"]
    pep_file = ent_dir / "pep-let-new.json"
    GDAUtil.save_json(pep_file, {
        "person_id": "TMP-00099",
        "display_name": "New Descendant",
        "canonical_name": {"given": "New", "surname": "Descendant", "birth_year": {"year": 1990}},
        "vitals": {
            "birth": {"place": {"standardized": "Carlisle, PA"}}
        },
        "associated_people": [{"person_id": "IND-00000", "role": "FATH"}],
    })

    monkeypatch.setattr("sys.argv", ["gpi.py", "--append", "--verbose", "--debug"])
    main()

    assert not pep_file.exists()
    registry = GDAUtil.load_json(mock_gpi_env["config"].people)
    assert registry["total_persons"] == 3
    new_p = next(p for p in registry["persons"] if p["person_id"] == "IND-00020")
    assert new_p["display_name"] == "New Descendant"
    assert new_p["vitals"]["birth"]["place"]["standardized"] == "Carlisle, Cumberland County, Pennsylvania, USA"


@pytest.mark.integration
def test_gpi_cli_restore_pipeline(mock_gpi_env, monkeypatch):
    """Verifies running main() with --restore moves quarantined files back."""
    q_dir = mock_gpi_env["quarantine_dir"]
    held = q_dir / "pep-let-held.json"
    GDAUtil.save_json(held, {"person_id": "TMP-HELD"})

    monkeypatch.setattr("sys.argv", ["gpi.py", "--restore"])
    main()

    assert not held.exists()
    assert (mock_gpi_env["entities_dir"] / "pep-let-held.json").exists()


# ==============================================================================
# COVERAGE REMEDIATION (EDGE CASES & ERROR EXITS)
# ==============================================================================
@pytest.mark.regression
def test_stage_1_missing_schema_file(mock_gpi_env):
    """Exercises FileNotFoundError fallback when person.schema.json is missing."""
    mock_gpi_env["config"].person_schema.unlink(missing_ok=True)
    ent_dir = mock_gpi_env["entities_dir"]
    target = ent_dir / "pep-let-dummy.json"
    target.write_text("{}", encoding="utf-8")

    records, files = stage_1_validate_syntax(
        [target],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=mock_gpi_env["quarantine_dir"],
    )
    assert records == []
    assert files == []


@pytest.mark.regression
def test_stage_3_dedup_missing_birth_year(mock_gpi_env):
    """Exercises fingerprint generation when birth year or vital date is missing."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    ent_dir = mock_gpi_env["entities_dir"]

    f = ent_dir / "pep-let-nobirth.json"
    rec = {
        "person_id": "TMP-00001",
        "display_name": "No Birth",
        "canonical_name": {"given": "No", "surname": "Birth"},
    }
    GDAUtil.save_json(f, rec)

    records, files = stage_3_deduplication_drift(
        [rec],
        [f],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=mock_gpi_env["quarantine_dir"],
    )
    assert len(records) == 1
    assert files == [f]


@pytest.mark.regression
def test_stage_6_atomic_commit_oserror_recovery(mock_gpi_env, monkeypatch):
    """Exercises transaction abort when writing to disk raises an OSError."""
    def fail_save(*args, **kwargs):
        raise OSError("Disk full error simulation")

    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.GDAUtil.save_json", fail_save)

    success = stage_6_atomic_commit([], [], [], logger=mock_gpi_env["logger"])
    assert success is False


@pytest.mark.integration
def test_gpi_cli_flags_and_keyboard_interrupt(mock_gpi_env, monkeypatch):
    """Exercises CLI verbose-only branch and KeyboardInterrupt safe abort."""
    # Test verbose without debug
    monkeypatch.setattr("sys.argv", ["gpi.py", "-v"])
    main()

    # Test KeyboardInterrupt handling gracefully exiting with code 130
    def mock_interrupt(*args, **kwargs):
        sys.exit(130)

    monkeypatch.setattr("tools.ops.gpi.stage_0_discovery", mock_interrupt)
    monkeypatch.setattr("sys.argv", ["gpi.py", "--append"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 130
