# Name: test_gam.py
# Path: tests/ops/test_gam.py
# Version: 1.1.0+build.20261006.5

"""Comprehensive test harness for GAM (Genealogy Archive Manager).

Operational Role:
    Validates baseline manifest generation, version extraction for schemas
    and operational tools (tools/ops), cryptographic SHA-256 drift detection,
    untracked component isolation, and automated version header remediation.
    Excludes tools/sys, tools/lib, and prompt markdown files.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly classified with pytest markers.
    - Dependencies: Requires tools/ops/gam.py, gdacore, and hermetic tmp_path sandboxes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict
import pytest

from gdacore.config import GDAConfig
from gdacore.util import GDAUtil
from tools.ops import gam
from tools.ops.gam import (
    audit_system,
    extract_metadata,
    generate_config,
    main,
    remediate_latest_report,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_gam_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Sets up an isolated archive sandbox rebinding GDAConfig and CONFIG singletons."""
    schemas_dir = tmp_path / "schemas" / "entities"
    ops_dir = tmp_path / "tools" / "ops"
    sys_dir = tmp_path / "tools" / "sys"
    reports_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"

    schemas_dir.mkdir(parents=True, exist_ok=True)
    ops_dir.mkdir(parents=True, exist_ok=True)
    sys_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    mock_config = GDAConfig(root=tmp_path)
    monkeypatch.setattr("gdacore.config.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.gam.CONFIG", mock_config)

    manifest_file = tmp_path / "gda_config.json"

    test_logger = logging.getLogger("gam_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    return {
        "root": tmp_path,
        "config": mock_config,
        "schemas_dir": schemas_dir,
        "ops_dir": ops_dir,
        "sys_dir": sys_dir,
        "reports_dir": reports_dir,
        "manifest_file": manifest_file,
        "logger": test_logger,
    }


# ==============================================================================
# 1. METADATA EXTRACTION (Atomized)
# ==============================================================================

@pytest.mark.unit
def test_extract_metadata_json_flat_schema_version(mock_gam_env: Dict[str, Any]) -> None:
    schema_file = mock_gam_env["schemas_dir"] / "person.schema.json"
    GDAUtil.save_json(schema_file, {"schema_version": "1.0.4", "title": "Person Schema"})

    ver, _ = extract_metadata(schema_file, logger=mock_gam_env["logger"])
    assert ver == "1.0.4"


@pytest.mark.unit
def test_extract_metadata_json_nested_wrapper_version(mock_gam_env: Dict[str, Any]) -> None:
    schema_file = mock_gam_env["schemas_dir"] / "wrapped.schema.json"
    GDAUtil.save_json(schema_file, {"Wrapper": {"schema_version": "2.1.0"}})

    ver, _ = extract_metadata(schema_file, logger=mock_gam_env["logger"])
    assert ver == "2.1.0"


@pytest.mark.unit
def test_extract_metadata_ops_tool_version_and_docstring(mock_gam_env: Dict[str, Any]) -> None:
    code_file = mock_gam_env["ops_dir"] / "gpi.py"
    code_file.write_text('"""GPI Pipeline Operational Tool."""\n__version__ = "1.1.0+build.20261006.1"\n', encoding="utf-8")

    ver, desc = extract_metadata(code_file, logger=mock_gam_env["logger"])
    assert ver == "1.1.0+build.20261006.1"
    assert desc == "GPI Pipeline Operational Tool."


@pytest.mark.unit
def test_extract_metadata_ops_tool_without_docstring(mock_gam_env: Dict[str, Any]) -> None:
    code_file = mock_gam_env["ops_dir"] / "nodoc.py"
    code_file.write_text('__version__ = "1.0.0"\nx = 1\n', encoding="utf-8")

    ver, desc = extract_metadata(code_file, logger=mock_gam_env["logger"])
    assert ver == "1.0.0"
    assert "Operational script (nodoc.py)" in desc


