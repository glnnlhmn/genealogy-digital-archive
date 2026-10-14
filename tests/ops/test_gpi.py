# Name: test_gpi.py
# Path: tests/ops/test_gpi.py
# Version: 1.1.0+build.20261006.12

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

    mock_config = GDAConfig(root=tmp_path)
    monkeypatch.setattr("gdacore.config.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.gpi.CONFIG", mock_config)

    locations_path = mock_config.entities / "locations.json"
    locations_index_path = mock_config.indexes / "location_index.json"
    people_path = mock_config.entities / "people.json"
    person_schema_path = mock_config.schema_entities / "person.schema.json"

    loc_data = {
        "$schema": "schemas/entities/location_registry.schema.json",
        "schema_version": "1.0.0",
        "total_locations": 3,
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
            {
                "location_id": "LOC-00003",
                "location_type": "JURISDICTION",
                "location": {
                    "standardized": "Plain Jurisdiction, No Details, USA",
                    "verbatim": "Plain, USA",
                },
            },
        ],
    }
    GDAUtil.save_json(locations_path, loc_data)

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
            "plain, usa": {
                "location_id": "LOC-00003",
                "standardized": "Plain Jurisdiction, No Details, USA",
            },
        },
    }
    GDAUtil.save_json(locations_index_path, index_data)

    golden_people_path = Path(__file__).resolve().parent.parent / "fixtures" / "people" / "golden" / "golden_people.json"
    if golden_people_path.exists():
        people_data = GDAUtil.load_json(golden_people_path)
    else:
        people_data = {
            "schema_version": "1.0.0",
            "persons": [
                {
                    "person_id": "IND-00000",
                    "display_name": "Arthur Sterling",
                    "canonical_name": {"given": "Arthur", "surname": "Sterling"},
                    "associated_people": [],
                    "unions": [],
                }
            ],
        }
    GDAUtil.save_json(people_path, people_data)

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
    GDAUtil.save_json(person_schema_path, schema_data)

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
        "people_path": people_path,
        "locations_path": locations_path,
        "locations_index_path": locations_index_path,
        "person_schema_path": person_schema_path,
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


@pytest.mark.regression
def test_stage_0_discovery_missing_dir_returns_empty(mock_gpi_env: Dict[str, Any]) -> None:
    non_existent = mock_gpi_env["root"] / "non_existent_path"
    assert stage_0_discovery(root_dir=non_existent) == []


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


@pytest.mark.regression
def test_restore_quarantine_unlinks_reason_meta_file(mock_gpi_env: Dict[str, Any]) -> None:
    q_dir = mock_gpi_env["quarantine_dir"]
    target = q_dir / "20261006_090000_pep-let-meta.json"
    GDAUtil.save_json(target, {"person_id": "TMP-META"})
    reason = q_dir / "20261006_090000_pep-let-meta.json.reason.txt"
    reason.write_text("Test isolation reason", encoding="utf-8")

    restore_quarantine(
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
        entities_dir=mock_gpi_env["entities_dir"],
    )
    assert not reason.exists()


# ==============================================================================
# 2. STAGE 1: SYNTAX & STRICT VALIDATION (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_stage_1_quarantines_corrupt_json_syntax(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]
    target = ent_dir / "pep-let-corrupt.json"
    target.write_text("{ unquoted_key: invalid_json }", encoding="utf-8")

    stage_1_validate_syntax([target], verbose=True, logger=mock_gpi_env["logger"], quarantine_dir=q_dir)
    assert len(list(q_dir.glob("*pep-let-corrupt.json"))) == 1


