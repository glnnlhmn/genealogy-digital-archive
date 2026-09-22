# Name: test_facts_md.py
# Path: tests/integration/test_facts_md.py

import json
import logging
import uuid
import pytest
from pathlib import Path
from unittest.mock import patch

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops import facts_md


@pytest.fixture
def mock_facts_env(tmp_path, monkeypatch):
    """Sets up an isolated filesystem environment by rebinding the GDAConfig singleton."""
    backups_dir = tmp_path / "backups"
    reports_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"
    entities_dir = tmp_path / "data" / "entities"

    backups_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    entities_dir.mkdir(parents=True, exist_ok=True)

    # Instantiate isolated configuration rooted in tmp_path
    mock_config = GDAConfig(root=tmp_path, manifest={})

    # Rebind singleton references across core and consumer modules
    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.facts_md.CONFIG", mock_config)

    test_logger = logging.getLogger("facts_md_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    return {
        "root": tmp_path,
        "config": mock_config,
        "facts_file": mock_config.facts,
        "reports_dir": mock_config.reports,
        "backups_dir": mock_config.backups,
        "logger": test_logger,
    }


# -----------------------------------------------------------------------------
# Completed Components: Tier 1, Report Resolution, Safe Backup Protocol
# -----------------------------------------------------------------------------

def test_resolve_insp_report_auto_discovery(mock_facts_env):
    """Verifies automatic discovery of the latest facts_audit_summary report."""
    reports_dir = mock_facts_env["reports_dir"]
    older_report = reports_dir / "facts_audit_summary_20260920_100000.json"
    newer_report = reports_dir / "facts_audit_summary_20260921_120000.json"

    older_report.write_text("{}", encoding="utf-8")
    newer_report.write_text("{}", encoding="utf-8")

    resolved = facts_md.resolve_insp_report(reports_dir=reports_dir)
    assert resolved == newer_report


def test_resolve_insp_report_explicit_arg(mock_facts_env):
    """Verifies resolving an explicit audit report filename."""
    reports_dir = mock_facts_env["reports_dir"]
    target_report = reports_dir / "facts_audit_summary_custom.json"
    target_report.write_text("{}", encoding="utf-8")

    resolved = facts_md.resolve_insp_report(
        insp_arg="facts_audit_summary_custom",
        reports_dir=reports_dir,
    )
    assert resolved == target_report


def test_resolve_insp_report_missing_raises(mock_facts_env):
    """Verifies FileNotFoundError when reports directory contains no summaries."""
    with pytest.raises(FileNotFoundError, match="No audit summary report found"):
        facts_md.resolve_insp_report(reports_dir=mock_facts_env["reports_dir"])


def test_fix_tier_1_facts_remediates_invalid_uuids(mock_facts_env):
    """Verifies Tier 1 converts flagged non-UUID fact_ids into compliant UUID4s."""
    facts_file = mock_facts_env["facts_file"]
    reports_dir = mock_facts_env["reports_dir"]
    logger = mock_facts_env["logger"]

    valid_uuid = str(uuid.uuid4())
    invalid_id = "INVALID_FACT_KEY_123"

    facts_payload = {
        "facts": [
            {"fact_id": invalid_id, "person_id": "IND-001", "fact_type": "Birth"},
            {"fact_id": valid_uuid, "person_id": "IND-002", "fact_type": "Death"},
        ]
    }
    GDAUtil.save_json(facts_file, facts_payload)

    audit_payload = {
        "findings": [
            {
                "category": "Schema",
                "fact_id": invalid_id,
                "message": "Identifier does not conform to standard GUID/UUID format.",
            }
        ]
    }
    audit_file = reports_dir / "facts_audit_summary_test.json"
    GDAUtil.save_json(audit_file, audit_payload)

    result = facts_md.fix_tier_1_facts(
        audit_file=audit_file,
        facts_path=facts_file,
        verbose=True,
        logger=logger,
    )

    assert result is True

    updated_data = GDAUtil.load_json(facts_file)
    updated_facts = updated_data["facts"]

    updated_f0 = updated_facts[0]
    assert updated_f0["fact_id"] != invalid_id
    assert uuid.UUID(updated_f0["fact_id"]).version == 4
    assert updated_f0["person_id"] == "IND-001"

    updated_f1 = updated_facts[1]
    assert updated_f1["fact_id"] == valid_uuid


