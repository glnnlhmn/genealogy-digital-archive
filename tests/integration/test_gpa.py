# Name: test_gpa.py
# Path: tests/integration/test_gpa.py

"""Unit test suite for GPA (Genealogy People Auditor).

Exercises envelope container verification, entity schema validation,
bidirectional kinship reciprocity, biological chronology limits,
vital date synchronization, and incomplete date checks.
"""

import json
import logging
from pathlib import Path
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops import gpa
from tools.ops.gpa import RegistryAuditor, TieredFindings


@pytest.fixture
def mock_gpa_env(tmp_path, monkeypatch):
    """Sets up an isolated digital archive environment by rebinding GDAConfig."""
    data_dir = tmp_path / "data"
    entities_dir = data_dir / "entities"
    reports_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"

    entities_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    mock_config = GDAConfig(root=tmp_path, manifest={})
    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.gpa.CONFIG", mock_config)

    # Base valid registry container
    initial_data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 0,
        "persons": [],
    }
    GDAUtil.save_json(mock_config.people, initial_data)

    test_logger = logging.getLogger("gpa_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    auditor = RegistryAuditor(
        people_path=mock_config.people,
        reports_dir=reports_dir,
        debug=False,
        verbose=False,
        logger=test_logger,
    )

    return {
        "auditor": auditor,
        "people_path": mock_config.people,
        "reports_dir": reports_dir,
        "logger": test_logger,
    }


def update_registry(auditor: RegistryAuditor, data_dict: dict) -> None:
    """Helper to update auditor in-memory state and reload mappings."""
    auditor.people_data = data_dict
    auditor.persons = data_dict.get("persons", [])
    auditor.person_map = {p["person_id"]: p for p in auditor.persons if "person_id" in p}


def test_container_valid(mock_gpa_env):
    """Verifies that a well-formed container passes without errors."""
    auditor = mock_gpa_env["auditor"]
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 1,
        "persons": [{"person_id": "IND-00001"}],
    }
    update_registry(auditor, data)
    findings = auditor.audit_container()
    assert len(findings.errors) == 0
    assert len(findings.warnings) == 0


def test_container_schema_and_version_mismatch(mock_gpa_env):
    """Verifies failure on invalid schema URI, incorrect version, and count mismatch."""
    auditor = mock_gpa_env["auditor"]
    data = {
        "$schema": "invalid/path/schema.json",
        "schema_version": "2.0.0",
        "total_persons": 5,
        "persons": [{"person_id": "IND-00001"}],
    }
    update_registry(auditor, data)
    findings = auditor.audit_container()
    assert len(findings.errors) == 3


def test_schema_valid_entity(mock_gpa_env):
    """Validates a structurally complete person record against controlled enums."""
    auditor = mock_gpa_env["auditor"]
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 1,
        "persons": [
            {
                "person_id": "IND-00001",
                "display_name": "John Doe",
                "canonical_name": {"given": "John", "surname": "Doe"},
                "sex": "Male",
                "vitals": {
                    "birth": {"date": {"date_start": "1900-01-01", "modifier": "EXACT"}},
                    "death": {"date": {"date_start": "1980-05-15", "modifier": "EXACT"}},
                },
                "associated_people": [],
            }
        ],
    }
    update_registry(auditor, data)
    findings = auditor.audit_schema()
    assert len(findings.errors) == 0


def test_schema_invalid_id_and_enum_violations(mock_gpa_env):
    """Catches invalid person_id formats, missing names, and controlled enum violations."""
    auditor = mock_gpa_env["auditor"]
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 1,
        "persons": [
            {
                "person_id": "BAD-ID-123",
                "canonical_name": {"raw_name": "Test Subject"},
                "sex": "INVALID_SEX",
                "vitals": {
                    "birth": {"date": {"date_start": "1900-01-01", "modifier": "INVALID_MOD"}},
                },
                "associated_people": [{"person_id": "IND-00002", "role": "INVALID_ROLE"}],
            }
        ],
    }
    update_registry(auditor, data)
    findings = auditor.audit_schema()
    assert any("Invalid or missing person_id" in err for err in findings.errors)
    assert any("Missing or invalid required string 'display_name'" in err for err in findings.errors)
    assert any("Invalid 'sex' enum value" in err for err in findings.errors)
    assert any("invalid modifier enum" in err for err in findings.errors)
    assert any("invalid role enum" in err for err in findings.errors)


