# Name: test_facts_merge.py
# Path: tests/unit/test_facts_merge.py

"""Unit test suite for tools/ops/facts_merge.py with full pytest marker classification."""

import json
from pathlib import Path
import uuid
import pytest
import tools.ops.facts_merge as fm


# =============================================================================
# REFERENCE FIXTURES
# =============================================================================

@pytest.fixture
def golden_people_registry() -> list[dict]:
    return [
        {
            "person_id": "IND-00023",
            "display_name": "Genevieve Louise Thornton",
            "canonical_name": {
                "given": "Genevieve",
                "middle": "Louise",
                "surname": "Thornton",
                "raw_name": "Genevieve Louise Thornton"
            }
        },
        {
            "person_id": "IND-00045",
            "display_name": "Rev. Donald Vance",
            "canonical_name": {
                "given": "Donald",
                "surname": "Vance",
                "suffix": "Rev.",
                "raw_name": "Rev. Donald Vance"
            }
        }
    ]


# =============================================================================
# GROUP 1: CORE ASSERTION & IDENTITY TESTS
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_g1_canonical_identity_minting() -> None:
    cluster = [
        {"fact_id": "00000001-0000-4000-8000-000000000001", "person_id": "IND-00019", "fact_type": "Birth"},
        {"fact_id": "00000001-0000-4000-8000-000000000002", "person_id": "IND-00019", "fact_type": "Birth"}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    
    val = uuid.UUID(canonical["fact_id"])
    assert str(val) == canonical["fact_id"]
    assert canonical["fact_id"] not in [cluster[0]["fact_id"], cluster[1]["fact_id"]]
    assert canonical["person_id"] == "IND-00019"
    assert canonical["fact_type"] == "Birth"
    assert canonical["canonical_fact_id"] is None
    assert canonical["absorbed_at"] is None


@pytest.mark.unit
@pytest.mark.regression
def test_g1_heterogeneous_fact_type_rejection() -> None:
    bad_cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00001", "fact_type": "Birth"},
        {"fact_id": "ID-2", "person_id": "IND-00001", "fact_type": "Death"}
    ]
    with pytest.raises(ValueError, match="Cannot merge heterogeneous fact types"):
        fm.merge_fact_cluster(bad_cluster)


@pytest.mark.unit
@pytest.mark.regression
def test_g1_heterogeneous_person_id_rejection() -> None:
    bad_cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00001", "fact_type": "Birth"},
        {"fact_id": "ID-2", "person_id": "IND-00002", "fact_type": "Birth"}
    ]
    with pytest.raises(ValueError, match="Cannot merge facts across multiple people"):
        fm.merge_fact_cluster(bad_cluster)


# =============================================================================
# GROUP 2: SPATIOTEMPORAL TESTS
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_g2_date_quay_primacy_overrides_granularity() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Birth", "quay_score": 1, "date": {"date_start": "1882-04-14", "modifier": "Exact"}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Birth", "quay_score": 2, "date": {"date_start": "1882-04", "modifier": "Exact"}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["date"]["date_start"] == "1882-04"
    assert canonical["quay_score"] == 2


@pytest.mark.unit
@pytest.mark.regression
def test_g2_date_quay_overridden_candidate_offloads_to_notes() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Birth", "quay_score": 1, "date": {"date_start": "1882-04-14", "modifier": "Exact"}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Birth", "quay_score": 2, "date": {"date_start": "1882-04", "modifier": "Exact"}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    notes = [n for n in canonical["notes"] if n.get("title") == "Alternate Date Context"]
    assert len(notes) == 1
    assert "1882-04-14" in notes[0]["text"]


@pytest.mark.unit
@pytest.mark.regression
def test_g2_date_granularity_tiebreaker_on_equal_quay() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Death", "quay_score": 2, "date": {"date_start": "1882-04", "modifier": "Exact"}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Death", "quay_score": 2, "date": {"date_start": "1882-04-12", "modifier": "Exact"}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["date"]["date_start"] == "1882-04-12"


