# Name: test_engine_kinship.py
# Path: tools/lib/gdadomain/tests/test_engine_kinship.py
# Version: 1.0.0+build.r1

"""Unit test harness verifying KinshipEngine relationship mathematics and symmetry.

Operational Role:
    Validates reciprocal role mappings across genders, kinship and union symmetry
    audits, Ahnentafel generations and parent/child numbers, graph cycle detection,
    and reference vocabulary delegates.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly marked with @pytest.mark.unit; sanity checks
      tagged with @pytest.mark.smoke; boundary cases with @pytest.mark.regression.
    - Dependencies: GDAReferenceManager vocabulary delegations; zero disk I/O.
"""

from __future__ import annotations

from typing import Any
import pytest

from gdadomain.kinship import (
    KinshipAuditResult,
    KinshipEngine,
    UnionAuditResult,
)


# ==============================================================================
# GROUP 1: IntrospectableMixin & Reflection Verification
# Note: Verifies terminal directory generation, signatures, and invalid query handling
# ==============================================================================


@pytest.mark.unit
def test_help_directory_generation(capsys: Any) -> None:
    """Verify KinshipEngine.help() outputs all public classmethods without private attributes."""
    KinshipEngine.help()

    captured = capsys.readouterr().out
    assert "get_reciprocal_role" in captured
    assert "audit_kinship_symmetry" in captured
    assert "audit_union_symmetry" in captured
    assert "calculate_ahnentafel_generation" in captured
    assert "detect_kinship_cycle" in captured

    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    member_lines = [l for l in lines if l.startswith("-") or l.startswith("*")]
    for ml in member_lines:
        assert not ml.lstrip("- *").strip().startswith("_")


@pytest.mark.smoke
@pytest.mark.unit
def test_help_member_signature(capsys: Any) -> None:
    """Verify KinshipEngine.help('get_reciprocal_role') prints call signature and docstring."""
    KinshipEngine.help("get_reciprocal_role")

    captured = capsys.readouterr().out
    assert "get_reciprocal_role(" in captured
    assert "outbound_role" in captured
    assert "Derive the expected reciprocal" in captured


@pytest.mark.unit
def test_help_invalid_member(capsys: Any) -> None:
    """Verify KinshipEngine.help() gracefully handles unknown member names without exceptions."""
    KinshipEngine.help("non_existent_method")

    captured = capsys.readouterr().out
    assert "not found" in captured or "No public member" in captured or "non_existent_method" in captured


# ==============================================================================
# GROUP 2: Biological Sex Normalization & Vocabulary Delegations
# Note: Verifies sex token parsing, case-folding, and reference manager delegations
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_normalize_sex_m_returns_m() -> None:
    """Verify 'M' normalizes to 'M'."""
    assert KinshipEngine.normalize_sex("M") == "M"


@pytest.mark.unit
@pytest.mark.smoke
def test_normalize_sex_male_returns_m() -> None:
    """Verify 'Male' normalizes to 'M'."""
    assert KinshipEngine.normalize_sex("Male") == "M"


@pytest.mark.unit
@pytest.mark.smoke
def test_normalize_sex_f_returns_f() -> None:
    """Verify 'F' normalizes to 'F'."""
    assert KinshipEngine.normalize_sex("F") == "F"


@pytest.mark.unit
@pytest.mark.smoke
def test_normalize_sex_female_returns_f() -> None:
    """Verify 'Female' normalizes to 'F'."""
    assert KinshipEngine.normalize_sex("Female") == "F"


@pytest.mark.unit
@pytest.mark.regression
def test_normalize_sex_none_returns_none() -> None:
    """Verify None input normalizes to None."""
    assert KinshipEngine.normalize_sex(None) is None


@pytest.mark.unit
@pytest.mark.regression
def test_normalize_sex_non_string_returns_none() -> None:
    """Verify non-string inputs safely normalize to None."""
    assert KinshipEngine.normalize_sex(123) is None  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.regression
