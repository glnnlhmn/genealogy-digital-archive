# Name: test_gam.py
# Path: tests/integration/test_gam.py

"""Integration test suite for GAM (Genealogy Archive Manager).

Validates:
- Manifest generation and SHA-256 asset registration
- Internal version and header extraction across JSON and Markdown
- Audit detection for UNTRACKED, DRIFT, and ERROR states
- Automated remediation of UNKNOWN versions to 0.0.999
"""

import json
import logging
from pathlib import Path
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops import gam
from tools.ops.gam import (
    extract_metadata,
    generate_config,
    audit_system,
    remediate_latest_report,
)


@pytest.fixture
def mock_gam_env(tmp_path, monkeypatch):
    """Sets up an isolated digital archive environment by rebinding GDAConfig."""
    schemas_dir = tmp_path / "schemas" / "entities"
    prompts_dir = tmp_path / "prompts" / "core"
    reports_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"

    schemas_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    mock_config = GDAConfig(root=tmp_path, manifest={})
    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.gam.CONFIG", mock_config)

    test_logger = logging.getLogger("gam_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    return {
        "root": tmp_path,
        "config": mock_config,
        "schemas_dir": schemas_dir,
        "prompts_dir": prompts_dir,
        "reports_dir": reports_dir,
        "manifest_file": mock_config.config_manifest,
        "logger": test_logger,
    }


def test_extract_metadata_json_and_markdown(mock_gam_env):
    """Verifies version and purpose extraction across JSON and Markdown assets."""
    schema_file = mock_gam_env["schemas_dir"] / "sample.schema.json"
    schema_file.write_text(json.dumps({"SchemaVersion": "1.0.4", "title": "Sample"}), encoding="utf-8")

    prompt_file = mock_gam_env["prompts_dir"] / "Sample-Core.md"
    prompt_file.write_text("# Sample Persona Protocol\n<!-- Version: 1.0.2 -->\nContent", encoding="utf-8")

    s_ver, s_desc = extract_metadata(schema_file, logger=mock_gam_env["logger"])
    assert s_ver == "1.0.4"
    assert "sample.schema.json" in s_desc

    p_ver, p_desc = extract_metadata(prompt_file, logger=mock_gam_env["logger"])
    assert p_ver == "1.0.2"
    assert p_desc == "Sample Persona Protocol"


def test_generate_config_creates_manifest_and_backup(mock_gam_env):
    """Verifies baseline gda_config.json generation and pre-execution backup creation."""
    root = mock_gam_env["root"]
    manifest = mock_gam_env["manifest_file"]

    schema_file = mock_gam_env["schemas_dir"] / "person.schema.json"
    schema_file.write_text(json.dumps({"SchemaVersion": "1.0.0"}), encoding="utf-8")

    prompt_file = mock_gam_env["prompts_dir"] / "MIP-Core.md"
    prompt_file.write_text("# MIP Protocol\n<!-- Version: 1.0.5 -->\n", encoding="utf-8")

    # Initial baseline generation
    config_data = generate_config(root_dir=root, config_file=manifest, logger=mock_gam_env["logger"])
    assert manifest.exists()
    assert config_data["ConfigVersion"] == "1.0.0"
    assert len(config_data["TrackedAssets"]["schemas"]) == 1
    assert len(config_data["TrackedAssets"]["prompts"]) == 1

    # Re-generation creates a backup of existing manifest
    generate_config(root_dir=root, config_file=manifest, logger=mock_gam_env["logger"])
    backup_file = manifest.with_suffix(manifest.suffix + ".bk")
    assert backup_file.exists()


def test_audit_system_missing_manifest_exits(mock_gam_env):
    """Verifies that audit_system exits with code 1 if manifest does not exist."""
    with pytest.raises(SystemExit) as exc_info:
        audit_system(
            root_dir=mock_gam_env["root"],
            config_file=mock_gam_env["manifest_file"],
            reports_dir=mock_gam_env["reports_dir"],
            logger=mock_gam_env["logger"],
        )
    assert exc_info.value.code == 1


def test_audit_system_detects_drift_and_untracked(mock_gam_env):
    """Verifies detection of drifted content hashes and untracked files."""
    root = mock_gam_env["root"]
    manifest = mock_gam_env["manifest_file"]

    schema_file = mock_gam_env["schemas_dir"] / "person.schema.json"
    schema_file.write_text(json.dumps({"SchemaVersion": "1.0.0"}), encoding="utf-8")

    # Generate baseline
    generate_config(root_dir=root, config_file=manifest, logger=mock_gam_env["logger"])

    # 1. Cause Hash Drift
    schema_file.write_text(json.dumps({"SchemaVersion": "1.0.0", "modified": True}), encoding="utf-8")

    # 2. Add Untracked File
    untracked_prompt = mock_gam_env["prompts_dir"] / "Extra-Core.md"
    untracked_prompt.write_text("# Extra\n<!-- Version: 1.0.0 -->\n", encoding="utf-8")

    report = audit_system(
        format_type="all",
        root_dir=root,
        config_file=manifest,
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )

    assert report["discrepancies_detected"] == 2
    statuses = {r["path"]: r["status"] for r in report["records"]}
    assert statuses["schemas/entities/person.schema.json"] == "DRIFT"
    assert statuses["prompts/core/Extra-Core.md"] == "UNTRACKED"

    # Deliverables generated
    json_reports = list(mock_gam_env["reports_dir"].glob("gam_audit_*.json"))
    md_reports = list(mock_gam_env["reports_dir"].glob("gam_audit_*.md"))
    assert len(json_reports) == 1
    assert len(md_reports) == 1


def test_remediate_latest_report_repairs_unknown(mock_gam_env):
    """Verifies automated remediation of UNKNOWN versions to 0.0.999."""
    root = mock_gam_env["root"]
    reports_dir = mock_gam_env["reports_dir"]

    unversioned_schema = mock_gam_env["schemas_dir"] / "legacy.json"
    unversioned_schema.write_text(json.dumps({"description": "no version"}), encoding="utf-8")

    audit_payload = {
        "audit_timestamp": "2026-09-22T10:00:00Z",
        "records": [
            {
                "path": "schemas/entities/legacy.json",
                "internal_version": "UNKNOWN",
                "status": "ERROR",
            }
        ],
    }
    audit_file = reports_dir / "gam_audit_20260922_100000.json"
    GDAUtil.save_json(audit_file, audit_payload)

    remediate_latest_report(root_dir=root, reports_dir=reports_dir, logger=mock_gam_env["logger"])

    repaired_data = GDAUtil.load_json(unversioned_schema)
    assert repaired_data["SchemaVersion"] == "0.0.999"