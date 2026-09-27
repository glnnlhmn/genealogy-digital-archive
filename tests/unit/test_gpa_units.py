# Name: test_gpa_units.py
# Path: tests/unit/test_gpa_units.py
# Version: 1.0.1+build.20260927.01

"""Unit test harness exercising edge guards and defensive parser paths in GPA.

Operational Role:
    Isolates and validates GPA (Genealogy People Auditor) internal logic:
    - Year parsing edge cases (empty strings, alphanumeric tokens, ISO dates).
    - Entity registry mapping defenses (missing person_id or empty names).
    - Biological chronology note exemption matching (longevity and mature motherhood).
    - Unmapped reciprocal association bypasses.
    - CLI warning output formatting and terminal slice boundaries.

Test Structure & Protocol:
    - Atomized tests: Pure in-memory unit tests with zero disk mutation.
    - Fully decorated: Classified with @pytest.mark.unit, @pytest.mark.smoke,
      and @pytest.mark.regression.
    - Dependencies: Requires tools/ops/gpa.py and tests/fixtures/people/failures/.
"""

from __future__ import annotations

import logging
from pathlib import Path
import pytest

from tools.ops.gpa import RegistryAuditor, run_cli

pytestmark = pytest.mark.unit

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "people"
FAILURES_DIR = FIXTURES_DIR / "failures"


@pytest.fixture
def null_logger() -> logging.Logger:
    """Provides a silent logger instance for pure computational testing."""
    logger = logging.getLogger("unit_null")
    logger.setLevel(logging.CRITICAL)
    return logger


# ==============================================================================
# 1. PARSER & INPUT DEFENSIVE GUARDS
# ==============================================================================

@pytest.mark.smoke
def test_parse_year_none_input() -> None:
    """Verifies None returns None safely."""
    assert RegistryAuditor._parse_year(None) is None


@pytest.mark.smoke
def test_parse_year_empty_string() -> None:
    """Verifies empty strings return None safely."""
    assert RegistryAuditor._parse_year("") is None


@pytest.mark.regression
def test_parse_year_non_digit_string() -> None:
    """Verifies strings without numeric digits return None."""
    assert RegistryAuditor._parse_year("NO_DIGITS_HERE") is None


@pytest.mark.smoke
def test_parse_year_iso_date_string() -> None:
    """Verifies standard ISO date strings extract the integer year."""
    assert RegistryAuditor._parse_year("1984-06-18") == 1984


@pytest.mark.regression
def test_auditor_missing_person_id_guard(null_logger: logging.Logger) -> None:
    """Verifies records lacking person_id are safely skipped during indexing."""
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


@pytest.mark.regression
def test_auditor_missing_name_fingerprint_guard(null_logger: logging.Logger) -> None:
    """Verifies records without given or surname skip fingerprint indexing."""
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
# 2. CHRONOLOGY NOTES EXEMPTION LOGIC
# ==============================================================================

@pytest.mark.regression
def test_chrono_documented_longevity_suppression(null_logger: logging.Logger) -> None:
    """Verifies verified longevity notes suppress CHRONO_IMPLAUSIBLE_LIFESPAN."""
    payload = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-26T00:00:00Z",
        "total_persons": 1,
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
            }
        ],
    }
    auditor = RegistryAuditor(people_data=payload, logger=null_logger)
    auditor.audit_biological_chronology()
    assert len(auditor.findings.find_rules("CHRONO_IMPLAUSIBLE_LIFESPAN")) == 0


@pytest.mark.regression
def test_chrono_documented_late_birth_suppression(null_logger: logging.Logger) -> None:
    """Verifies documented late birth notes suppress CHRONO_MOTHER_TOO_OLD."""
    payload = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-26T00:00:00Z",
        "total_persons": 2,
        "persons": [
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
    assert len(auditor.findings.find_rules("CHRONO_MOTHER_TOO_OLD")) == 0


# ==============================================================================
# 3. KINSHIP UNMAPPED ROLES
# ==============================================================================

@pytest.mark.regression
def test_kinship_unmapped_role_ignored(null_logger: logging.Logger) -> None:
    """Verifies relationships without reciprocal definitions skip verification."""
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
# 4. CLI WARNING PRINTER & TERMINAL SLICES
# ==============================================================================

@pytest.mark.smoke
def test_cli_warning_slice_emission(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies CLI formats warnings cleanly using a connected failure fixture."""
    fixture_file = FAILURES_DIR / "failed_kinship_and_unions.json"
    assert fixture_file.exists(), f"Missing required fixture: {fixture_file}"
    monkeypatch.setattr("sys.argv", ["gpa.py", "--file", str(fixture_file)])
    assert run_cli() == 0