@pytest.mark.unit
@pytest.mark.regression
def test_g2_date_exact_modifier_tiebreaker_on_equal_quay() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Death", "quay_score": 2, "date": {"date_start": "1882-04-12", "modifier": "About"}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Death", "quay_score": 2, "date": {"date_start": "1882-04-12", "modifier": "Exact"}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["date"]["modifier"] == "Exact"


@pytest.mark.unit
@pytest.mark.regression
def test_g2_date_disjoint_interval_retains_discrete_date() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 3, "date": {"date_start": "1882-04-12", "modifier": "Exact"}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 1, "date": {"date_start": "1875", "date_end": "1880", "modifier": "Between"}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["date"]["date_start"] == "1882-04-12"


@pytest.mark.unit
@pytest.mark.regression
def test_g2_date_disjoint_interval_offloads_as_research_note() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 3, "date": {"date_start": "1882-04-12", "modifier": "Exact"}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 1, "date": {"date_start": "1875", "date_end": "1880", "modifier": "Between"}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    research_notes = [n for n in canonical["notes"] if n.get("category") == "RESEARCH"]
    assert any("1875" in n["text"] for n in research_notes)


@pytest.mark.unit
@pytest.mark.regression
def test_g2_location_state_abbreviation_expansion() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Residence", "quay_score": 3, "location": {"standardized": "Altoona, Blair County, Pennsylvania, USA", "details": {"state_or_province": "PA"}}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Residence", "quay_score": 2, "location": {"standardized": "Altoona, Blair County, Pennsylvania, USA", "details": {"state_or_province": "PA"}}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["location"]["details"]["state_or_province"] == "Pennsylvania"


@pytest.mark.unit
@pytest.mark.regression
def test_g2_location_compound_ordinal_standardization() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Residence", "quay_score": 3, "location": {"standardized": "Altoona, Blair County, Pennsylvania, USA", "details": {"address_line_1": "727 twenty-seventh st"}}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Residence", "quay_score": 1, "location": {"standardized": "Altoona, Blair County, Pennsylvania, USA", "details": {}}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["location"]["details"]["address_line_1"] == "727 27th st"


@pytest.mark.unit
@pytest.mark.smoke
def test_g2_location_detail_enrichment() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Residence", "quay_score": 3, "location": {"standardized": "Altoona, Blair County, Pennsylvania, USA", "details": {"local_jurisdiction": "Altoona"}}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Residence", "quay_score": 2, "location": {"standardized": "Altoona, Blair County, Pennsylvania, USA", "details": {"county": "Blair", "coordinates": {"latitude": 40.51, "longitude": -78.39}}}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    details = canonical["location"]["details"]
    assert details["local_jurisdiction"] == "Altoona"
    assert details["county"] == "Blair"
    assert details["coordinates"]["latitude"] == 40.51
    assert details["coordinates"]["longitude"] == -78.39


@pytest.mark.unit
@pytest.mark.regression
def test_g2_location_verbatim_standard_merge_notice() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Residence", "quay_score": 3, "location": {"standardized": "Altoona, Blair County, Pennsylvania, USA", "verbatim": "Sheet 4B", "details": {}}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Residence", "quay_score": 2, "location": {"standardized": "Altoona, Blair County, Pennsylvania, USA", "verbatim": "City Dir", "details": {}}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["location"]["verbatim"] == fm._FactClusterMerger.VERBATIM_MERGE_NOTICE


@pytest.mark.unit
@pytest.mark.regression
def test_g2_location_conflicting_jurisdictions_retains_highest_quay() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Death", "quay_score": 3, "location": {"standardized": "Harrisburg, Dauphin County, Pennsylvania, USA", "details": {}}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Death", "quay_score": 1, "location": {"standardized": "Carlisle, Cumberland County, Pennsylvania, USA", "details": {}}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["location"]["standardized"] == "Harrisburg, Dauphin County, Pennsylvania, USA"


