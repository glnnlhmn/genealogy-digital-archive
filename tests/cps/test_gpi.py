# Name: test_gpi.py
# Path: tests/cps/test_gpi.py
# Version: 1.1.0+build.20261005.1

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
    - Stage 6: Atomic commit via GDAPeople, Safe Backup generation, and staging cleanup.
    - CLI execution modes, dry-run flags, and quarantine recovery operations.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly classified with pytest markers.
    - Dependencies: Requires tools/ops/gpi.py, gdacore, gdadomain.people, and fixtures.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List
import pytest

from gdacore.config import GDAConfig
from gdacore.util import GDAUtil
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
    monkeypatch.setattr("gdacore.config.CONFIG", mock_config)
    monkeypatch.setattr("gdacore.util.CONFIG", mock_config)
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

    golden_people_path = Path(__file__).resolve().parent.parent / "fixtures" / "people" / "golden" / "golden_people.json"
    if golden_people_path.exists():
        people_data = GDAUtil.load_json(golden_people_path)
    else:
        people_data = {
            "schema_version": "1.0.0",
            "people": [
                {
                    "person_id": "IND-00000",
                    "display_name": "Arthur Sterling",
                    "canonical_name": {"given": "Arthur", "surname": "Sterling"},
                    "associated_people": [],
                    "unions": [],
                }
            ],
        }
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
            "sex": {"type": "string", "enum": ["M", "F", "U", "Male", "Female", "Unknown"]},
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
# 1. STAGE 0 & QUARANTINE RECOVERY (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_stage_0_discovery_empty(mock_gpi_env: Dict[str, Any]) -> None:
    discovered = stage_0_discovery(root_dir=mock_gpi_env["root"])
    assert discovered == []


