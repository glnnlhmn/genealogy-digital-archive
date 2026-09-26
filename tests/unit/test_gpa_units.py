# Name: test_gpa_units.py
# Path: tests/unit/test_gpa_units.py

"""Unit test harness exercising edge guards, defensive paths, and CLI formatters in GPA."""

import logging
from pathlib import Path
import pytest

from tools.ops.gpa import RegistryAuditor, run_cli

pytestmark = pytest.mark.unit

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FAILURES_DIR = FIXTURES_DIR / "failures"


@pytest.fixture
def null_logger():
    logger = logging.getLogger("unit_null")
    logger.setLevel(logging.CRITICAL)
    return logger


# ==============================================================================
# 1. PARSER & INPUT DEFENSIVE GUARDS (Lines 59, 82, 117->110)
# ==============================================================================
def test_parse_year_empty_and_invalid_inputs():
    """Covers line 82: defensive checks on None, empty, and invalid date strings."""
    assert RegistryAuditor._parse_year(None) is None
    assert RegistryAuditor._parse_year("") is None
    assert RegistryAuditor._parse_year("NO_DIGITS_HERE") is None
    assert RegistryAuditor._parse_year("1984-06-18") == 1984


def test_auditor_missing_person_id_guard(null_logger):
    """Covers line 59: records lacking person_id are safely skipped during indexing."""
    payload = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-26T00:00:00Z",
        "total_persons": 1,
        "persons": [
            {
                "display_name": "No Identifier",
                "canonical_name": {"given": "No", "surname": "ID"},
            }
        ],
    }
    auditor = RegistryAuditor(people_data=payload, logger=null_logger)
    assert len(auditor.person_map) == 0


def test_auditor_missing_name_fingerprint_guard(null_logger):
    """Covers branch 117->110: records without given or surname skip fingerprint indexing."""
    payload = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-26T00:00:00Z",
        "total_persons": 1,
        "persons": [
            {
                "person_id": "IND-NO-NAME",
                "display_name": "Only Given Name",
                "canonical_name": {"given": "GivenOnly", "surname": ""},
            }
        ],
    }
    auditor = RegistryAuditor(people_data=payload, logger=null_logger)
    auditor.audit_deduplication()
    assert len(auditor.findings.warning) == 0


# ==============================================================================
# 2. CHRONOLOGY NOTES EXEMPTION LOGIC (Branches 184->188, 198->208, 204->208)
# ==============================================================================
def test_chrono_documented_notes_suppression_paths(null_logger):
    """Covers note evaluation branches for longevity and late maternal birth."""
    payload = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-26T00:00:00Z",
        "total_persons": 3,
        "persons": [
            {
                "person_id": "IND-EXEMPT-01",
                "display_name": "Centenarian",
                "canonical_name": {"given": "Old", "surname": "Timer"},
                "vitals": {
                    "birth": {"date": {"date_start": "1800-01-01"}},
                    "death": {"date": {"date_start": "1930-01-01"}},
                },
                "notes": [
                    {"title": "Verified Longevity", "text": "Parish records confirm age"}
                ],
                "associated_people": [],
                "unions": [],
            },
            {
                "person_id": "IND-EXEMPT-MOTHER",
                "display_name": "Mature Mother",
                "canonical_name": {"given": "Mature", "surname": "Mother"},
                "vitals": {
                    "birth": {"date": {"date_start": "1850-01-01"}},
                    "death": {"date": {"date_start": "1925-01-01"}},
                },
                "associated_people": [{"person_id": "IND-EXEMPT-CHILD", "role": "CHIL"}],
                "unions": [],
            },
            {
                "person_id": "IND-EXEMPT-CHILD",
                "display_name": "Late Child",
                "canonical_name": {"given": "Late", "surname": "Child"},
                "vitals": {
                    "birth": {"date": {"date_start": "1908-01-01"}},
                    "death": {"date": {"date_start": "1980-01-01"}},
                },
                "notes": [{"title": "Late delivery", "text": "Mother was 58 at birth"}],
                "associated_people": [{"person_id": "IND-EXEMPT-MOTHER", "role": "MOTH"}],
                "unions": [],
            },
        ],
    }
    auditor = RegistryAuditor(people_data=payload, logger=null_logger)
    auditor.audit_biological_chronology()
    assert len(auditor.findings.find_rules("CHRONO_IMPLAUSIBLE_LIFESPAN")) == 0
    assert len(auditor.findings.find_rules("CHRONO_MOTHER_TOO_OLD")) == 0


# ==============================================================================
# 3. KINSHIP UNMAPPED ROLES (Line 221)
# ==============================================================================
def test_kinship_unmapped_role_ignored(null_logger):
    """Covers line 221: relationships without reciprocal definitions skip verification."""
    payload = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-26T00:00:00Z",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-01",
                "canonical_name": {"given": "Person", "surname": "One"},
                "associated_people": [{"person_id": "IND-02", "role": "SPONSOR"}],
                "unions": [],
            },
            {
                "person_id": "IND-02",
                "canonical_name": {"given": "Person", "surname": "Two"},
                "associated_people": [],
                "unions": [],
            },
        ],
    }
    auditor = RegistryAuditor(people_data=payload, logger=null_logger)
    auditor.audit_associated_people_reciprocity()
    assert len(auditor.findings.warning) == 0


# ==============================================================================
# 4. CLI WARNING PRINTER & TERMINAL SLICES (Lines 330–331, 337)
# ==============================================================================
def test_cli_warning_slice_emission(monkeypatch):
    """Covers lines 330-331 and 337: CLI formats warnings using a connected failure fixture."""
    fixture_file = FAILURES_DIR / "failed_kinship_and_unions.json"
    assert fixture_file.exists(), f"Missing required fixture: {fixture_file}"
    monkeypatch.setattr("sys.argv", ["gpa.py", "--file", str(fixture_file)])
    assert run_cli() == 0
