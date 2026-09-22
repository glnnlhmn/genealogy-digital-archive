# Name: test_facts_insp.py
# Path: tests/integration/test_facts_insp.py

import json
import logging
import uuid
import pytest
from pathlib import Path

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops import facts_insp
from tools.ops.facts_insp import (
    extract_person_name,
    extract_person_lifespan,
    extract_source_keys,
    extract_year,
    normalize_date_str,
    short_fact_id,
    write_audit_deliverables,
    inspect_facts,
)


@pytest.fixture
def mock_insp_env(tmp_path, monkeypatch):
    """Sets up an isolated filesystem environment by rebinding the GDAConfig singleton."""
    reports_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"
    entities_dir = tmp_path / "data" / "entities"

    reports_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    entities_dir.mkdir(parents=True, exist_ok=True)

    mock_config = GDAConfig(root=tmp_path, manifest={})

    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.facts_insp.CONFIG", mock_config)

    test_logger = logging.getLogger("facts_insp_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    return {
        "root": tmp_path,
        "config": mock_config,
        "facts_file": mock_config.facts,
        "people_file": mock_config.people,
        "reports_dir": mock_config.reports,
        "logger": test_logger,
    }


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
    assert extract_person_name({}, "IND-99999") == "IND-99999"
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
                "URN:CENSUS:US:1840:PA:DAUPHIN:MEMBER-2",
            ]
        }
    }
    keys = extract_source_keys(fact)
    assert keys == [
        "URN:CENSUS:US:1840:PA:DAUPHIN:MEMBER-1",
        "URN:CENSUS:US:1840:PA:DAUPHIN:MEMBER-2",
    ]


def test_extract_source_keys_plural_sources():
    fact = {
        "sources": [
            {"record_urn": "URN:ARCHIVE:DOC_001"},
            {"source_urn": "URN:ARCHIVE:DOC_002"},
        ]
    }
    keys = extract_source_keys(fact)
    assert keys == ["URN:ARCHIVE:DOC_001", "URN:ARCHIVE:DOC_002"]


def test_extract_source_keys_fallback_root():
    fact = {"record_urn": "URN:ROOT:REC_123"}
    assert extract_source_keys(fact) == ["URN:ROOT:REC_123"]


def test_extract_source_keys_empty():
    assert extract_source_keys({"description": "No sources attached"}) == []


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


# --- 4. Integration Tests: Deliverables & Conditional CSV Export ---

def test_write_audit_deliverables_with_merges(mock_insp_env):
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

    json_path, csv_path = write_audit_deliverables(
        timestamp, 10, findings, merge_candidates, reports_dir=mock_insp_env["reports_dir"]
    )

    assert json_path.exists()
    assert csv_path is not None
    assert csv_path.exists()

    payload = GDAUtil.load_json(json_path)
    assert payload["total_findings"] == 3
    assert payload["counts"]["errors"] == 1
    assert payload["counts"]["warnings"] == 1
    assert payload["counts"]["info"] == 1
    assert payload["counts"]["proposals"] == 1


def test_write_audit_deliverables_suppresses_csv_when_no_merges(mock_insp_env):
    timestamp = "20260921_999998"
    findings = [
        {"level": "WARN", "category": "Schema", "fact_id": "F2", "person_id": "IND-2", "message": "Warn"}
    ]
    merge_candidates = []

    json_path, csv_path = write_audit_deliverables(
        timestamp, 5, findings, merge_candidates, reports_dir=mock_insp_env["reports_dir"]
    )

    assert json_path.exists()
    assert csv_path is None

    payload = GDAUtil.load_json(json_path)
    assert payload["counts"]["proposals"] == 0
    assert payload["merge_candidates_exported"] is None


# --- 5. Integration Tests: Audit Engine Execution & Rule Enforcement ---

def test_inspect_facts_missing_file(mock_insp_env):
    """Verifies that inspecting a non-existent facts file exits with code 1."""
    code = inspect_facts(
        facts_path=mock_insp_env["facts_file"],
        people_path=mock_insp_env["people_file"],
        reports_dir=mock_insp_env["reports_dir"],
        logger=mock_insp_env["logger"],
    )
    assert code == 1


def test_inspect_facts_clean_registry_exits_zero(mock_insp_env):
    """Verifies that a conformant facts registry generates zero errors and exits with code 0."""
    uid = str(uuid.uuid4())
    facts_payload = {
        "facts": [
            {
                "fact_id": uid,
                "person_id": "IND-001",
                "fact_type": "Birth",
                "date": {"date_start": "1900-01-01", "modifier": "EXACT"},
            }
        ]
    }
    people_payload = {
        "people": [
            {
                "person_id": "IND-001",
                "canonical_name": "John Doe",
                "vitals": {"birth": {"date": "1900-01-01"}},
            }
        ]
    }
    GDAUtil.save_json(mock_insp_env["facts_file"], facts_payload)
    GDAUtil.save_json(mock_insp_env["people_file"], people_payload)

    code = inspect_facts(
        facts_path=mock_insp_env["facts_file"],
        people_path=mock_insp_env["people_file"],
        reports_dir=mock_insp_env["reports_dir"],
        logger=mock_insp_env["logger"],
    )
    assert code == 0


def test_inspect_facts_post_mortem_exemption(mock_insp_env):
    """Verifies that post-mortem fact types (e.g., Parentage, Burial) do not trigger biological errors."""
    uid = str(uuid.uuid4())
    facts_payload = {
        "facts": [
            {
                "fact_id": uid,
                "person_id": "IND-001",
                "fact_type": "Parentage",
                "date": {"date_start": "1960-01-01", "modifier": "EXACT"},
            }
        ]
    }
    people_payload = {
        "people": [
            {
                "person_id": "IND-001",
                "canonical_name": "Parent Person",
                "vitals": {"birth": {"date": "1890-01-01"}, "death": {"date": "1950-01-01"}},
            }
        ]
    }
    GDAUtil.save_json(mock_insp_env["facts_file"], facts_payload)
    GDAUtil.save_json(mock_insp_env["people_file"], people_payload)

    code = inspect_facts(
        facts_path=mock_insp_env["facts_file"],
        people_path=mock_insp_env["people_file"],
        reports_dir=mock_insp_env["reports_dir"],
        logger=mock_insp_env["logger"],
    )
    # Parentage occurring in 1960 after death in 1950 is exempt; no ERROR findings produced
    assert code == 0


def test_inspect_facts_flags_non_exempt_post_mortem(mock_insp_env):
    """Verifies that non-exempt post-mortem fact types (e.g., Residence) trigger biological ERROR."""
    uid = str(uuid.uuid4())
    facts_payload = {
        "facts": [
            {
                "fact_id": uid,
                "person_id": "IND-001",
                "fact_type": "Residence",
                "date": {"date_start": "1960-01-01", "modifier": "EXACT"},
            }
        ]
    }
    people_payload = {
        "people": [
            {
                "person_id": "IND-001",
                "canonical_name": "Deceased Subject",
                "vitals": {"birth": {"date": "1890-01-01"}, "death": {"date": "1950-01-01"}},
            }
        ]
    }
    GDAUtil.save_json(mock_insp_env["facts_file"], facts_payload)
    GDAUtil.save_json(mock_insp_env["people_file"], people_payload)

    code = inspect_facts(
        facts_path=mock_insp_env["facts_file"],
        people_path=mock_insp_env["people_file"],
        reports_dir=mock_insp_env["reports_dir"],
        logger=mock_insp_env["logger"],
    )
    assert code == 2