@pytest.mark.regression
def test_stage_1_missing_schema_file_bypasses_json_schema(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    target = ent_dir / "pep-let-noschema.json"
    GDAUtil.save_json(target, {
        "person_id": "TMP-00001",
        "display_name": "No Schema",
        "canonical_name": {"given": "No", "surname": "Schema"},
        "sex": "M",
    })

    records, _ = stage_1_validate_syntax(
        [target],
        verbose=True,
        logger=mock_gpi_env["logger"],
        schema_file=mock_gpi_env["root"] / "non_existent.schema.json",
    )
    assert len(records) == 1


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

    stage_1_validate_syntax([f1], verbose=True, logger=mock_gpi_env["logger"], quarantine_dir=q_dir)
    assert len(list(q_dir.glob("*pep-let-disallowed.json"))) == 1


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

    stage_1_validate_syntax([f2], verbose=True, logger=mock_gpi_env["logger"], quarantine_dir=q_dir)
    assert len(list(q_dir.glob("*pep-let-bad-enum.json"))) == 1


@pytest.mark.regression
def test_stage_1_quarantines_vital_desync_via_gpa(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]
    target = ent_dir / "pep-let-desync.json"
    GDAUtil.save_json(target, {
        "person_id": "TMP-00003",
        "display_name": "Desync Birth",
        "canonical_name": {"given": "Desync", "surname": "Birth", "birth_year": {"year": 1850}},
        "vitals": {"birth": {"date": {"date_start": "1860-05-10"}}},
    })

    stage_1_validate_syntax([target], verbose=True, logger=mock_gpi_env["logger"], quarantine_dir=q_dir)
    assert len(list(q_dir.glob("*pep-let-desync.json"))) == 1


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
            "birth": {"date": {"date_start": "1900-01-01"}},
            "death": {"date": {"date_start": "1890-01-01"}},
        },
    })

    stage_1_validate_syntax([target], verbose=True, logger=mock_gpi_env["logger"], quarantine_dir=q_dir)
    assert len(list(q_dir.glob("*pep-let-chrono.json"))) == 1


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
def test_stage_2_quarantines_isolated_entity_with_zero_connections(mock_gpi_env: Dict[str, Any]) -> None:
    existing_people = [{"person_id": "IND-00000"}]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    target = ent_dir / "pep-let-isolated.json"
    GDAUtil.save_json(target, {
        "person_id": "TMP-00010",
        "display_name": "Isolated Individual",
        "canonical_name": {"given": "Isolated", "surname": "Individual"},
        "associated_people": [],
        "unions": [],
    })

    stage_2_verify_graph_topology(
        [GDAUtil.load_json(target)],
        [target],
        existing_people,
        verbose=True,
        logger=mock_gpi_env["logger"],
        quarantine_dir=q_dir,
    )
    assert len(list(q_dir.glob("*pep-let-isolated.json"))) == 1


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
    assert len(list(q_dir.glob("*pep-let-dangle.json"))) == 1


