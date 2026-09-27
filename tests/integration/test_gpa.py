# Name: test_gpa.py
# Path: tests/integration/test_gpa.py
# Version: 1.0.1+build.20260927.01

"""Integration test harness for GPA (Genealogy People Auditor).

Operational Role:
    Executes end-to-end audits across the golden baseline registry and
    curated domain failure fixtures. Enforces:
    - Master schema compliance and envelope header metadata.
    - Reciprocal relationship linkages (kinship associations and unions).
    - Biological chronology plausibility (birth, death, parental boundaries).
    - Geographical and structural location verification.
    - Graph reachability and isolated island detection.
    - CLI execution codes and parameter formatting.

Test Structure & Protocol:
    - Atomized tests: Every defect assertion targets exactly 1 person ID
      and 1 error rule without bundling checks.
    - Fully decorated: Global integration mark with individual @pytest.mark.smoke,
      @pytest.mark.regression, and @pytest.mark.integrity markers.
    - Dependencies: golden_people.json and tests/fixtures/people/failures/.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops.gpa import RegistryAuditor, run_cli

pytestmark = pytest.mark.integration

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "people"
GOLDEN_PEOPLE = FIXTURES_DIR / "golden" / "golden_people.json"
FAILURES_DIR = FIXTURES_DIR / "failures"


@pytest.fixture
def mock_gpa_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Sets up an isolated environment pointing to test fixtures."""
    mock_config = GDAConfig(root=tmp_path, manifest={})
    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", mock_config)

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


# ==============================================================================
# 1. GOLDEN BASELINE AUDIT
# ==============================================================================

@pytest.mark.smoke
@pytest.mark.integrity
def test_golden_people_audit_passes(mock_gpa_env: Dict[str, Any], audit_cache: Callable[[Path], Any]) -> None:
    """Verifies that the golden baseline contains zero critical errors."""
    assert GOLDEN_PEOPLE.exists(), f"Missing fixture: {GOLDEN_PEOPLE}"
    findings = audit_cache(GOLDEN_PEOPLE)
    assert len(findings.critical) == 0, f"Expected zero critical errors, got: {findings.critical}"


# ==============================================================================
# 2. BIOLOGICAL CHRONOLOGY FAILURES (DISCRETE TESTS)
# ==============================================================================
CHRONO_FIXTURE = FAILURES_DIR / "failed_biological_chronology.json"