@pytest.mark.unit
def test_extract_metadata_unsupported_extension_returns_unknown(mock_gam_env: Dict[str, Any]) -> None:
    txt_file = mock_gam_env["ops_dir"] / "notes.txt"
    txt_file.write_text("plain text", encoding="utf-8")

    ver, desc = extract_metadata(txt_file, logger=mock_gam_env["logger"])
    assert ver == "UNKNOWN"
    assert desc == "N/A"


@pytest.mark.unit
def test_extract_metadata_corrupt_file_returns_unknown(mock_gam_env: Dict[str, Any]) -> None:
    corrupt_file = mock_gam_env["schemas_dir"] / "corrupt.json"
    corrupt_file.write_text("{ corrupt json }", encoding="utf-8")

    ver, desc = extract_metadata(corrupt_file, logger=mock_gam_env["logger"])
    assert ver == "UNKNOWN"
    assert desc == "N/A"


# ==============================================================================
# 2. CONFIG MANIFEST GENERATION (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_generate_config_creates_manifest_file(mock_gam_env: Dict[str, Any]) -> None:
    manifest = mock_gam_env["manifest_file"]
    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])
    assert manifest.exists()


@pytest.mark.smoke
def test_generate_config_tracks_schemas_and_ops_tools(mock_gam_env: Dict[str, Any]) -> None:
    schema_file = mock_gam_env["schemas_dir"] / "fact.schema.json"
    GDAUtil.save_json(schema_file, {"schema_version": "1.0.0"})

    tool_file = mock_gam_env["ops_dir"] / "gpa.py"
    tool_file.write_text('__version__ = "1.0.0"\n', encoding="utf-8")

    config_data = generate_config(
        root_dir=mock_gam_env["root"], config_file=mock_gam_env["manifest_file"], logger=mock_gam_env["logger"]
    )
    assert len(config_data["TrackedAssets"]["schemas"]) == 1
    assert len(config_data["TrackedAssets"]["ops"]) == 1


@pytest.mark.regression
def test_generate_config_missing_subdirs_returns_empty_manifest(tmp_path: Path) -> None:
    bare_manifest = tmp_path / "gda_config.json"
    config_data = generate_config(root_dir=tmp_path, config_file=bare_manifest)
    assert len(config_data["TrackedAssets"]["schemas"]) == 0
    assert len(config_data["TrackedAssets"]["ops"]) == 0


@pytest.mark.regression
def test_generate_config_ignores_archive_and_backup_schemas(mock_gam_env: Dict[str, Any]) -> None:
    archive_dir = mock_gam_env["root"] / "schemas" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived_schema = archive_dir / "old.json"
    GDAUtil.save_json(archived_schema, {"schema_version": "0.1.0"})

    bk_schema = mock_gam_env["schemas_dir"] / "test-bk-temp.json"
    GDAUtil.save_json(bk_schema, {"schema_version": "0.1.0"})

    config_data = generate_config(
        root_dir=mock_gam_env["root"], config_file=mock_gam_env["manifest_file"], logger=mock_gam_env["logger"]
    )
    assert len(config_data["TrackedAssets"]["schemas"]) == 0


@pytest.mark.regression
def test_generate_config_skips_unversioned_schema(mock_gam_env: Dict[str, Any]) -> None:
    unversioned = mock_gam_env["schemas_dir"] / "no_ver.json"
    GDAUtil.save_json(unversioned, {"type": "object"})

    config_data = generate_config(
        root_dir=mock_gam_env["root"], config_file=mock_gam_env["manifest_file"], logger=mock_gam_env["logger"]
    )
    assert len(config_data["TrackedAssets"]["schemas"]) == 0


@pytest.mark.regression
def test_generate_config_skips_dunder_init_and_unversioned_tool(mock_gam_env: Dict[str, Any]) -> None:
    init_file = mock_gam_env["ops_dir"] / "__init__.py"
    init_file.write_text("", encoding="utf-8")

    unver_tool = mock_gam_env["ops_dir"] / "no_ver.py"
    unver_tool.write_text("x = 1\n", encoding="utf-8")

    config_data = generate_config(
        root_dir=mock_gam_env["root"], config_file=mock_gam_env["manifest_file"], logger=mock_gam_env["logger"]
    )
    assert len(config_data["TrackedAssets"]["ops"]) == 0


