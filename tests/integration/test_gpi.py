# Name: test_gpi.py
# Path: tests/integration/test_gpi.py
# Version: 1.0.1+build.20260927.01

"""Comprehensive test harness for GPI (Genealogy Person Intake Pipeline).

Operational Role:
    Validates the 7-stage state machine for staging entity intake:
    - Stage 0: Staging discovery pattern matching (pep-let-*.json).
    - Stage 1: Syntax and strict schema conformance (disallowed props, vital sync).
    - Stage 2: Topological graph reachability and path-to-root validation.
    - Stage 2b: Inter-record relational chronology checks (parent age boundaries).
    - Stage 3: Deduplication drift and master registry collision detection.
    - Stage 4: Canonical location resolution, redirects, and detail expansion.
    - Stage 5: Sequential identifier minting and reciprocal relation rewrites.
    - Stage 6: Atomic commit, Safe Backup generation, and staging cleanup.
    - CLI execution modes, flags, and quarantine recovery operations.

Test Structure & Protocol:
    - Atomized tests: Fine-grained tests for each pipeline stage, quarantine
      condition, and batch ingestion assertion.
    - Fully decorated: Classified with @pytest.mark.integration, @pytest.mark.smoke,
      @pytest.mark.regression, and @pytest.mark.burnin.
    - Dependencies: Requires tools/ops/gpi.py, GDAConfig, GDAUtil, golden_people.json,
      and tests/fixtures/peplets/.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List
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

pytestmark = pytest.mark.integration

PEPLET_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "peplets"
PEPLET_GOLDEN_DIR = PEPLET_FIXTURES_DIR / "golden"
PEPLET_FAILURES_DIR = PEPLET_FIXTURES_DIR / "failures"


@pytest.fixture
def mock_gpi_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
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

    golden_people_path = Path(
        __file__).resolve().parent.parent / "fixtures" / "people" / "golden" / "golden_people.json"
    people_data = GDAUtil.load_json(golden_people_path)
    GDAUtil.save_json(mock_config.people, people_data)

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
# 1. STAGE 0 & QUARANTINE RECOVERY
# ==============================================================================

@pytest.mark.smoke
def test_stage_0_discovery_empty(mock_gpi_env: Dict[str, Any]) -> None:
    """Verifies discovery on an empty directory returns an empty list."""
    discovered = stage_0_discovery(root_dir=mock_gpi_env["root"])
    assert discovered == []


@pytest.mark.smoke
def test_stage_0_discovery_populated(mock_gpi_env: Dict[str, Any]) -> None:
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
def test_restore_quarantine_empty(mock_gpi_env: Dict[str, Any]) -> None:
    """Verifies restore_quarantine exits gracefully when directory is empty."""
    restore_quarantine(
        logger=mock_gpi_env["logger"],
        quarantine_dir=mock_gpi_env["quarantine_dir"],
        entities_dir=mock_gpi_env["entities_dir"],
    )
    assert list(mock_gpi_env["entities_dir"].glob("pep-let-*.json")) == []


@pytest.mark.smoke
def test_restore_quarantine_missing_dir(mock_gpi_env: Dict[str, Any]) -> None:
    """Verifies restore_quarantine handles non-existent quarantine path."""
    non_existent = mock_gpi_env["root"] / "non_existent_quarantine"
    restore_quarantine(
        logger=mock_gpi_env["logger"],
        quarantine_dir=non_existent,
        entities_dir=mock_gpi_env["entities_dir"],
    )
    assert not non_existent.exists()


# ==============================================================================
# 2. STAGE 1: SYNTAX & STRICT VALIDATION
# ==============================================================================

@pytest.mark.regression
def test_stage_1_disallowed_properties_and_enums(mock_gpi_env: Dict[str, Any]) -> None:
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
def test_stage_1_quarantines_vital_desync_via_gpa(mock_gpi_env: Dict[str, Any]) -> None:
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
def test_stage_1_quarantines_chrono_death_before_birth(mock_gpi_env: Dict[str, Any]) -> None:
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
def test_stage_1_quarantines_malformed_location_object(mock_gpi_env: Dict[str, Any]) -> None:
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
def test_stage_1_golden_valid_peplet_passes(mock_gpi_env: Dict[str, Any]) -> None:
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
# 3. STAGES 2 & 2B: TOPOLOGY & RELATIONAL CHRONOLOGY
# ==============================================================================

@pytest.mark.regression
def test_stage_2_self_referential_and_dangling_loops(mock_gpi_env: Dict[str, Any]) -> None:
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
def test_stage_2b_quarantines_parent_too_young(mock_gpi_env: Dict[str, Any]) -> None:
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


@pytest.mark.burnin
def test_stage_2_deep_five_generation_topology(mock_gpi_env: Dict[str, Any]) -> None:
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


# ==============================================================================
# 4. STAGE 3: DEDUPLICATION DRIFT
# ==============================================================================

@pytest.mark.regression
def test_stage_3_phonetic_variants_pass_fingerprint(mock_gpi_env: Dict[str, Any]) -> None:
    """Verifies similar names pass deduplication while exact fingerprints collide."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    f_dup = ent_dir / "pep-let-dup.json"
    rec_dup = {
        "person_id": "TMP-00001",
        "display_name": "Garrison Sterling",
        "canonical_name": {"given": "Garrison", "surname": "Sterling", "birth_year": {"year": 1941}},
    }
    GDAUtil.save_json(f_dup, rec_dup)

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
def test_stage_3_quarantines_exact_master_registry_collision(mock_gpi_env: Dict[str, Any]) -> None:
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
def test_stage_3_quarantines_intra_batch_duplicate(mock_gpi_env: Dict[str, Any]) -> None:
    """Verifies Stage 3 accepts first instance and quarantines second identical intra-batch pep-let."""
    existing_people = mock_gpi_env["people_data"]["persons"]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    src_fixture = PEPLET_FAILURES_DIR / "fail-dedup-intra-batch-collision.json"
    target1 = ent_dir / "pep-let-batch-1.json"
    target2 = ent_dir / "pep-let-batch-2.json"

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


