# Name: conftest.py
# Path: tools/lib/gdacore/tests/conftest.py
# Version: 1.0.0+build.rc1

"""Provide shared pytest fixtures and test harness environment isolation for GDACore.

Operational Role:
    Configures hermetic sandboxing for GDACore tests, providing isolated
    temporary directories, mock configuration instances, pre-configured
    test loggers, and controlled filesystem structures.

Test Structure & Protocol:
    - Sandboxing: tmp_path-backed directory trees isolating data, backups, and logs.
    - Zero Production Disk I/O: Guarantees zero mutations against canonical stores.
    - Windows DACL Safeguard: Compatible with --basetemp=gtemp/pytest_tmp.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from gdacore.config import GDAConfig
from gdacore.logger import GDALogger


@pytest.fixture
def sandbox_root(tmp_path: Path) -> Path:
    """Create a fully partitioned mock repository workspace.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        Path pointing to the root of the mock archive workspace.
    """
    root = tmp_path / "mock_archive"
    root.mkdir(parents=True, exist_ok=True)

    # Populate canonical directory topology
    (root / "data" / "reference").mkdir(parents=True, exist_ok=True)
    (root / "data" / "entities").mkdir(parents=True, exist_ok=True)
    (root / "schemas" / "naming").mkdir(parents=True, exist_ok=True)
    (root / "schemas" / "defs").mkdir(parents=True, exist_ok=True)
    (root / "backups").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "gtemp").mkdir(parents=True, exist_ok=True)

    return root


@pytest.fixture
def mock_config(sandbox_root: Path) -> GDAConfig:
    """Provide an isolated GDAConfig instance anchored to sandbox_root.

    Args:
        sandbox_root: Isolated root workspace fixture.

    Returns:
        Configured GDAConfig instance pointing to sandboxed paths.
    """
    config = GDAConfig()
    config.repo_root = sandbox_root
    config.data_dir = sandbox_root / "data"
    config.backup_dir = sandbox_root / "backups"
    config.log_dir = sandbox_root / "logs"
    config.temp_dir = sandbox_root / "gtemp"
    config.schema_dir = sandbox_root / "schemas"
    return config


@pytest.fixture
def test_logger(sandbox_root: Path) -> Generator[logging.Logger, None, None]:
    """Provide a sandboxed logger instance emitting to the temporary log directory.

    Args:
        sandbox_root: Isolated root workspace fixture.

    Yields:
        Configured logging.Logger instance with isolated handlers.
    """
    logger_name = "test_gdacore_logger"
    log_file = sandbox_root / "logs" / "test_execution.log"
    logger = GDALogger.get_logger(logger_name, log_file=log_file, level=logging.DEBUG)

    yield logger

    # Teardown handlers to prevent open file locks on Windows
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


@pytest.fixture
def sample_states_json(sandbox_root: Path) -> Path:
    """Generate a minimal valid colloquial states reference JSON file in sandbox.

    Args:
        sandbox_root: Isolated root workspace fixture.

    Returns:
        Path to the sandboxed states_colloquial.json file.
    """
    file_path = sandbox_root / "data" / "reference" / "states_colloquial.json"
    payload = {
        "metadata": {
            "version": "1.0.0",
            "description": "Colloquial state abbreviations test baseline."
        },
        "mappings": {
            "NH": "New Hampshire",
            "PA": "Pennsylvania",
            "MA": "Massachusetts"
        }
    }
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return file_path


@pytest.fixture
def sample_token_registry_json(sandbox_root: Path) -> Path:
    """Generate a minimal valid token registry JSON file in sandbox.

    Args:
        sandbox_root: Isolated root workspace fixture.

    Returns:
        Path to the sandboxed _token_registry.json file.
    """
    file_path = sandbox_root / "schemas" / "naming" / "_token_registry.json"
    payload = {
        "tokens": {
            "DOC": "Document",
            "PHO": "Photograph",
            "REC": "Record"
        }
    }
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return file_path