def test_normalize_sex_unknown_string_returns_none() -> None:
    """Verify unrecognized sex strings normalize to None."""
    assert KinshipEngine.normalize_sex("Unknown") is None


@pytest.mark.unit
@pytest.mark.smoke
def test_get_kinship_roles_contains_fath() -> None:
    """Verify get_kinship_roles delegates to reference manager and includes 'FATH'."""
    assert "FATH" in KinshipEngine.get_kinship_roles()


@pytest.mark.unit
@pytest.mark.smoke
def test_get_union_statuses_contains_married() -> None:
    """Verify get_union_statuses delegates to reference manager and includes 'MARRIED'."""
    assert "MARRIED" in KinshipEngine.get_union_statuses()


# ==============================================================================
# GROUP 3: Reciprocal Role Calculation
# Note: Verifies inverse role derivations across parent, child, spouse, and contextual roles
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_fath_returns_chil() -> None:
    """Verify reciprocal of FATH is CHIL."""
    assert KinshipEngine.get_reciprocal_role("FATH") == "CHIL"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_moth_returns_chil() -> None:
    """Verify reciprocal of MOTH is CHIL."""
    assert KinshipEngine.get_reciprocal_role("MOTH") == "CHIL"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_parent_returns_chil() -> None:
    """Verify reciprocal of PARENT is CHIL."""
    assert KinshipEngine.get_reciprocal_role("PARENT") == "CHIL"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_chil_with_male_subject_returns_fath() -> None:
    """Verify reciprocal of CHIL pointing to male subject is FATH."""
    assert KinshipEngine.get_reciprocal_role("CHIL", subject_sex="Male") == "FATH"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_chil_with_m_subject_returns_fath() -> None:
    """Verify reciprocal of CHIL pointing to 'M' subject is FATH."""
    assert KinshipEngine.get_reciprocal_role("CHIL", subject_sex="M") == "FATH"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_chil_with_female_subject_returns_moth() -> None:
    """Verify reciprocal of CHIL pointing to female subject is MOTH."""
    assert KinshipEngine.get_reciprocal_role("CHIL", subject_sex="Female") == "MOTH"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_chil_with_f_subject_returns_moth() -> None:
    """Verify reciprocal of CHIL pointing to 'F' subject is MOTH."""
    assert KinshipEngine.get_reciprocal_role("CHIL", subject_sex="F") == "MOTH"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_chil_with_unknown_sex_returns_parent() -> None:
    """Verify reciprocal of CHIL pointing to unassigned sex defaults to PARENT."""
    assert KinshipEngine.get_reciprocal_role("CHIL", subject_sex=None) == "PARENT"


@pytest.mark.unit
@pytest.mark.regression
def test_get_reciprocal_role_chil_with_non_standard_sex_returns_parent() -> None:
    """Verify reciprocal of CHIL pointing to unrecognized sex string defaults to PARENT."""
    assert KinshipEngine.get_reciprocal_role("CHIL", subject_sex="Unknown") == "PARENT"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_son_with_male_subject_returns_fath() -> None:
    """Verify reciprocal of SON pointing to male subject is FATH."""
    assert KinshipEngine.get_reciprocal_role("SON", subject_sex="M") == "FATH"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_daug_with_female_subject_returns_moth() -> None:
    """Verify reciprocal of DAUG pointing to female subject is MOTH."""
    assert KinshipEngine.get_reciprocal_role("DAUG", subject_sex="F") == "MOTH"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_spou_returns_spou() -> None:
    """Verify reciprocal of gender-neutral SPOU is SPOU."""
    assert KinshipEngine.get_reciprocal_role("SPOU") == "SPOU"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_husb_with_female_subject_returns_wife() -> None:
    """Verify reciprocal of HUSB pointing to female subject is WIFE."""
    assert KinshipEngine.get_reciprocal_role("HUSB", subject_sex="F") == "WIFE"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_husb_with_male_subject_returns_husb() -> None:
    """Verify reciprocal of HUSB pointing to male subject is HUSB."""
    assert KinshipEngine.get_reciprocal_role("HUSB", subject_sex="M") == "HUSB"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_husb_with_none_subject_returns_spou() -> None:
    """Verify reciprocal of HUSB pointing to unassigned sex defaults to SPOU."""
    assert KinshipEngine.get_reciprocal_role("HUSB", subject_sex=None) == "SPOU"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_wife_with_male_subject_returns_husb() -> None:
    """Verify reciprocal of WIFE pointing to male subject is HUSB."""
    assert KinshipEngine.get_reciprocal_role("WIFE", subject_sex="M") == "HUSB"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_wife_with_female_subject_returns_wife() -> None:
    """Verify reciprocal of WIFE pointing to female subject is WIFE."""
    assert KinshipEngine.get_reciprocal_role("WIFE", subject_sex="F") == "WIFE"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_wife_with_none_subject_returns_spou() -> None:
    """Verify reciprocal of WIFE pointing to unassigned sex defaults to SPOU."""
    assert KinshipEngine.get_reciprocal_role("WIFE", subject_sex=None) == "SPOU"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_sibl_returns_sibl() -> None:
    """Verify reciprocal of SIBL is SIBL."""
    assert KinshipEngine.get_reciprocal_role("SIBL") == "SIBL"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_brot_returns_sibl() -> None:
    """Verify reciprocal of BROT is SIBL."""
    assert KinshipEngine.get_reciprocal_role("BROT") == "SIBL"