@pytest.mark.unit
@pytest.mark.regression
def test_g2_location_conflicting_jurisdictions_offloads_to_notes() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Death", "quay_score": 3, "location": {"standardized": "Harrisburg, Dauphin County, Pennsylvania, USA", "details": {}}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Death", "quay_score": 1, "location": {"standardized": "Carlisle, Cumberland County, Pennsylvania, USA", "details": {}}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    notes = [n for n in canonical["notes"] if n.get("title") == "Alternate Location Context"]
    assert len(notes) == 1
    assert "Carlisle, Cumberland County, Pennsylvania, USA" in notes[0]["text"]


# =============================================================================
# GROUP 3: NARRATIVE & CONTEXT TESTS
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_g3_description_highest_quay_and_token_density() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 3, "description": "Wedding ceremony"},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 3, "description": "Solemnization of marriage between Garrison Sterling and Genevieve Thornton"}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["description"] == "Solemnization of marriage between Garrison Sterling and Genevieve Thornton"


@pytest.mark.unit
@pytest.mark.regression
def test_g3_divergent_description_offloaded_as_alternate_context() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 3, "description": "Marriage of Garrison Sterling to Genevieve Thornton"},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 1, "description": "Officiated by Rev. Vance at Grace Methodist Church"}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["description"] == "Marriage of Garrison Sterling to Genevieve Thornton"
    
    notes = [n for n in canonical["notes"] if n.get("title") == "Alternate Description Context"]
    assert len(notes) == 1
    assert "Officiated by Rev. Vance" in notes[0]["text"]


@pytest.mark.unit
@pytest.mark.regression
def test_g3_similar_description_suppression() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 3, "description": "Marriage of Garrison Sterling to Genevieve Thornton"},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 2, "description": "Marriage of Garrison Sterling and Genevieve Thornton"}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    notes = [n for n in canonical["notes"] if n.get("title") == "Alternate Description Context"]
    assert len(notes) == 0


@pytest.mark.unit
@pytest.mark.regression
def test_g3_life_story_deduplication() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Marriage", "life_story": "A summer wedding in Harrisburg."},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Marriage", "life_story": "A summer wedding in Harrisburg. Attended by close family."}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert "A summer wedding in Harrisburg." in canonical["life_story"]
    assert "Attended by close family." in canonical["life_story"]


# =============================================================================
# GROUP 4: ASSOCIATED PEOPLE TESTS
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_g4_person_pre_grounding_to_registry_id(golden_people_registry: list[dict]) -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 3, "associated_people": [{"name": "Genevieve Thornton", "person_id": None, "role": "SPOU", "relation": "Wife"}]},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 2, "associated_people": [{"name": "Genevieve Louise Thornton", "person_id": "IND-00023", "role": "SPOU", "is_primary_subject": True}]}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster, people_registry=golden_people_registry)
    assoc = canonical["associated_people"]
    assert len(assoc) == 1
    assert assoc[0]["person_id"] == "IND-00023"
    assert assoc[0]["name"] == "Genevieve Louise Thornton"
    assert assoc[0]["role"] == "SPOU"
    assert assoc[0]["relation"] == "Wife"
    assert assoc[0]["is_primary_subject"] is True


@pytest.mark.unit
@pytest.mark.regression
def test_g4_person_dual_role_preservation(golden_people_registry: list[dict]) -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 3, "associated_people": [{"name": "Genevieve Louise Thornton", "person_id": "IND-00023", "role": "SPOU"}]},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 2, "associated_people": [{"name": "Genevieve Louise Thornton", "person_id": "IND-00023", "role": "WITN"}]}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster, people_registry=golden_people_registry)
    assoc = canonical["associated_people"]
    assert len(assoc) == 2
    roles = {p["role"] for p in assoc}
    assert roles == {"SPOU", "WITN"}
    for p in assoc:
        assert p["person_id"] == "IND-00023"


@pytest.mark.unit
@pytest.mark.smoke
def test_g4_unlinked_soundex_fuzzy_deduplication() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 1, "associated_people": [{"name": "Johnathon Vance", "person_id": None, "role": "OFFICIANT"}]},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 2, "associated_people": [{"name": "Jonathan Vance", "person_id": None, "role": "OFFICIANT"}]}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assoc = canonical["associated_people"]
    assert len(assoc) == 1
    assert assoc[0]["person_id"] is None
    assert assoc[0]["name"] == "Jonathan Vance"
    assert assoc[0]["role"] == "OFFICIANT"


