# Name: test_gpi.py
# Path: tools/tests/test_gpi.py

import json
from pathlib import Path
import pytest

from tools.ops.gpi import (
    stage_1_validate_syntax,
    stage_2_verify_graph_topology,
    stage_3_deduplication_drift,
    stage_4_canonicalize_locations,
    stage_5_minting_and_rewrite
)


@pytest.fixture
def mock_archive_data(tmp_path):
    loc_file = tmp_path / "locations.json"
    loc_data = {
        "$schema": "schemas/entities/location_registry.schema.json",
        "schema_version": "1.0.0",
        "total_locations": 1,
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
                        "country": "USA"
                    }
                }
            }
        ]
    }
    loc_file.write_text(json.dumps(loc_data), encoding="utf-8")

    index_file = tmp_path / "location_index.json"
    index_data = {
        "schema_version": "1.0.0",
        "redirects": {
            "west pennsboro, pa": {
                "location_id": "LOC-00001",
                "standardized": "West Pennsboro Township, Cumberland County, Pennsylvania, USA"
            }
        }
    }
    index_file.write_text(json.dumps(index_data), encoding="utf-8")

    people_file = tmp_path / "people.json"
    people_data = {
        "schema_version": "1.0.2",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00000",
                "display_name": "Root Ancestor",
                "canonical_name": {"given": "Root", "surname": "Ancestor"},
                "associated_people": [{"person_id": "IND-00001", "role": "CHIL"}]
            },
            {
                "person_id": "IND-00001",
                "display_name": "Existing Parent",
                "canonical_name": {"given": "Existing", "surname": "Parent", "birth_year": {"year": 1800}},
                "associated_people": [{"person_id": "IND-00000", "role": "FATH"}]
            }
        ]
    }
    people_file.write_text(json.dumps(people_data), encoding="utf-8")

    return {
        "loc_data": loc_data,
        "index_data": index_data,
        "people_data": people_data
    }


def test_stage_1_syntax_validation(tmp_path):
    valid_pep = tmp_path / "pep-let-001.json"
    valid_pep.write_text(json.dumps({
        "person_id": "TMP-00001",
        "display_name": "Test Child",
        "canonical_name": {"given": "Test", "surname": "Child"}
    }), encoding="utf-8")

    records, files = stage_1_validate_syntax([valid_pep], verbose=False)
    assert len(records) == 1
    assert records[0]["person_id"] == "TMP-00001"
    assert len(files) == 1


def test_stage_2_graph_topology(mock_archive_data, tmp_path):
    existing_people = mock_archive_data["people_data"]["persons"]

    connected_record = {
        "person_id": "TMP-00002",
        "display_name": "Linked Child",
        "canonical_name": {"given": "Linked", "surname": "Child"},
        "associated_people": [{"person_id": "IND-00001", "role": "FATH"}]
    }
    f1 = tmp_path / "pep-let-linked.json"
    f1.write_text(json.dumps(connected_record), encoding="utf-8")

    orphan_record = {
        "person_id": "TMP-00003",
        "display_name": "Orphan Child",
        "canonical_name": {"given": "Orphan", "surname": "Child"}
    }
    f2 = tmp_path / "pep-let-orphan.json"
    f2.write_text(json.dumps(orphan_record), encoding="utf-8")

    records, files = stage_2_verify_graph_topology(
        [connected_record, orphan_record],
        [f1, f2],
        existing_people,
        verbose=False
    )

    assert len(records) == 1
    assert records[0]["person_id"] == "TMP-00002"


def test_stage_3_deduplication(mock_archive_data, tmp_path):
    existing_people = mock_archive_data["people_data"]["persons"]

    dup_record = {
        "person_id": "TMP-00004",
        "display_name": "Existing Parent",
        "canonical_name": {"given": "Existing", "surname": "Parent", "birth_year": {"year": 1800}}
    }
    f1 = tmp_path / "pep-let-dup.json"
    f1.write_text(json.dumps(dup_record), encoding="utf-8")

    records, files = stage_3_deduplication_drift([dup_record], [f1], existing_people)
    assert len(records) == 0


def test_stage_4_location_canonicalization(mock_archive_data, tmp_path):
    locations_entity = mock_archive_data["loc_data"]
    location_index = mock_archive_data["index_data"]

    record = {
        "person_id": "TMP-00005",
        "display_name": "Loc Test",
        "canonical_name": {"given": "Loc", "surname": "Test"},
        "vitals": {
            "birth": {
                "place": {
                    "standardized": "West Pennsboro, PA",
                    "verbatim": "West Pennsboro, PA"
                }
            }
        }
    }
    f1 = tmp_path / "pep-let-loc.json"
    f1.write_text(json.dumps(record), encoding="utf-8")

    records, files = stage_4_canonicalize_locations(
        [record], [f1], locations_entity, location_index, verbose=False
    )

    assert len(records) == 1
    resolved_place = records[0]["vitals"]["birth"]["place"]["standardized"]
    assert resolved_place == "West Pennsboro Township, Cumberland County, Pennsylvania, USA"


def test_stage_5_minting_and_rewrite():
    staged = [
        {
            "person_id": "TMP-00001",
            "display_name": "Son",
            "canonical_name": {"given": "Son", "surname": "Lehman"},
            "associated_people": [{"person_id": "TMP-00002", "role": "FATH"}]
        },
        {
            "person_id": "TMP-00002",
            "display_name": "Father",
            "canonical_name": {"given": "Father", "surname": "Lehman"},
            "associated_people": [{"person_id": "TMP-00001", "role": "CHIL"}]
        }
    ]
    existing = [{"person_id": "IND-00010", "display_name": "Old", "canonical_name": {"given": "Old", "surname": "Lehman"}}]

    minted, _ = stage_5_minting_and_rewrite(staged, existing)

    assert minted[0]["person_id"] == "IND-00011"
    assert minted[1]["person_id"] == "IND-00012"
    assert minted[0]["associated_people"][0]["person_id"] == "IND-00012"
    assert minted[1]["associated_people"][0]["person_id"] == "IND-00011"