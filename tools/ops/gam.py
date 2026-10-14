# Name: gam.py
# Path: tools/ops/gam.py
# Version: 1.1.0+build.20261006.2

"""GAM (Genealogy Archive Manager).

Permanent operational tool for system configuration, asset tracking,
operational script and schema integrity auditing, hash drift detection,
automated remediation, and diagnostic report generation.

Tracks strictly:
- Active operational tools: tools/ops/*.py
- Schema specifications: schemas/**/*.json (excluding schemas/archive/)
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from gdacore.config import CONFIG, GDAConfig
from gdacore.logger import get_logger, setup_logger
from gdacore.util import GDAUtil

__version__ = "1.1.0+build.20261006.2"


def extract_metadata(file_path: Path, logger: Optional[logging.Logger] = None) -> Tuple[str, str]:
    """Extracts internal version string and description from schemas or operational tools.

    Args:
        file_path: Target file to inspect (.json or .py).
        logger: Operational logger.

    Returns:
        Tuple of (version, description).
    """
    log = logger or logging.getLogger("gam")
    version = "UNKNOWN"
    description = "N/A"
    try:
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            data = GDAUtil.load_json(file_path)
            for key in ["schema_version", "SchemaVersion", "version", "Version", "FileVersion"]:
                if isinstance(data, dict) and key in data:
                    version = str(data[key])
                    break
            if version == "UNKNOWN" and isinstance(data, dict) and len(data) == 1:
                top_key = list(data.keys())[0]
                if isinstance(data[top_key], dict):
                    for sub_key in ["schema_version", "SchemaVersion", "version"]:
                        if sub_key in data[top_key]:
                            version = str(data[top_key][sub_key])
                            break
            description = (
                data.get("description") or data.get("title") or f"Schema specification ({file_path.name})"
                if isinstance(data, dict)
                else f"JSON Entity ({file_path.name})"
            )
        elif suffix == ".py":
            content = file_path.read_text(encoding="utf-8", errors="replace")
            v_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if v_match:
                version = v_match.group(1).strip()
            d_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
            if d_match:
                description = d_match.group(1).strip().splitlines()[0]
            else:
                description = f"Operational script ({file_path.name})"
    except Exception as e:
        log.error("Error parsing metadata for %s: %s", file_path, e)
    return version, description


def generate_config(
    root_dir: Optional[Path] = None,
    config_file: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """Scans operational tools and schemas to generate the baseline manifest.

    Args:
        root_dir: Archive root directory.
        config_file: Path to target manifest file.
        logger: Operational logger.

    Returns:
        Generated configuration manifest dictionary.
    """
    target_root = root_dir or CONFIG.root
    target_config = config_file or (target_root / "gda_config.json")
    log = logger or logging.getLogger("gam")

    log.info("Generating system configuration manifest...", extra={"sys_event": True})

    if target_config.exists():
        bk_file = target_config.with_suffix(target_config.suffix + ".bk")
        try:
            target_config.replace(bk_file)
            log.info("Backed up existing config to %s", bk_file)
        except Exception as e:
            log.error("Failed to backup existing config: %s", e)

    tracked_schemas: List[Dict[str, Any]] = []
    schemas_dir = target_root / "schemas"
    if schemas_dir.exists():
        for p in sorted(schemas_dir.rglob("*.json")):
            if "archive" in p.parts or "-bk-" in p.name:
                continue
            rel = p.relative_to(target_root).as_posix()
            ver, desc = extract_metadata(p, logger=log)
            if ver == "UNKNOWN":
                log.warning("Skipping unversioned schema: %s", rel)
                continue
            tracked_schemas.append({
                "path": rel,
                "expected_version": ver,
                "sha256": GDAUtil.compute_sha256(p),
                "purpose": desc,
            })

    tracked_ops: List[Dict[str, Any]] = []
    ops_dir = target_root / "tools" / "ops"
    if ops_dir.exists():
        for p in sorted(ops_dir.glob("*.py")):
            if p.name.startswith("__"):
                continue
            rel = p.relative_to(target_root).as_posix()
            ver, desc = extract_metadata(p, logger=log)
            if ver == "UNKNOWN":
                log.warning("Skipping unversioned operational tool: %s", rel)
                continue
            tracked_ops.append({
                "path": rel,
                "expected_version": ver,
                "sha256": GDAUtil.compute_sha256(p),
                "purpose": desc,
            })

    config_data: Dict[str, Any] = {
        "ConfigVersion": "1.1.0",
        "LastUpdated": datetime.now().strftime("%Y-%m-%d"),
        "ArchiveName": "Genealogy Digital Archive",
        "RootAnchor": str(target_root),
        "TrackedAssets": {
            "schemas": tracked_schemas,
            "ops": tracked_ops,
        },
    }

    GDAUtil.save_json(target_config, config_data)
    log.info("Configuration file written to %s", target_config)
    return config_data


def audit_system(
    format_type: str = "all",
    verbose: bool = False,
    root_dir: Optional[Path] = None,
    config_file: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """Audits operational tools and schemas against internal versions and hashes.

    Args:
        format_type: Output format ("json", "md", or "all").
        verbose: Whether to log detailed diagnostic messages.
        root_dir: Archive root directory.
        config_file: Path to gda_config.json.
        reports_dir: Target reports directory.
        logger: Operational logger.

    Returns:
        Audit report dictionary.
    """
    target_root = root_dir or CONFIG.root
    target_config = config_file or (target_root / "gda_config.json")
    target_reports = reports_dir or CONFIG.reports
    log = logger or logging.getLogger("gam")

    if not target_config.exists():
        log.error("Audit aborted: gda_config.json missing.")
        sys.exit(1)

    config = GDAUtil.load_json(target_config)
    if config.get("ConfigVersion", "UNKNOWN") == "UNKNOWN":
        log.error("Critical error: gda_config.json ConfigVersion is UNKNOWN.")

    tracked_map: Dict[str, Dict[str, Any]] = {}
    for category in ["schemas", "ops"]:
        for item in config.get("TrackedAssets", {}).get(category, []):
            tracked_map[item["path"]] = item

    all_disk_files: List[Path] = []
    schemas_dir = target_root / "schemas"
    if schemas_dir.exists():
        for p in schemas_dir.rglob("*.json"):
            if "archive" in p.parts or "-bk-" in p.name:
                continue
            all_disk_files.append(p)

    ops_dir = target_root / "tools" / "ops"
    if ops_dir.exists():
        for p in ops_dir.glob("*.py"):
            if p.name.startswith("__"):
                continue
            all_disk_files.append(p)

    audit_records: List[Dict[str, Any]] = []
    discrepancies = 0

    for file_path in sorted(all_disk_files):
        rel_path = file_path.relative_to(target_root).as_posix()
        file_hash = GDAUtil.compute_sha256(file_path)
        internal_ver, description = extract_metadata(file_path, logger=log)
        status = "OK"
        issues: List[str] = []

        if internal_ver == "UNKNOWN":
            status = "ERROR"
            issues.append("Internal version is UNKNOWN (requires repair to 0.0.999)")
            discrepancies += 1

        if status == "OK":
            if rel_path in tracked_map:
                expected_hash = tracked_map[rel_path]["sha256"]
                expected_ver = tracked_map[rel_path].get("expected_version")
                if internal_ver != expected_ver:
                    status = "DRIFT"
                    issues.append(f"Internal version changed from manifest ({expected_ver} -> {internal_ver})")
                    discrepancies += 1
                elif expected_hash != file_hash:
                    status = "DRIFT"
                    issues.append("File content hash differs from gda_config.json baseline")
                    discrepancies += 1
            else:
                status = "UNTRACKED"
                issues.append("File exists on disk but is missing from gda_config.json")
                discrepancies += 1

        audit_records.append({
            "path": rel_path,
            "internal_version": internal_ver,
            "sha256": file_hash,
            "status": status,
            "issues": issues,
            "description": description,
        })

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_data: Dict[str, Any] = {
        "audit_timestamp": datetime.now().isoformat(),
        "total_audited": len(audit_records),
        "discrepancies_detected": discrepancies,
        "records": audit_records,
    }

    target_reports.mkdir(parents=True, exist_ok=True)
    if format_type in ["json", "all"]:
        json_rep = target_reports / f"gam_audit_{run_timestamp}.json"
        GDAUtil.save_json(json_rep, report_data)

    if format_type in ["md", "all"]:
        md_rep = target_reports / f"gam_audit_{run_timestamp}.md"
        md_lines = [
            "# GAM System Integrity Audit Report",
            f"<!-- Timestamp: {report_data['audit_timestamp']} -->",
            "",
            f"* **Total Files Audited:** {len(audit_records)}",
            f"* **Discrepancies Detected:** {discrepancies}",
            "",
            "| File Path | Version | Status | Issues |",
            "|---|---|---|---|",
        ]
        for rec in audit_records:
            iss_str = ", ".join(rec["issues"]) if rec["issues"] else "None"
            md_lines.append(f"| `{rec['path']}` | {rec['internal_version']} | **{rec['status']}** | {iss_str} |")
        md_rep.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return report_data


def remediate_latest_report(
    root_dir: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Reads the most recent audit report and forces UNKNOWN versions to 0.0.999.

    Args:
        root_dir: Archive root directory.
        reports_dir: Directory containing audit reports.
        logger: Operational logger.

    Returns:
        Total number of repaired files.
    """
    target_root = root_dir or CONFIG.root
    target_reports = reports_dir or CONFIG.reports
    log = logger or logging.getLogger("gam")

    reports = sorted(list(target_reports.glob("gam_audit_*.json")))
    if not reports:
        reports = sorted(list(target_reports.glob("gna_audit_*.json")))

    if not reports:
        log.warning("No prior audit reports found in reports/ to remediate.")
        return 0

    latest_report = reports[-1]
    data = GDAUtil.load_json(latest_report)
    fixed_count = 0

    for rec in data.get("records", []):
        file_path = target_root / rec["path"]
        if not file_path.exists():
            continue
        if rec["internal_version"] == "UNKNOWN" or rec["status"] == "ERROR":
            forced_ver = "0.0.999"
            if file_path.suffix.lower() == ".json":
                try:
                    jdata = GDAUtil.load_json(file_path)
                    jdata["schema_version"] = forced_ver
                    GDAUtil.save_json(file_path, jdata)
                    fixed_count += 1
                except Exception as e:
                    log.error("Failed to update schema %s: %s", rec["path"], e)
            elif file_path.suffix.lower() == ".py":
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if "__version__" in content:
                        content = re.sub(
                            r'__version__\s*=\s*["\'][^"\']+["\']',
                            f'__version__ = "{forced_ver}"',
                            content,
                        )
                    else:
                        content = f'__version__ = "{forced_ver}"\n' + content
                    file_path.write_text(content, encoding="utf-8")
                    fixed_count += 1
                except Exception as e:
                    log.error("Failed to update operational tool %s: %s", rec["path"], e)

    if fixed_count > 0:
        generate_config(root_dir=target_root, logger=log)

    return fixed_count


