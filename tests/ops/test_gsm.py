# Name: test_gsm.py
# Path: tests/ops/test_gsm.py
# Version: 1.7.0+build.20261008.1

"""Integration test suite verifying Genealogy Schema Manager (GSM) CLI tool.

Operational Role:
    Validates end-to-end command-line invocation and operational execution of
    tools/ops/gsm.py, testing help generation, invalid flag rejection, single
    schema targeting, dynamic compilation (--compile), read-only drift auditing
    (--check), and meta-schema verification (--validate) with complete branch
    coverage across success and failure paths.

Test Structure & Protocol:
    - Atomized tests: 1:1 assertion mapping isolating CLI parameters and execution loops.
    - Fully decorated: Explicitly decorated with @pytest.mark.integration,
      @pytest.mark.smoke, and @pytest.mark.regression.
    - In-Process Execution: Employs pytest capsys fixture and dependency injection into run_gsm.
    - Dependencies: tools.ops.gsm, gdaschema.schema_manager, gdacore.config.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from gdaschema.schema_manager import GDASchemaManager, SchemaItem
import tools.ops.gsm as gsm


@pytest.fixture
def isolated_gsm_env(tmp_path: Path) -> Dict[str, Any]:
    """Construct an isolated sandbox directory topology with a test GDASchemaManager."""
    defs_dir = tmp_path / "schemas" / "defs"
    entities_dir = tmp_path / "schemas" / "entities"
    defs_dir.mkdir(parents=True, exist_ok=True)
    entities_dir.mkdir(parents=True, exist_ok=True)

    manager = GDASchemaManager(defs_dir=defs_dir, entities_dir=entities_dir)
    return {
        "manager": manager,
        "defs_dir": defs_dir,
        "entities_dir": entities_dir,
        "tmp_path": tmp_path,
    }


# -----------------------------------------------------------------------------
# CLI Parameter & Flag Boundary Tests (Atomized 1:1)
# -----------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.smoke
def test_gsm_cli_no_args_displays_help() -> None:
    """Verify executing gsm with no arguments returns status 0."""
    assert gsm.main([]) == 0


@pytest.mark.integration
@pytest.mark.smoke
def test_gsm_cli_force_alone_displays_help() -> None:
    """Verify executing gsm with modifier flag --force alone returns status 0."""
    assert gsm.main(["--force"]) == 0


@pytest.mark.integration
@pytest.mark.regression
def test_gsm_cli_invalid_flag_raises_system_exit() -> None:
    """Verify passing an unrecognized flag raises SystemExit with code 2."""
    with pytest.raises(SystemExit) as exc_info:
        gsm.main(["--badflag"])
    assert exc_info.value.code == 2


@pytest.mark.integration
@pytest.mark.regression
def test_gsm_cli_rejects_unregistered_single_schema(
    isolated_gsm_env: Dict[str, Any]
) -> None:
    """Verify specifying an unregistered schema name returns status 1."""
    manager: GDASchemaManager = isolated_gsm_env["manager"]
    args = argparse.Namespace(
        schema="unknown.schema.json",
        check=True,
        compile=False,
        validate=False,
        force=False,
    )
    assert gsm.run_gsm(args, manager=manager) == 1


# -----------------------------------------------------------------------------
# Read-Only Drift Audit Tests (--check)
# -----------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.smoke
def test_gsm_cli_check_drift_clean_returns_zero(
    isolated_gsm_env: Dict[str, Any]
) -> None:
    """Verify --check returns 0 when all targeted schemas match disk state."""
    manager: GDASchemaManager = isolated_gsm_env["manager"]
    manager["_enums.schema.json"].write(create_backup=False)

    args = argparse.Namespace(
        schema="_enums.schema.json",
        check=True,
        compile=False,
        validate=False,
        force=False,
    )
    assert gsm.run_gsm(args, manager=manager) == 0


@pytest.mark.integration
@pytest.mark.smoke
def test_gsm_cli_check_drift_dirty_returns_one(
    isolated_gsm_env: Dict[str, Any]
) -> None:
    """Verify --check returns 1 when any targeted schema is missing or modified on disk."""
    manager: GDASchemaManager = isolated_gsm_env["manager"]
    manager["_enums.schema.json"].write(create_backup=False)

    args = argparse.Namespace(
        schema=None,
        check=True,
        compile=False,
        validate=False,
        force=False,
    )
    assert gsm.run_gsm(args, manager=manager) == 1


# -----------------------------------------------------------------------------
# Compilation & Persistence Tests (--compile)
# -----------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.smoke
def test_gsm_cli_compile_updates_drifted_schemas(
    isolated_gsm_env: Dict[str, Any]
) -> None:
    """Verify --compile updates drifted files and returns status 0."""
    manager: GDASchemaManager = isolated_gsm_env["manager"]
    manager["_enums.schema.json"].write(create_backup=False)

    args = argparse.Namespace(
        schema=None,
        compile=True,
        check=False,
        validate=False,
        force=False,
    )
    assert gsm.run_gsm(args, manager=manager) == 0


@pytest.mark.integration
@pytest.mark.smoke
def test_gsm_cli_force_compile_writes_synchronized_schemas(
    isolated_gsm_env: Dict[str, Any]
) -> None:
    """Verify --compile --force writes schemas unconditionally and returns status 0."""
    manager: GDASchemaManager = isolated_gsm_env["manager"]
    manager["_enums.schema.json"].write(create_backup=False)

    args = argparse.Namespace(
        schema="_enums.schema.json",
        compile=True,
        check=False,
        validate=False,
        force=True,
    )
    assert gsm.run_gsm(args, manager=manager) == 0


# -----------------------------------------------------------------------------
# Meta-Schema Validation Tests (--validate)
# -----------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.smoke
def test_gsm_cli_validate_success_returns_zero() -> None:
    """Verify --validate returns status 0 when all targeted schemas are valid."""
    mock_valid = MagicMock(spec=SchemaItem)
    mock_valid.key = "valid.schema.json"
    mock_valid.validate.return_value = (True, None)

    mock_manager = MagicMock(spec=GDASchemaManager)
    mock_manager.__iter__.return_value = iter([mock_valid])
    mock_manager.__len__.return_value = 1

    args = argparse.Namespace(
        schema=None,
        compile=False,
        check=False,
        validate=True,
        force=False,
    )
    assert gsm.run_gsm(args, manager=mock_manager) == 0


@pytest.mark.integration
@pytest.mark.regression
def test_gsm_cli_validate_failure_returns_one() -> None:
    """Verify --validate returns status 1 when any targeted schema is invalid."""
    mock_invalid = MagicMock(spec=SchemaItem)
    mock_invalid.key = "corrupt.schema.json"
    mock_invalid.validate.return_value = (False, "Draft 2020-12 syntax error")

    mock_manager = MagicMock(spec=GDASchemaManager)
    mock_manager.__iter__.return_value = iter([mock_invalid])
    mock_manager.__len__.return_value = 1

    args = argparse.Namespace(
        schema=None,
        compile=False,
        check=False,
        validate=True,
        force=False,
    )
    assert gsm.run_gsm(args, manager=mock_manager) == 1


# -----------------------------------------------------------------------------
# Main CLI Entrypoint Delegation Tests (Atomized 1:1)
# -----------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.smoke
def test_gsm_cli_main_compile_invocation(
    monkeypatch: pytest.MonkeyPatch, isolated_gsm_env: Dict[str, Any]
) -> None:
    """Verify main(['--compile']) parses arguments and completes with status 0."""
    manager: GDASchemaManager = isolated_gsm_env["manager"]
    monkeypatch.setattr("tools.ops.gsm.GDASchemaManager", lambda: manager)
    assert gsm.main(["--compile"]) == 0


@pytest.mark.integration
@pytest.mark.smoke
def test_gsm_cli_main_check_invocation(
    monkeypatch: pytest.MonkeyPatch, isolated_gsm_env: Dict[str, Any]
) -> None:
    """Verify main(['--check']) parses arguments and returns status 1 on drifted collection."""
    manager: GDASchemaManager = isolated_gsm_env["manager"]
    monkeypatch.setattr("tools.ops.gsm.GDASchemaManager", lambda: manager)
    assert gsm.main(["--check"]) == 1


@pytest.mark.integration
@pytest.mark.smoke
def test_gsm_cli_main_validate_invocation(
    monkeypatch: pytest.MonkeyPatch, isolated_gsm_env: Dict[str, Any]
) -> None:
    """Verify main(['_enums.schema.json', '--validate']) completes with status 0."""
    manager: GDASchemaManager = isolated_gsm_env["manager"]
    monkeypatch.setattr("tools.ops.gsm.GDASchemaManager", lambda: manager)
    assert gsm.main(["_enums.schema.json", "--validate"]) == 0