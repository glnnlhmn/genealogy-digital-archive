# Name: gam.py
# Path: tools/ops/gam.py

"""GAM (Genealogy Archive Manager).

Permanent operational tool for system configuration, asset tracking,
schema/persona integrity auditing, hash drift detection, automated remediation,
and report generation.

Public Interface:
    - audit_system(format_type: str, verbose: bool) -> dict: Executes system integrity checks and exports unique timestamped audit reports.
    - generate_config() -> dict: Backs up existing config, scans the archive root, and generates a fresh gda_config.json baseline manifest.
    - remediate_latest_report() -> None: Parses the latest audit report and automatically repairs UNKNOWN faults.
"""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple

# Ensure repository root is on sys.path for standalone invocation
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil

__version__ = "1.0.7+build.20260922.1"


def extract_metadata(file_path: Path, logger: Optional[logging.Logger] = None) -> Tuple[str, str]:
    """Extracts internal version string and description from file headers or JSON metadata.

    Args:
        file_path (Path): Target file to inspect.
        logger (Optional[logging.Logger]): Operational logger.

    Returns:
        Tuple[str, str]: Extracted internal version and description.
    """
    log = logger or logging.getLogger("gam")
    version = "UNKNOWN"
    description = "N/A"
    try:
        if file_path.suffix.lower() == ".json":
            data = GDAUtil.load_json(file_path)
            for key in ["SchemaVersion", "version", "Version", "FileVersion", "ConfigVersion"]:
                if isinstance(data, dict) and key in data:
                    version = str(data[key])
                    break
            if version == "UNKNOWN" and isinstance(data, dict) and len(data) == 1:
                top_key = list(data.keys())[0]
                if isinstance(data[top_key], dict) and "SchemaVersion" in data[top_key]:
                    version = str(data[top_key]["SchemaVersion"])
            description = f"JSON Metadata / Config entity ({file_path.name})"
        elif file_path.suffix.lower() == ".md":
            content = file_path.read_text(encoding="utf-8", errors="replace")
            v_match = re.search(
                r"<!--\s*(?:version|spec\s*version|v):\s*([vV]?\d+\.\d+\.\d+)\s*-->",
                content,
                re.IGNORECASE,
            )
            if v_match:
                version = v_match.group(1).strip()
            else:
                v_match_alt = re.search(
                    r"(?:version|v)\s*[:=]\s*([vV]?\d+\.\d+\.\d+)",
                    content,
                    re.IGNORECASE,
                )
                if v_match_alt:
                    version = v_match_alt.group(1).strip()
            lines = content.splitlines()
            for line in lines:
                if line.startswith("# "):
                    description = line.replace("#", "").strip()
                    break
    except Exception as e:
        log.error(f"Error parsing metadata for {file_path}: {e}")
    return version, description


def generate_config(
    root_dir: Optional[Path] = None,
    config_file: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
) -> dict:
    """Backs up existing config, scans repository schemas/prompts, and generates baseline manifest.

    Args:
        root_dir (Optional[Path]): Archive root directory.
        config_file (Optional[Path]): Path to target manifest file.
        logger (Optional[logging.Logger]): Operational logger.

    Returns:
        dict: Generated configuration manifest payload.
    """
    target_root = root_dir or CONFIG.root
    target_config = config_file or CONFIG.config_manifest
    log = logger or logging.getLogger("gam")

    log.info("Generating system configuration manifest...", extra={"sys_event": True})

    if target_config.exists():
        bk_file = target_config.with_suffix(target_config.suffix + ".bk")
        try:
            target_config.replace(bk_file)
            rel_bk = bk_file.relative_to(target_root) if bk_file.is_relative_to(target_root) else bk_file
            print(f"[+] Existing configuration backed up to: {rel_bk}")
            log.info(f"Backed up existing config to {bk_file}")
        except Exception as e:
            log.error(f"Failed to backup existing config: {e}")
            print(f"[!] Warning: Failed to backup existing config: {e}")

    schemas_dir = target_root / "schemas"
    prompts_dir = target_root / "prompts"

    tracked_schemas = []
    if schemas_dir.exists():
        for p in sorted(schemas_dir.rglob("*.json")):
            if "archive" in p.parts or "-bk-" in p.name:
                continue
            rel = p.relative_to(target_root).as_posix()
            ver, desc = extract_metadata(p, logger=log)
            if ver == "UNKNOWN":
                print(f"[!] Skipping unversioned schema (UNKNOWN version): {rel}")
                continue
            tracked_schemas.append({
                "path": rel,
                "expected_version": ver,
                "sha256": GDAUtil.compute_sha256(p),
                "purpose": desc,
            })

    tracked_prompts = []
    if prompts_dir.exists():
        for p in sorted(prompts_dir.rglob("*.md")):
            if "archive" in p.parts or "-bk-" in p.name:
                continue
            rel = p.relative_to(target_root).as_posix()
            ver, desc = extract_metadata(p, logger=log)
            if ver == "UNKNOWN":
                print(f"[!] Skipping unversioned prompt (UNKNOWN version): {rel}")
                continue
            tracked_prompts.append({
                "path": rel,
                "expected_version": ver,
                "sha256": GDAUtil.compute_sha256(p),
                "purpose": desc,
            })

    config_data = {
        "ConfigVersion": "1.0.0",
        "LastUpdated": datetime.now().strftime("%Y-%m-%d"),
        "ArchiveName": "Genealogy Digital Archive",
        "RootAnchor": str(target_root),
        "TrackedAssets": {
            "schemas": tracked_schemas,
            "prompts": tracked_prompts,
        },
    }

    GDAUtil.save_json(target_config, config_data)
    log.info(f"Configuration file written to {target_config}")
    rel_cfg = target_config.relative_to(target_root) if target_config.is_relative_to(target_root) else target_config
    print(f"[+] Configuration file successfully written to: {rel_cfg}")
    return config_data


