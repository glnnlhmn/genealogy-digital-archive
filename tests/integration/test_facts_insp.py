# Name: test_facts_insp.py
# Path: tests/integration/test_facts_insp.py
# Version: 1.0.1+build.20260927.01

"""Integration test suite for FACTS_INSP (Fact Registry Inspection Engine).

Operational Role:
    Validates the four-stage inspection engine across master fact entities:
    - Stage 1: Schema conformance, UUID formatting, and controlled vocabularies.
    - Stage 2: Biological and chronological plausibility (anachronisms, bounds,
      and mandatory post-mortem relational exemptions for Death, Burial,
      Probate, Association, and Parentage).
    - Stage 3: Deduplication and consolidation proposal candidate detection.
    - Stage 4: Relational consistency (union reciprocity and divorce cross-validation).
    - CLI execution, arguments, and parameter failure pathways.

Test Structure & Protocol:
    - Atomized tests: Each validation rule and edge defect is verified in an
      isolated test function with 1:1 assertion reporting.
    - Fully decorated: Globally marked with @pytest.mark.integration; individual
      smoke checks tagged with @pytest.mark.smoke; defect rules tagged with
      @pytest.mark.regression.
    - Dependencies: Requires tools/ops/facts_insp.py, GDAConfig, GDAUtil, and
      isolated filesystem sandbox via tmp_path.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Tuple
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops.facts_insp import FactInspector, run_cli

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_facts_env(tmp_path: Path) -> Tuple[GDAConfig, Path, Path, Dict[str, Any], Dict[str, Any]]:
    """Sets up mock entities directories and sample facts/people payloads."""
    root_dir = tmp_path / "genealogy-digital-archive"
    entities_dir = root_dir / "data" / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)

    people_payload = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.1",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-25T06:00:00Z",
        "total_persons": 2,
        "persons": [
            {
                "person_id": "IND-00001",
                "display_name": "John Doe",
                "canonical_name": {
                    "given": "John",
                    "surname": "Doe",
                    "birth_year": {"year": 1850, "modifier": "EXACT"},
                    "death_year": {"year": 1920, "modifier": "EXACT"},
                },
                "vitals": {
                    "birth": {"date": {"date_start": "1850-01-01", "modifier": "EXACT"}},
                    "death": {"date": {"date_start": "1920-01-01", "modifier": "EXACT"}},
                },
                "unions": [
                    {
                        "spouse_id": "IND-00002",
                        "status": "MARRIED",
                        "marriage_date": {"date_start": "1875-06-15", "modifier": "EXACT"},
                    }
                ],
            },
            {
                "person_id": "IND-00002",
                "display_name": "Jane Smith",
                "canonical_name": {
                    "given": "Jane",
                    "surname": "Smith",
                    "birth_year": {"year": 1855, "modifier": "EXACT"},
                    "death_year": {"year": 1930, "modifier": "EXACT"},
                },
                "vitals": {
                    "birth": {"date": {"date_start": "1855-05-10", "modifier": "EXACT"}},
                    "death": {"date": {"date_start": "1930-10-10", "modifier": "EXACT"}},
                },
                "unions": [
                    {
                        "spouse_id": "IND-00001",
                        "status": "MARRIED",
                        "marriage_date": {"date_start": "1875-06-15", "modifier": "EXACT"},
                    }
                ],
            },
        ],
    }

    facts_payload = {
        "$schema": "schemas/entities/fact_registry.schema.json",
        "schema_version": "1.0.1",
        "created_at": "2026-01-01T00:00:00Z",
        "last_modified": "2026-09-25T06:00:00Z",
        "facts": [
            {
                "fact_id": "11111111-1111-4111-8111-111111111111",
                "person_id": "IND-00001",
                "fact_type": "Marriage",
                "date": {"date_start": "1875-06-15", "modifier": "EXACT"},
                "associated_people": [{"person_id": "IND-00002", "role": "Spouse"}],
            },
            {
                "fact_id": "22222222-2222-4222-8222-222222222222",
                "person_id": "IND-00001",
                "fact_type": "Burial",
                "date": {"date_start": "1920-01-05", "modifier": "EXACT"},
            },
            {
                "fact_id": "33333333-3333-4333-8333-333333333333",
                "person_id": "IND-00001",
                "fact_type": "Parentage",
                "date": {"date_start": "1925-06-01", "modifier": "EXACT"},
            },
        ],
    }

    p_path = entities_dir / "people.json"
    f_path = entities_dir / "facts.json"
    GDAUtil.save_json(p_path, people_payload)
    GDAUtil.save_json(f_path, facts_payload)

    config = GDAConfig(root_dir)
    return config, f_path, p_path, facts_payload, people_payload


# ==============================================================================
# 1. CORE SANITY & EXEMPTION AUDITS
# ==============================================================================

@pytest.mark.smoke
def test_facts_insp_passes_valid_registry(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies that an error-free facts and people payload completes cleanly."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    assert results["errors_count"] == 0
    assert results["warnings_count"] == 0


@pytest.mark.smoke
@pytest.mark.regression
def test_facts_insp_exempts_post_mortem_facts(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies Burial and Parentage assertions after death apply post-mortem exemption."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    assert results["errors_count"] == 0
    assert any(i["rule"] == "POST_MORTEM_EXEMPTION_APPLIED" for i in results["info"])


# ==============================================================================
# 2. BIOLOGICAL & CHRONOLOGICAL CHECKS
# ==============================================================================

@pytest.mark.regression
def test_facts_insp_flags_non_exempt_post_death_events(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies that non-exempt events (Residence) occurring after death raise ANACHRONISTIC_POST_DEATH."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"].append({
        "fact_id": "44444444-4444-4444-8444-444444444444",
        "person_id": "IND-00001",
        "fact_type": "Residence",
        "date": {"date_start": "1928-01-01", "modifier": "EXACT"},
    })
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    assert any(e["rule"] == "ANACHRONISTIC_POST_DEATH" for e in results["errors"])


@pytest.mark.regression
def test_facts_insp_flags_anachronistic_pre_birth_events(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies assertions occurring prior to subject birth raise ANACHRONISTIC_PRE_BIRTH."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"].append({
        "fact_id": "55555555-5555-4555-8555-555555555555",
        "person_id": "IND-00001",
        "fact_type": "Occupation",
        "date": {"date_start": "1840-01-01", "modifier": "EXACT"},
    })
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    assert any(e["rule"] == "ANACHRONISTIC_PRE_BIRTH" for e in results["errors"])


# ==============================================================================
# 3. RELATIONAL & DEDUPLICATION CHECKS
# ==============================================================================

@pytest.mark.regression
def test_facts_insp_cross_validates_unions(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies that union marriage dates conflicting with fact records trigger warning."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"][0]["date"]["date_start"] = "1880-01-01"
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    assert any(w["rule"] == "UNION_MARRIAGE_DATE_MISMATCH" for w in results["warnings"])


@pytest.mark.smoke
@pytest.mark.regression
def test_facts_insp_flags_dedup_collisions(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies redundant facts generate DEDUP_EVENT_COLLISION and merge proposals."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"].append({
        "fact_id": "66666666-6666-4666-8666-666666666666",
        "person_id": "IND-00001",
        "fact_type": "Marriage",
        "date": {"date_start": "1875-06-15", "modifier": "EXACT"},
    })
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    assert any(w["rule"] == "DEDUP_EVENT_COLLISION" for w in results["warnings"])
    assert results["merge_proposals_count"] > 0


@pytest.mark.regression
def test_facts_insp_union_divorce_status_mismatch(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies divorce assertion against a person whose union status is MARRIED raises warning."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"].append({
        "fact_id": "77777777-7777-4777-8777-777777777777",
        "person_id": "IND-00001",
        "fact_type": "Divorce",
        "date": {"date_start": "1890-01-01", "modifier": "EXACT"},
        "associated_people": [{"person_id": "IND-00002"}],
    })
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    warn_rules = {w["rule"] for w in results["warnings"]}
    assert "UNION_STATUS_DIVORCE_MISMATCH" in warn_rules


@pytest.mark.regression
def test_facts_insp_union_fact_missing_from_person(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies marriage facts pointing to individuals without recorded unions raise warning."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"].append({
        "fact_id": "88888888-8888-4888-8888-888888888888",
        "person_id": "IND-00002",
        "fact_type": "Marriage",
        "date": {"date_start": "1900-01-01", "modifier": "EXACT"},
        "associated_people": [{"person_id": "IND-00001"}],
    })
    p_payload["persons"][1]["unions"] = []
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    warn_rules = {w["rule"] for w in results["warnings"]}
    assert "UNION_FACT_NOT_IN_PERSON" in warn_rules


# ==============================================================================
# 4. ATOMIZED SCHEMA CONFORMANCE & VOCABULARY AUDITS
# ==============================================================================

@pytest.mark.regression
def test_schema_flags_missing_envelope_property(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies envelope lacking $schema property triggers ENV_PROPERTY_MISSING warning."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    del f_payload["$schema"]
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    warn_rules = {w["rule"] for w in results["warnings"]}
    assert "ENV_PROPERTY_MISSING" in warn_rules


@pytest.mark.regression
def test_schema_flags_invalid_uuid_format(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies non-UUID fact_id formatting triggers UUID_PATTERN_INVALID."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"].append({
        "fact_id": "bad-guid-string",
        "person_id": "IND-00001",
        "fact_type": "Birth",
        "date": {"date_start": "1850-01-01", "modifier": "EXACT"},
    })
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    warn_rules = {w["rule"] for w in results["warnings"]}
    assert "UUID_PATTERN_INVALID" in warn_rules


@pytest.mark.regression
def test_schema_flags_orphaned_person_id(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies fact referencing a person_id not in people.json triggers ORPHANED_PERSON_ID."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"].append({
        "fact_id": "99999999-9999-4999-8999-999999999999",
        "person_id": "IND-99999",
        "fact_type": "Birth",
        "date": {"date_start": "1850-01-01", "modifier": "EXACT"},
    })
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    error_rules = {e["rule"] for e in results["errors"]}
    assert "ORPHANED_PERSON_ID" in error_rules


@pytest.mark.regression
def test_schema_flags_invalid_fact_type(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies unapproved fact_type triggers FACT_TYPE_INVALID."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"].append({
        "fact_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "person_id": "IND-00001",
        "fact_type": "InvalidFactType",
        "date": {"date_start": "1850-01-01", "modifier": "EXACT"},
    })
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    error_rules = {e["rule"] for e in results["errors"]}
    assert "FACT_TYPE_INVALID" in error_rules


@pytest.mark.regression
def test_schema_flags_invalid_date_format_and_modifier(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies malformed date_start strings and invalid modifiers trigger respective errors."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"].append({
        "fact_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "person_id": "IND-00001",
        "fact_type": "Birth",
        "date": {"date_start": "bad-date-format", "modifier": "INVALID_MOD"},
    })
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    error_rules = {e["rule"] for e in results["errors"]}
    assert "DATE_START_FORMAT_INVALID" in error_rules
    assert "DATE_MODIFIER_INVALID" in error_rules


@pytest.mark.regression
def test_schema_flags_missing_core_identifiers(mock_facts_env: Tuple[Any, ...]) -> None:
    """Verifies null or absent identity keys trigger FACT_ID, PERSON_ID, and FACT_TYPE missing errors."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    logger = logging.getLogger("test_facts_insp")
    f_payload["facts"].append({
        "fact_id": None,
        "person_id": None,
        "fact_type": None,
    })
    inspector = FactInspector(f_payload, p_payload, logger)
    results = inspector.run_all()
    error_rules = {e["rule"] for e in results["errors"]}
    assert "FACT_ID_MISSING" in error_rules
    assert "PERSON_ID_MISSING" in error_rules
    assert "FACT_TYPE_MISSING" in error_rules


# ==============================================================================
# 5. CLI OPERATIONS & PARAMETER VERIFICATION
# ==============================================================================

@pytest.mark.smoke
def test_facts_insp_cli_execution(mock_facts_env: Tuple[Any, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies CLI execution with explicit facts and people paths returns exit code 0."""
    config, f_path, p_path, f_payload, p_payload = mock_facts_env
    monkeypatch.setattr(
        "sys.argv",
        ["facts_insp.py", "-f", str(f_path), "-p", str(p_path), "--verbose", "--export-csv"],
    )
    exit_code = run_cli()
    assert exit_code == 0


@pytest.mark.regression
def test_facts_insp_cli_missing_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies CLI returns exit code 1 when target files do not exist."""
    missing_f = tmp_path / "missing_facts.json"
    missing_p = tmp_path / "missing_people.json"
    monkeypatch.setattr(
        "sys.argv",
        ["facts_insp.py", "-f", str(missing_f), "-p", str(missing_p)],
    )
    exit_code = run_cli()
    assert exit_code == 1