@pytest.mark.unit
@pytest.mark.regression
def test_g4_distinct_grounded_isolation_never_merges() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 3, "associated_people": [{"name": "Witness One", "person_id": "IND-00077", "role": "WITN"}]},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Marriage", "quay_score": 2, "associated_people": [{"name": "Witness Two", "person_id": "IND-00088", "role": "WITN"}]}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assoc = canonical["associated_people"]
    assert len(assoc) == 2
    assert {p["person_id"] for p in assoc} == {"IND-00077", "IND-00088"}


# =============================================================================
# GROUP 5: EVIDENCE & NOTES TESTS
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_g5_sources_union_and_backfill() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Birth", "source": {"record_urn": "URN:SRC:100", "file_name": "cert.pdf"}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Birth", "source": {"record_urn": "URN:SRC:100", "repository_path": "archives/state/"}},
        {"fact_id": "ID-3", "person_id": "IND-00019", "fact_type": "Birth", "source": {"file_name": "bible_scan.jpg"}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    sources = canonical["source"] if isinstance(canonical["source"], list) else [canonical["source"]]
    assert len(sources) == 2
    
    urn_src = next(s for s in sources if s.get("record_urn") == "URN:SRC:100")
    assert urn_src["file_name"] == "cert.pdf"
    assert urn_src["repository_path"] == "archives/state/"
    
    phys_src = next(s for s in sources if s.get("file_name") == "bible_scan.jpg")
    assert phys_src["file_name"] == "bible_scan.jpg"


@pytest.mark.unit
@pytest.mark.smoke
def test_g5_notes_string_and_dict_normalization() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Birth", "notes": "Simple raw string note."},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Birth", "notes": [{"note_id": "NOT-99999", "category": "RESEARCH", "title": "Old Research", "text": "Detailed note."}]}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    notes = canonical["notes"]
    texts = [n["text"] for n in notes]
    assert "Simple raw string note." in texts
    assert "Detailed note." in texts


@pytest.mark.unit
@pytest.mark.regression
def test_g5_sequential_note_renumbering() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Birth", "notes": "First note."},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Birth", "notes": "Second note."}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    notes = canonical["notes"]
    assert len(notes) == 3
    for idx, n in enumerate(notes, 1):
        assert n["note_id"] == f"NOT-{idx:05d}"


@pytest.mark.unit
@pytest.mark.regression
def test_g5_external_identifiers_union() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Birth", "external_identifiers": {"gedcom_event_id": "E100"}},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Birth", "external_identifiers": {"familysearch_id": "FS-999"}}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    ext = canonical["external_identifiers"]
    assert ext["gedcom_event_id"] == "E100"
    assert ext["familysearch_id"] == "FS-999"


# =============================================================================
# GROUP 6: AUDIT & LIFECYCLE PROVENANCE TESTS
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_g6_oldest_created_at_selection() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Birth", "created_at": "2025-06-15T12:00:00Z"},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Birth", "created_at": "2026-01-02T10:30:00Z"}
    ]
    canonical, _ = fm.merge_fact_cluster(cluster)
    assert canonical["created_at"] == "2025-06-15T12:00:00Z"


@pytest.mark.unit
@pytest.mark.smoke
def test_g6_absorbed_records_provenance_marking() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Birth"},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Birth"}
    ]
    canonical, archived = fm.merge_fact_cluster(cluster)
    assert len(archived) == 2
    for arc in archived:
        assert arc["canonical_fact_id"] == canonical["fact_id"]
        assert arc["absorbed_at"] is not None
        assert arc["updated_at"] is not None