def audit_system(
    format_type: str = "all",
    verbose: bool = False,
    root_dir: Optional[Path] = None,
    config_file: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
) -> dict:
    """Performs full system integrity audit against internal versions and hashes.

    Args:
        format_type (str): Output format ("json", "md", or "all").
        verbose (bool): Whether to log detailed diagnostic messages.
        root_dir (Optional[Path]): Archive root directory.
        config_file (Optional[Path]): Path to gda_config.json.
        reports_dir (Optional[Path]): Target reports output directory.
        logger (Optional[logging.Logger]): Operational logger.

    Returns:
        dict: Full audit report payload.
    """
    target_root = root_dir or CONFIG.root
    target_config = config_file or CONFIG.config_manifest
    target_reports = reports_dir or CONFIG.reports
    log = logger or logging.getLogger("gam")

    if not target_config.exists():
        print("[!] Error: Configuration file 'gda_config.json' does not exist.")
        print("[i] Hard stop: Run with --generate-config (-g) to initialize baseline manifest.")
        log.error("Audit aborted: gda_config.json missing.")
        sys.exit(1)

    config = GDAUtil.load_json(target_config)
    if config.get("ConfigVersion", "UNKNOWN") == "UNKNOWN":
        print("[!] CRITICAL ERROR: gda_config.json contains an UNKNOWN ConfigVersion.")
        log.error("Critical error: gda_config.json ConfigVersion is UNKNOWN.")

    tracked_map = {}
    for category in ["schemas", "prompts"]:
        for item in config.get("TrackedAssets", {}).get(category, []):
            if item.get("expected_version") == "UNKNOWN":
                print(f"[!] CRITICAL CONFIG ERROR: Tracked asset '{item['path']}' has expected_version: UNKNOWN")
            tracked_map[item["path"]] = item

    all_disk_files = []
    schemas_dir = target_root / "schemas"
    prompts_dir = target_root / "prompts"

    if schemas_dir.exists():
        for p in schemas_dir.rglob("*.json"):
            if "archive" in p.parts or "-bk-" in p.name:
                continue
            all_disk_files.append(p)
    if prompts_dir.exists():
        for p in prompts_dir.rglob("*.md"):
            if "archive" in p.parts or "-bk-" in p.name:
                continue
            all_disk_files.append(p)

    audit_records = []
    discrepancies = 0
    print("\n" + "=" * 95)
    print(f"{'FILE PATH':<55} | {'INTERNAL VER':<14} | {'STATUS'}")
    print("=" * 95)

    for file_path in sorted(all_disk_files):
        rel_path = file_path.relative_to(target_root).as_posix()
        file_hash = GDAUtil.compute_sha256(file_path)
        internal_ver, description = extract_metadata(file_path, logger=log)
        status = "OK"
        issues = []

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
        print(f"{rel_path:<55} | {internal_ver:<14} | {status}")
        for issue in issues:
            print(f"    [!] {issue}")
    print("=" * 95)

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_data = {
        "audit_timestamp": datetime.now().isoformat(),
        "total_audited": len(audit_records),
        "discrepancies_detected": discrepancies,
        "records": audit_records,
    }

    target_reports.mkdir(parents=True, exist_ok=True)
    if format_type in ["json", "all"]:
        json_rep = target_reports / f"gam_audit_{run_timestamp}.json"
        GDAUtil.save_json(json_rep, report_data)
        rel_jrep = json_rep.relative_to(target_root) if json_rep.is_relative_to(target_root) else json_rep
        print(f"[+] JSON report saved to: {rel_jrep}")

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
        rel_mrep = md_rep.relative_to(target_root) if md_rep.is_relative_to(target_root) else md_rep
        print(f"[+] Markdown report saved to: {rel_mrep}")

    return report_data


