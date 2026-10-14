# Name: conftest.py
# Path: tests/conftest.py
# Version: 1.1.0+build.20260930.1

"""Root test configuration and centralized test fixtures for the archive suite."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Generator
import pytest

from gdacore import config
from gdacore.config import GDAConfig
from gdacore.logger import setup_logger


@pytest.fixture
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GDAConfig:
    """Instantiate and bind a hermetic GDAConfig rooted inside tmp_path.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        Isolated GDAConfig instance.
    """
    sandbox_config = GDAConfig(root=tmp_path.resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)
    return sandbox_config


@pytest.fixture
def test_logger(mock_config: GDAConfig) -> Generator[logging.Logger, None, None]:
    """Provide a sandboxed logger routing ephemeral output to the mock temp directory.

    Args:
        mock_config: Sandboxed GDAConfig instance.

    Yields:
        Configured logging.Logger instance.
    """
    logger = setup_logger(
        tool_name="test_runner",
        log_dir=mock_config.temp,
        ephemeral=True,
        force_reconfigure=True,
    )
    yield logger
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)