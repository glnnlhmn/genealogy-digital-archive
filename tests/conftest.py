"""
Root pytest configuration and shared fixtures for the Genealogy Digital Archive test harness.
Provides hermetic test sandboxes, mock GDAConfig injection, and logging suppression.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Generator, Tuple
import pytest

from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil


@pytest.fixture
def gda_sandbox(tmp_path: Path) -> Path:
    """Creates a hermetic directory structure mirroring production topology."""
    dirs = [
        tmp_path / "data" / "entities" / "quarantine",
        tmp_path / "data" / "indexes",
        tmp_path / "data" / "archival_records",
        tmp_path / "backups",
        tmp_path / "logs",
        tmp_path / "reports",
        tmp_path / "gtemp",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def mock_config(gda_sandbox: Path) -> Any:
    """Provides a mock GDAConfig anchored strictly to the temporary sandbox."""
    class MockGDAConfig:
        root = gda_sandbox
        data = gda_sandbox / "data"
        entities = gda_sandbox / "data" / "entities"
        quarantine = gda_sandbox / "data" / "entities" / "quarantine"
        indexes = gda_sandbox / "data" / "indexes"
        records = gda_sandbox / "data" / "archival_records"
        backups = gda_sandbox / "backups"
        logs = gda_sandbox / "logs"
        reports = gda_sandbox / "reports"
        temp = gda_sandbox / "gtemp"
        people = gda_sandbox / "data" / "entities" / "people.json"
        facts = gda_sandbox / "data" / "entities" / "facts.json"
        token_registry = gda_sandbox / "schemas" / "naming" / "_token_registry.json"

    return MockGDAConfig()


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provides an isolated non-polluting logger for test executions."""
    return setup_logger(tool_name="test_runner", ephemeral=True, console_level=logging.CRITICAL)
