# Name: conftest.py
# Path: tests/conftest.py

"""Shared root pytest fixtures for the digital genealogy archive."""

from pathlib import Path
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig


@pytest.fixture
def mock_archive_env(tmp_path: Path):
    """Initializes an isolated mock archive root and returns a bound GDAConfig."""
    root_dir = tmp_path / "genealogy-digital-archive"
    for sub in [
        "data/entities",
        "data/indexes",
        "schemas/entities",
        "schemas/defs",
        "backups",
        "logs",
        "reports",
    ]:
        (root_dir / sub).mkdir(parents=True, exist_ok=True)

    config = GDAConfig(root_dir)
    return config