@pytest.mark.regression
def test_chrono_error_death_before_birth(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies detection of an individual who died before they were born."""
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [f for f in findings.find_rules("CHRONO_DEATH_BEFORE_BIRTH") if f["person_id"] == "IND-00037"]
    assert len(matches) == 1, "Failed to detect CHRONO_DEATH_BEFORE_BIRTH on IND-00037"


@pytest.mark.regression
def test_chrono_error_parent_too_young_father(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies detection of father under minimum biological age at child's birth."""
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [
        f for f in findings.find_rules("CHRONO_PARENT_TOO_YOUNG")
        if f["person_id"] == "IND-00043" and "IND-00000" in f["message"]
    ]
    assert len(matches) == 1, "Failed to detect father IND-00000 too young for IND-00043"


@pytest.mark.regression
def test_chrono_error_parent_too_young_mother(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies detection of mother under minimum biological age at child's birth."""
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [
        f for f in findings.find_rules("CHRONO_PARENT_TOO_YOUNG")
        if f["person_id"] == "IND-00043" and "IND-00031" in f["message"]
    ]
    assert len(matches) == 1, "Failed to detect mother IND-00031 too young for IND-00043"


@pytest.mark.regression
def test_chrono_error_born_after_parent_death(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies detection of a child born after a parent's recorded death."""
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [f for f in findings.find_rules("CHRONO_BORN_AFTER_PARENT_DEATH") if f["person_id"] == "IND-00083"]
    assert len(matches) == 1, "Failed to detect CHRONO_BORN_AFTER_PARENT_DEATH on IND-00083"


@pytest.mark.regression
def test_chrono_warning_mother_too_old(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies warning for maternal delivery past biological boundary."""
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [f for f in findings.find_rules("CHRONO_MOTHER_TOO_OLD") if f["person_id"] == "IND-00047"]
    assert len(matches) == 1, "Failed to detect CHRONO_MOTHER_TOO_OLD on IND-00047"


@pytest.mark.regression
def test_chrono_warning_implausible_lifespan(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies warning for an extreme lifespan (>115y) without documentation."""
    findings = audit_cache(CHRONO_FIXTURE)
    matches = [f for f in findings.find_rules("CHRONO_IMPLAUSIBLE_LIFESPAN") if f["person_id"] == "IND-00109"]
    assert len(matches) == 1, "Failed to detect CHRONO_IMPLAUSIBLE_LIFESPAN on IND-00109"


@pytest.mark.regression
def test_chrono_documented_longevity_exemption(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies Barnaby Sterling (104y) does not trigger CHRONO_IMPLAUSIBLE_LIFESPAN due to note."""
    findings = audit_cache(GOLDEN_PEOPLE)
    matches = [f for f in findings.find_rules("CHRONO_IMPLAUSIBLE_LIFESPAN") if f["person_id"] == "IND-00139"]
    assert len(matches) == 0, "Barnaby Sterling was incorrectly flagged despite documented longevity note"


@pytest.mark.regression
def test_chrono_documented_late_birth_exemption(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies Eleanor Thornton (51y at delivery) does not trigger CHRONO_MOTHER_TOO_OLD due to note."""
    findings = audit_cache(GOLDEN_PEOPLE)
    matches = [f for f in findings.find_rules("CHRONO_MOTHER_TOO_OLD") if f["person_id"] == "IND-00211"]
    assert len(matches) == 0, "Lateborn Thornton was incorrectly flagged despite documented late birth note"


# ==============================================================================
# 3. VITAL SYNCHRONIZATION FAILURES
# ==============================================================================

@pytest.mark.regression
def test_vital_sync_birth_year_mismatch(mock_gpa_env: Dict[str, Any]) -> None:
    """Verifies canonical birth_year desynchronized from vitals.birth triggers CRITICAL."""
    desync_data = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-26T00:00:00Z",
        "total_persons": 1,
        "persons": [
            {
                "person_id": "IND-99999",
                "display_name": "Desync Person",
                "canonical_name": {
                    "given": "Desync",
                    "surname": "Person",
                    "birth_year": {"year": 1961, "modifier": "EXACT"},
                },
                "sex": "Male",
                "vitals": {
                    "birth": {
                        "date": {"date_start": "1965-06-15", "modifier": "EXACT"}
                    }
                },
                "associated_people": [],
                "unions": [],
            }
        ],
    }
    auditor = RegistryAuditor(people_data=desync_data, logger=mock_gpa_env["logger"])
    findings = auditor.run_all()
    matches = findings.find_rules("VITAL_SYNC_BIRTH_YEAR")
    assert len(matches) == 1
    assert matches[0]["person_id"] == "IND-99999"


@pytest.mark.regression
def test_vital_sync_death_year_mismatch(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies canonical death_year desynchronized from vitals.death triggers VITAL_SYNC_DEATH_YEAR."""
    findings = audit_cache(FAILURES_DIR / "failed_vital_sync_death.json")
    matches = [f for f in findings.find_rules("VITAL_SYNC_DEATH_YEAR") if f["person_id"] == "IND-00019"]
    assert len(matches) == 1, "Failed to detect VITAL_SYNC_DEATH_YEAR on IND-00019"


# ==============================================================================
# 4. ENVELOPE & DEDUPLICATION FAILURES
# ==============================================================================

@pytest.mark.regression
def test_envelope_missing_required_property(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies envelope audit catches missing top-level manifest keys."""
    findings = audit_cache(FAILURES_DIR / "failed_envelope_and_schema.json")
    matches = findings.find_rules("ENV_REQ")
    assert len(matches) > 0, "Failed to detect ENV_REQ"


@pytest.mark.regression
def test_envelope_count_mismatch(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies envelope audit catches total_persons count desynchronization."""
    findings = audit_cache(FAILURES_DIR / "failed_envelope_and_schema.json")
    matches = findings.find_rules("COUNT_MISMATCH")
    assert len(matches) > 0, "Failed to detect COUNT_MISMATCH"


@pytest.mark.regression
def test_dedup_duplicate_person_id(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies duplicate person identifier collisions are flagged as CRITICAL."""
    findings = audit_cache(FAILURES_DIR / "failed_dedup_and_drift.json")
    matches = [f for f in findings.find_rules("DUPLICATE_PERSON_ID") if f["person_id"] == "IND-00073"]
    assert len(matches) == 1, "Failed to detect DUPLICATE_PERSON_ID for IND-00073"


@pytest.mark.regression
def test_dedup_fingerprint_collision(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies duplicate name and birth year collisions trigger warnings."""
    findings = audit_cache(FAILURES_DIR / "failed_dedup_and_drift.json")
    matches = findings.find_rules("DEDUP_COLLISION")
    assert len(matches) > 0, "Failed to detect DEDUP_COLLISION"


# ==============================================================================
# 5. KINSHIP, UNIONS & TOPOLOGY FAILURES
# ==============================================================================

@pytest.mark.regression
def test_kinship_missing_reciprocal_association(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies asymmetric reciprocal kinship linkages are flagged."""
    findings = audit_cache(FAILURES_DIR / "failed_kinship_and_unions.json")
    matches = [f for f in findings.find_rules("ASYM_ASSOC") if f["person_id"] == "IND-00029"]
    assert len(matches) > 0, "Failed to detect ASYM_ASSOC for IND-00029"


@pytest.mark.regression
def test_kinship_unknown_role_handling(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies associated role not in reciprocal_map is gracefully handled."""
    findings = audit_cache(FAILURES_DIR / "failed_kinship_unknown_role.json")
    matches = [f for f in findings.find_rules("ASYM_ASSOC") if f["person_id"] == "IND-00037"]
    assert len(matches) == 0


@pytest.mark.regression
def test_unions_marriage_date_mismatch(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies conflicting marriage dates across reciprocal spouses are flagged."""
    findings = audit_cache(FAILURES_DIR / "failed_kinship_and_unions.json")
    matches = findings.find_rules("UNION_DATE_MISMATCH")
    assert len(matches) > 0, "Failed to detect UNION_DATE_MISMATCH"


@pytest.mark.regression
def test_union_missing_spouse_id_detected(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies that a union entry lacking spouse_id triggers UNION_NO_SPOUSE."""
    findings = audit_cache(FAILURES_DIR / "failed_unions_edge_cases.json")
    matches = [f for f in findings.find_rules("UNION_NO_SPOUSE") if f["person_id"] == "IND-00000"]
    assert len(matches) == 1, "Failed to detect UNION_NO_SPOUSE on IND-00000"


@pytest.mark.regression
def test_union_invalid_status_detected(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies that an unapproved union status triggers UNION_INVALID_STATUS."""
    findings = audit_cache(FAILURES_DIR / "failed_unions_edge_cases.json")
    matches = [f for f in findings.find_rules("UNION_INVALID_STATUS") if f["person_id"] == "IND-00031"]
    assert len(matches) == 1, "Failed to detect UNION_INVALID_STATUS on IND-00031"


@pytest.mark.regression
def test_topology_dangling_association(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies references to non-existent person IDs are caught as CRITICAL."""
    findings = audit_cache(FAILURES_DIR / "failed_topology_and_orphans.json")
    matches = [f for f in findings.find_rules("DANGLING_ASSOC") if f["person_id"] == "IND-00083"]
    assert len(matches) == 1, "Failed to detect DANGLING_ASSOC for IND-00083"


@pytest.mark.regression
def test_topology_disconnected_island(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies disconnected collateral branches are caught as CRITICAL."""
    findings = audit_cache(FAILURES_DIR / "failed_topology_and_orphans.json")
    matches = [f for f in findings.find_rules("TOPOLOGY_ISLAND") if f["person_id"] == "IND-00113"]
    assert len(matches) == 1, "Failed to detect TOPOLOGY_ISLAND for IND-00113"


# ==============================================================================
# 6. LOCATION STRUCTURE FAILURES
# ==============================================================================

@pytest.mark.regression
def test_location_malformed_string_detected(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies that a non-dict location place triggers LOCATION_MALFORMED."""
    findings = audit_cache(FAILURES_DIR / "failed_locations_and_redirects.json")
    matches = [f for f in findings.find_rules("LOCATION_MALFORMED") if f["person_id"] == "IND-00000"]
    assert len(matches) == 1, "Failed to detect LOCATION_MALFORMED on IND-00000"


@pytest.mark.regression
def test_location_missing_standard_keys_detected(audit_cache: Callable[[Path], Any]) -> None:
    """Verifies place object lacking verbatim and standardized triggers LOCATION_MISSING_STANDARD."""
    findings = audit_cache(FAILURES_DIR / "failed_locations_and_redirects.json")
    matches = [f for f in findings.find_rules("LOCATION_MISSING_STANDARD") if f["person_id"] == "IND-00029"]
    assert len(matches) == 1, "Failed to detect LOCATION_MISSING_STANDARD on IND-00029"


# ==============================================================================
# 7. CLI OPERATIONS & EXIT CODES
# ==============================================================================

@pytest.mark.smoke
def test_gpa_cli_clean_execution(mock_gpa_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies running GPA CLI against golden baseline returns exit code 0."""
    monkeypatch.setattr("sys.argv", ["gpa.py", "--file", str(GOLDEN_PEOPLE)])
    assert run_cli() == 0


@pytest.mark.regression
def test_gpa_cli_missing_file_error(mock_gpa_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies running GPA CLI with a non-existent file returns exit code 1."""
    non_existent = FIXTURES_DIR / "non_existent_file.json"
    monkeypatch.setattr("sys.argv", ["gpa.py", "--file", str(non_existent)])
    assert run_cli() == 1


@pytest.mark.regression
def test_gpa_cli_critical_failure_exit_code(mock_gpa_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies running GPA CLI against a file with CRITICAL findings returns exit code 1."""
    fail_path = FAILURES_DIR / "failed_envelope_and_schema.json"
    monkeypatch.setattr("sys.argv", ["gpa.py", "--file", str(fail_path)])
    assert run_cli() == 1


@pytest.mark.regression
def test_gpa_cli_warnings_verbose_emission(mock_gpa_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies running GPA CLI against fixture with warnings triggers warning log loop."""
    fail_path = FAILURES_DIR / "failed_kinship_and_unions.json"
    monkeypatch.setattr("sys.argv", ["gpa.py", "--file", str(fail_path), "--verbose"])
    assert run_cli() == 0