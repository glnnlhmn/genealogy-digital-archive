# Name: test_facts_insp.py
# Path: tests/tools/ops/test_facts_insp.py

"""
Comprehensive pytest test suite for facts_insp.py (Build 17).
Validates:
- Person display name extraction across multiple schema layouts.
- Record/source URN extraction (scalar, array, nested, fallback).
- Date and year extraction across varying date formats.
- Severity tier classifications (ERROR vs. WARN vs. INFO).
- Conditional CSV deliverable export behavior.
"""

import json
from pathlib import Path
import pytest

from tools.ops.facts_insp import (
    extract_person_name,
    extract_source_keys,
    extract_year,
    normalize_date_str,
    short_fact_id,
    write_audit_deliverables,
)


# --- 1. Unit Tests: Person Display Name Extraction ---

def test_extract_person_name_from_canonical_dict():
    person = {"canonical_name": {"full": "Daniel Webster Lehman", "display": "Daniel Lehman"}}
    assert extract_person_name(person, "IND-00008") == "Daniel Webster Lehman"


def test_extract_person_name_from_canonical_str():
    person = {"canonical_name": "Daniel Webster Lehman"}
    assert extract_person_name(person, "IND-00008") == "Daniel Webster Lehman"


def test_extract_person_name_from_name_dict():
    person = {"name": {"display_name": "Karen Nadine Witmer", "full": "Karen Witmer"}}
    assert extract_person_name(person, "IND-00020") == "Karen Nadine Witmer"


def test_extract_person_name_from_names_list():
    person = {"names": [{"full": "Harold Edward Goddard"}]}
    assert extract_person_name(person, "IND-00143") == "Harold Edward Goddard"


def test_extract_person_name_fallback_to_id():
    person = {}
    assert extract_person_name(person, "IND-99999") == "IND-99999"
    assert extract_person_name(None, "IND-99999") == "IND-99999"


# --- 2. Unit Tests: Source and Record URN Extraction ---

def test_extract_source_keys_singular_dict_scalar():
    fact = {
        "source": {
            "record_urn": "URN:NEWSPAPER:PA:DAUPHIN:HARRISBURG:THE_PATRIOT_NEWS:1964-04-05:PAGE_18:HERSHEY_HILL_CLIMB"
        }
    }
    keys = extract_source_keys(fact)
    assert keys == ["URN:NEWSPAPER:PA:DAUPHIN:HARRISBURG:THE_PATRIOT_NEWS:1964-04-05:PAGE_18:HERSHEY_HILL_CLIMB"]


def test_extract_source_keys_singular_dict_array():
    fact = {
        "source": {
            "record_urn": [
                "URN:CENSUS:US:1840:PA:DAUPHIN:MEMBER-1",
                "URN:CENSUS:US:1840:PA:DAUPHIN:MEMBER-2"
            ]
        }
    }
    keys = extract_source_keys(fact)
    assert keys == [
        "URN:CENSUS:US:1840:PA:DAUPHIN:MEMBER-1",
        "URN:CENSUS:US:1840:PA:DAUPHIN:MEMBER-2"
    ]


def test_extract_source_keys_plural_sources():
    fact = {
        "sources": [
            {"record_urn": "URN:ARCHIVE:DOC_001"},
            {"source_urn": "URN:ARCHIVE:DOC_002"}
        ]
    }
    keys = extract_source_keys(fact)
    assert keys == ["URN:ARCHIVE:DOC_001", "URN:ARCHIVE:DOC_002"]


def test_extract_source_keys_fallback_root():
    fact = {"record_urn": "URN:ROOT:REC_123"}
    assert extract_source_keys(fact) == ["URN:ROOT:REC_123"]


def test_extract_source_keys_empty():
    fact = {"description": "No sources attached"}
    assert extract_source_keys(fact) == []


# --- 3. Unit Tests: Date and Identifier Utilities ---

@pytest.mark.parametrize(
    "date_input,expected_year",
    [
        ({"date_start": "1964-04-05", "modifier": "EXACT"}, 1964),
        ({"date": "1840", "modifier": "ABOUT"}, 1840),
        ({"raw_text": "Born on 2 Apr 1965"}, 1965),
        ("1923-11-12", 1923),
        ("Circa 1888", 1888),
        (None, None),
        ("Unknown", None),
    ],
)
def test_extract_year(date_input, expected_year):
    assert extract_year(date_input) == expected_year


def test_normalize_date_str():
    assert normalize_date_str({"date_start": "1965-04-02"}) == "1965-04-02"
    assert normalize_date_str("1840") == "1840"
    assert normalize_date_str(None) == ""


def test_short_fact_id():
    assert short_fact_id("factoid-3c9a1d4f-b271-49e2-8f32-194b8e217031") == "3c9a1d4f"
    assert short_fact_id("59e1f1e8-897d-4ae5-b3e0-6155fc76b909") == "59e1f1e8"


# --- 4. Integration Test: Deliverables & Conditional CSV Export ---

def test_write_audit_deliverables_with_merges(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.ops.facts_insp.REPORTS_DIR", tmp_path)
    
    timestamp = "20260921_999999"
    findings = [
        {"level": "ERROR", "category": "Temporal", "fact_id": "F1", "person_id": "IND-1", "message": "Err"},
        {"level": "WARN", "category": "Schema", "fact_id": "F2", "person_id": "IND-2", "message": "Warn"},
        {"level": "INFO", "category": "Relational", "fact_id": "F3", "person_id": "IND-3", "message": "Info"},
    ]
    merge_candidates = [
        {
            "primary_id": "F4",
            "absorbed_ids": "F5<br>F6",
            "subject": "IND-4",
            "fact_type": "Other",
            "rationale": "Duplicate URN",
        }
    ]

    json_path, csv_path = write_audit_deliverables(timestamp, 10, findings, merge_candidates)

    assert json_path.exists()
    assert csv_path is not None
    assert csv_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["total_findings"] == 3
    assert payload["counts"]["errors"] == 1
    assert payload["counts"]["warnings"] == 1
    assert payload["counts"]["info"] == 1
    assert payload["counts"]["proposals"] == 1


def test_write_audit_deliverables_suppresses_csv_when_no_merges(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.ops.facts_insp.REPORTS_DIR", tmp_path)
    
    timestamp = "20260921_999998"
    findings = [
        {"level": "WARN", "category": "Schema", "fact_id": "F2", "person_id": "IND-2", "message": "Warn"}
    ]
    merge_candidates = []

    json_path, csv_path = write_audit_deliverables(timestamp, 5, findings, merge_candidates)

    assert json_path.exists()
    assert csv_path is None

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["counts"]["proposals"] == 0
    assert payload["merge_candidates_exported"] is None