@pytest.mark.unit
@pytest.mark.regression
def test_g6_remerge_prevention_raises_error() -> None:
    cluster = [
        {"fact_id": "ID-1", "person_id": "IND-00019", "fact_type": "Birth", "absorbed_at": "2026-09-27T00:00:00Z", "canonical_fact_id": "CANON-999"},
        {"fact_id": "ID-2", "person_id": "IND-00019", "fact_type": "Birth"}
    ]
    with pytest.raises(ValueError, match="already absorbed"):
        fm.merge_fact_cluster(cluster)


# =============================================================================
# CLI, BATCH & POSTPONED CAPABILITIES TESTS
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_parse_csv_clusters(tmp_path) -> None:
    csv_file = tmp_path / "clusters.csv"
    csv_file.write_text("ID-1,ID-2\nID-3,ID-4,ID-5\nID-SINGLE\n", encoding="utf-8")
    parsed = fm.parse_csv_clusters(csv_file)
    assert len(parsed) == 2
    assert parsed[0] == ["ID-1", "ID-2"]
    assert parsed[1] == ["ID-3", "ID-4", "ID-5"]


@pytest.mark.unit
@pytest.mark.regression
def test_gix_integration_postponed() -> None:
    with pytest.raises(NotImplementedError, match="Automated index rebuilding is postponed"):
        fm._FactClusterMerger._rebuild_indexes()


# =============================================================================
# ITEM 1, ITEM 3 & ITEM 6: PRE-FLIGHT, COMMIT & AUDIT REPORT TESTS
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
@pytest.mark.regression
def test_batch_validation_rejects_overlapping_clusters() -> None:
    clusters = [
        ["ID-1", "ID-2"],
        ["ID-2", "ID-3"]
    ]
    facts = [
        {"fact_id": "ID-1", "person_id": "IND-00001", "fact_type": "Birth"},
        {"fact_id": "ID-2", "person_id": "IND-00001", "fact_type": "Birth"},
        {"fact_id": "ID-3", "person_id": "IND-00001", "fact_type": "Birth"}
    ]
    with pytest.raises(ValueError, match="Batch collision detected"):
        fm.validate_batch_clusters(clusters, facts)


@pytest.mark.unit
@pytest.mark.smoke
@pytest.mark.regression
def test_batch_validation_rejects_pre_absorbed_facts() -> None:
    clusters = [
        ["ID-1", "ID-2"]
    ]
    facts = [
        {"fact_id": "ID-1", "person_id": "IND-00001", "fact_type": "Birth", "absorbed_at": "2026-09-27T00:00:00Z", "canonical_fact_id": "CANON-1"},
        {"fact_id": "ID-2", "person_id": "IND-00001", "fact_type": "Birth"}
    ]
    with pytest.raises(ValueError, match="is already absorbed into canonical"):
        fm.validate_batch_clusters(clusters, facts)


@pytest.mark.unit
@pytest.mark.smoke
def test_dry_run_job_produces_no_backups_or_reports(tmp_path, monkeypatch) -> None:
    entities_dir = tmp_path / "data" / "entities"
    backups_dir = tmp_path / "backups"
    logs_dir = tmp_path / "logs"
    reports_dir = tmp_path / "reports"
    entities_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    facts_path = entities_dir / "facts.json"
    initial_registry = {
        "$schema": "schemas/entities/fact_registry.schema.json",
        "schema_version": "1.0.0",
        "total_facts": 2,
        "facts": [
            {"fact_id": "00000001-0000-4000-8000-000000000001", "person_id": "IND-00019", "fact_type": "Birth", "quay_score": 1, "created_at": "2026-01-01T00:00:00Z"},
            {"fact_id": "00000001-0000-4000-8000-000000000002", "person_id": "IND-00019", "fact_type": "Birth", "quay_score": 2, "created_at": "2026-01-02T00:00:00Z"}
        ]
    }
    facts_path.write_text(json.dumps(initial_registry, indent=2), encoding="utf-8")

    class DummyConfig:
        def __init__(self, root=None):
            self.root = tmp_path
            self.entities = entities_dir
            self.backups = backups_dir
            self.logs = logs_dir
            self.reports = reports_dir
            self.people = tmp_path / "nonexistent_people.json"

    monkeypatch.setattr(fm, "GDAConfig", DummyConfig)

    cluster = [["00000001-0000-4000-8000-000000000001", "00000001-0000-4000-8000-000000000002"]]
    exit_code = fm.run_merge_job(cluster, run_commit=False)
    assert exit_code == 0

    assert len(list(backups_dir.glob("*"))) == 0
    assert len(list(reports_dir.glob("*"))) == 0

    data = json.loads(facts_path.read_text(encoding="utf-8"))
    assert data["total_facts"] == 2


