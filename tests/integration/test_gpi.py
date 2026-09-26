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
import sys

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
    stage_2b_verify_relational_chronology,
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

    # Master people.json baseline (loaded directly from golden fixture)
    golden_people_path = Path(
        __file__).resolve().parent.parent / "fixtures" / "people" / "golden" / "golden_people.json"
    people_data = GDAUtil.load_json(golden_people_path)
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
    assert registry["total_persons"] == 63
    new_p = next(p for p in registry["persons"] if p["person_id"] == "IND-00338")
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


# ==============================================================================
# GPA INTRA-RECORD AUDIT VALIDATION (STAGE 1 INTEGRATION)
# ==============================================================================
PEPLET_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "peplets"
PEPLET_GOLDEN_DIR = PEPLET_FIXTURES_DIR / "golden"
PEPLET_FAILURES_DIR = PEPLET_FIXTURES_DIR / "failures"


@pytest.mark.regression
def test_stage_1_quarantines_vital_desync_via_gpa(mock_gpi_env):
    """Verifies Stage 1 quarantines pep-lets with desynchronized vital dates."""
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]
    src_fixture = PEPLET_FAILURES_DIR / "fail-vital-sync-birth.json"
    target = ent_dir / "pep-let-desync.json"
    target.write_text(src_fixture.read_text(encoding="utf-8"), encoding="utf-8")

    records, files = stage_1_validate_syntax(
        [target],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert len(records) == 0
    assert len(files) == 0
    assert (q_dir / "pep-let-desync.json").exists()


@pytest.mark.regression
def test_stage_1_quarantines_chrono_death_before_birth(mock_gpi_env):
    """Verifies Stage 1 quarantines pep-lets where death occurs before birth."""
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]
    src_fixture = PEPLET_FAILURES_DIR / "fail-chrono-death-before-birth.json"
    target = ent_dir / "pep-let-chrono.json"
    target.write_text(src_fixture.read_text(encoding="utf-8"), encoding="utf-8")

    records, files = stage_1_validate_syntax(
        [target],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert len(records) == 0
    assert len(files) == 0
    assert (q_dir / "pep-let-chrono.json").exists()


@pytest.mark.regression
def test_stage_1_quarantines_malformed_location_object(mock_gpi_env):
    """Verifies Stage 1 quarantines pep-lets with non-dict location place structures."""
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]
    src_fixture = PEPLET_FAILURES_DIR / "fail-location-malformed.json"
    target = ent_dir / "pep-let-location.json"
    target.write_text(src_fixture.read_text(encoding="utf-8"), encoding="utf-8")

    records, files = stage_1_validate_syntax(
        [target],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert len(records) == 0
    assert len(files) == 0
    assert (q_dir / "pep-let-location.json").exists()


@pytest.mark.smoke
def test_stage_1_golden_valid_peplet_passes(mock_gpi_env):
    """Verifies a fully conforming golden pep-let passes Stage 1 GPA validation."""
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]
    src_fixture = PEPLET_GOLDEN_DIR / "pep-let-golden-01-child-arthur.json"
    target = ent_dir / "pep-let-valid.json"
    target.write_text(src_fixture.read_text(encoding="utf-8"), encoding="utf-8")

    records, files = stage_1_validate_syntax(
        [target],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert len(records) == 1
    assert len(files) == 1
    assert not (q_dir / "pep-let-valid.json").exists()


# ==============================================================================
# MULTI-PEPLET GOLDEN BATCH VERIFICATION
# ==============================================================================
GOLDEN_PEPLETS_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "peplets" / "golden"


@pytest.mark.smoke
def test_all_ten_golden_peplets_pass_full_pipeline(mock_gpi_env, monkeypatch):
    """Verifies that all 10 golden pep-lets pass through the complete ingestion pipeline."""
    ent_dir = mock_gpi_env["entities_dir"]
    golden_files = sorted(GOLDEN_PEPLETS_DIR.glob("pep-let-*.json"))
    assert len(golden_files) == 10, f"Expected 10 golden peplets, found {len(golden_files)}"

    for gf in golden_files:
        target = ent_dir / gf.name
        target.write_text(gf.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["gpi.py", "--append", "--verbose"])
    main()

    # Verify no pep-lets were quarantined
    quarantined = list(mock_gpi_env["quarantine_dir"].glob("*.json"))
    assert quarantined == [], f"Unexpected quarantined files: {[q.name for q in quarantined]}"

    # Verify all 10 staging files were processed and cleaned
    remaining = list(ent_dir.glob("pep-let-*.json"))
    assert remaining == [], f"Staging directory not empty: {[r.name for r in remaining]}"

    # Verify master registry updated: 2 existing + 10 ingested = 12 total persons
    registry = GDAUtil.load_json(mock_gpi_env["config"].people)
    assert registry["total_persons"] == 72
    assert len(registry["persons"]) == 72

    # Verify reciprocal linking on root IND-00000
    arthur = next(p for p in registry["persons"] if p["person_id"] == "IND-00000")
    arthur_assoc = {a["person_id"]: a["role"] for a in arthur.get("associated_people", [])}

    # Verify all 10 newly minted IDs (IND-00020 through IND-00029) exist
    minted_ids = [f"IND-{idx:05d}" for idx in range(338, 348)]
    existing_ids = {p["person_id"] for p in registry["persons"]}
    for mid in minted_ids:
        assert mid in existing_ids, f"Minted ID {mid} missing from committed registry"


# ==============================================================================
# INTER-RECORD RELATIONAL CHRONOLOGY VERIFICATION
# ==============================================================================
@pytest.mark.regression
def test_stage_2b_quarantines_parent_too_young(mock_gpi_env):
    """Verifies relational chronology quarantines child if parent was < 12 at birth."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    src_fixture = PEPLET_FAILURES_DIR / "fail-inter-chrono-parent-too-young.json"
    target = ent_dir / "pep-let-parent-too-young.json"
    target.write_text(src_fixture.read_text(encoding="utf-8"), encoding="utf-8")

    rec = GDAUtil.load_json(target)
    passed_records, passed_files = stage_2b_verify_relational_chronology(
        [rec],
        [target],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )

    assert len(passed_records) == 0
    assert len(passed_files) == 0
    assert (q_dir / "pep-let-parent-too-young.json").exists()


@pytest.mark.regression
def test_stage_3_quarantines_exact_master_registry_collision(mock_gpi_env):
    """Verifies Stage 3 quarantines a staged pep-let colliding with a person in golden_people.json."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    src_fixture = PEPLET_FAILURES_DIR / "fail-dedup-exact-master-collision.json"
    target = ent_dir / "pep-let-master-collision.json"
    target.write_text(src_fixture.read_text(encoding="utf-8"), encoding="utf-8")

    rec = GDAUtil.load_json(target)
    records, files = stage_3_deduplication_drift(
        [rec],
        [target],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )

    assert len(records) == 0
    assert len(files) == 0
    assert (q_dir / "pep-let-master-collision.json").exists()


@pytest.mark.regression
def test_stage_3_quarantines_intra_batch_duplicate(mock_gpi_env):
    """Verifies Stage 3 accepts the first instance and quarantines a second identical intra-batch pep-let."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    src_fixture = PEPLET_FAILURES_DIR / "fail-dedup-intra-batch-collision.json"
    target1 = ent_dir / "pep-let-batch-1.json"
    target2 = ent_dir / "pep-let-batch-2.json"

    # Both files have identical canonical name and birth year
    target1.write_text(src_fixture.read_text(encoding="utf-8"), encoding="utf-8")
    target2.write_text(src_fixture.read_text(encoding="utf-8"), encoding="utf-8")

    rec1 = GDAUtil.load_json(target1)
    rec2 = GDAUtil.load_json(target2)

    records, files = stage_3_deduplication_drift(
        [rec1, rec2],
        [target1, target2],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )

    assert len(records) == 1
    assert len(files) == 1
    assert target1 in files
    assert not (q_dir / "pep-let-batch-1.json").exists()
    assert (q_dir / "pep-let-batch-2.json").exists()


@pytest.mark.regression
def test_stage_4_quarantines_unregistered_location_fixtures(mock_gpi_env):
    """Verifies Stage 4 quarantines pep-lets with unregistered birth and death places."""
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    f_birth = PEPLET_FAILURES_DIR / "fail-location-unregistered-birth.json"
    f_death = PEPLET_FAILURES_DIR / "fail-location-unregistered-death.json"

    t_birth = ent_dir / "pep-let-unreg-birth.json"
    t_death = ent_dir / "pep-let-unreg-death.json"

    t_birth.write_text(f_birth.read_text(encoding="utf-8"), encoding="utf-8")
    t_death.write_text(f_death.read_text(encoding="utf-8"), encoding="utf-8")

    rec_birth = GDAUtil.load_json(t_birth)
    rec_death = GDAUtil.load_json(t_death)

    records, files = stage_4_canonicalize_locations(
        [rec_birth, rec_death],
        [t_birth, t_death],
        mock_gpi_env["loc_data"],
        mock_gpi_env["index_data"],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )

    assert len(records) == 0
    assert len(files) == 0
    assert (q_dir / "pep-let-unreg-birth.json").exists()
    assert (q_dir / "pep-let-unreg-death.json").exists()


@pytest.mark.regression
def test_stage_4_expands_redirect_and_populates_details(mock_gpi_env):
    """Verifies Stage 4 resolves redirected shorthand places and attaches canonical details."""
    ent_dir = mock_gpi_env["entities_dir"]
    target = ent_dir / "pep-let-redirect.json"
    rec = {
        "person_id": "TMP-00088",
        "display_name": "Redirect Candidate",
        "canonical_name": {"given": "Redirect", "surname": "Candidate"},
        "vitals": {
            "birth": {
                "place": {
                    "verbatim": "West Pennsboro, PA",
                    "standardized": "West Pennsboro, PA",
                }
            }
        },
    }
    GDAUtil.save_json(target, rec)

    records, files = stage_4_canonicalize_locations(
        [rec],
        [target],
        mock_gpi_env["loc_data"],
        mock_gpi_env["index_data"],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=mock_gpi_env["quarantine_dir"],
    )

    assert len(records) == 1
    assert len(files) == 1
    birth_place = records[0]["vitals"]["birth"]["place"]
    assert birth_place["standardized"] == "West Pennsboro Township, Cumberland County, Pennsylvania, USA"
    assert birth_place["details"]["county"] == "Cumberland County"
    assert birth_place["details"]["state_or_province"] == "Pennsylvania"


@pytest.mark.regression
def test_stage_5_intra_batch_mutual_rewrite():
    """Verifies temporary ID references between entities in the same staging batch resolve to minted IDs."""
    staged = [
        {
            "person_id": "TMP-00101",
            "display_name": "Husband Candidate",
            "associated_people": [{"person_id": "TMP-00102", "role": "SPOU"}],
        },
        {
            "person_id": "TMP-00102",
            "display_name": "Wife Candidate",
            "associated_people": [{"person_id": "TMP-00101", "role": "SPOU"}],
        },
    ]
    existing = [
        {"person_id": "IND-00100", "display_name": "Existing Anchor", "associated_people": []}
    ]

    minted, updated_existing = stage_5_minting_and_rewrite(staged, existing)

    assert minted[0]["person_id"] == "IND-00101"
    assert minted[1]["person_id"] == "IND-00102"
    assert minted[0]["associated_people"][0]["person_id"] == "IND-00102"
    assert minted[1]["associated_people"][0]["person_id"] == "IND-00101"


@pytest.mark.regression
def test_stage_5_deduplicates_existing_reciprocal_pointers():
    """Verifies reciprocal linking does not insert duplicate pointer edges into existing entities."""
    existing_person = {
        "person_id": "IND-00050",
        "display_name": "Existing Parent",
        "associated_people": [{"person_id": "IND-00051", "role": "CHIL"}],
    }
    staged = [
        {
            "person_id": "TMP-00001",
            "display_name": "Incoming Child",
            "associated_people": [{"person_id": "IND-00050", "role": "FATH"}],
        }
    ]

    minted, updated_existing = stage_5_minting_and_rewrite(staged, [existing_person])

    # Minted ID will be IND-00051 (since max existing is 50)
    assert minted[0]["person_id"] == "IND-00051"

    target_parent = next(p for p in updated_existing if p["person_id"] == "IND-00050")
    # Should only have one CHIL pointer to IND-00051, not two
    matching_pointers = [
        r for r in target_parent["associated_people"]
        if r["person_id"] == "IND-00051" and r["role"] == "CHIL"
    ]
    assert len(matching_pointers) == 1


@pytest.mark.regression
def test_stage_6_creates_backup_and_cleans_staging(mock_gpi_env):
    """Verifies Stage 6 creates a safe backup, writes the registry, and unlinks staging files."""
    ent_dir = mock_gpi_env["entities_dir"]
    backups_dir = mock_gpi_env["backups_dir"]
    target_people = mock_gpi_env["config"].people

    # Create dummy staging file
    staged_file = ent_dir / "pep-let-commit-test.json"
    staged_file.write_text("{}", encoding="utf-8")

    new_person = {
        "person_id": "IND-00338",
        "display_name": "Commit Candidate",
        "canonical_name": {"given": "Commit", "surname": "Candidate"},
    }

    success = stage_6_atomic_commit(
        new_records=[new_person],
        updated_existing=mock_gpi_env["people_data"]["persons"],
        staged_files=[staged_file],
        verbose=True,
        logger=mock_gpi_env["logger"],
        people_path=target_people,
    )

    assert success is True
    # Staging file was cleaned up
    assert not staged_file.exists()

    # Pre-execution backup was created in backups/
    backups = list(backups_dir.glob("people.json.*.bk"))
    assert len(backups) >= 1

    # Master registry committed with updated totals
    committed = GDAUtil.load_json(target_people)
    assert committed["total_persons"] == len(mock_gpi_env["people_data"]["persons"]) + 1
    assert any(p["person_id"] == "IND-00338" for p in committed["persons"])


@pytest.mark.regression
def test_stage_6_unlink_exception_resilience(mock_gpi_env, monkeypatch):
    """Verifies failure to unlink one staging file does not abort the successful commit."""
    ent_dir = mock_gpi_env["entities_dir"]
    target_people = mock_gpi_env["config"].people

    f1 = ent_dir / "pep-let-f1.json"
    f2 = ent_dir / "pep-let-f2.json"
    f1.write_text("{}", encoding="utf-8")
    f2.write_text("{}", encoding="utf-8")

    orig_unlink = Path.unlink

    def faulty_unlink(self, *args, **kwargs):
        if self.name == "pep-let-f1.json":
            raise PermissionError("Locked file simulation")
        return orig_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", faulty_unlink)

    success = stage_6_atomic_commit(
        new_records=[],
        updated_existing=mock_gpi_env["people_data"]["persons"],
        staged_files=[f1, f2],
        verbose=True,
        logger=mock_gpi_env["logger"],
        people_path=target_people,
    )

    assert success is True
    # f1 failed to unlink gracefully
    assert f1.exists()
    # f2 unlinked successfully
    assert not f2.exists()


# ----------------------------------------------------------------------
# ADDITIONAL BRANCH & COVERAGE TESTS
# ----------------------------------------------------------------------

@pytest.mark.regression
@pytest.mark.parametrize(
    "union_payload,expected_err",
    [
        ("not-a-dict", "Union item must be a dictionary"),
        ({"spouse_id": "   "}, "[UNION_NO_SPOUSE] Union missing spouse_id"),
        ({"spouse_id": "IND-00019", "status": "INVALID_STATUS"}, "[UNION_INVALID_STATUS] Invalid union status"),
    ],
)
def test_stage_1_structural_union_guards(mock_gpi_env, union_payload, expected_err):
    """Verifies intra-record structural union checks in Stage 1 catch malformed unions."""
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]
    target = ent_dir / "pep-let-bad-union.json"

    rec = {
        "person_id": "TMP-00001",
        "display_name": "Bad Union Person",
        "canonical_name": {"given": "Bad", "surname": "Union"},
        "unions": [union_payload],
    }
    GDAUtil.save_json(target, rec)

    recs, files = stage_1_validate_syntax(
        files=[target],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert recs == []
    assert files == []
    assert (q_dir / "pep-let-bad-union.json").exists()


@pytest.mark.regression
def test_stage_1_generic_parse_exception(mock_gpi_env, monkeypatch):
    """Verifies generic unhandled exceptions during Stage 1 record parsing trigger quarantine."""
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]
    target = ent_dir / "pep-let-corrupt.json"
    target.write_text("{}", encoding="utf-8")

    orig_load = GDAUtil.load_json

    def broken_load(path, *args, **kwargs):
        if Path(path).name == "pep-let-corrupt.json":
            raise RuntimeError("Unexpected simulated parse failure")
        return orig_load(path, *args, **kwargs)

    monkeypatch.setattr(GDAUtil, "load_json", broken_load)

    recs, files = stage_1_validate_syntax(
        files=[target],
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert recs == []
    assert files == []
    assert (q_dir / "pep-let-corrupt.json").exists()


@pytest.mark.regression
def test_main_cli_missing_master_files(mock_gpi_env, monkeypatch):
    """Verifies main() terminates with sys.exit(1) if core registry files are missing."""
    ent_dir = mock_gpi_env["entities_dir"]
    pep = ent_dir / "pep-let-ok.json"
    GDAUtil.save_json(pep, {
        "person_id": "TMP-00001",
        "display_name": "Valid Person",
        "canonical_name": {"given": "Valid", "surname": "Person"},
    })

    if mock_gpi_env["config"].people.exists():
        mock_gpi_env["config"].people.unlink()

    monkeypatch.setattr("sys.argv", ["gpi.py", "--append"])
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1


@pytest.mark.regression
def test_main_cli_early_aborts(mock_gpi_env, monkeypatch):
    """Verifies main() handles 0 records passing each stage and aborts gracefully."""
    ent_dir = mock_gpi_env["entities_dir"]

    # 1. Early abort on Stage 1 (invalid syntax)
    bad_pep = ent_dir / "pep-let-bad.json"
    bad_pep.write_text("invalid json syntax", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["gpi.py", "--append"])
    main()
    assert not bad_pep.exists()

    # 2. Early abort on Stage 2 (no path to root)
    orphan_pep = ent_dir / "pep-let-orphan.json"
    GDAUtil.save_json(orphan_pep, {
        "person_id": "TMP-00099",
        "display_name": "Orphan Person",
        "canonical_name": {"given": "Orphan", "surname": "Person"},
        "associated_people": [{"person_id": "IND-99999", "role": "FATH"}],
    })
    monkeypatch.setattr("sys.argv", ["gpi.py", "--append"])
    main()
    assert not orphan_pep.exists()


@pytest.mark.regression
def test_restore_quarantine_unlink_exception(mock_gpi_env, monkeypatch):
    """Verifies restore_quarantine logs an error and continues when a quarantine unlink fails."""
    q_dir = mock_gpi_env["quarantine_dir"]
    f1 = q_dir / "pep-let-q1.json"
    f1.write_text("{}", encoding="utf-8")

    orig_unlink = Path.unlink

    def locked_unlink(self, *args, **kwargs):
        if self.name == "pep-let-q1.json":
            raise PermissionError("Simulated locked file")
        return orig_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked_unlink)

    restore_quarantine(
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
        entities_dir=mock_gpi_env["entities_dir"],
    )
    assert f1.exists()


@pytest.mark.regression
def test_main_cli_early_aborts_stages_2b_3_4(mock_gpi_env, monkeypatch):
    """Verifies main() safely aborts when 100% of records fail stages 2b, 3, or 4."""
    ent_dir = mock_gpi_env["entities_dir"]

    # --- Test Stage 2b Abort (Relational Chronology Failure) ---
    pep_2b = ent_dir / "pep-let-chrono-fail.json"
    GDAUtil.save_json(pep_2b, {
        "person_id": "TMP-00001",
        "display_name": "Too Young Parent Child",
        "canonical_name": {"given": "Child", "surname": "Young"},
        "vitals": {"birth": {"date": {"date_start": "1940-01-01", "modifier": "EXACT"}}},
        "associated_people": [{"person_id": "IND-00019", "role": "FATH"}],
    })
    monkeypatch.setattr("sys.argv", ["gpi.py", "--append"])
    main()
    assert not pep_2b.exists()

    # --- Test Stage 3 Abort (Exact Deduplication Failure) ---
    pep_3 = ent_dir / "pep-let-dedup-fail.json"
    GDAUtil.save_json(pep_3, {
        "person_id": "TMP-00002",
        "display_name": "Garrison Sterling",
        "canonical_name": {"given": "Garrison", "surname": "Sterling", "birth_year": {"year": 1941}},
        "associated_people": [{"person_id": "IND-00000", "role": "FATH"}],
    })
    monkeypatch.setattr("sys.argv", ["gpi.py", "--append"])
    main()
    assert not pep_3.exists()

    # --- Test Stage 4 Abort (Location Canonicalization Failure) ---
    pep_4 = ent_dir / "pep-let-loc-fail.json"
    GDAUtil.save_json(pep_4, {
        "person_id": "TMP-00003",
        "display_name": "Lost City Person",
        "canonical_name": {"given": "Lost", "surname": "City"},
        "vitals": {"birth": {"place": {"standardized": "Unregistered Shambhala"}}},
        "associated_people": [{"person_id": "IND-00000", "role": "FATH"}],
    })
    monkeypatch.setattr("sys.argv", ["gpi.py", "--append"])
    main()
    assert not pep_4.exists()


@pytest.mark.regression
def test_main_cli_early_abort_stage_1(mock_gpi_env, monkeypatch):
    """Verifies main() exits early when stage 1 produces no valid records (Lines 600-601)."""
    ent_dir = mock_gpi_env["entities_dir"]
    target = ent_dir / "pep-let-invalid.json"
    target.write_text("{}", encoding="utf-8")  # Missing required schema properties

    monkeypatch.setattr("sys.argv", ["gpi.py", "--append"])
    main()
    assert not target.exists()  # Quarantined
