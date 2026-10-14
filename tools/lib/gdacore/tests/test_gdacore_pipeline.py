# Name: test_gdacore_pipeline.py
# Path: tools/lib/gdacore/tests/test_gdacore_pipeline.py
# Version: 1.0.0+build.rc1

"""Integration test harness verifying cross-module coordination within gdacore.

Operational Role:
    Validates atomic filesystem coordination and lifecycle interaction across
    GDAConfig, GDALogger, GDAUtil, GDAReferenceManager, and GDAVocabularyManager
    in an integrated mock archive sandbox topology.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 assertion boundary mapping per lifecycle action.
    - Fully decorated: Strictly marked with @pytest.mark.integration and @pytest.mark.smoke.
    - Dependencies: Hermetic tmp_path sandbox emulating canonical archive layout.
"""

from __future__ import annotations

__version__ = "1.0.0+build.rc1"

import json
from pathlib import Path
import pytest

from gdacore import config
from gdacore.config import GDAConfig
from gdacore.logger import GDALogger, setup_logger
from gdacore.reference_manager import GDAReferenceManager
from gdacore.util import GDAUtil
from gdacore.vocabulary_manager import GDAVocabularyManager

pytestmark = pytest.mark.integration


@pytest.fixture
def integrated_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GDAConfig:
    """Construct an isolated repository filesystem topology in a temporary directory."""
    sandbox_root = tmp_path / "mock_archive"
    sandbox_root.mkdir()

    manifest_data = {
        "name": "Genealogy Digital Archive Integration Sandbox",
        "version": "1.0.0",
        "archive_root": str(sandbox_root),
    }
    (sandbox_root / "gda_config.json").write_text(json.dumps(manifest_data), encoding="utf-8")
    (sandbox_root / ".git").mkdir()

    sandbox_cfg = GDAConfig(root=sandbox_root)
    monkeypatch.setattr(config, "CONFIG", sandbox_cfg)

    sandbox_cfg.logs.mkdir(parents=True, exist_ok=True)
    sandbox_cfg.backups.mkdir(parents=True, exist_ok=True)
    sandbox_cfg.temp.mkdir(parents=True, exist_ok=True)
    sandbox_cfg.schema_defs.mkdir(parents=True, exist_ok=True)
    (sandbox_cfg.data / "reference").mkdir(parents=True, exist_ok=True)
    sandbox_cfg.entities.mkdir(parents=True, exist_ok=True)

    enums_payload = {
        "$defs": {
            "fact_type": {"enum": ["Birth", "Death", "Census", "Marriage"]},
            "date_modifier": {"enum": ["EXACT", "ABOUT", "ESTIMATED"]},
            "union_status": {"enum": ["MARRIED", "DIVORCED"]},
            "associated_role": {"enum": ["FATH", "MOTH", "CHIL", "SPOU"]},
        }
    }
    schema_file = sandbox_cfg.schema_defs / "_enums.schema.json"
    schema_file.write_text(json.dumps(enums_payload), encoding="utf-8")

    ref_payload = {
        "_name": "states_colloquial.json",
        "_path": "data/reference/states_colloquial.json",
        "mappings": {
            "pa": "Pennsylvania",
            "nh": "New Hampshire",
        },
    }
    (sandbox_cfg.data / "reference" / "states_colloquial.json").write_text(
        json.dumps(ref_payload), encoding="utf-8"
    )

    GDAReferenceManager.clear_cache()
    GDAVocabularyManager.reset_cache()
    GDAVocabularyManager.set_custom_schema_path(schema_file)

    yield sandbox_cfg

    GDAReferenceManager.clear_cache()
    GDAVocabularyManager.reset_cache()


# ==============================================================================
# GROUP 1: Configuration and Schema Pipeline Integration
# Note: Verification of GDAConfig routing to Vocabulary and Reference managers
# ==============================================================================