@pytest.mark.regression
def test_generate_config_creates_safe_backup_on_replacement(mock_gam_env: Dict[str, Any]) -> None:
    manifest = mock_gam_env["manifest_file"]
    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])
    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])

    backup_file = manifest.with_suffix(".json.bk")
    assert backup_file.exists()


# ==============================================================================
# 3. AUDIT ENGINE & DISCREPANCY DETECTION (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_audit_system_missing_manifest_aborts(mock_gam_env: Dict[str, Any]) -> None:
    with pytest.raises(SystemExit) as exc:
        audit_system(
            root_dir=mock_gam_env["root"],
            config_file=mock_gam_env["manifest_file"],
            reports_dir=mock_gam_env["reports_dir"],
            logger=mock_gam_env["logger"],
        )
    assert exc.value.code == 1


@pytest.mark.regression
def test_audit_system_unknown_config_version_logs_error(mock_gam_env: Dict[str, Any]) -> None:
    manifest = mock_gam_env["manifest_file"]
    GDAUtil.save_json(manifest, {"ConfigVersion": "UNKNOWN", "TrackedAssets": {"schemas": [], "ops": []}})

    report = audit_system(
        format_type="all",
        root_dir=mock_gam_env["root"],
        config_file=manifest,
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert report["total_audited"] == 0


@pytest.mark.regression
def test_audit_system_ignores_archive_schemas_and_dunder_init(mock_gam_env: Dict[str, Any]) -> None:
    manifest = mock_gam_env["manifest_file"]
    archive_dir = mock_gam_env["root"] / "schemas" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    GDAUtil.save_json(archive_dir / "archived.json", {"schema_version": "1.0.0"})

    init_file = mock_gam_env["ops_dir"] / "__init__.py"
    init_file.write_text("", encoding="utf-8")

    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])
    report = audit_system(
        format_type="all",
        root_dir=mock_gam_env["root"],
        config_file=manifest,
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert report["total_audited"] == 0


@pytest.mark.regression
def test_audit_system_detects_pure_hash_drift(mock_gam_env: Dict[str, Any]) -> None:
    manifest = mock_gam_env["manifest_file"]
    tool_file = mock_gam_env["ops_dir"] / "drift_tool.py"
    tool_file.write_text('__version__ = "1.0.0"\n# initial comment\n', encoding="utf-8")

    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])
    tool_file.write_text('__version__ = "1.0.0"\n# modified content comment\n', encoding="utf-8")

    report = audit_system(
        format_type="all",
        root_dir=mock_gam_env["root"],
        config_file=manifest,
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    records = {r["path"]: r["status"] for r in report["records"]}
    assert records["tools/ops/drift_tool.py"] == "DRIFT"
    assert "File content hash differs from gda_config.json baseline" in records["tools/ops/drift_tool.py"] or any(
        "File content hash differs" in iss for r in report["records"] if r["path"] == "tools/ops/drift_tool.py" for iss in r["issues"]
    )


@pytest.mark.regression
def test_audit_system_detects_version_drift(mock_gam_env: Dict[str, Any]) -> None:
    manifest = mock_gam_env["manifest_file"]
    tool_file = mock_gam_env["ops_dir"] / "gpi.py"
    tool_file.write_text('__version__ = "1.0.0"\n', encoding="utf-8")

    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])
    tool_file.write_text('__version__ = "1.0.1"\n', encoding="utf-8")

    report = audit_system(
        format_type="all",
        root_dir=mock_gam_env["root"],
        config_file=manifest,
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    records = {r["path"]: r["status"] for r in report["records"]}
    assert records["tools/ops/gpi.py"] == "DRIFT"


@pytest.mark.regression
def test_audit_system_detects_untracked_asset(mock_gam_env: Dict[str, Any]) -> None:
    manifest = mock_gam_env["manifest_file"]
    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])

    new_tool = mock_gam_env["ops_dir"] / "gfi.py"
    new_tool.write_text('__version__ = "1.0.0"\n', encoding="utf-8")

    report = audit_system(
        format_type="all",
        root_dir=mock_gam_env["root"],
        config_file=manifest,
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    records = {r["path"]: r["status"] for r in report["records"]}
    assert records["tools/ops/gfi.py"] == "UNTRACKED"


@pytest.mark.regression
def test_audit_system_flags_error_on_unversioned_disk_file(mock_gam_env: Dict[str, Any]) -> None:
    manifest = mock_gam_env["manifest_file"]
    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])

    bad_file = mock_gam_env["ops_dir"] / "broken.py"
    bad_file.write_text("x = 1\n", encoding="utf-8")

    report = audit_system(
        format_type="all",
        root_dir=mock_gam_env["root"],
        config_file=manifest,
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    records = {r["path"]: r["status"] for r in report["records"]}
    assert records["tools/ops/broken.py"] == "ERROR"


@pytest.mark.unit
def test_audit_system_supports_json_only_format(mock_gam_env: Dict[str, Any]) -> None:
    manifest = mock_gam_env["manifest_file"]
    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])

    audit_system(
        format_type="json",
        root_dir=mock_gam_env["root"],
        config_file=manifest,
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert len(list(mock_gam_env["reports_dir"].glob("*.json"))) == 1
    assert len(list(mock_gam_env["reports_dir"].glob("*.md"))) == 0


@pytest.mark.unit
def test_audit_system_supports_md_only_format(mock_gam_env: Dict[str, Any]) -> None:
    manifest = mock_gam_env["manifest_file"]
    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])

    audit_system(
        format_type="md",
        root_dir=mock_gam_env["root"],
        config_file=manifest,
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert len(list(mock_gam_env["reports_dir"].glob("*.json"))) == 0
    assert len(list(mock_gam_env["reports_dir"].glob("*.md"))) == 1


# ==============================================================================
# 4. REMEDIATION & REPAIR (Atomized)
# ==============================================================================

@pytest.mark.regression
def test_remediate_latest_report_missing_reports_returns_zero(mock_gam_env: Dict[str, Any]) -> None:
    count = remediate_latest_report(
        root_dir=mock_gam_env["root"],
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert count == 0


@pytest.mark.regression
def test_remediate_latest_report_supports_legacy_gna_prefix(mock_gam_env: Dict[str, Any]) -> None:
    legacy_report = mock_gam_env["reports_dir"] / "gna_audit_20260901_000000.json"
    GDAUtil.save_json(legacy_report, {"records": []})

    count = remediate_latest_report(
        root_dir=mock_gam_env["root"],
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert count == 0


@pytest.mark.regression
def test_remediate_latest_report_skips_ok_records(mock_gam_env: Dict[str, Any]) -> None:
    ok_file = mock_gam_env["ops_dir"] / "ok_file.py"
    ok_file.write_text('__version__ = "1.0.0"\n', encoding="utf-8")

    audit_file = mock_gam_env["reports_dir"] / "gam_audit_20261006_005000.json"
    GDAUtil.save_json(
        audit_file,
        {
            "records": [
                {
                    "path": "tools/ops/ok_file.py",
                    "internal_version": "1.0.0",
                    "status": "OK",
                }
            ]
        },
    )

    count = remediate_latest_report(
        root_dir=mock_gam_env["root"],
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert count == 0


@pytest.mark.regression
def test_remediate_latest_report_skips_missing_disk_file(mock_gam_env: Dict[str, Any]) -> None:
    audit_file = mock_gam_env["reports_dir"] / "gam_audit_20261006_010000.json"
    GDAUtil.save_json(
        audit_file,
        {
            "records": [
                {
                    "path": "tools/ops/phantom.py",
                    "internal_version": "UNKNOWN",
                    "status": "ERROR",
                }
            ]
        },
    )

    count = remediate_latest_report(
        root_dir=mock_gam_env["root"],
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert count == 0


@pytest.mark.regression
def test_remediate_latest_report_repairs_unversioned_schema(mock_gam_env: Dict[str, Any]) -> None:
    unversioned_schema = mock_gam_env["schemas_dir"] / "bad_schema.json"
    GDAUtil.save_json(unversioned_schema, {"type": "object"})

    audit_file = mock_gam_env["reports_dir"] / "gam_audit_20261006_020000.json"
    GDAUtil.save_json(
        audit_file,
        {
            "records": [
                {
                    "path": "schemas/entities/bad_schema.json",
                    "internal_version": "UNKNOWN",
                    "status": "ERROR",
                }
            ]
        },
    )

    count = remediate_latest_report(
        root_dir=mock_gam_env["root"],
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert count == 1
    repaired = GDAUtil.load_json(unversioned_schema)
    assert repaired["schema_version"] == "0.0.999"


@pytest.mark.regression
def test_remediate_latest_report_repairs_ops_tool_with_existing_unknown_version(mock_gam_env: Dict[str, Any]) -> None:
    unversioned_tool = mock_gam_env["ops_dir"] / "unknown_ver.py"
    unversioned_tool.write_text('__version__ = "UNKNOWN"\nx = 1\n', encoding="utf-8")

    audit_file = mock_gam_env["reports_dir"] / "gam_audit_20261006_030000.json"
    GDAUtil.save_json(
        audit_file,
        {
            "records": [
                {
                    "path": "tools/ops/unknown_ver.py",
                    "internal_version": "UNKNOWN",
                    "status": "ERROR",
                }
            ]
        },
    )

    count = remediate_latest_report(
        root_dir=mock_gam_env["root"],
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert count == 1
    content = unversioned_tool.read_text(encoding="utf-8")
    assert '__version__ = "0.0.999"' in content


@pytest.mark.regression
def test_remediate_latest_report_prepends_version_when_missing_in_ops_tool(mock_gam_env: Dict[str, Any]) -> None:
    bare_tool = mock_gam_env["ops_dir"] / "bare.py"
    bare_tool.write_text("x = 100\n", encoding="utf-8")

    audit_file = mock_gam_env["reports_dir"] / "gam_audit_20261006_040000.json"
    GDAUtil.save_json(
        audit_file,
        {
            "records": [
                {
                    "path": "tools/ops/bare.py",
                    "internal_version": "UNKNOWN",
                    "status": "ERROR",
                }
            ]
        },
    )

    count = remediate_latest_report(
        root_dir=mock_gam_env["root"],
        reports_dir=mock_gam_env["reports_dir"],
        logger=mock_gam_env["logger"],
    )
    assert count == 1
    content = bare_tool.read_text(encoding="utf-8")
    assert content.startswith('__version__ = "0.0.999"')


# ==============================================================================
# 5. CLI PIPELINE INTEGRATION (Atomized)
# ==============================================================================

@pytest.mark.smoke
def test_gam_cli_no_args_exits_cleanly(mock_gam_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["gam.py"])
    assert main() == 0


@pytest.mark.smoke
def test_gam_cli_generate_config_mode(mock_gam_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["gam.py", "--generate-config"])
    assert main() == 0
    assert (mock_gam_env["root"] / "gda_config.json").exists()


@pytest.mark.smoke
def test_gam_cli_audit_mode(mock_gam_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = mock_gam_env["manifest_file"]
    generate_config(root_dir=mock_gam_env["root"], config_file=manifest, logger=mock_gam_env["logger"])

    monkeypatch.setattr("sys.argv", ["gam.py", "--audit", "--report", "json"])
    assert main() == 0
    assert len(list(mock_gam_env["reports_dir"].glob("*.json"))) == 1


@pytest.mark.smoke
def test_gam_cli_repair_mode(mock_gam_env: Dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["gam.py", "--repair"])
    assert main() == 0