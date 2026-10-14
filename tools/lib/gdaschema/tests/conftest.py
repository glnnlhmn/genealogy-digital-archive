# Name: conftest.py
# Path: tools/lib/gdaschema/tests/conftest.py
# Version: 1.0.0rc1+build.r2

"""Pytest shared fixtures and hermetic environment setup for gdaschema test suites.

Operational Role:
    Provides centralized temporary workspace sandboxes, hermetic GDAConfig
    instances anchored to tmp_path, isolated schema directories, test loggers,
    and shared golden/failure definitions fixture loaders.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Generator

import pytest

from gdacore.config import GDAConfig
from gdacore.logger import GDALogger


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provide an isolated, ephemeral test logger."""
    return GDALogger.get_logger("test.gdaschema")


@pytest.fixture
def schema_sandbox(tmp_path: Path) -> Generator[dict[str, Path | GDAConfig], None, None]:
    """Construct an isolated directory topology with mock schemas directories."""
    workspace = tmp_path / "genealogy-digital-archive"
    schemas_root = workspace / "schemas"
    defs_dir = schemas_root / "defs"
    entities_dir = schemas_root / "entities"
    sources_dir = schemas_root / "sources"
    indexes_dir = schemas_root / "indexes"
    naming_dir = schemas_root / "naming"
    profiles_dir = schemas_root / "profiles"

    for d in (defs_dir, entities_dir, sources_dir, indexes_dir, naming_dir, profiles_dir):
        d.mkdir(parents=True, exist_ok=True)

    config = GDAConfig(root=workspace)

    yield {
        "workspace": workspace,
        "schemas_root": schemas_root,
        "defs_dir": defs_dir,
        "entities_dir": entities_dir,
        "sources_dir": sources_dir,
        "indexes_dir": indexes_dir,
        "naming_dir": naming_dir,
        "profiles_dir": profiles_dir,
        "config": config,
    }


@pytest.fixture
def fixtures_defs_dir() -> Path:
    """Return resolved path to tests/fixtures/defs/."""
    # Anchors relative to repo root
    current = Path(__file__).resolve()
    # current: tools/lib/gdaschema/tests/conftest.py -> parents[4] is repo root
    repo_root = current.parents[4]
    fixtures_dir = repo_root / "tests" / "fixtures" / "defs"
    return fixtures_dir


@pytest.fixture
def golden_defs_data(fixtures_defs_dir: Path) -> Dict[str, Any]:
    """Load canonical synthetic golden definitions test payloads."""
    target = fixtures_defs_dir / "golden" / "golden_base_defs.json"
    if not target.is_file():
        pytest.skip(f"Fixture file not found: {target}")
    return json.loads(target.read_text(encoding="utf-8"))


@pytest.fixture
def failure_defs_data(fixtures_defs_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load all defect test payloads under tests/fixtures/defs/failure/."""
    failure_dir = fixtures_defs_dir / "failure"
    if not failure_dir.is_dir():
        pytest.skip(f"Failure fixtures dir not found: {failure_dir}")

    payloads: Dict[str, Dict[str, Any]] = {}
    for item in failure_dir.glob("*.json"):
        payloads[item.stem] = json.loads(item.read_text(encoding="utf-8"))
    return payloads