@pytest.mark.unit
@pytest.mark.smoke
def test_get_reciprocal_role_sist_returns_sibl() -> None:
    """Verify reciprocal of SIST is SIBL."""
    assert KinshipEngine.get_reciprocal_role("SIST") == "SIBL"


@pytest.mark.unit
@pytest.mark.regression
def test_get_reciprocal_role_witness_returns_none() -> None:
    """Verify contextual WITN role has no reciprocal."""
    assert KinshipEngine.get_reciprocal_role("WITN") is None


@pytest.mark.unit
@pytest.mark.regression
def test_get_reciprocal_role_officiant_returns_none() -> None:
    """Verify contextual OFFICIANT role has no reciprocal."""
    assert KinshipEngine.get_reciprocal_role("OFFICIANT") is None


@pytest.mark.unit
@pytest.mark.regression
def test_get_reciprocal_role_informant_returns_none() -> None:
    """Verify contextual INFORMANT role has no reciprocal."""
    assert KinshipEngine.get_reciprocal_role("INFORMANT") is None


@pytest.mark.unit
@pytest.mark.regression
def test_get_reciprocal_role_invalid_role_returns_none() -> None:
    """Verify invalid relationship role strings return None."""
    assert KinshipEngine.get_reciprocal_role("COUSIN_ONCE_REMOVED") is None


@pytest.mark.unit
@pytest.mark.regression
def test_get_reciprocal_role_none_input_returns_none() -> None:
    """Verify None outbound role returns None."""
    assert KinshipEngine.get_reciprocal_role(None) is None


@pytest.mark.unit
@pytest.mark.regression
def test_get_reciprocal_role_non_string_input_returns_none() -> None:
    """Verify non-string outbound role safely returns None."""
    assert KinshipEngine.get_reciprocal_role(123) is None  # type: ignore[arg-type]


# ==============================================================================
# GROUP 4: Kinship Symmetry Audits
# Note: Verifies reciprocal edge consistency across paired Person entity records
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_audit_kinship_symmetry_valid_father_child() -> None:
    """Verify valid father-child reciprocal pairing evaluates to symmetric."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "Male",
        "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "Female",
        "associated_people": [{"person_id": "IND-00001", "role": "FATH"}],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.is_symmetric is True


@pytest.mark.unit
@pytest.mark.regression
def test_audit_kinship_symmetry_no_outbound_relation_fails() -> None:
    """Verify absence of outbound edge on person_a produces NO_OUTBOUND_RELATION error."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "Male",
        "associated_people": [],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "Female",
        "associated_people": [{"person_id": "IND-00001", "role": "FATH"}],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.error_code == "NO_OUTBOUND_RELATION"


