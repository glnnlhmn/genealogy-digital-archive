# Name: test_gpa.py
# Path: tests/ops/test_gpa.py
# Version: 1.1.0+build.20261006.7

"""Consolidated integration and unit test harness for GPA (Genealogy People Auditor).

Operational Role:
    Executes comprehensive audits across golden baselines, curated domain
    failure fixtures, and defensive parser paths. Enforces:
    - Master schema compliance and envelope header metadata.
    - Reciprocal relationship linkages (kinship associations and unions).
    - Biological chronology plausibility (birth, death, parental boundaries).
    - Geographical and structural location verification.
    - Graph reachability and isolated island detection.
    - Defensive parser handling (years, missing IDs, note exemptions).
    - CLI execution codes and parameter formatting.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly marked with pytest marker taxonomy.
    - Dependencies: golden_people.json and tests/fixtures/people/failures/.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict
import pytest

from gdacore.config import GDAConfig
from gdacore.util import GDAUtil
from gdadomain.people import GDAPeople
from tools.ops.gpa import RegistryAuditor, TieredFindings, run_cli

pytestmark = [pytest.mark.integration, pytest.mark.unit]

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "people"
GOLDEN_PEOPLE = FIXTURES_DIR / "golden" / "golden_people.json"
FAILURES_DIR = FIXTURES_DIR / "failures"


@pytest.fixture
def mock_gpa_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Sets up an isolated environment pointing to test fixtures."""
    mock_config = GDAConfig(root=tmp_path)
    monkeypatch.setattr("gdacore.config.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.gpa.CONFIG", mock_config)

    logger = logging.getLogger("test_gpa")
    logger.setLevel(logging.CRITICAL)

    return {
        "root": tmp_path,
        "config": mock_config,
        "golden_people": GOLDEN_PEOPLE,
        "failures_dir": FAILURES_DIR,
        "logger": logger,
    }


@pytest.fixture(scope="module")
def audit_cache() -> Callable[[Path], Any]:
    """Caches audited fixtures across fine-grained tests to minimize disk I/O."""
    cache: Dict[Path, Any] = {}

    def _get(file_path: Path) -> Any:
        if file_path not in cache:
            data = GDAUtil.load_json(file_path)
            null_logger = logging.getLogger(f"cache_{file_path.stem}")
            null_logger.setLevel(logging.CRITICAL)
            auditor = RegistryAuditor(people_data=data, logger=null_logger)
            cache[file_path] = auditor.run_all()
        return cache[file_path]

    return _get


@pytest.fixture
def null_logger() -> logging.Logger:
    """Provides a silent logger instance for pure computational testing."""
    logger = logging.getLogger("unit_null")
    logger.setLevel(logging.CRITICAL)
    return logger


# ==============================================================================
# 1. PARSER & INPUT DEFENSIVE GUARDS (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_parse_year_none_input() -> None:
    assert RegistryAuditor._parse_year(None) is None


@pytest.mark.smoke
def test_parse_year_empty_string() -> None:
    assert RegistryAuditor._parse_year("") is None


@pytest.mark.regression
def test_parse_year_non_digit_string() -> None:
    assert RegistryAuditor._parse_year("NO_DIGITS_HERE") is None


@pytest.mark.smoke
def test_parse_year_iso_date_string() -> None:
    assert RegistryAuditor._parse_year("1984-06-18") == 1984


@pytest.mark.smoke
def test_parse_year_from_dict_year() -> None:
    assert RegistryAuditor._parse_year({"year": 1961}) == 1961


@pytest.mark.smoke
def test_parse_year_from_dict_date_start() -> None:
    assert RegistryAuditor._parse_year({"date_start": "1961-12-01"}) == 1961


@pytest.mark.regression
def test_auditor_rejects_invalid_type() -> None:
    with pytest.raises(TypeError, match="must be a dictionary or a GDAPeople"):
        RegistryAuditor(people_data=123)  # type: ignore[arg-type]


@pytest.mark.regression
def test_auditor_missing_person_id_guard(null_logger: logging.Logger) -> None:
    payload = {
        "total_persons": 1,
        "persons": [{"display_name": "No ID", "canonical_name": {"given": "No", "surname": "ID"}}],
    }
    auditor = RegistryAuditor(people_data=payload, logger=null_logger)
    assert len(auditor.person_map) == 0