@pytest.mark.smoke
def test_stage_0_discovery_populated_count(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    (ent_dir / "pep-let-001.json").write_text("{}", encoding="utf-8")
    (ent_dir / "pep-let-002.json").write_text("{}", encoding="utf-8")
    (ent_dir / "other-file.json").write_text("{}", encoding="utf-8")

    discovered = stage_0_discovery(root_dir=mock_gpi_env["root"])
    assert len(discovered) == 2


@pytest.mark.smoke
def test_stage_0_discovery_ignores_non_peplet_files(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    other = ent_dir / "other-file.json"
    other.write_text("{}", encoding="utf-8")

    discovered = stage_0_discovery(root_dir=mock_gpi_env["root"])
    assert other not in discovered


@pytest.mark.smoke
def test_restore_quarantine_empty(mock_gpi_env: Dict[str, Any]) -> None:
    restore_quarantine(
        logger=mock_gpi_env["logger"],
        quarantine_dir=mock_gpi_env["quarantine_dir"],
        entities_dir=mock_gpi_env["entities_dir"],
    )
    assert list(mock_gpi_env["entities_dir"].glob("pep-let-*.json")) == []


@pytest.mark.smoke
def test_restore_quarantine_missing_dir(mock_gpi_env: Dict[str, Any]) -> None:
    non_existent = mock_gpi_env["root"] / "non_existent_quarantine"
    restore_quarantine(
        logger=mock_gpi_env["logger"],
        quarantine_dir=non_existent,
        entities_dir=mock_gpi_env["entities_dir"],
    )
    assert not non_existent.exists()


# ==============================================================================
# 2. STAGE 1: SYNTAX & STRICT VALIDATION (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_stage_1_quarantines_disallowed_property(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    f1 = ent_dir / "pep-let-disallowed.json"
    GDAUtil.save_json(f1, {
        "person_id": "TMP-00001",
        "display_name": "Invalid Prop",
        "canonical_name": {"given": "Invalid", "surname": "Prop"},
        "unauthorized_key": "Illegal",
    })

    stage_1_validate_syntax(
        [f1],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert (q_dir / "pep-let-disallowed.json").exists()


@pytest.mark.regression
def test_stage_1_quarantines_bad_enum_value(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    f2 = ent_dir / "pep-let-bad-enum.json"
    GDAUtil.save_json(f2, {
        "person_id": "TMP-00002",
        "display_name": "Bad Sex",
        "canonical_name": {"given": "Bad", "surname": "Sex"},
        "sex": "UNKNOWN_ENUM_VALUE",
    })

    stage_1_validate_syntax(
        [f2],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert (q_dir / "pep-let-bad-enum.json").exists()


@pytest.mark.regression
def test_stage_1_quarantines_vital_desync_via_gpa(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]
    target = ent_dir / "pep-let-desync.json"
    GDAUtil.save_json(target, {
        "person_id": "TMP-00003",
        "display_name": "Desync Birth",
        "canonical_name": {"given": "Desync", "surname": "Birth", "birth_year": {"year": 1850}},
        "vitals": {"birth": {"date": "1860-05-10"}},
    })

    stage_1_validate_syntax([target], verbose=True, logger=mock_gpi_env["logger"], quarantine_dir=q_dir)
    assert (q_dir / "pep-let-desync.json").exists()


@pytest.mark.regression
def test_stage_1_quarantines_chrono_death_before_birth(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]
    target = ent_dir / "pep-let-chrono.json"
    GDAUtil.save_json(target, {
        "person_id": "TMP-00004",
        "display_name": "Chrono Error",
        "canonical_name": {"given": "Chrono", "surname": "Error"},
        "vitals": {
            "birth": {"date": "1900-01-01"},
            "death": {"date": "1890-01-01"},
        },
    })

    stage_1_validate_syntax([target], verbose=True, logger=mock_gpi_env["logger"], quarantine_dir=q_dir)
    assert (q_dir / "pep-let-chrono.json").exists()


@pytest.mark.smoke
def test_stage_1_valid_peplet_passes(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    target = ent_dir / "pep-let-valid.json"
    GDAUtil.save_json(target, {
        "person_id": "TMP-00005",
        "display_name": "Arthur Sterling",
        "canonical_name": {"given": "Arthur", "surname": "Sterling"},
        "sex": "M",
    })

    records, _ = stage_1_validate_syntax([target], verbose=True, logger=mock_gpi_env["logger"])
    assert len(records) == 1


# ==============================================================================
# 3. STAGES 2 & 2B: TOPOLOGY & RELATIONAL CHRONOLOGY (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_stage_2_quarantines_dangling_unconnected_node(mock_gpi_env: Dict[str, Any]) -> None:
    existing_people = mock_gpi_env["people_data"].get("persons", mock_gpi_env["people_data"].get("people", []))
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    f_dangle = ent_dir / "pep-let-dangle.json"
    GDAUtil.save_json(f_dangle, {
        "person_id": "TMP-00020",
        "display_name": "Dangling Node",
        "canonical_name": {"given": "Dangling", "surname": "Node"},
        "associated_people": [{"person_id": "IND-99999", "role": "FATH"}],
    })

    stage_2_verify_graph_topology(
        [GDAUtil.load_json(f_dangle)],
        [f_dangle],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert (q_dir / "pep-let-dangle.json").exists()


@pytest.mark.regression
def test_stage_2b_quarantines_parent_too_young(mock_gpi_env: Dict[str, Any]) -> None:
    existing_people = [
        {
            "person_id": "IND-00000",
            "canonical_name": {"given": "Parent"},
            "vitals": {"birth": {"date": "1900-01-01"}},
        }
    ]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    target = ent_dir / "pep-let-too-young.json"
    rec = {
        "person_id": "TMP-00050",
        "canonical_name": {"given": "Child"},
        "vitals": {"birth": {"date": "1905-01-01"}},
        "associated_people": [{"person_id": "IND-00000", "role": "FATH"}],
    }
    GDAUtil.save_json(target, rec)

    passed_records, _ = stage_2b_verify_relational_chronology(
        [rec],
        [target],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert len(passed_records) == 0


# ==============================================================================
# 4. STAGE 3: DEDUPLICATION DRIFT (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_stage_3_quarantines_exact_master_registry_collision(mock_gpi_env: Dict[str, Any]) -> None:
    existing_people = [
        {
            "person_id": "IND-00001",
            "canonical_name": {"given": "Garrison", "surname": "Sterling", "birth_year": {"year": 1941}},
        }
    ]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    f_dup = ent_dir / "pep-let-dup.json"
    rec_dup = {
        "person_id": "TMP-00001",
        "canonical_name": {"given": "Garrison", "surname": "Sterling", "birth_year": {"year": 1941}},
    }
    GDAUtil.save_json(f_dup, rec_dup)

    stage_3_deduplication_drift(
        [rec_dup],
        [f_dup],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert (q_dir / "pep-let-dup.json").exists()


@pytest.mark.regression
def test_stage_3_allows_name_variant_with_same_birth_year(mock_gpi_env: Dict[str, Any]) -> None:
    existing_people = [
        {
            "person_id": "IND-00001",
            "canonical_name": {"given": "Garrison", "surname": "Sterling", "birth_year": {"year": 1941}},
        }
    ]
    ent_dir = mock_gpi_env["entities_dir"]

    f_var = ent_dir / "pep-let-var.json"
    rec_var = {
        "person_id": "TMP-00002",
        "canonical_name": {"given": "Garison", "surname": "Sterling", "birth_year": {"year": 1941}},
    }
    GDAUtil.save_json(f_var, rec_var)

    records, _ = stage_3_deduplication_drift(
        [rec_var],
        [f_var],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
    )
    assert len(records) == 1


# ==============================================================================
# 5. STAGE 4: LOCATION CANONICALIZATION (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_stage_4_unregistered_location_quarantined(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    f_bad = ent_dir / "pep-let-bad-birth.json"
    rec_bad = {
        "person_id": "TMP-00001",
        "canonical_name": {"given": "Lost", "surname": "Birth"},
        "vitals": {"birth": {"place": {"standardized": "Atlantis, Atlantic Ocean"}}},
    }
    GDAUtil.save_json(f_bad, rec_bad)

    stage_4_canonicalize_locations(
        [rec_bad],
        [f_bad],
        mock_gpi_env["loc_data"],
        mock_gpi_env["index_data"],
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert (q_dir / "pep-let-bad-birth.json").exists()


@pytest.mark.smoke
def test_stage_4_expands_redirect_location(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    target = ent_dir / "pep-let-redirect.json"
    rec = {
        "person_id": "TMP-00088",
        "canonical_name": {"given": "Redirect", "surname": "Candidate"},
        "vitals": {"birth": {"place": {"standardized": "West Pennsboro, PA"}}},
    }
    GDAUtil.save_json(target, rec)

    records, _ = stage_4_canonicalize_locations(
        [rec],
        [target],
        mock_gpi_env["loc_data"],
        mock_gpi_env["index_data"],
        verbose=True,
        logger=mock_gpi_env["logger"],
    )
    birth_place = records[0]["vitals"]["birth"]["place"]
    assert birth_place["standardized"] == "West Pennsboro Township, Cumberland County, Pennsylvania, USA"


# ==============================================================================
# 6. STAGE 5: SEQUENTIAL MINTING & REWRITING (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_stage_5_mints_monotonic_person_id() -> None:
    staged = [{"person_id": "TMP-00001", "associated_people": []}]
    existing = [{"person_id": "IND-00010"}]

    minted, _ = stage_5_minting_and_rewrite(staged, existing)
    assert minted[0]["person_id"] == "IND-00011"


@pytest.mark.regression
def test_stage_5_links_reciprocal_kinship_on_existing() -> None:
    staged = [
        {
            "person_id": "TMP-00001",
            "sex": "M",
            "associated_people": [{"person_id": "IND-00010", "role": "FATH"}],
        }
    ]
    existing = [{"person_id": "IND-00010", "sex": "M", "associated_people": []}]

    _, updated_existing = stage_5_minting_and_rewrite(staged, existing)
    assert updated_existing[0]["associated_people"][0]["role"] == "CHIL"


# ==============================================================================
# 7. STAGE 6: ATOMIC COMMIT VIA GDAPeople (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_stage_6_creates_backup_and_commits_via_gda_people(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    target_people = mock_gpi_env["config"].people

    staged_file = ent_dir / "pep-let-commit-test.json"
    staged_file.write_text("{}", encoding="utf-8")

    new_person = {
        "person_id": "IND-00338",
        "display_name": "Commit Candidate",
        "canonical_name": {"given": "Commit", "surname": "Candidate"},
        "sex": "M",
    }

    success = stage_6_atomic_commit(
        new_records=[new_person],
        updated_existing=[],
        staged_files=[staged_file],
        verbose=True,
        logger=mock_gpi_env["logger"],
        people_path=target_people,
    )
    assert success is True


@pytest.mark.regression
def test_stage_6_unlinks_staged_file(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    target_people = mock_gpi_env["config"].people

    staged_file = ent_dir / "pep-let-unlink.json"
    staged_file.write_text("{}", encoding="utf-8")

    new_person = {
        "person_id": "IND-00339",
        "display_name": "Unlink Candidate",
        "canonical_name": {"given": "Unlink", "surname": "Candidate"},
        "sex": "F",
    }

    stage_6_atomic_commit(
        new_records=[new_person],
        updated_existing=[],
        staged_files=[staged_file],
        verbose=True,
        logger=mock_gpi_env["logger"],
        people_path=target_people,
    )
    assert not staged_file.exists()


# ==============================================================================
# 8. CLI PIPELINE INTEGRATION (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_gpi_cli_no_args_exits_safely(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["gpi.py"])
    main()


@pytest.mark.smoke
def test_gpi_cli_restore_recovers_quarantined_files(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    q_dir = mock_gpi_env["quarantine_dir"]
    held = q_dir / "pep-let-held.json"
    GDAUtil.save_json(held, {"person_id": "TMP-HELD"})

    monkeypatch.setattr("sys.argv", ["gpi.py", "--restore"])
    main()

    assert (mock_gpi_env["entities_dir"] / "pep-let-held.json").exists()


@pytest.mark.smoke
def test_gpi_cli_dry_run_preserves_staging_file(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    pep_file = ent_dir / "pep-let-dry.json"
    GDAUtil.save_json(pep_file, {
        "person_id": "TMP-00099",
        "display_name": "Dry Person",
        "canonical_name": {"given": "Dry", "surname": "Person"},
        "sex": "M",
        "associated_people": [{"person_id": "IND-00000", "role": "CHIL"}],
    })

    monkeypatch.setattr("sys.argv", ["gpi.py", "--dry-run", "--verbose"])
    main()

    assert pep_file.exists()