def main() -> int:
    """Main CLI entry point for GAM pipeline."""
    parser = argparse.ArgumentParser(
        description=f"GAM System Manager ({__version__}): Operational Tool & Schema Baseline Auditor."
    )
    parser.add_argument("-a", "--audit", action="store_true", help="Run system integrity audit and generate reports")
    parser.add_argument("-g", "--generate-config", action="store_true", help="Generate or refresh gda_config.json baseline")
    parser.add_argument("-r", "--report", choices=["json", "md", "all"], default="all", help="Audit report format")
    parser.add_argument("--repair", action="store_true", help="Remediate UNKNOWN versions using latest report")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose diagnostics")
    parser.add_argument("--debug", action="store_true", help="Output execution traces directly to stderr")
    args = parser.parse_args()

    c_level = logging.DEBUG if args.debug else (logging.DEBUG if args.verbose else logging.INFO)
    logger = setup_logger("gam", ephemeral=True, console_level=c_level)
    logger.info("Initialized GAM System Manager CLI (%s).", __version__, extra={"sys_event": True})

    if args.generate_config:
        generate_config(logger=logger)
        return 0
    if args.repair:
        remediate_latest_report(logger=logger)
        return 0
    if args.audit:
        audit_system(format_type=args.report, verbose=args.verbose, logger=logger)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())