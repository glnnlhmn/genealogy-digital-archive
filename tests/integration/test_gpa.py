# Name: test_gpa.py
# Path: tests/test_gpa.py

"""Unit test suite for GPA (Genealogy People Auditor) v1.0.0.

Exercises envelope container verification, entity schema validation,
bidirectional kinship reciprocity, biological chronology limits,
and vital date synchronization using isolated mock registries.
"""

import json
from pathlib import Path
import pytest
from tools.ops.gpa import RegistryAuditor, TieredFindings


@pytest.fixture
def mock_auditor(tmp_path, monkeypatch):
    """Creates a RegistryAuditor instance backed by an isolated temporary people.json."""
    mock_people_path = tmp_path / "people.json"
    mock_reports_dir = tmp_path / "reports"
    mock_logs_dir = tmp_path / "logs"

    mock_reports_dir.mkdir(parents=True, exist_ok=True)
    mock_logs_dir.mkdir(parents=True, exist_ok=True)

    # Base valid registry container
    initial_data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 0,
        "persons": []
    }
    mock_people_path.write_text(json.dumps(initial_data), encoding="utf-8")

    # Monkeypatch target paths in gpa module
    monkeypatch.setattr("tools.ops.gpa.PEOPLE_PATH", mock_people_path)
    monkeypatch.setattr("tools.ops.gpa.REPORTS_DIR", mock_reports_dir)
    monkeypatch.setattr("tools.ops.gpa.LOGS_DIR", mock_logs_dir)

    auditor = RegistryAuditor(debug=False, verbose=False)
    return auditor


def update_registry(auditor, data_dict):
    """Helper to update the auditor's in-memory state and reload mappings."""
    auditor.people_data = data_dict
    auditor.persons = data_dict.get("persons", [])
    auditor.person_map = {p["person_id"]: p for p in auditor.persons if "person_id" in p}


def test_container_valid(mock_auditor):
    """Verifies that a well-formed container passes without errors."""
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 1,
        "persons": [{"person_id": "IND-00001"}]
    }
    update_registry(mock_auditor, data)
    findings = mock_auditor.audit_container()
    assert len(findings.errors) == 0
    assert len(findings.warnings) == 0


def test_container_schema_and_version_mismatch(mock_auditor):
    """Verifies failure on invalid schema URI, incorrect version, and count mismatch."""
    data = {
        "$schema": "invalid/path/schema.json",
        "schema_version": "2.0.0",
        "total_persons": 5,
        "persons": [{"person_id": "IND-00001"}]
    }
    update_registry(mock_auditor, data)
    findings = mock_auditor.audit_container()
    assert len(findings.errors) == 3


def test_schema_valid_entity(mock_auditor):
    """Validates a structurally complete person record."""
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
                    "death": {"date": {"date_start": "1980-05-15", "modifier": "EXACT"}}
                },
                "associated_people": []
            }
        ]
    }
    update_registry(mock_auditor, data)
    findings = mock_auditor.audit_schema()
    assert len(findings.errors) == 0


def test_schema_invalid_id_and_missing_name(mock_auditor):
    """Catches invalid person_id formats and missing display names."""
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 1,
        "persons": [
            {
                "person_id": "BAD-ID-123",
                "canonical_name": {"raw_name": "Test Subject"},
                "sex": "Unknown"
            }
        ]
    }
    update_registry(mock_auditor, data)
    findings = mock_auditor.audit_schema()
    assert any("Invalid or missing person_id" in err for err in findings.errors)
    assert any("Missing or invalid required string 'display_name'" in err for err in findings.errors)


def test_reciprocity_valid(mock_auditor):
    """Verifies that reciprocal kinship relationships evaluate cleanly."""
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "sex": "Male",
                "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}]
            },
            {
                "person_id": "IND-00002",
                "sex": "Female",
                "associated_people": [{"person_id": "IND-00001", "role": "FATH"}]
            }
        ]
    }
    update_registry(mock_auditor, data)
    findings = mock_auditor.audit_reciprocity()
    assert len(findings.errors) == 0


def test_reciprocity_missing_child_link(mock_auditor):
    """Detects when a parent links to a child but child fails to link back."""
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "sex": "Female",
                "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}]
            },
            {
                "person_id": "IND-00002",
                "sex": "Male",
                "associated_people": []
            }
        ]
    }
    update_registry(mock_auditor, data)
    findings = mock_auditor.audit_reciprocity()
    assert len(findings.errors) == 1
    assert "does not link back as MOTH" in findings.errors[0]


def test_chronology_valid_and_violations(mock_auditor):
    """Tests biologically plausible parent-child age differences and flags violations."""
    # Parent b. 1950, Child b. 1955 -> Difference 5 years (biological impossibility < 12)
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"birth_year": {"year": 1950}},
                "associated_people": []
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"birth_year": {"year": 1955}},
                "associated_people": [{"person_id": "IND-00001", "role": "FATH"}]
            }
        ]
    }
    update_registry(mock_auditor, data)
    findings = mock_auditor.audit_chronology()
    assert len(findings.errors) == 1
    assert "Biological impossibility" in findings.errors[0]


def test_vital_synchronization_conflict(mock_auditor):
    """Detects discrepancies between canonical year summaries and vitals dates."""
    data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "total_persons": 1,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"birth_year": {"year": 1880, "modifier": "EXACT"}},
                "vitals": {
                    "birth": {"date": {"date_start": "1885-06-12", "modifier": "EXACT"}}
                }
            }
        ]
    }
    update_registry(mock_auditor, data)
    findings = mock_auditor.audit_vital_synchronization()
    assert len(findings.errors) == 1
    assert "Birth year conflict" in findings.errors[0]
    assert len(mock_auditor.remediation_rows) == 1
    assert mock_auditor.remediation_rows[0]["proposed_action"] == "UPDATE_CANONICAL_YEAR"