def test_fix_tier_1_facts_noop_when_no_findings(mock_facts_env):
    """Verifies Tier 1 takes no write action when no Schema findings are present."""
    facts_file = mock_facts_env["facts_file"]
    reports_dir = mock_facts_env["reports_dir"]
    logger = mock_facts_env["logger"]

    original_uuid = str(uuid.uuid4())
    facts_payload = {
        "facts": [
            {"fact_id": original_uuid, "person_id": "IND-001", "fact_type": "Birth"}
        ]
    }
    GDAUtil.save_json(facts_file, facts_payload)

    audit_payload = {
        "findings": [
            {
                "category": "Typology",
                "fact_id": original_uuid,
                "message": "Invalid fact type.",
            }
        ]
    }
    audit_file = reports_dir / "facts_audit_summary_test.json"
    GDAUtil.save_json(audit_file, audit_payload)

    with patch.object(GDAUtil, "save_json") as mock_save:
        result = facts_md.fix_tier_1_facts(
            audit_file=audit_file,
            facts_path=facts_file,
            verbose=False,
            logger=logger,
        )
        assert result is True
        mock_save.assert_not_called()


def test_run_all_fixes_creates_safe_backup(mock_facts_env):
    """Verifies batch execution triggers GDAUtil.create_safe_backup on facts.json."""
    facts_file = mock_facts_env["facts_file"]
    reports_dir = mock_facts_env["reports_dir"]
    logger = mock_facts_env["logger"]

    GDAUtil.save_json(facts_file, {"facts": []})
    audit_file = reports_dir / "facts_audit_summary_test.json"
    GDAUtil.save_json(audit_file, {"findings": []})

    with patch.object(GDAUtil, "create_safe_backup", wraps=GDAUtil.create_safe_backup) as mock_backup:
        facts_md.run_all_fixes(
            audit_file=audit_file,
            facts_path=facts_file,
            verbose=False,
            logger=logger,
        )
        mock_backup.assert_called_once_with(facts_file)

    backups = list(mock_facts_env["backups_dir"].glob("facts.json.*.bk"))
    assert len(backups) == 1


# -----------------------------------------------------------------------------
# Undone Components: Placeholder Safeguard Tests (Tiers 2, 3, 4)
# Fails when placeholders are completed without updating test coverage.
# -----------------------------------------------------------------------------

def test_tier_2_placeholder_boundary(mock_facts_env, caplog):
    """
    Guards Tier 2 placeholder contract.
    Fails when implementation begins without replacing this test with actual logic checks.
    """
    facts_file = mock_facts_env["facts_file"]
    reports_dir = mock_facts_env["reports_dir"]
    logger = mock_facts_env["logger"]

    audit_file = reports_dir / "facts_audit_summary_test.json"
    audit_file.write_text("{}", encoding="utf-8")

    with caplog.at_level(logging.INFO):
        result = facts_md.fix_tier_2_facts(
            audit_file=audit_file,
            facts_path=facts_file,
            verbose=False,
            logger=logger,
        )

    assert result is True
    assert any(
        "Status: Placeholder - not yet implemented." in record.message
        for record in caplog.records
    ), "Tier 2 placeholder was modified or implemented without updating tests/unit/test_facts_md.py."


def test_tier_3_placeholder_boundary(mock_facts_env, caplog):
    """
    Guards Tier 3 placeholder contract.
    Fails when implementation begins without replacing this test with actual logic checks.
    """
    facts_file = mock_facts_env["facts_file"]
    reports_dir = mock_facts_env["reports_dir"]
    logger = mock_facts_env["logger"]

    audit_file = reports_dir / "facts_audit_summary_test.json"
    audit_file.write_text("{}", encoding="utf-8")

    with caplog.at_level(logging.INFO):
        result = facts_md.fix_tier_3_facts(
            audit_file=audit_file,
            facts_path=facts_file,
            verbose=False,
            logger=logger,
        )

    assert result is True
    assert any(
        "Status: Placeholder - not yet implemented." in record.message
        for record in caplog.records
    ), "Tier 3 placeholder was modified or implemented without updating tests/unit/test_facts_md.py."


def test_tier_4_placeholder_boundary(mock_facts_env, caplog):
    """
    Guards Tier 4 placeholder contract.
    Fails when implementation begins without replacing this test with actual logic checks.
    """
    facts_file = mock_facts_env["facts_file"]
    reports_dir = mock_facts_env["reports_dir"]
    logger = mock_facts_env["logger"]

    audit_file = reports_dir / "facts_audit_summary_test.json"
    audit_file.write_text("{}", encoding="utf-8")

    with caplog.at_level(logging.INFO):
        result = facts_md.fix_tier_4_facts(
            audit_file=audit_file,
            facts_path=facts_file,
            verbose=False,
            logger=logger,
        )

    assert result is True
    assert any(
        "Status: Placeholder - not yet implemented." in record.message
        for record in caplog.records
    ), "Tier 4 placeholder was modified or implemented without updating tests/unit/test_facts_md.py."