@pytest.mark.integration
@pytest.mark.smoke
def test_pipeline_config_resolves_schema_enums(integrated_sandbox: GDAConfig) -> None:
    """Verify GDAVocabularyManager resolves vocabulary definitions via GDAConfig paths."""
    fact_types = GDAVocabularyManager.get_fact_types()
    assert set(fact_types) == {"Birth", "Death", "Census", "Marriage"}


@pytest.mark.integration
@pytest.mark.smoke
def test_pipeline_config_resolves_reference_mappings(integrated_sandbox: GDAConfig) -> None:
    """Verify GDAReferenceManager resolves static tables via GDAConfig paths."""
    states = GDAReferenceManager.get_colloquial_states()
    assert states["nh"] == "New Hampshire"


# ==============================================================================
# GROUP 2: Structured Logging Pipeline Integration
# Note: Verification of log emission, directory targeting, and formatted records
# ==============================================================================

@pytest.mark.integration
@pytest.mark.smoke
def test_pipeline_logger_creates_file_in_logs_directory(integrated_sandbox: GDAConfig) -> None:
    """Verify GDALogger creates log file on disk in config.logs."""
    cfg = integrated_sandbox
    logger = setup_logger("integration_runner_file", log_dir=cfg.logs, force_reconfigure=True)
    logger.info("Pipeline lifecycle log record.")

    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    assert len(list(cfg.logs.glob("integration_runner_file-*.log"))) == 1


@pytest.mark.integration
@pytest.mark.smoke
def test_pipeline_logger_records_message_in_file(integrated_sandbox: GDAConfig) -> None:
    """Verify GDALogger writes formatted record content to the log file."""
    cfg = integrated_sandbox
    logger = setup_logger("integration_runner_msg", log_dir=cfg.logs, force_reconfigure=True)
    logger.info("Pipeline lifecycle log record.")

    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    log_files = list(cfg.logs.glob("integration_runner_msg-*.log"))
    assert len(log_files) == 1
    assert "Pipeline lifecycle log record." in log_files[0].read_text(encoding="utf-8")


# ==============================================================================
# GROUP 3: Filesystem Utilities and Safe Backup Integration
# Note: Verification of atomic JSON commits and pre-write backup snapshots
# ==============================================================================

@pytest.mark.integration
@pytest.mark.smoke
def test_pipeline_util_atomic_save_in_entities_directory(integrated_sandbox: GDAConfig) -> None:
    """Verify GDAUtil executes atomic JSON write into config.entities."""
    cfg = integrated_sandbox
    target_file = cfg.entities / "person_00001.json"
    payload = {"id": "IND-00001", "name": "Glenn Lehman"}

    GDAUtil.save_json(target_file, payload)
    assert GDAUtil.load_json(target_file) == payload


@pytest.mark.integration
@pytest.mark.smoke
def test_pipeline_util_safe_backup_targets_backups_directory(integrated_sandbox: GDAConfig) -> None:
    """Verify GDAUtil generates atomic pre-write snapshot inside config.backups."""
    cfg = integrated_sandbox
    target_file = cfg.entities / "person_00002.json"
    target_file.write_text(json.dumps({"id": "IND-00002", "v": 1}), encoding="utf-8")

    backup_path = GDAUtil.create_safe_backup(target_file, backup_dir=cfg.backups)
    assert backup_path.parent == cfg.backups


@pytest.mark.integration
@pytest.mark.smoke
def test_pipeline_util_safe_backup_creates_regular_file(integrated_sandbox: GDAConfig) -> None:
    """Verify GDAUtil backup snapshot exists as a regular file on disk."""
    cfg = integrated_sandbox
    target_file = cfg.entities / "person_00003.json"
    target_file.write_text(json.dumps({"id": "IND-00003", "v": 1}), encoding="utf-8")

    backup_path = GDAUtil.create_safe_backup(target_file, backup_dir=cfg.backups)
    assert backup_path.is_file()