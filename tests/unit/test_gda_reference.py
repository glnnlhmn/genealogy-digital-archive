# Name: test_gda_reference.py
# Path: tests/unit/test_gda_reference.py
# Version: 1.0.0+build.20260929.2

"""Unit test suite for GDAReference static table provider and cache manager.

Operational Role:
    Validates in-memory caching, canonical file resolution from data/reference/,
    missing table error handling, and colloquial US state lookup integration
    under tools/lib/gda_core/GDAReference.py without live external network dependencies.

Test Structure & Protocol:
    - Atomized tests: Each test function isolates a single behavioral invariant.
    - Fully decorated: Strictly tagged with @pytest.mark.unit and @pytest.mark.regression.
    - Dependencies: Exercises tools.lib.gda_core.GDAReference against tmp_path fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from tools.lib.gda_core.GDAReference import GDAReference


@pytest.fixture(autouse=True)
def reset_reference_cache() -> None:
    """Ensures in-memory cache on GDAReference is cleanly reset before each test."""
    GDAReference.clear_cache()
    yield
    GDAReference.clear_cache()


@pytest.fixture
def mock_reference_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Configures an isolated mock data/reference directory in tmp_path."""
    ref_dir = tmp_path / "data" / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)

    # Monkeypatch get_reference_dir to hermetically point to tmp_path
    monkeypatch.setattr(GDAReference, "get_reference_dir", classmethod(lambda cls: ref_dir))
    return ref_dir


@pytest.mark.unit
def test_get_table_loads_valid_json(mock_reference_dir: Path) -> None:
    """Verifies that get_table correctly loads and parses an existing reference table."""
    table_payload: Dict[str, Any] = {
        "_name": "test_table.json",
        "_path": "data/reference/test_table.json",
        "mappings": {"k1": "v1", "k2": "v2"},
    }
    target_file = mock_reference_dir / "test_table.json"
    target_file.write_text(json.dumps(table_payload), encoding="utf-8")

    result = GDAReference.get_table("test_table")
    assert result == table_payload
    assert result["mappings"]["k1"] == "v1"


@pytest.mark.unit
def test_get_table_caches_in_memory(mock_reference_dir: Path) -> None:
    """Verifies that subsequent table requests return cached instances without disk re-reads."""
    table_payload = {"mappings": {"initial": "data"}}
    target_file = mock_reference_dir / "cached_table.json"
    target_file.write_text(json.dumps(table_payload), encoding="utf-8")

    first_call = GDAReference.get_table("cached_table")
    assert first_call["mappings"]["initial"] == "data"

    # Mutate file on disk; second call should return identical cached memory reference
    target_file.write_text(json.dumps({"mappings": {"mutated": "disk"}}), encoding="utf-8")
    second_call = GDAReference.get_table("cached_table")

    assert second_call is first_call
    assert "mutated" not in second_call["mappings"]


@pytest.mark.unit
def test_get_table_raises_on_missing_file(mock_reference_dir: Path) -> None:
    """Verifies FileNotFoundError is raised when attempting to load a non-existent table."""
    with pytest.raises(FileNotFoundError, match="Reference table 'non_existent' not found"):
        GDAReference.get_table("non_existent")


@pytest.mark.unit
def test_get_table_raises_on_corrupt_json(mock_reference_dir: Path) -> None:
    """Verifies ValueError is raised if table file contains malformed JSON."""
    target_file = mock_reference_dir / "corrupt_table.json"
    target_file.write_text("{malformed: json,", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to parse reference table"):
        GDAReference.get_table("corrupt_table")


@pytest.mark.unit
@pytest.mark.regression
def test_get_colloquial_states_resolves_mappings(mock_reference_dir: Path) -> None:
    """Verifies get_colloquial_states extracts the inner mappings dictionary."""
    table_payload = {
        "_name": "states_colloquial.json",
        "_path": "data/reference/states_colloquial.json",
        "mappings": {
            "penn": "Pennsylvania",
            "penna": "Pennsylvania",
            "mass": "Massachusetts",
        },
    }
    target_file = mock_reference_dir / "states_colloquial.json"
    target_file.write_text(json.dumps(table_payload), encoding="utf-8")

    states = GDAReference.get_colloquial_states()
    assert isinstance(states, dict)
    assert states["penn"] == "Pennsylvania"
    assert states["penna"] == "Pennsylvania"
    assert states["mass"] == "Massachusetts"


@pytest.mark.unit
@pytest.mark.regression
def test_clear_cache_evicts_loaded_tables(mock_reference_dir: Path) -> None:
    """Verifies that clear_cache forces subsequent table reads to reload from disk."""
    target_file = mock_reference_dir / "evict_table.json"
    target_file.write_text(json.dumps({"mappings": {"v": 1}}), encoding="utf-8")

    call_1 = GDAReference.get_table("evict_table")
    assert call_1["mappings"]["v"] == 1

    target_file.write_text(json.dumps({"mappings": {"v": 2}}), encoding="utf-8")
    GDAReference.clear_cache()

    call_2 = GDAReference.get_table("evict_table")
    assert call_2["mappings"]["v"] == 2