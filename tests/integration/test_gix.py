# Name: test_gix.py
# Path: tests/integration/test_gix.py
# Version: 1.0.1+build.20260927.01

"""Integration test suite for GIX (Genealogy Indexing Executor).

Operational Role:
    Validates surname index compilation, aliased surname resolution, nuclear
    family group index synthesis against ground truth entities, defensive
    resilience against corrupted records, and explicit NotImplementedError
    enforcement on postponed index generator stubs.

Test Structure & Protocol:
    - Atomized tests: Surname indexing, family group indexing, corrupted data
      handling, and stubs tested as separate isolated functions.
    - Fully decorated: Global integration mark with individual @pytest.mark.smoke
      and @pytest.mark.regression markers.
    - Dependencies: Requires tools/ops/gix.py and hermetic controlled sandbox fixtures.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Tuple
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops.gix import (
    build_surname_index,
    build_family_group_index,
    build_ahnentafel_index,
    build_newspaper_obituary_index,
    build_place_index,
    build_timeline_index,
    build_source_index,
    build_all_indices,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def controlled_env(tmp_path: Path) -> Tuple[Any, logging.Logger]:
    """Creates a hermetic test sandbox with controlled data and mock GDAConfig."""
    data_dir = tmp_path / "data"
    entities_dir = data_dir / "entities"
    indexes_dir = data_dir / "indexes"
    logs_dir = tmp_path / "logs"

    entities_dir.mkdir(parents=True, exist_ok=True)
    indexes_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    people_file = entities_dir / "people.json"
    alias_file = indexes_dir / "surname_aliases.json"

    aliases_data = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": "1.0.1",
        "last_modified": "2026-09-22",
        "total_aliases": 2,
        "description": "Mock alias registry.",
        "aliases": {
            "dietch": "deitch",
            "garberich": "garverich"
        }
    }
    GDAUtil.save_json(alias_file, aliases_data)

    people_data = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": "1.0.0",
        "total_persons": 10,
        "persons": [
            {
                "person_id": "IND-00001",
                "sex": "Male",
                "canonical_name": {"given": "William", "surname": "Lehman"},
                "associated_people": [
                    {"person_id": "IND-00002", "role": "SPOU"},
                    {"person_id": "IND-00004", "role": "SPOU"},
                    {"person_id": "IND-00003", "role": "CHIL"},
                    {"person_id": "IND-00005", "role": "CHIL"}
                ]
            },
            {
                "person_id": "IND-00002",
                "sex": "Female",
                "canonical_name": {"given": "Annie", "surname": "Failor"},
                "associated_people": [
                    {"person_id": "IND-00001", "role": "SPOU"},
                    {"person_id": "IND-00003", "role": "CHIL"}
                ]
            },
            {
                "person_id": "IND-00003",
                "sex": "Female",
                "canonical_name": {
                    "given": "Orpha",
                    "surname": "Lehman",
                    "birth_year": {"year": 1920, "modifier": "EXACT"}
                },
                "associated_people": [
                    {"person_id": "IND-00001", "role": "FATH"},
                    {"person_id": "IND-00002", "role": "MOTH"}
                ]
            },
            {
                "person_id": "IND-00004",
                "sex": "Female",
                "canonical_name": {"given": "Katherine", "surname": "Williams"},
                "associated_people": [
                    {"person_id": "IND-00001", "role": "SPOU"},
                    {"person_id": "IND-00005", "role": "CHIL"}
                ]
            },
            {
                "person_id": "IND-00005",
                "sex": "Male",
                "canonical_name": {
                    "given": "George",
                    "surname": "Lehman",
                    "birth_year": {"year": 1935, "modifier": "EXACT"}
                },
                "associated_people": [
                    {"person_id": "IND-00001", "role": "FATH"},
                    {"person_id": "IND-00004", "role": "MOTH"}
                ]
            },
            {
                "person_id": "IND-00010",
                "sex": "Male",
                "canonical_name": {"given": "John", "surname": "Deitch"},
                "associated_people": [
                    {"person_id": "IND-00011", "role": "SPOU"},
                    {"person_id": "IND-00012", "role": "CHIL"},
                    {"person_id": "IND-00013", "role": "CHIL"}
                ]
            },
            {
                "person_id": "IND-00011",
                "sex": "Female",
                "canonical_name": {"given": "Sarah", "surname": "Miller"},
                "associated_people": [
                    {"person_id": "IND-00010", "role": "SPOU"},
                    {"person_id": "IND-00012", "role": "CHIL"},
                    {"person_id": "IND-00013", "role": "CHIL"}
                ]
            },
            {
                "person_id": "IND-00012",
                "sex": "Female",
                "canonical_name": {
                    "given": "Betty",
                    "surname": "Dietch",
                    "birth_year": {"year": 1950, "modifier": "EXACT"}
                },
                "associated_people": [
                    {"person_id": "IND-00010", "role": "FATH"},
                    {"person_id": "IND-00011", "role": "MOTH", "relationship": "Adoptive mother"}
                ]
            },
            {
                "person_id": "IND-00013",
                "sex": "Male",
                "canonical_name": {
                    "given": "Paul",
                    "surname": "Miller",
                    "birth_year": {"year": 1945, "modifier": "EXACT"}
                },
                "associated_people": [
                    {"person_id": "IND-00011", "role": "MOTH"},
                    {"person_id": "IND-00010", "role": "FATH", "relationship": "Stepfather"}
                ]
            },
            {
                "person_id": "IND-00020",
                "sex": "Female",
                "canonical_name": {"given": "Mary", "surname": "Garberich"},
                "associated_people": [
                    {"person_id": "IND-00021", "role": "CHIL"}
                ]
            },
            {
                "person_id": "IND-00021",
                "sex": "Male",
                "canonical_name": {
                    "given": "James",
                    "surname": "Garberich",
                    "birth_year": {"year": 1960, "modifier": "EXACT"}
                },
                "associated_people": [
                    {"person_id": "IND-00020", "role": "MOTH"}
                ]
            }
        ]
    }
    GDAUtil.save_json(people_file, people_data)

    class MockGDAConfig:
        root = tmp_path
        data = data_dir
        entities = entities_dir
        indexes = indexes_dir
        logs = logs_dir
        temp = tmp_path / "gtemp"
        people = people_file

    logger = setup_logger("test_gix", ephemeral=True, console_level=logging.CRITICAL)
    return MockGDAConfig(), logger


@pytest.fixture
def corrupted_env(tmp_path: Path) -> Tuple[Any, logging.Logger]:
    """Creates a test sandbox loaded with malformed and incomplete entities."""
    data_dir = tmp_path / "data"
    entities_dir = data_dir / "entities"
    indexes_dir = data_dir / "indexes"
    logs_dir = tmp_path / "logs"

    entities_dir.mkdir(parents=True, exist_ok=True)
    indexes_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    people_file = entities_dir / "people.json"

    corrupted_data = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": "1.0.0",
        "total_persons": 7,
        "persons": [
            {
                "sex": "Male",
                "canonical_name": {"given": "Ghost", "surname": "Entity"}
            },
            {
                "person_id": "IND-00100",
                "sex": "Male"
            },
            {
                "person_id": "IND-00101",
                "sex": "Female",
                "canonical_name": {"given": "Nameless"}
            },
            {
                "person_id": "IND-00102",
                "sex": "Male",
                "canonical_name": {"given": "Self", "surname": "Referencing"},
                "associated_people": [
                    {"person_id": "IND-00102", "role": "SPOU"},
                    {"person_id": "IND-00102", "role": "FATH"},
                    {"person_id": "IND-00102", "role": "CHIL"},
                    {"person_id": "IND-99999", "role": "SPOU"},
                    {"person_id": "IND-88888", "role": "CHIL"}
                ]
            },
            {
                "person_id": "IND-00103",
                "sex": "Male",
                "canonical_name": {
                    "given": "BadDate",
                    "surname": "Person",
                    "birth_year": {"year": "UNKNOWN_STRING", "modifier": "APPROX"}
                },
                "associated_people": [
                    {"person_id": "IND-00104", "role": "SPOU"},
                    {"person_id": "IND-00105", "role": "CHIL"}
                ]
            },
            {
                "person_id": "IND-00104",
                "sex": "Female",
                "canonical_name": {
                    "given": "Valid",
                    "surname": "Partner",
                    "birth_year": None
                },
                "associated_people": [
                    {"person_id": "IND-00103", "role": "SPOU"},
                    {"person_id": "IND-00105", "role": "CHIL"}
                ]
            },
            {
                "person_id": "IND-00105",
                "sex": "Female",
                "canonical_name": {
                    "given": "Child",
                    "surname": "Person",
                    "birth_year": {}
                },
                "associated_people": [
                    {"person_id": "IND-00103", "role": "FATH"},
                    {"person_id": "IND-00104", "role": "MOTH"}
                ]
            }
        ]
    }
    GDAUtil.save_json(people_file, corrupted_data)

    class MockCorruptedConfig:
        root = tmp_path
        data = data_dir
        entities = entities_dir
        indexes = indexes_dir
        logs = logs_dir
        temp = tmp_path / "gtemp"
        people = people_file

    logger = setup_logger("test_corrupt_gix", ephemeral=True, console_level=logging.CRITICAL)
    return MockCorruptedConfig(), logger


# ==============================================================================
# 1. GROUND TRUTH INDEX GENERATION TESTS
# ==============================================================================

@pytest.mark.smoke
def test_surname_index_ground_truth(controlled_env: Tuple[Any, logging.Logger]) -> None:
    """Verifies that surname indexing correctly buckets canonical and aliased surnames."""
    config, logger = controlled_env
    target_index = config.indexes / "surname_index.json"

    assert build_surname_index(config, logger) is True
    assert target_index.exists()

    payload = GDAUtil.load_json(target_index)
    surnames = payload.get("surnames", {})

    assert "lehman" in surnames
    assert surnames["lehman"]["total_persons"] == 3

    assert "dietch" not in surnames
    assert "deitch" in surnames
    assert surnames["deitch"]["total_persons"] == 2
    assert "Dietch" in surnames["deitch"]["spelling_variants"]

    assert "garberich" not in surnames
    assert "garverich" in surnames
    assert surnames["garverich"]["total_persons"] == 2
    assert "Garberich" in surnames["garverich"]["spelling_variants"]


@pytest.mark.smoke
def test_family_group_index_ground_truth(controlled_env: Tuple[Any, logging.Logger]) -> None:
    """Verifies exact nuclear family group compilation against known ground truth."""
    config, logger = controlled_env
    target_index = config.indexes / "family_group_index.json"

    assert build_family_group_index(config, logger) is True
    assert target_index.exists()

    payload = GDAUtil.load_json(target_index)
    assert payload["schema_version"] == "1.1.0"
    families = payload.get("families", {})

    assert len(families) == 4
    assert payload["total_families"] == 4

    assert "FAM-00001-A" in families
    fam1_a = families["FAM-00001-A"]
    assert fam1_a["parent_x"]["person_id"] == "IND-00001"
    assert fam1_a["parent_y"]["person_id"] == "IND-00002"
    assert fam1_a["total_children"] == 1
    assert fam1_a["children"][0]["person_id"] == "IND-00003"
    assert fam1_a["children"][0]["relationship_note"] is None

    assert "FAM-00001-B" in families
    fam1_b = families["FAM-00001-B"]
    assert fam1_b["parent_x"]["person_id"] == "IND-00001"
    assert fam1_b["parent_y"]["person_id"] == "IND-00004"
    assert fam1_b["total_children"] == 1
    assert fam1_b["children"][0]["person_id"] == "IND-00005"

    assert "FAM-00010-A" in families
    fam10 = families["FAM-00010-A"]
    assert fam10["total_children"] == 2
    assert fam10["children"][0]["person_id"] == "IND-00013"
    assert fam10["children"][0]["relationship_note"] == "Stepchild of John Deitch"
    assert fam10["children"][1]["person_id"] == "IND-00012"
    assert fam10["children"][1]["relationship_note"] == "Adopted by Sarah Miller"

    assert "FAM-00020-A" in families
    fam20 = families["FAM-00020-A"]
    assert fam20["parent_x"]["person_id"] == "IND-00020"
    assert fam20["parent_y"] is None
    assert fam20["total_children"] == 1
    assert fam20["children"][0]["person_id"] == "IND-00021"


# ==============================================================================
# 2. DEFENSIVE RESILIENCE TESTS
# ==============================================================================

@pytest.mark.regression
def test_surname_index_bad_data_resilience(corrupted_env: Tuple[Any, logging.Logger]) -> None:
    """Verifies that surname indexing skips nameless entities without crashing."""
    config, logger = corrupted_env
    target_index = config.indexes / "surname_index.json"

    assert build_surname_index(config, logger) is True
    assert target_index.exists()

    payload = GDAUtil.load_json(target_index)
    surnames = payload.get("surnames", {})

    assert "entity" not in surnames
    assert "nameless" not in surnames
    assert "referencing" in surnames
    assert "person" in surnames
    assert "partner" in surnames


@pytest.mark.regression
def test_family_group_index_bad_data_resilience(corrupted_env: Tuple[Any, logging.Logger]) -> None:
    """Verifies family grouping handles dangling pointers, self-links, and malformed dates."""
    config, logger = corrupted_env
    target_index = config.indexes / "family_group_index.json"

    assert build_family_group_index(config, logger) is True
    assert target_index.exists()

    payload = GDAUtil.load_json(target_index)
    families = payload.get("families", {})

    for fam_id, fam in families.items():
        px = fam.get("parent_x")
        py = fam.get("parent_y")
        if px:
            assert px["person_id"] in ["IND-00102", "IND-00103", "IND-00104"]
        if py:
            assert py["person_id"] in ["IND-00102", "IND-00103", "IND-00104"]
        for child in fam["children"]:
            assert child["person_id"] != "IND-88888"

    fam_103 = next((f for f in families.values() if f["parent_x"] and f["parent_x"]["person_id"] == "IND-00103"), None)
    assert fam_103 is not None
    assert fam_103["total_children"] == 1
    assert fam_103["children"][0]["person_id"] == "IND-00105"


# ==============================================================================
# 3. POSTPONED STUB ENFORCEMENT TESTS
# ==============================================================================

@pytest.mark.regression
@pytest.mark.parametrize(
    "build_func, expected_error_msg, target_file_name",
    [
        (build_ahnentafel_index, "not yet developed: build_ahnentafel_index", "ahnentafel_index.json"),
        (build_newspaper_obituary_index, "not yet developed: build_newspaper_obituary_index", "newspaper_obituary_index.json"),
        (build_place_index, "not yet developed: build_place_index", "place_index.json"),
        (build_timeline_index, "not yet developed: build_timeline_index", "timeline_index.json"),
        (build_source_index, "not yet developed: build_source_index", "source_index.json"),
    ]
)
def test_unimplemented_stubs_raise_not_implemented(
    controlled_env: Tuple[Any, logging.Logger],
    build_func: Callable[[Any, logging.Logger], bool],
    expected_error_msg: str,
    target_file_name: str
) -> None:
    """Verifies unstarted generator stubs raise NotImplementedError without writing files."""
    config, logger = controlled_env
    target_path = config.indexes / target_file_name

    with pytest.raises(NotImplementedError, match=expected_error_msg):
        build_func(config, logger)

    assert not target_path.exists(), f"Stub {build_func.__name__} should not write file {target_file_name} before implementation."


@pytest.mark.regression
def test_build_all_indices_halts_on_stubs(controlled_env: Tuple[Any, logging.Logger]) -> None:
    """Verifies batch execution halts at the first unimplemented stub."""
    config, logger = controlled_env
    with pytest.raises(NotImplementedError, match="not yet developed: build_ahnentafel_index"):
        build_all_indices(config, logger)