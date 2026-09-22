# Name: test_gsi.py
# Path: tests/integration/test_gsi.py

import logging
from pathlib import Path
from unittest.mock import patch
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops import gsi
from tools.ops.gsi import (
    extract_script_headers,
    process_import,
)


@pytest.fixture
def mock_gsi_env(tmp_path, monkeypatch):
    """Sets up an isolated filesystem environment rebinding GDAConfig."""
    backups_dir = tmp_path / "backups"
    logs_dir = tmp_path / "logs"
    tools_dir = tmp_path / "tools" / "ops"
    intake_dir = tmp_path / "intake"

    backups_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)
    intake_dir.mkdir(parents=True, exist_ok=True)

    mock_config = GDAConfig(root=tmp_path, manifest={})
    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.gsi.CONFIG", mock_config)

    test_logger = logging.getLogger("gsi_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    return {
        "root": tmp_path,
        "config": mock_config,
        "backups_dir": backups_dir,
        "tools_dir": tools_dir,
        "intake_dir": intake_dir,
        "logger": test_logger,
    }


# -----------------------------------------------------------------------------
# Unit Tests: Header Extraction
# -----------------------------------------------------------------------------

def test_extract_script_headers_valid(tmp_path):
    """Verifies parsing of mandatory # Name: and # Path: headers."""
    script_file = tmp_path / "sample_script.py"
    script_file.write_text(
        "# Name: sample_script.py\n"
        "# Path: tools/ops/sample_script.py\n\n"
        "print('hello')\n",
        encoding="utf-8",
    )

    name, path = extract_script_headers(script_file)
    assert name == "sample_script.py"
    assert path == Path("tools/ops/sample_script.py")


def test_extract_script_headers_missing_path(tmp_path):
    """Verifies that omitted # Path: headers return None."""
    script_file = tmp_path / "no_path.py"
    script_file.write_text(
        "# Name: no_path.py\n"
        "print('no path specified')\n",
        encoding="utf-8",
    )

    name, path = extract_script_headers(script_file)
    assert name == "no_path.py"
    assert path is None


# -----------------------------------------------------------------------------
# Integration Tests: Import & Relocation Lifecycle
# -----------------------------------------------------------------------------

def test_process_import_new_script(mock_gsi_env):
    """Verifies successful relocation of a new script into tools/ops/."""
    intake_dir = mock_gsi_env["intake_dir"]
    candidate = intake_dir / "gemini_tool.py"
    candidate.write_text(
        "# Name: new_tool.py\n"
        "# Path: tools/ops/new_tool.py\n\n"
        "print('installed')\n",
        encoding="utf-8",
    )

    process_import(
        source_dir=intake_dir,
        pattern="gemini",
        force=False,
        run_after=False,
        passthrough_args=[],
        logger=mock_gsi_env["logger"],
    )

    target_path = mock_gsi_env["root"] / "tools" / "ops" / "new_tool.py"
    assert target_path.exists()
    assert not candidate.exists()


def test_process_import_collision_default_yes_overwrite(mock_gsi_env):
    """Verifies default [Y/n] behavior overwrites on Enter and generates a Safe Backup."""
    intake_dir = mock_gsi_env["intake_dir"]
    target_path = mock_gsi_env["root"] / "tools" / "ops" / "target.py"

    # Pre-existing target file
    target_path.write_text(
        "# Name: target.py\n"
        "# Path: tools/ops/target.py\n"
        "# OLD VERSION\n",
        encoding="utf-8",
    )

    # Incoming replacement
    incoming = intake_dir / "gemini_patch.py"
    incoming.write_text(
        "# Name: target.py\n"
        "# Path: tools/ops/target.py\n"
        "# NEW VERSION\n",
        encoding="utf-8",
    )

    # Simulate user pressing Enter (empty string), defaulting to Yes
    with patch("builtins.input", return_value=""):
        process_import(
            source_dir=intake_dir,
            pattern="gemini",
            force=False,
            run_after=False,
            passthrough_args=[],
            logger=mock_gsi_env["logger"],
        )

    # Verify overwritten file content
    assert target_path.exists()
    assert "# NEW VERSION" in target_path.read_text(encoding="utf-8")
    assert not incoming.exists()

    # Verify pre-execution atomic safe backup created
    backups = list(mock_gsi_env["backups_dir"].glob("target.py.*.bk"))
    assert len(backups) == 1
    assert "# OLD VERSION" in backups[0].read_text(encoding="utf-8")


def test_process_import_collision_user_cancels(mock_gsi_env):
    """Verifies that typing 'n' or 'no' cancels overwrite and retains original file."""
    intake_dir = mock_gsi_env["intake_dir"]
    target_path = mock_gsi_env["root"] / "tools" / "ops" / "protected.py"

    target_path.write_text(
        "# Name: protected.py\n"
        "# Path: tools/ops/protected.py\n"
        "# DO NOT OVERWRITE\n",
        encoding="utf-8",
    )

    incoming = intake_dir / "gemini_protected.py"
    incoming.write_text(
        "# Name: protected.py\n"
        "# Path: tools/ops/protected.py\n"
        "# MALICIOUS PAYLOAD\n",
        encoding="utf-8",
    )

    with patch("builtins.input", return_value="n"):
        process_import(
            source_dir=intake_dir,
            pattern="gemini",
            force=False,
            run_after=False,
            passthrough_args=[],
            logger=mock_gsi_env["logger"],
        )

    # Target unchanged, incoming kept in place, zero backups made
    assert "# DO NOT OVERWRITE" in target_path.read_text(encoding="utf-8")
    assert incoming.exists()
    backups = list(mock_gsi_env["backups_dir"].glob("protected.py.*.bk"))
    assert len(backups) == 0


def test_process_import_force_bypasses_prompt(mock_gsi_env):
    """Verifies that --force overwrites without prompting and still takes a safe backup."""
    intake_dir = mock_gsi_env["intake_dir"]
    target_path = mock_gsi_env["root"] / "tools" / "ops" / "forced.py"

    target_path.write_text(
        "# Name: forced.py\n"
        "# Path: tools/ops/forced.py\n"
        "# ORIGINAL\n",
        encoding="utf-8",
    )

    incoming = intake_dir / "gemini_forced.py"
    incoming.write_text(
        "# Name: forced.py\n"
        "# Path: tools/ops/forced.py\n"
        "# FORCED UPDATE\n",
        encoding="utf-8",
    )

    with patch("builtins.input") as mock_prompt:
        process_import(
            source_dir=intake_dir,
            pattern="gemini",
            force=True,
            run_after=False,
            passthrough_args=[],
            logger=mock_gsi_env["logger"],
        )
        mock_prompt.assert_not_called()

    assert "# FORCED UPDATE" in target_path.read_text(encoding="utf-8")
    backups = list(mock_gsi_env["backups_dir"].glob("forced.py.*.bk"))
    assert len(backups) == 1
    assert "# ORIGINAL" in backups[0].read_text(encoding="utf-8")