# Name: test_gpi_unit.py
# Path: tests/unit/test_gpi_unit.py

"""Unit test harness for GPI (Genealogy Person Intake Pipeline).

Focuses on pure functional stage logic in memory: graph edge resolution,
relational chronology filtering, fingerprint collisions, location resolution,
and sequential identifier allocation.
"""

from pathlib import Path
import pytest

from tools.ops.gpi import (
    stage_0_discovery,
    stage_1_validate_syntax,
    stage_2_verify_graph_topology,
    stage_2b_verify_relational_chronology,
    stage_3_deduplication_drift,
    stage_4_canonicalize_locations,
    stage_5_minting_and_rewrite,
)


@pytest.mark.unit
def test_stage_1_missing_schema_direct(tmp_path):
    """Verifies stage_1 returns empty lists when schema path does not exist."""
    fake_schema = tmp_path / "does_not_exist.json"
    recs, files = stage_1_validate_syntax([], person_schema_path=fake_schema)
    assert recs == []
    assert files == []


@pytest.mark.unit
def test_stage_2_missing_root_in_graph():
    """Verifies stage_2 quarantines all records if IND-00000 is not in graph."""
    staged_records = [
        {"person_id": "TMP-00001", "associated_people": [{"person_id": "IND-00001", "role": "FATH"}]}
    ]
    staged_files = [Path("pep-let-001.json")]
    existing = [
        {"person_id": "IND-00001", "associated_people": []}
    ]

    verified_recs, verified_files = stage_2_verify_graph_topology(
        staged_records, staged_files, existing, quarantine_dir=Path(".")
    )
    assert verified_recs == []
    assert verified_files == []


@pytest.mark.unit
def test_stage_4_resolve_place_edge_cases():
    """Verifies stage_4 handles non-dict places and missing standardized keys gracefully."""
    staged_records = [
        {"person_id": "TMP-00001", "vitals": {"birth": {"place": "A string instead of dict"}}},
        {"person_id": "TMP-00002", "vitals": {"birth": {"place": {}}}},
        {"person_id": "TMP-00003", "vitals": {}},
    ]
    staged_files = [Path("p1.json"), Path("p2.json"), Path("p3.json")]
    loc_entity = {"locations": []}
    loc_index = {"redirects": {}}

    passed_recs, passed_files = stage_4_canonicalize_locations(
        staged_records, staged_files, loc_entity, loc_index
    )
    assert len(passed_recs) == 3
    assert len(passed_files) == 3


@pytest.mark.unit
def test_stage_5_minting_with_non_standard_existing_ids():
    """Verifies stage_5 handles non-standard ID formats in existing registry without error."""
    staged = [{"person_id": "TMP-00001", "associated_people": []}]
    existing = [
        {"person_id": "LEGACY_PERSON_1"},
        {"person_id": "IND-00005"},
    ]

    minted, updated_existing = stage_5_minting_and_rewrite(staged, existing)
    assert minted[0]["person_id"] == "IND-00006"


@pytest.mark.unit
def test_stage_5_non_reciprocal_role_passthrough():
    """Verifies associated roles not in reciprocal_map do not generate inverse links."""
    staged = [{
        "person_id": "TMP-00001",
        "display_name": "Associate",
        "associated_people": [{"person_id": "IND-00001", "role": "WITNESS"}],
    }]
    existing = [{
        "person_id": "IND-00001",
        "display_name": "Existing Record",
        "associated_people": [],
    }]

    minted, updated_existing = stage_5_minting_and_rewrite(staged, existing)
    assert minted[0]["person_id"] == "IND-00002"
    # Existing person should not receive an inverse link for WITNESS
    assert updated_existing[0]["associated_people"] == []


@pytest.mark.unit
def test_stage_4_unresolved_place_branch():
    """Verifies resolve_place returns False, None when place is unrecognized (Line 370)."""
    staged = [{
        "person_id": "TMP-00001",
        "vitals": {"birth": {"place": {"standardized": "Completely Unregistered Place"}}},
    }]
    recs, files = stage_4_canonicalize_locations(
        staged, [Path("p1.json")], {"locations": []}, {"redirects": {}}
    )
    assert recs == []
    assert files == []


@pytest.mark.unit
def test_stage_5_association_missing_person_id_branch():
    """Verifies stage_5 handles association objects without person_id or unmapped IDs."""
    staged = [{
        "person_id": "TMP-00001",
        "associated_people": [
            {"role": "FATH"},  # missing person_id
            {"person_id": "UNMAPPED-01", "role": "MOTH"},  # not in id_map or existing
        ],
    }]
    existing = [{"person_id": "IND-00001", "associated_people": []}]

    minted, updated_existing = stage_5_minting_and_rewrite(staged, existing)
    assert minted[0]["person_id"] == "IND-00002"


@pytest.mark.unit
def test_stage_2b_indirect_message_mention_quarantine(monkeypatch):
    """Exercises lines 260-267 where staged ID is only detected inside finding message."""
    from tools.ops.gpa import RegistryAuditor

    staged = [{
        "person_id": "TMP-00777",
        "display_name": "Indirect Match",
        "canonical_name": {"given": "Indirect", "surname": "Match"},
    }]
    staged_files = [Path("pep-let-indirect.json")]
    existing = [{"person_id": "IND-00000"}]

    def mock_audit(self):
        self.findings.critical.append({
            "rule": "CHRONO_PARENT_TOO_YOUNG",
            "person_id": "IND-00000",
            "message": "Parent IND-00000 too young for child TMP-00777",
        })

    monkeypatch.setattr(RegistryAuditor, "audit_biological_chronology", mock_audit)

    passed_recs, passed_files = stage_2b_verify_relational_chronology(
        staged, staged_files, existing, quarantine_dir=Path(".")
    )
    assert passed_recs == []
    assert passed_files == []


@pytest.mark.unit
def test_stage_4_resolve_place_unregistered_fallback():
    """Exercises line 370 (return False, None) for unrecognized place string."""
    staged = [{
        "person_id": "TMP-00001",
        "vitals": {"birth": {"place": {"standardized": "Unknown Territory"}}},
    }]
    recs, files = stage_4_canonicalize_locations(
        staged, [Path("p1.json")], {"locations": []}, {"redirects": {}}, quarantine_dir=Path(".")
    )
    assert recs == []
    assert files == []


@pytest.mark.unit
def test_stage_5_loop_edge_branches():
    """Exercises lines 496->500, 515->517, 523->520 with unmapped or empty target references."""
    staged = [{
        "person_id": "TMP-00001",
        "associated_people": [
            {"role": "FATH"},  # Missing person_id (496->500 bypass)
            {"person_id": "UNMAPPED-99", "role": "FATH"},  # Not in id_map (496->500)
            {"person_id": "IND-00001", "role": "WITNESS"},  # Not in reciprocal_map (515->517)
        ],
    }]
    existing = [
        {"person_id": "IND-00001", "associated_people": []},
        {"person_id": "IND-00002", "associated_people": [{"person_id": "IND-00003", "role": "CHIL"}]},
    ]

    minted, updated_existing = stage_5_minting_and_rewrite(staged, existing)
    assert minted[0]["person_id"] == "IND-00003"