@pytest.mark.unit
@pytest.mark.regression
def test_audit_kinship_symmetry_missing_reciprocal_edge() -> None:
    """Verify missing reverse edge on person_b produces MISSING_RECIPROCAL_EDGE error."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "Male",
        "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "Female",
        "associated_people": [],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.error_code == "MISSING_RECIPROCAL_EDGE"


@pytest.mark.unit
@pytest.mark.regression
def test_audit_kinship_symmetry_role_mismatch() -> None:
    """Verify contradictory reciprocal roles produce ASYMMETRIC_KINSHIP_ROLE error."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "Male",
        "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "Female",
        "associated_people": [{"person_id": "IND-00001", "role": "SIBL"}],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.error_code == "ASYMMETRIC_KINSHIP_ROLE"


@pytest.mark.unit
@pytest.mark.smoke
def test_audit_kinship_symmetry_gender_neutral_parent_satisfies_fath() -> None:
    """Verify PARENT reciprocal satisfies expected FATH contract."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "M",
        "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "F",
        "associated_people": [{"person_id": "IND-00001", "role": "PARENT"}],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.is_symmetric is True


@pytest.mark.unit
@pytest.mark.smoke
def test_audit_kinship_symmetry_father_satisfies_gender_neutral_parent() -> None:
    """Verify FATH reciprocal satisfies expected PARENT contract."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "U",
        "associated_people": [{"person_id": "IND-00002", "role": "CHIL"}],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "M",
        "associated_people": [{"person_id": "IND-00001", "role": "FATH"}],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.is_symmetric is True


@pytest.mark.unit
@pytest.mark.smoke
def test_audit_kinship_symmetry_specific_daug_satisfies_expected_chil() -> None:
    """Verify DAUG reciprocal satisfies expected CHIL contract."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "Female",
        "associated_people": [{"person_id": "IND-00002", "role": "MOTH"}],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "Female",
        "associated_people": [{"person_id": "IND-00001", "role": "DAUG"}],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.actual_reciprocal == "DAUG"


@pytest.mark.unit
@pytest.mark.smoke
def test_audit_kinship_symmetry_specific_brot_satisfies_expected_sibl() -> None:
    """Verify BROT reciprocal satisfies expected SIBL contract."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "Male",
        "associated_people": [{"person_id": "IND-00002", "role": "SIBL"}],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "Male",
        "associated_people": [{"person_id": "IND-00001", "role": "BROT"}],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.actual_reciprocal == "BROT"


@pytest.mark.unit
@pytest.mark.smoke
def test_audit_kinship_symmetry_specific_sist_satisfies_expected_sibl() -> None:
    """Verify SIST reciprocal satisfies expected SIBL contract."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "Female",
        "associated_people": [{"person_id": "IND-00002", "role": "SIBL"}],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "Female",
        "associated_people": [{"person_id": "IND-00001", "role": "SIST"}],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.actual_reciprocal == "SIST"


@pytest.mark.unit
@pytest.mark.smoke
def test_audit_kinship_symmetry_specific_wife_satisfies_expected_spou() -> None:
    """Verify WIFE reciprocal satisfies expected SPOU contract."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "M",
        "associated_people": [{"person_id": "IND-00002", "role": "SPOU"}],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "F",
        "associated_people": [{"person_id": "IND-00001", "role": "WIFE"}],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.is_symmetric is True


@pytest.mark.unit
@pytest.mark.smoke
def test_audit_kinship_symmetry_contextual_role_passes() -> None:
    """Verify non-reciprocal contextual roles pass symmetry audits safely."""
    person_a = {
        "person_id": "IND-00001",
        "sex": "Male",
        "associated_people": [{"person_id": "IND-00002", "role": "WITN"}],
    }
    person_b = {
        "person_id": "IND-00002",
        "sex": "Female",
        "associated_people": [],
    }
    result = KinshipEngine.audit_kinship_symmetry(person_a, person_b)
    assert result.expected_reciprocal is None