@pytest.mark.unit
@pytest.mark.regression
def test_generate_merge_report_structure(tmp_path) -> None:
    rep_path = tmp_path / "test_report.md"
    canonical = {
        "fact_id": "CANON-001",
        "person_id": "IND-00019",
        "fact_type": "Birth",
        "quay_score": 3,
        "notes": [
            {"category": "RESEARCH", "title": "Alternate Date Context", "text": "Variant date 1882-04-14 from absorbed fact."}
        ]
    }
    archived = [
        {"fact_id": "FACT-001", "canonical_fact_id": "CANON-001"},
        {"fact_id": "FACT-002", "canonical_fact_id": "CANON-001"}
    ]
    backup_file = Path("backups/facts.json.20260927_120000.bk")

    fm.generate_merge_report(
        report_path=rep_path,
        mode="RUN",
        new_canonicals=[canonical],
        archived_constituents=archived,
        backup_file=backup_file
    )

    assert rep_path.is_file()
    content = rep_path.read_text(encoding="utf-8")
    assert "CANON-001" in content
    assert "FACT-001" in content
    assert "FACT-002" in content
    assert "Alternate Date Context" in content
    assert "facts.json.20260927_120000.bk" in content


@pytest.mark.integration
@pytest.mark.regression
def test_run_merge_job_safe_backup_commit_and_report(tmp_path, monkeypatch) -> None:
    entities_dir = tmp_path / "data" / "entities"
    backups_dir = tmp_path / "backups"
    logs_dir = tmp_path / "logs"
    reports_dir = tmp_path / "reports"
    entities_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    facts_path = entities_dir / "facts.json"
    initial_registry = {
        "$schema": "schemas/entities/fact_registry.schema.json",
        "schema_version": "1.0.0",
        "total_facts": 2,
        "facts": [
            {"fact_id": "00000001-0000-4000-8000-000000000001", "person_id": "IND-00019", "fact_type": "Birth", "quay_score": 1, "created_at": "2026-01-01T00:00:00Z"},
            {"fact_id": "00000001-0000-4000-8000-000000000002", "person_id": "IND-00019", "fact_type": "Birth", "quay_score": 2, "created_at": "2026-01-02T00:00:00Z"}
        ]
    }
    facts_path.write_text(json.dumps(initial_registry, indent=2), encoding="utf-8")

    class DummyConfig:
        def __init__(self, root=None):
            self.root = tmp_path
            self.entities = entities_dir
            self.backups = backups_dir
            self.logs = logs_dir
            self.reports = reports_dir
            self.people = tmp_path / "nonexistent_people.json"

    monkeypatch.setattr(fm, "GDAConfig", DummyConfig)

    cluster = [["00000001-0000-4000-8000-000000000001", "00000001-0000-4000-8000-000000000002"]]
    exit_code = fm.run_merge_job(cluster, run_commit=True)
    assert exit_code == 0

    backups = list(backups_dir.glob("facts.json.*.bk"))
    assert len(backups) == 1

    updated_data = json.loads(facts_path.read_text(encoding="utf-8"))
    assert updated_data["total_facts"] == 3
    assert "last_modified" in updated_data
    
    canonical = next(f for f in updated_data["facts"] if f.get("canonical_fact_id") is None)
    assert canonical["quay_score"] == 2

    reports = list(reports_dir.glob("facts_merge_report_*.md"))
    assert len(reports) == 1
    report_text = reports[0].read_text(encoding="utf-8")
    assert "Fact Consolidation Audit Report" in report_text
    assert canonical["fact_id"] in report_text