def test_reciprocity_valid(mock_gpa_env):
    """Verifies that reciprocal kinship relationships evaluate cleanly."""
    auditor = mock_gpa_env["auditor"]
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "sex": "Male",
                "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}],
            },
            {
                "person_id": "IND-00002",
                "sex": "Female",
                "associated_people": [{"person_id": "IND-00001", "role": "FATH"}],
            },
        ],
    }
    update_registry(auditor, data)
    findings = auditor.audit_reciprocity()
    assert len(findings.errors) == 0


def test_reciprocity_missing_child_link(mock_gpa_env):
    """Detects when a parent links to a child but child fails to link back."""
    auditor = mock_gpa_env["auditor"]
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "sex": "Female",
                "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}],
            },
            {
                "person_id": "IND-00002",
                "sex": "Male",
                "associated_people": [],
            },
        ],
    }
    update_registry(auditor, data)
    findings = auditor.audit_reciprocity()
    assert len(findings.errors) == 1
    assert "does not link back as MOTH" in findings.errors[0]


def test_chronology_valid_and_bounds_violations(mock_gpa_env):
    """Tests biologically plausible parent-child age differences and flags violations."""
    auditor = mock_gpa_env["auditor"]

    # 1. Too young (< 12)
    data_young = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"birth_year": {"year": 1950}},
                "associated_people": [],
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"birth_year": {"year": 1955}},
                "associated_people": [{"person_id": "IND-00001", "role": "FATH"}],
            },
        ],
    }
    update_registry(auditor, data_young)
    findings_young = auditor.audit_chronology()
    assert len(findings_young.errors) == 1
    assert "Minimum threshold: 12" in findings_young.errors[0]

    # 2. Too old (> 85)
    data_old = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00003",
                "canonical_name": {"birth_year": {"year": 1850}},
                "associated_people": [],
            },
            {
                "person_id": "IND-00004",
                "canonical_name": {"birth_year": {"year": 1940}},
                "associated_people": [{"person_id": "IND-00003", "role": "FATH"}],
            },
        ],
    }
    update_registry(auditor, data_old)
    findings_old = auditor.audit_chronology()
    assert len(findings_old.errors) == 1
    assert "Maximum threshold: 85" in findings_old.errors[0]


def test_vital_synchronization_conflict(mock_gpa_env):
    """Detects discrepancies between canonical year summaries and vitals dates."""
    auditor = mock_gpa_env["auditor"]
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 1,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"birth_year": {"year": 1880, "modifier": "EXACT"}},
                "vitals": {
                    "birth": {"date": {"date_start": "1885-06-12", "modifier": "EXACT"}},
                },
            }
        ],
    }
    update_registry(auditor, data)
    findings = auditor.audit_vital_synchronization()
    assert len(findings.errors) == 1
    assert "Birth year conflict" in findings.errors[0]
    assert len(auditor.remediation_rows) == 1
    assert auditor.remediation_rows[0]["proposed_action"] == "UPDATE_CANONICAL_YEAR"


def test_audit_incomplete_dates(mock_gpa_env):
    """Verifies that missing and partial vital dates are cataloged."""
    auditor = mock_gpa_env["auditor"]
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"birth_year": {"year": 1920}},
                "vitals": {"birth": {"date": {}}},
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"birth_year": {"year": 1930}},
                "vitals": {"birth": {"date": {"date_start": "1930-04"}}},
            },
        ],
    }
    update_registry(auditor, data)
    findings = auditor.audit_incomplete_dates()
    assert len(findings.warnings) >= 1
    assert len(findings.notes) >= 1
    assert any("Missing vital date" in w for w in findings.warnings)
    assert any("Partial date [YYYY-MM]" in n for n in findings.notes)


def test_write_report_and_remediation_csv(mock_gpa_env):
    """Verifies full audit report writing and CSV ledger generation."""
    auditor = mock_gpa_env["auditor"]
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 1,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"birth_year": {"year": 1880}},
                "vitals": {"birth": {"date": {"date_start": "1885-06-12"}}},
            }
        ],
    }
    update_registry(auditor, data)
    findings = auditor.audit_vital_synchronization()
    auditor.write_report("vital_synchronization", findings)

    reports = list(mock_gpa_env["reports_dir"].glob("audit_people_vital_synchronization_*.txt"))
    csvs = list(mock_gpa_env["reports_dir"].glob("remediation_vital_sync_*.csv"))

    assert len(reports) == 1
    assert len(csvs) == 1
    assert "Birth year conflict" in reports[0].read_text(encoding="utf-8")