# ==============================================================================
# 5. STAGE 4: LOCATION CANONICALIZATION
# ==============================================================================

@pytest.mark.regression
def test_stage_4_unregistered_location_quarantine(mock_gpi_env: Dict[str, Any]) -> None:
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
def test_stage_4_expands_redirect_and_populates_details(mock_gpi_env: Dict[str, Any]) -> None:
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


# ==============================================================================
# 6. STAGE 5: SEQUENTIAL MINTING & REWRITING
# ==============================================================================

@pytest.mark.burnin
def test_stage_5_minting_multi_reciprocal_rewrite() -> None:
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


@pytest.mark.regression
def test_stage_5_intra_batch_mutual_rewrite() -> None:
    """Verifies temporary ID references between entities in same batch resolve to minted IDs."""
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
def test_stage_5_deduplicates_existing_reciprocal_pointers() -> None:
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
    assert minted[0]["person_id"] == "IND-00051"
    target_parent = next(p for p in updated_existing if p["person_id"] == "IND-00050")
    matching_pointers = [
        r for r in target_parent["associated_people"]
        if r["person_id"] == "IND-00051" and r["role"] == "CHIL"
    ]
    assert len(matching_pointers) == 1


# ==============================================================================
# 7. STAGE 6: ATOMIC COMMIT & SAFE BACKUP
# ==============================================================================

@pytest.mark.regression
def test_stage_6_creates_backup_and_cleans_staging(mock_gpi_env: Dict[str, Any]) -> None:
    """Verifies Stage 6 creates a safe backup, writes the registry, and unlinks staging files."""
    ent_dir = mock_gpi_env["entities_dir"]
    backups_dir = mock_gpi_env["backups_dir"]
    target_people = mock_gpi_env["config"].people

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
    assert not staged_file.exists()

    backups = list(backups_dir.glob("people.json.*.bk"))
    assert len(backups) >= 1

    committed = GDAUtil.load_json(target_people)
    assert committed["total_persons"] == len(mock_gpi_env["people_data"]["persons"]) + 1
    assert any(p["person_id"] == "IND-00338" for p in committed["persons"])