def remediate_latest_report(
    root_dir: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Reads the most recent audit report and forces UNKNOWN versions to 0.0.999.

    Args:
        root_dir (Optional[Path]): Archive root directory.
        reports_dir (Optional[Path]): Directory containing audit reports.
        logger (Optional[logging.Logger]): Operational logger.
    """
    target_root = root_dir or CONFIG.root
    target_reports = reports_dir or CONFIG.reports
    log = logger or logging.getLogger("gam")

    reports = sorted(list(target_reports.glob("gam_audit_*.json")))
    if not reports:
        # Check backward-compatible legacy report names
        reports = sorted(list(target_reports.glob("gna_audit_*.json")))

    if not reports:
        print("[!] No prior audit reports found in reports/ to remediate.")
        return

    latest_report = reports[-1]
    print(f"[i] Loading latest audit report: {latest_report.name}")
    data = GDAUtil.load_json(latest_report)
    fixed_count = 0

    for rec in data.get("records", []):
        file_path = target_root / rec["path"]
        if not file_path.exists():
            continue
        if rec["internal_version"] == "UNKNOWN" or rec["status"] == "ERROR":
            forced_ver = "0.0.999"
            if file_path.suffix.lower() == ".md":
                content = file_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                new_lines = []
                injected = False
                for line in lines:
                    new_lines.append(line)
                    if line.startswith("# ") and not injected:
                        new_lines.append(f"<!-- Version: {forced_ver} -->")
                        injected = True
                if not injected:
                    new_lines.insert(0, f"<!-- Version: {forced_ver} -->")
                file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                print(f"    [!] Forced version {forced_ver} into markdown header for {rec['path']}")
                fixed_count += 1
            elif file_path.suffix.lower() == ".json":
                try:
                    jdata = GDAUtil.load_json(file_path)
                    jdata["SchemaVersion"] = forced_ver
                    GDAUtil.save_json(file_path, jdata)
                    print(f"    [!] Forced SchemaVersion {forced_ver} into JSON schema {rec['path']}")
                    fixed_count += 1
                except Exception as e:
                    log.error(f"Failed to update JSON schema {rec['path']}: {e}")

    print(f"[+] Remediation complete. Successfully resolved {fixed_count} issue(s) with forced 0.0.999 overrides.")
    if fixed_count > 0:
        print("[i] Refreshing configuration manifest...")
        generate_config(root_dir=target_root, logger=log)


def interactive_menu() -> None:
    """Runs the interactive TUI management console loop."""
    while True:
        print("\n" + "=" * 50)
        print(f" GAM SYSTEM MANAGEMENT CONSOLE ({__version__})")
        print("=" * 50)
        print("[1] Run Full System Integrity Audit")
        print("[2] Generate / Refresh System Config (gda_config.json)")
        print("[3] Auto-Repair Discrepancies (Force UNKNOWN to 0.0.999)")
        print("[Q] Exit")
        print("=" * 50)
        choice = input("Select an option [1-3, Q]: ").strip()
        if choice == "" or choice.lower() == "q":
            print("Exiting GAM Management Console. Goodbye!")
            break
        elif choice == "1":
            audit_system(format_type="all")
        elif choice == "2":
            generate_config()
        elif choice == "3":
            remediate_latest_report()
        else:
            print("[!] Invalid option. Please enter 1, 2, 3, or Q.")


def main() -> None:
    """Main CLI entry point for argument parsing and routing."""
    parser = argparse.ArgumentParser(
        description=f"GAM System Manager ({__version__}): Genealogy Archive Configuration & Integrity Auditor."
    )
    parser.add_argument("-a", "--audit", action="store_true",
                        help="Run full system integrity audit and generate reports")
    parser.add_argument("-g", "--generate-config", action="store_true",
                        help="Generate or refresh gda_config.json baseline manifest")
    parser.add_argument("-r", "--report", choices=["json", "md", "all"], default="all",
                        help="Export audit report format")
    parser.add_argument("--repair", action="store_true",
                        help="Attempt automated remediation using latest report")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose debugging logs")
    parser.add_argument("--debug", action="store_true",
                        help="Route runtime traces directly to console/stderr")
    args = parser.parse_args()

    c_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logger("gam", console_level=c_level, file_level=logging.DEBUG)
    logger.info(f"Initialized GAM System Manager CLI ({__version__}).", extra={"sys_event": True})

    if not args.audit and not args.generate_config and not args.repair:
        interactive_menu()
        return
    if args.generate_config:
        generate_config(logger=logger)
    if args.repair:
        remediate_latest_report(logger=logger)
    if args.audit:
        audit_system(format_type=args.report, verbose=args.verbose, logger=logger)


if __name__ == "__main__":
    main()