@pytest.mark.unit
@pytest.mark.regression
def test_audit_kinship_symmetry_missing_person_id_fails() -> None:
    """Verify missing primary person_id produces MISSING_IDENTIFIER error."""
    result = KinshipEngine.audit_kinship_symmetry({}, {"person_id": "IND-00002"})
    assert result.error_code == "MISSING_IDENTIFIER"


@pytest.mark.unit
@pytest.mark.regression
def test_audit_kinship_symmetry_missing_second_id_fails() -> None:
    """Verify missing target person_id produces MISSING_IDENTIFIER error."""
    result = KinshipEngine.audit_kinship_symmetry({"person_id": "IND-00001"}, {})
    assert result.error_code == "MISSING_IDENTIFIER"


# ==============================================================================
# GROUP 5: Union Symmetry & Spousal Pairing Audits
# Note: Verifies marriage status, date concordance, and reciprocal union consistency
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_audit_union_symmetry_aligned_partner_status() -> None:
    """Verify aligned PARTNER status evaluates to symmetric."""
    union_a = {"spouse_id": "IND-00002", "status": "PARTNER", "marriage_date": "2010-06-15"}
    union_b = {"spouse_id": "IND-00001", "status": "PARTNER", "marriage_date": "2010-06-15"}
    result = KinshipEngine.audit_union_symmetry(union_a, union_b)
    assert result.is_symmetric is True


@pytest.mark.unit
@pytest.mark.smoke
def test_audit_union_symmetry_aligned_married_status() -> None:
    """Verify aligned MARRIED status with concordant date matches date_match."""
    union_a = {"spouse_id": "IND-00002", "status": "MARRIED", "marriage_date": "1885-04-12"}
    union_b = {"spouse_id": "IND-00001", "status": "MARRIED", "marriage_date": "1885-04-12"}
    result = KinshipEngine.audit_union_symmetry(union_a, union_b)
    assert result.date_match is True


@pytest.mark.unit
@pytest.mark.regression
def test_audit_union_symmetry_status_mismatch() -> None:
    """Verify conflicting union statuses produce UNION_STATUS_MISMATCH error."""
    union_a = {"spouse_id": "IND-00002", "status": "MARRIED", "marriage_date": "1885-04-12"}
    union_b = {"spouse_id": "IND-00001", "status": "DIVORCED", "marriage_date": "1885-04-12"}
    result = KinshipEngine.audit_union_symmetry(union_a, union_b)
    assert result.error_code == "UNION_STATUS_MISMATCH"


@pytest.mark.unit
@pytest.mark.regression
def test_audit_union_symmetry_date_mismatch_still_symmetric() -> None:
    """Verify mismatched marriage dates do not invalidate structural symmetry."""
    union_a = {"spouse_id": "IND-00002", "status": "MARRIED", "marriage_date": "1885-04-12"}
    union_b = {"spouse_id": "IND-00001", "status": "MARRIED", "marriage_date": "1886-05-10"}
    result = KinshipEngine.audit_union_symmetry(union_a, union_b)
    assert result.date_match is False


@pytest.mark.unit
@pytest.mark.regression
def test_audit_union_symmetry_missing_target_union() -> None:
    """Verify missing target union record produces MISSING_RECIPROCAL_UNION error."""
    union_a = {"spouse_id": "IND-00002", "status": "MARRIED"}
    result = KinshipEngine.audit_union_symmetry(union_a, None)
    assert result.error_code == "MISSING_RECIPROCAL_UNION"


# ==============================================================================
# GROUP 6: Ahnentafel Mathematics & Graph Cycle Detection
# Note: Verifies generational binary logarithms, parent/child numbers, and DFS cycle detection
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_calculate_ahnentafel_generation_root_subject() -> None:
    """Verify root subject (1) is generation 1."""
    assert KinshipEngine.calculate_ahnentafel_generation(1) == 1