@pytest.mark.regression
def test_auditor_missing_name_fingerprint_guard(null_logger: logging.Logger) -> None:
    payload = {
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


@pytest.mark.smoke
def test_auditor_supports_gda_people_instance(tmp_path: Path, null_logger: logging.Logger) -> None:
    mgr = GDAPeople(filepath=tmp_path / "people.json", auto_load=False)
    mgr.add(canonical_name={"given": "Test", "surname": "User"}, sex="M")
    auditor = RegistryAuditor(people_data=mgr, logger=null_logger)
    assert len(auditor.persons) == 1


# ==============================================================================
# 2. GOLDEN BASELINE AUDIT (Atomized)
# ==============================================================================

@pytest.mark.smoke
@pytest.mark.integrity
def test_golden_people_fixture_exists() -> None:
    assert GOLDEN_PEOPLE.exists()


@pytest.mark.smoke
@pytest.mark.integrity
def test_golden_people_audit_has_zero_critical_findings(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(GOLDEN_PEOPLE)
    assert len(findings.critical) == 0


# ==============================================================================
# 3. BIOLOGICAL CHRONOLOGY FAILURES (Atomized)
# ==============================================================================
CHRONO_FIXTURE = FAILURES_DIR / "failed_biological_chronology.json"


@pytest.mark.regression
def test_chrono_error_death_before_birth(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [f for f in findings.find_rules("CHRONO_DEATH_BEFORE_BIRTH") if f["person_id"] == "IND-00037"]
    assert len(matches) == 1


@pytest.mark.regression
def test_chrono_error_parent_too_young_father(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [
        f for f in findings.find_rules("CHRONO_PARENT_TOO_YOUNG")
        if f["person_id"] == "IND-00043" and "IND-00000" in f["message"]
    ]
    assert len(matches) == 1


@pytest.mark.regression
def test_chrono_error_parent_too_young_mother(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [
        f for f in findings.find_rules("CHRONO_PARENT_TOO_YOUNG")
        if f["person_id"] == "IND-00043" and "IND-00031" in f["message"]
    ]
    assert len(matches) == 1


@pytest.mark.regression
def test_chrono_error_born_after_parent_death(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [f for f in findings.find_rules("CHRONO_BORN_AFTER_PARENT_DEATH") if f["person_id"] == "IND-00083"]
    assert len(matches) == 1


@pytest.mark.regression
def test_chrono_warning_mother_too_old(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [f for f in findings.find_rules("CHRONO_MOTHER_TOO_OLD") if f["person_id"] == "IND-00047"]
    assert len(matches) == 1


@pytest.mark.regression
def test_chrono_warning_implausible_lifespan(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [f for f in findings.find_rules("CHRONO_IMPLAUSIBLE_LIFESPAN") if f["person_id"] == "IND-00109"]
    assert len(matches) == 1


@pytest.mark.regression
def test_chrono_documented_longevity_exemption(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(GOLDEN_PEOPLE)
    matches = [f for f in findings.find_rules("CHRONO_IMPLAUSIBLE_LIFESPAN") if f["person_id"] == "IND-00139"]
    assert len(matches) == 0


@pytest.mark.regression
def test_chrono_documented_late_birth_exemption(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(GOLDEN_PEOPLE)
    matches = [f for f in findings.find_rules("CHRONO_MOTHER_TOO_OLD") if f["person_id"] == "IND-00211"]
    assert len(matches) == 0


# ==============================================================================
# 4. VITAL SYNCHRONIZATION FAILURES (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_vital_sync_birth_year_mismatch(null_logger: logging.Logger) -> None:
    desync_data = {
        "total_persons": 1,
        "persons": [
            {
                "person_id": "IND-99999",
                "canonical_name": {
                    "given": "Desync",
                    "surname": "Person",
                    "birth_year": {"year": 1961},
                },
                "vitals": {"birth": {"date": {"date_start": "1965-06-15"}}},
            }
        ],
    }
    auditor = RegistryAuditor(people_data=desync_data, logger=null_logger)
    auditor.audit_vital_synchronization()
    assert len(auditor.findings.find_rules("VITAL_SYNC_BIRTH_YEAR")) == 1


@pytest.mark.regression
def test_vital_sync_death_year_mismatch(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_vital_sync_death.json")
    matches = [f for f in findings.find_rules("VITAL_SYNC_DEATH_YEAR") if f["person_id"] == "IND-00019"]
    assert len(matches) == 1


# ==============================================================================
# 5. ENVELOPE & DEDUPLICATION FAILURES (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_envelope_missing_required_property(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_envelope_and_schema.json")
    assert len(findings.find_rules("ENV_REQ")) > 0


@pytest.mark.regression
def test_envelope_count_mismatch(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_envelope_and_schema.json")
    assert len(findings.find_rules("COUNT_MISMATCH")) > 0


@pytest.mark.regression
def test_dedup_duplicate_person_id(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_dedup_and_drift.json")
    matches = [f for f in findings.find_rules("DUPLICATE_PERSON_ID") if f["person_id"] == "IND-00073"]
    assert len(matches) == 1


@pytest.mark.regression
def test_dedup_fingerprint_collision(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_dedup_and_drift.json")
    assert len(findings.find_rules("DEDUP_COLLISION")) > 0


# ==============================================================================
# 6. KINSHIP, UNIONS & TOPOLOGY FAILURES (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_kinship_missing_reciprocal_association(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_kinship_and_unions.json")
    matches = [f for f in findings.find_rules("ASYM_ASSOC") if f["person_id"] == "IND-00029"]
    assert len(matches) > 0


@pytest.mark.regression
def test_kinship_unknown_role_handling(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_kinship_unknown_role.json")
    matches = [f for f in findings.find_rules("ASYM_ASSOC") if f["person_id"] == "IND-00037"]
    assert len(matches) == 0


@pytest.mark.regression
def test_unions_marriage_date_mismatch(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_kinship_and_unions.json")
    assert len(findings.find_rules("UNION_DATE_MISMATCH")) > 0


@pytest.mark.regression
def test_union_missing_spouse_id_detected(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_unions_edge_cases.json")
    matches = [f for f in findings.find_rules("UNION_NO_SPOUSE") if f["person_id"] == "IND-00000"]
    assert len(matches) == 1


@pytest.mark.regression
def test_union_invalid_status_detected(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_unions_edge_cases.json")
    matches = [f for f in findings.find_rules("UNION_INVALID_STATUS") if f["person_id"] == "IND-00031"]
    assert len(matches) == 1


@pytest.mark.regression
def test_topology_dangling_association(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_topology_and_orphans.json")
    matches = [f for f in findings.find_rules("DANGLING_ASSOC") if f["person_id"] == "IND-00083"]
    assert len(matches) == 1


@pytest.mark.regression
def test_topology_disconnected_island(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_topology_and_orphans.json")
    matches = [f for f in findings.find_rules("TOPOLOGY_ISLAND") if f["person_id"] == "IND-00113"]
    assert len(matches) == 1


# ==============================================================================
# 7. LOCATION STRUCTURE FAILURES (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_location_malformed_string_detected(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_locations_and_redirects.json")
    matches = [f for f in findings.find_rules("LOCATION_MALFORMED") if f["person_id"] == "IND-00000"]
    assert len(matches) == 1


@pytest.mark.regression
def test_location_missing_standard_keys_detected(audit_cache: Callable[[Path], Any]) -> None:
    findings = audit_cache(FAILURES_DIR / "failed_locations_and_redirects.json")
    matches = [f for f in findings.find_rules("LOCATION_MISSING_STANDARD") if f["person_id"] == "IND-00029"]
    assert len(matches) == 1


# ==============================================================================
# 8. CLI OPERATIONS & EXIT CODES (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_gpa_cli_clean_execution(mock_gpa_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["gpa.py", "--file", str(GOLDEN_PEOPLE)])
    assert run_cli() == 0


@pytest.mark.regression
def test_gpa_cli_missing_file_error(mock_gpa_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    non_existent = FIXTURES_DIR / "non_existent_file.json"
    monkeypatch.setattr("sys.argv", ["gpa.py", "--file", str(non_existent)])
    assert run_cli() == 1


@pytest.mark.regression
def test_gpa_cli_critical_failure_exit_code(mock_gpa_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fail_path = FAILURES_DIR / "failed_envelope_and_schema.json"
    monkeypatch.setattr("sys.argv", ["gpa.py", "--file", str(fail_path)])
    assert run_cli() == 1


@pytest.mark.regression
def test_gpa_cli_warnings_verbose_emission(mock_gpa_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fail_path = FAILURES_DIR / "failed_kinship_and_unions.json"
    monkeypatch.setattr("sys.argv", ["gpa.py", "--file", str(fail_path), "--verbose"])
    assert run_cli() == 0


# ==============================================================================
# 9. BRANCH & DEFENSIVE COVERAGE COMPLETION (Atomized)
# ==============================================================================

@pytest.mark.unit
def test_tiered_findings_info_level_addition() -> None:
    findings = TieredFindings()
    findings.add("INFO", "IND-00001", "INFO_NOTE", "Informational audit record")
    assert len(findings.info) == 1


@pytest.mark.unit
def test_vital_sync_missing_vital_dates_bypass(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 1,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "Half", "surname": "Date", "birth_year": {"year": 1900}},
                "vitals": {"death": {"date": {"date_start": "1970-01-01"}}},
            }
        ],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_vital_synchronization()
    assert auditor.findings.total == 0


@pytest.mark.unit
def test_chrono_centenarian_with_verified_longevity_exemption(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 1,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "Centenarian"},
                "vitals": {
                    "birth": {"date": {"date_start": "1800-01-01"}},
                    "death": {"date": {"date_start": "1930-01-01"}},
                },
                "notes": [{"title": "Verified Longevity", "text": "Parish records confirm age"}],
            }
        ],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_biological_chronology()
    assert len(auditor.findings.find_rules("CHRONO_IMPLAUSIBLE_LIFESPAN")) == 0


@pytest.mark.unit
def test_chrono_normal_parent_generational_gap(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "Parent"},
                "vitals": {"birth": {"date": {"date_start": "1900-01-01"}}},
                "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}],
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"given": "Child"},
                "vitals": {"birth": {"date": {"date_start": "1925-01-01"}}},
                "associated_people": [{"person_id": "IND-00001", "role": "FATH"}],
            },
        ],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_biological_chronology()
    assert auditor.findings.total == 0


@pytest.mark.unit
def test_chrono_mother_over_55_with_exemption_note(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "Mother"},
                "vitals": {"birth": {"date": {"date_start": "1850-01-01"}}},
                "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}],
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"given": "Child"},
                "vitals": {"birth": {"date": {"date_start": "1908-01-01"}}},
                "notes": [{"title": "Late Delivery", "text": "Mother was 58 at late delivery"}],
                "associated_people": [{"person_id": "IND-00001", "role": "MOTH"}],
            },
        ],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_biological_chronology()
    assert len(auditor.findings.find_rules("CHRONO_MOTHER_TOO_OLD")) == 0


@pytest.mark.unit
def test_topology_single_person_registry_bypasses(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 1,
        "persons": [{"person_id": "IND-00001", "canonical_name": {"given": "Solo"}}],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_topology()
    assert len(auditor.findings.find_rules("TOPOLOGY_ISLAND")) == 0


@pytest.mark.unit
def test_associated_people_unmapped_role_bypasses(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "Sponsor"},
                "associated_people": [{"person_id": "IND-00002", "role": "UNMAPPED_CUSTOM_ROLE"}],
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"given": "Recipient"},
                "associated_people": [],
            },
        ],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_associated_people_reciprocity()
    assert len(auditor.findings.find_rules("ASYM_ASSOC")) == 0


@pytest.mark.unit
def test_unions_symmetric_matching_statuses(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "Husband"},
                "associated_people": [{"person_id": "IND-00002", "role": "SPOU"}],
                "unions": [{"spouse_id": "IND-00002", "status": "MARRIED"}],
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"given": "Wife"},
                "associated_people": [{"person_id": "IND-00001", "role": "SPOU"}],
                "unions": [{"spouse_id": "IND-00001", "status": "MARRIED"}],
            },
        ],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_unions()
    assert len(auditor.findings.find_rules("UNION_STATUS_MISMATCH")) == 0


@pytest.mark.unit
def test_unions_compatible_widowed_and_married_pairing(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "Husband"},
                "associated_people": [{"person_id": "IND-00002", "role": "SPOU"}],
                "unions": [{"spouse_id": "IND-00002", "status": "WIDOWED"}],
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"given": "Wife"},
                "associated_people": [{"person_id": "IND-00001", "role": "SPOU"}],
                "unions": [{"spouse_id": "IND-00001", "status": "MARRIED"}],
            },
        ],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_unions()
    assert len(auditor.findings.find_rules("UNION_STATUS_MISMATCH")) == 0


@pytest.mark.unit
@pytest.mark.unit
def test_unions_incompatible_status_mismatch_detected(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "Person A"},
                "associated_people": [{"person_id": "IND-00002", "role": "SPOU"}],
                "unions": [{"spouse_id": "IND-00002", "status": "MARRIED"}],
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"given": "Person B"},
                "associated_people": [{"person_id": "IND-00001", "role": "SPOU"}],
                "unions": [{"spouse_id": "IND-00001", "status": "DIVORCED"}],
            },
        ],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_unions()
    assert len(auditor.findings.find_rules("UNION_STATUS_MISMATCH")) == 2


@pytest.mark.unit
def test_vital_sync_birth_date_as_plain_string(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 1,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "Plain", "surname": "Date", "birth_year": {"year": 1965}},
                "vitals": {"birth": {"date": "1965-06-15"}},
            }
        ],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_vital_synchronization()
    assert auditor.findings.total == 0


@pytest.mark.unit
def test_chrono_parent_missing_birth_date_skips_generational_gap(null_logger: logging.Logger) -> None:
    data = {
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "canonical_name": {"given": "Parent", "surname": "UnknownBirth"},
                "vitals": {"death": {"date": {"date_start": "1950-01-01"}}},
                "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}],
            },
            {
                "person_id": "IND-00002",
                "canonical_name": {"given": "Child", "surname": "RecordedBirth"},
                "vitals": {"birth": {"date": {"date_start": "1920-01-01"}}},
                "associated_people": [{"person_id": "IND-00001", "role": "FATH"}],
            },
        ],
    }
    auditor = RegistryAuditor(people_data=data, logger=null_logger)
    auditor.audit_biological_chronology()
    assert len(auditor.findings.find_rules("CHRONO_PARENT_TOO_YOUNG")) == 0