# ==============================================================================
# 8. MULTI-PEPLET GOLDEN BATCH ATOMIZED VERIFICATION
# ==============================================================================

@pytest.fixture
def executed_golden_batch_env(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Stages and executes the 10 golden pep-lets through the append pipeline."""
    ent_dir = mock_gpi_env["entities_dir"]
    golden_files = sorted(PEPLET_GOLDEN_DIR.glob("pep-let-*.json"))
    assert len(golden_files) == 10, f"Expected 10 golden peplets, found {len(golden_files)}"

    for gf in golden_files:
        target = ent_dir / gf.name
        target.write_text(gf.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["gpi.py", "--append", "--verbose"])
    main()

    registry = GDAUtil.load_json(mock_gpi_env["config"].people)
    return {
        "env": mock_gpi_env,
        "registry": registry,
        "quarantined": list(mock_gpi_env["quarantine_dir"].glob("*.json")),
        "remaining": list(ent_dir.glob("pep-let-*.json")),
    }


@pytest.mark.smoke
def test_all_ten_golden_peplets_ingestion_and_cleanup(executed_golden_batch_env: Dict[str, Any]) -> None:
    """Verifies that all 10 golden pep-lets processed with zero quarantines and staging unlinked."""
    assert executed_golden_batch_env["quarantined"] == []
    assert executed_golden_batch_env["remaining"] == []


@pytest.mark.smoke
def test_all_ten_golden_peplets_registry_totals(executed_golden_batch_env: Dict[str, Any]) -> None:
    """Verifies master people registry count updated from 62 to 72 persons."""
    registry = executed_golden_batch_env["registry"]
    assert registry["total_persons"] == 72
    assert len(registry["persons"]) == 72


@pytest.mark.smoke
def test_all_ten_golden_peplets_minted_id_sequence(executed_golden_batch_env: Dict[str, Any]) -> None:
    """Verifies all 10 minted IDs (IND-00338 through IND-00347) exist in master registry."""
    existing_ids = {p["person_id"] for p in executed_golden_batch_env["registry"]["persons"]}
    minted_ids = [f"IND-{idx:05d}" for idx in range(338, 348)]
    for mid in minted_ids:
        assert mid in existing_ids, f"Minted ID {mid} missing from committed registry"


@pytest.mark.smoke
def test_all_ten_golden_peplets_reciprocal_linkages(executed_golden_batch_env: Dict[str, Any]) -> None:
    """Verifies reciprocal kinship linkages established on root IND-00000."""
    registry = executed_golden_batch_env["registry"]
    arthur = next(p for p in registry["persons"] if p["person_id"] == "IND-00000")
    assoc_ids = {a["person_id"] for a in arthur.get("associated_people", [])}
    assert "IND-00338" in assoc_ids


# ==============================================================================
# 9. CLI PIPELINE INTEGRATION
# ==============================================================================

@pytest.mark.smoke
def test_gpi_cli_no_args_exits_safely(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies running GPI without operation mode warns and exits safely."""
    monkeypatch.setattr("sys.argv", ["gpi.py"])
    main()


@pytest.mark.smoke
def test_gpi_cli_restore_pipeline(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies running main() with --restore moves quarantined files back to entities/."""
    q_dir = mock_gpi_env["quarantine_dir"]
    held = q_dir / "pep-let-held.json"
    GDAUtil.save_json(held, {"person_id": "TMP-HELD"})

    monkeypatch.setattr("sys.argv", ["gpi.py", "--restore"])
    main()

    assert not held.exists()
    assert (mock_gpi_env["entities_dir"] / "pep-let-held.json").exists()


@pytest.mark.smoke
def test_gpi_cli_append_pipeline(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
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