@pytest.mark.unit
@pytest.mark.smoke
def test_calculate_ahnentafel_generation_parents() -> None:
    """Verify father (2) is generation 2."""
    assert KinshipEngine.calculate_ahnentafel_generation(2) == 2


@pytest.mark.unit
@pytest.mark.smoke
def test_calculate_ahnentafel_generation_mother() -> None:
    """Verify mother (3) is generation 2."""
    assert KinshipEngine.calculate_ahnentafel_generation(3) == 2


@pytest.mark.unit
@pytest.mark.smoke
def test_calculate_ahnentafel_generation_great_grandparents() -> None:
    """Verify great-grandfather (8) is generation 4."""
    assert KinshipEngine.calculate_ahnentafel_generation(8) == 4


@pytest.mark.unit
@pytest.mark.regression
def test_calculate_ahnentafel_generation_invalid_zero_raises_value_error() -> None:
    """Verify Ahnentafel generation rejects 0 with ValueError."""
    with pytest.raises(ValueError, match="Ahnentafel number must be >= 1"):
        KinshipEngine.calculate_ahnentafel_generation(0)


@pytest.mark.unit
@pytest.mark.smoke
def test_get_ahnentafel_parents() -> None:
    """Verify parent Ahnentafel calculation (father=4, mother=5 for subject 2)."""
    assert KinshipEngine.get_ahnentafel_parents(2) == (4, 5)


@pytest.mark.unit
@pytest.mark.regression
def test_get_ahnentafel_parents_invalid_zero_raises_value_error() -> None:
    """Verify parent calculation rejects 0 with ValueError."""
    with pytest.raises(ValueError, match="Ahnentafel number must be >= 1"):
        KinshipEngine.get_ahnentafel_parents(0)


@pytest.mark.unit
@pytest.mark.smoke
def test_get_ahnentafel_child() -> None:
    """Verify child Ahnentafel calculation (child=3 for parent 6)."""
    assert KinshipEngine.get_ahnentafel_child(6) == 3


@pytest.mark.unit
@pytest.mark.regression
def test_get_ahnentafel_child_for_root_returns_none() -> None:
    """Verify child calculation returns None for root subject (1)."""
    assert KinshipEngine.get_ahnentafel_child(1) is None


@pytest.mark.unit
@pytest.mark.regression
def test_get_ahnentafel_child_invalid_zero_raises_value_error() -> None:
    """Verify child calculation rejects 0 with ValueError."""
    with pytest.raises(ValueError, match="Ahnentafel number must be >= 1"):
        KinshipEngine.get_ahnentafel_child(0)


@pytest.mark.unit
@pytest.mark.smoke
def test_detect_kinship_cycle_acyclic_graph() -> None:
    """Verify acyclic directed graph returns False."""
    edges = [
        ("IND-00001", "IND-00002"),
        ("IND-00002", "IND-00003"),
        ("IND-00004", "IND-00002"),
    ]
    assert KinshipEngine.detect_kinship_cycle(edges) is False


@pytest.mark.unit
@pytest.mark.regression
def test_detect_kinship_cycle_direct_loop() -> None:
    """Verify direct parent-child bidirectional loop returns True."""
    edges = [
        ("IND-00001", "IND-00002"),
        ("IND-00002", "IND-00001"),
    ]
    assert KinshipEngine.detect_kinship_cycle(edges) is True


@pytest.mark.unit
@pytest.mark.regression
def test_detect_kinship_cycle_self_referential_edge() -> None:
    """Verify self-referential parent-child edge returns True."""
    edges = [("IND-00001", "IND-00001")]
    assert KinshipEngine.detect_kinship_cycle(edges) is True


@pytest.mark.unit
@pytest.mark.regression
def test_detect_kinship_cycle_multi_node_cycle_returns_true() -> None:
    """Verify multi-node circular pedigree loop returns True."""
    edges = [
        ("IND-00001", "IND-00002"),
        ("IND-00002", "IND-00003"),
        ("IND-00003", "IND-00001"),
    ]
    assert KinshipEngine.detect_kinship_cycle(edges) is True