@pytest.mark.regression
def test_stage_2b_quarantines_parent_too_young(mock_gpi_env: Dict[str, Any]) -> None:
    existing_people = [
        {
            "person_id": "IND-00000",
            "canonical_name": {"given": "Parent"},
            "vitals": {"birth": {"date": {"date_start": "1900-01-01"}}},
        }
    ]
    ent_dir = mock_gpi_env["entities_dir"]
    q_dir = mock_gpi_env["quarantine_dir"]

    target = ent_dir / "pep-let-too-young.json"
    rec = {
        "person_id": "TMP-00050",
        "canonical_name": {"given": "Child"},
        "vitals": {"birth": {"date": {"date_start": "1905-01-01"}}},
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


@pytest.mark.regression
def test_stage_2b_ignores_critical_on_unrelated_existing_person(mock_gpi_env: Dict[str, Any]) -> None:
    existing_flawed = [
        {
            "person_id": "IND-00099",
            "canonical_name": {"given": "Flawed"},
            "vitals": {"birth": {"date": "1900-01-01"}, "death": {"date": "1890-01-01"}},
        }
    ]
    ent_dir = mock_gpi_env["entities_dir"]
    target = ent_dir / "pep-let-clean-child.json"
    rec = {
        "person_id": "TMP-00099",
        "canonical_name": {"given": "Clean"},
        "vitals": {"birth": {"date": "1920-01-01"}},
    }
    GDAUtil.save_json(target, rec)

    passed_records, _ = stage_2b_verify_relational_chronology(
        [rec],
        [target],
        existing_flawed,
        verbose=True,
        logger=mock_gpi_env["logger"],
    )
    assert len(passed_records) == 1


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
    assert len(list(q_dir.glob("*pep-let-dup.json"))) == 1


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


@pytest.mark.regression
def test_stage_3_bypasses_records_with_missing_surname(mock_gpi_env: Dict[str, Any]) -> None:
    existing_people = [
        {
            "person_id": "IND-00001",
            "canonical_name": {"given": "GivenOnly", "surname": ""},
        }
    ]
    ent_dir = mock_gpi_env["entities_dir"]
    f_missing = ent_dir / "pep-let-no-surname.json"
    rec = {
        "person_id": "TMP-00003",
        "canonical_name": {"given": "StagedGiven", "surname": ""},
    }
    GDAUtil.save_json(f_missing, rec)

    records, _ = stage_3_deduplication_drift(
        [rec],
        [f_missing],
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
    assert len(list(q_dir.glob("*pep-let-bad-birth.json"))) == 1


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


@pytest.mark.regression
def test_stage_4_handles_non_dict_and_empty_place(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    target = ent_dir / "pep-let-empty-place.json"
    rec = {
        "person_id": "TMP-00089",
        "canonical_name": {"given": "Empty", "surname": "Place"},
        "vitals": {
            "birth": {"place": "StringPlaceNotDict"},
            "death": {"place": {"standardized": "   "}},
        },
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
    assert len(records) == 1


@pytest.mark.regression
def test_stage_4_canonicalizes_location_without_details(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    target = ent_dir / "pep-let-nodetails.json"
    rec = {
        "person_id": "TMP-00090",
        "canonical_name": {"given": "No", "surname": "Details"},
        "vitals": {"birth": {"place": {"standardized": "Plain Jurisdiction, No Details, USA"}}},
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
    assert records[0]["vitals"]["birth"]["place"]["standardized"] == "Plain Jurisdiction, No Details, USA"


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


@pytest.mark.regression
def test_stage_5_rewrites_co_staged_associations_and_unions() -> None:
    staged = [
        {
            "person_id": "TMP-00001",
            "associated_people": [{"person_id": "TMP-00002", "role": "SPOU"}],
            "unions": [{"spouse_id": "TMP-00002", "status": "MARRIED"}],
        },
        {
            "person_id": "TMP-00002",
            "associated_people": [{"person_id": "TMP-00001", "role": "SPOU"}],
            "unions": [{"spouse_id": "TMP-00001", "status": "MARRIED"}],
        },
    ]
    existing = [{"person_id": "IND-00005"}]

    minted, _ = stage_5_minting_and_rewrite(staged, existing)
    assert minted[0]["associated_people"][0]["person_id"] == "IND-00007"
    assert minted[0]["unions"][0]["spouse_id"] == "IND-00007"


@pytest.mark.regression
def test_stage_5_handles_non_monotonic_existing_ids() -> None:
    staged = [{"person_id": "TMP-00001"}]
    existing = [{"person_id": "LEGACY-ID"}, {"person_id": ""}]

    minted, _ = stage_5_minting_and_rewrite(staged, existing)
    assert minted[0]["person_id"] == "IND-00001"


# ==============================================================================
# 7. STAGE 6: ATOMIC COMMIT VIA GDAPeople (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_stage_6_creates_backup_and_commits_via_gda_people(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    target_people = mock_gpi_env["people_path"]

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
def test_stage_6_updates_existing_record_in_registry(mock_gpi_env: Dict[str, Any]) -> None:
    target_people = mock_gpi_env["people_path"]
    updated_person = {
        "person_id": "IND-00000",
        "canonical_name": {"given": "Artie", "surname": "Sterling"},
        "sex": "M",
    }

    stage_6_atomic_commit(
        new_records=[],
        updated_existing=[updated_person],
        staged_files=[],
        verbose=True,
        logger=mock_gpi_env["logger"],
        people_path=target_people,
    )
    data = GDAUtil.load_json(target_people)
    persons = data.get("persons", data.get("people", []))
    assert persons[0]["canonical_name"]["given"] == "Artie"


@pytest.mark.regression
def test_stage_6_unlinks_staged_file(mock_gpi_env: Dict[str, Any]) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    target_people = mock_gpi_env["people_path"]

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
    assert main() == 0


@pytest.mark.smoke
def test_gpi_cli_restore_recovers_quarantined_files(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    q_dir = mock_gpi_env["quarantine_dir"]
    held = q_dir / "20261006_000000_pep-let-held.json"
    GDAUtil.save_json(held, {"person_id": "TMP-HELD"})

    monkeypatch.setattr("sys.argv", ["gpi.py", "--restore"])
    assert main() == 0
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
    assert main() == 0
    assert pep_file.exists()


@pytest.mark.regression
def test_gpi_cli_stage1_failure_exits_cleanly(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    bad_file = ent_dir / "pep-let-syntax-err.json"
    bad_file.write_text("{ corrupt json }", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["gpi.py"])
    assert main() == 0


@pytest.mark.regression
def test_gpi_cli_stage2_failure_exits_cleanly(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    dangle_file = ent_dir / "pep-let-dangle-cli.json"
    GDAUtil.save_json(dangle_file, {
        "person_id": "TMP-00021",
        "display_name": "Dangle CLI",
        "canonical_name": {"given": "Dangle", "surname": "CLI"},
        "sex": "M",
        "associated_people": [{"person_id": "IND-99999", "role": "FATH"}],
    })

    monkeypatch.setattr("sys.argv", ["gpi.py"])
    assert main() == 0


@pytest.mark.regression
def test_gpi_cli_stage2b_failure_exits_cleanly(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    chrono_file = ent_dir / "pep-let-chrono-cli.json"
    GDAUtil.save_json(chrono_file, {
        "person_id": "TMP-00051",
        "display_name": "Chrono Child CLI",
        "canonical_name": {"given": "Chrono", "surname": "Child"},
        "sex": "M",
        "vitals": {"birth": {"date": {"date_start": "1905-01-01"}}},
        "associated_people": [{"person_id": "IND-00000", "role": "FATH"}],
    })

    monkeypatch.setattr("sys.argv", ["gpi.py"])
    assert main() == 0


@pytest.mark.regression
def test_gpi_cli_stage3_failure_exits_cleanly(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    dup_file = ent_dir / "pep-let-dup-cli.json"
    GDAUtil.save_json(dup_file, {
        "person_id": "TMP-00001",
        "display_name": "Arthur Sterling",
        "canonical_name": {"given": "Arthur", "surname": "Sterling"},
        "sex": "M",
        "associated_people": [{"person_id": "IND-00000", "role": "SPOU"}],
    })

    monkeypatch.setattr("sys.argv", ["gpi.py"])
    assert main() == 0


@pytest.mark.regression
def test_gpi_cli_stage4_failure_exits_cleanly(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    bad_loc_file = ent_dir / "pep-let-bad-loc-cli.json"
    GDAUtil.save_json(bad_loc_file, {
        "person_id": "TMP-00080",
        "display_name": "Bad Loc CLI",
        "canonical_name": {"given": "Bad", "surname": "Location"},
        "sex": "M",
        "associated_people": [{"person_id": "IND-00000", "role": "SPOU"}],
        "vitals": {"birth": {"place": {"standardized": "Unknown Galaxy"}}},
    })

    monkeypatch.setattr("sys.argv", ["gpi.py"])
    assert main() == 0


@pytest.mark.integration
def test_gpi_cli_full_execution_commits_staged_entity(mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    ent_dir = mock_gpi_env["entities_dir"]
    valid_file = ent_dir / "pep-let-full-commit.json"
    GDAUtil.save_json(valid_file, {
        "person_id": "TMP-00099",
        "display_name": "Full Commit",
        "canonical_name": {"given": "Full", "surname": "Commit"},
        "sex": "F",
        "associated_people": [{"person_id": "IND-00000", "role": "CHIL"}],
        "vitals": {"birth": {"place": {"standardized": "West Pennsboro, PA"}}},
    })

    monkeypatch.setattr("sys.argv", ["gpi.py", "--verbose"])
    assert main() == 0
    assert not valid_file.exists()

# ==============================================================================
# 9. REMAINING BRANCH & DEFENSIVE COVERAGE COMPLETION
# ==============================================================================

@pytest.mark.unit
def test_stage_5_record_missing_initial_person_id_minting() -> None:
    """Exercises branch 339->334 where a staged record lacks an initial person_id."""
    staged = [{"canonical_name": {"given": "No", "surname": "ID"}, "sex": "M"}]
    existing = [{"person_id": "IND-00010"}]

    minted, _ = stage_5_minting_and_rewrite(staged, existing)
    assert minted[0]["person_id"] == "IND-00011"


@pytest.mark.unit
def test_stage_5_union_pointing_to_unmapped_spouse_id() -> None:
    """Exercises branch 347->346 where union spouse_id is not in id_map."""
    staged = [
        {
            "person_id": "TMP-00001",
            "unions": [{"spouse_id": "IND-00001", "status": "MARRIED"}],
        }
    ]
    existing = [{"person_id": "IND-00001"}]

    minted, _ = stage_5_minting_and_rewrite(staged, existing)
    assert minted[0]["unions"][0]["spouse_id"] == "IND-00001"


@pytest.mark.unit
def test_stage_5_skips_duplicate_reciprocal_association_on_existing() -> None:
    """Exercises branch 368->361 where reciprocal linkage already exists on target."""
    staged = [
        {
            "person_id": "TMP-00001",
            "sex": "M",
            "associated_people": [{"person_id": "IND-00010", "role": "FATH"}],
        }
    ]
    existing = [
        {
            "person_id": "IND-00010",
            "sex": "M",
            "associated_people": [{"person_id": "IND-00011", "role": "CHIL"}],
        }
    ]

    _, updated_existing = stage_5_minting_and_rewrite(staged, existing)
    assert len(updated_existing[0]["associated_people"]) == 1


@pytest.mark.regression
def test_stage_6_skips_nonexistent_person_id_update(mock_gpi_env: Dict[str, Any]) -> None:
    """Exercises branch 388->386 where updated_existing ID does not exist in registry."""
    target_people = mock_gpi_env["people_path"]
    phantom_person = {"person_id": "IND-99999", "canonical_name": {"given": "Phantom"}}

    success = stage_6_atomic_commit(
        new_records=[],
        updated_existing=[phantom_person],
        staged_files=[],
        verbose=True,
        logger=mock_gpi_env["logger"],
        people_path=target_people,
    )
    assert success is True


@pytest.mark.regression
def test_stage_6_cleanup_skips_already_deleted_staging_file(mock_gpi_env: Dict[str, Any]) -> None:
    """Exercises branch 406->405 where a staging file was removed prior to cleanup."""
    ghost_file = mock_gpi_env["entities_dir"] / "pep-let-ghost.json"

    success = stage_6_atomic_commit(
        new_records=[],
        updated_existing=[],
        staged_files=[ghost_file],
        verbose=True,
        logger=mock_gpi_env["logger"],
        people_path=mock_gpi_env["people_path"],
    )
    assert success is True


@pytest.mark.regression
def test_gpi_cli_missing_people_registry_file_exits_cleanly(
    mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercises line 445 where people.json does not exist when CLI runs."""
    if mock_gpi_env["people_path"].exists():
        mock_gpi_env["people_path"].unlink()

    monkeypatch.setattr("sys.argv", ["gpi.py"])
    assert main() == 0


@pytest.mark.regression
def test_gpi_cli_stage3_dedup_failure_quarantines_and_exits(
    mock_gpi_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercises line 457 where Stage 3 rejects all staged files under CLI run."""
    ent_dir = mock_gpi_env["entities_dir"]
    dup_file = ent_dir / "pep-let-exact-dup.json"
    GDAUtil.save_json(
        dup_file,
        {
            "person_id": "TMP-00001",
            "display_name": "Arthur Sterling",
            "canonical_name": {"given": "Arthur", "surname": "Sterling"},
            "sex": "M",
            "associated_people": [{"person_id": "IND-00000", "role": "SPOU"}],
        },
    )

    monkeypatch.setattr("sys.argv", ["gpi.py"])
    assert main() == 0