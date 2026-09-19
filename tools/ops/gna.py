# Name: gna.py
# Path: tools/ops/gna.py
"""GNA (Genealogy Archive System Manager)

Permanent operational tool for system configuration, asset tracking,
schema/persona integrity auditing, hash drift detection, automated remediation, and report generation.

Public Interface:
    - audit_system(format_type: str, verbose: bool) -> dict: Executes system integrity checks and exports unique timestamped audit reports.
    - generate_config() -> dict: Backs up existing config, scans the archive root, and generates a fresh gda_config.json baseline manifest.
    - remediate_latest_report() -> None: Parses the latest audit report and automatically repairs UNKNOWN faults.

Dependencies:
    - Standard Library only: argparse, hashlib, json, pathlib, re, sys, datetime

Version: 1.0.6
"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple

ROOT_DIR = Path("G:/My Drive/genealogy-digital-archive")
CONFIG_FILE = ROOT_DIR / "gda_config.json"
REPORTS_DIR = ROOT_DIR / "reports"
LOGS_DIR = ROOT_DIR / "logs"
GTEMP_DIR = ROOT_DIR / "gtemp"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
GTEMP_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SESSION_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOGS_DIR / f"gna-{SESSION_TIMESTAMP}.log"


def log(msg: str, is_error: bool = False, verbose: bool = False) -> None:
    """Writes a timestamped log entry to the active session log and stderr/stdout if verbose."""
    line = f"[{datetime.now().isoformat()}] {'ERROR: ' if is_error else ''}{msg}\n"
    if is_error:
        sys.stderr.write(line)
    elif verbose:
        sys.stdout.write(line)
    sys.stdout.flush()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def compute_sha256(file_path: Path) -> str:
    """Computes the SHA-256 cryptographic hash of a target file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        log(f"Failed to compute hash for {file_path}: {e}", is_error=True)
        return "ERROR_HASH"


def extract_metadata(file_path: Path) -> Tuple[str, str]:
    """Extracts internal version string and description from file headers or JSON metadata."""
    version = "UNKNOWN"
    description = "N/A"
    try:
        if file_path.suffix.lower() == ".json":
            content = file_path.read_text(encoding="utf-8", errors="replace")
            data = json.loads(content)
            for key in ["SchemaVersion", "version", "Version", "FileVersion", "ConfigVersion"]:
                if key in data:
                    version = str(data[key])
                    break
            if version == "UNKNOWN" and len(data) == 1:
                top_key = list(data.keys())[0]
                if isinstance(data[top_key], dict) and "SchemaVersion" in data[top_key]:
                    version = str(data[top_key]["SchemaVersion"])
            description = f"JSON Metadata / Config entity ({file_path.name})"
        elif file_path.suffix.lower() == ".md":
            content = file_path.read_text(encoding="utf-8", errors="replace")
            v_match = re.search(r"<!--\s*(?:version|spec\s*version|v):\s*([vV]?\d+\.\d+\.\d+)\s*-->", content,
                                re.IGNORECASE)
            if v_match:
                version = v_match.group(1).strip()
            else:
                v_match_alt = re.search(r"(?:version|v)\s*[:=]\s*([vV]?\d+\.\d+\.\d+)", content, re.IGNORECASE)
                if v_match_alt:
                    version = v_match_alt.group(1).strip()
            lines = content.splitlines()
            for line in lines:
                if line.startswith("# "):
                    description = line.replace("#", "").strip()
                    break
    except Exception as e:
        log(f"Error parsing metadata for {file_path}: {e}", is_error=True)
    return version, description


def generate_config() -> dict:
    """Backs up existing config, scans repository schemas/prompts, and generates a fresh gda_config.json baseline."""
    log("Generating system configuration manifest...")

    if CONFIG_FILE.exists():
        bk_file = CONFIG_FILE.with_suffix(CONFIG_FILE.suffix + ".bk")
        try:
            CONFIG_FILE.replace(bk_file)
            print(f"[+] Existing configuration backed up to: {bk_file.relative_to(ROOT_DIR)}")
            log(f"Backed up existing config to {bk_file}")
        except Exception as e:
            log(f"Failed to backup existing config: {e}", is_error=True)
            print(f"[!] Warning: Failed to backup existing config: {e}")

    schemas_dir = ROOT_DIR / "schemas"
    prompts_dir = ROOT_DIR / "prompts"
    tracked_schemas = []
    if schemas_dir.exists():
        for p in sorted(schemas_dir.rglob("*.json")):
            if "archive" in p.parts or "-bk-" in p.name:
                continue
            rel = p.relative_to(ROOT_DIR).as_posix()
            ver, desc = extract_metadata(p)
            if ver == "UNKNOWN":
                print(f"[!] Skipping unversioned schema (UNKNOWN version): {rel}")
                continue
            tracked_schemas.append({"path": rel, "expected_version": ver, "sha256": compute_sha256(p), "purpose": desc})

    tracked_prompts = []
    if prompts_dir.exists():
        for p in sorted(prompts_dir.rglob("*.md")):
            if "archive" in p.parts or "-bk-" in p.name:
                continue
            rel = p.relative_to(ROOT_DIR).as_posix()
            ver, desc = extract_metadata(p)
            if ver == "UNKNOWN":
                print(f"[!] Skipping unversioned prompt (UNKNOWN version): {rel}")
                continue
            tracked_prompts.append({"path": rel, "expected_version": ver, "sha256": compute_sha256(p), "purpose": desc})

    config_data = {
        "ConfigVersion": "1.0.0",
        "LastUpdated": datetime.now().strftime("%Y-%m-%d"),
        "ArchiveName": "Genealogy Digital Archive",
        "RootAnchor": str(ROOT_DIR),
        "TrackedAssets": {"schemas": tracked_schemas, "prompts": tracked_prompts},
    }
    CONFIG_FILE.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
    log(f"Configuration file written to {CONFIG_FILE}")
    print(f"[+] Configuration file successfully written to: {CONFIG_FILE.relative_to(ROOT_DIR)}")
    return config_data


def audit_system(format_type: str = "all", verbose: bool = False) -> dict:
    """Performs full system integrity audit against internal versions and hashes."""
    if not CONFIG_FILE.exists():
        print("[!] Error: Configuration file 'gda_config.json' does not exist.")
        print("[i] Hard stop: Run with --generate-config (-g) to initialize baseline manifest.")
        log("Audit aborted: gda_config.json missing.", is_error=True)
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if config.get("ConfigVersion", "UNKNOWN") == "UNKNOWN":
        print("[!] CRITICAL ERROR: gda_config.json contains an UNKNOWN ConfigVersion.")
        log("Critical error: gda_config.json ConfigVersion is UNKNOWN.", is_error=True)

    tracked_map = {}
    for category in ["schemas", "prompts"]:
        for item in config.get("TrackedAssets", {}).get(category, []):
            if item.get("expected_version") == "UNKNOWN":
                print(f"[!] CRITICAL CONFIG ERROR: Tracked asset '{item['path']}' has expected_version: UNKNOWN")
            tracked_map[item["path"]] = item

    all_disk_files = []
    schemas_dir = ROOT_DIR / "schemas"
    prompts_dir = ROOT_DIR / "prompts"
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
        rel_path = file_path.relative_to(ROOT_DIR).as_posix()
        file_hash = compute_sha256(file_path)
        internal_ver, description = extract_metadata(file_path)
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
    if format_type in ["json", "all"]:
        json_rep = REPORTS_DIR / f"gna_audit_{run_timestamp}.json"
        json_rep.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        print(f"[+] JSON report saved to: {json_rep.relative_to(ROOT_DIR)}")
    if format_type in ["md", "all"]:
        md_rep = REPORTS_DIR / f"gna_audit_{run_timestamp}.md"
        md_lines = [
            "# GNA System Integrity Audit Report",
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
        print(f"[+] Markdown report saved to: {md_rep.relative_to(ROOT_DIR)}")
    return report_data


def remediate_latest_report() -> None:
    """Reads the most recent audit report and forces UNKNOWN versions to 0.0.999."""
    reports = sorted(list(REPORTS_DIR.glob("gna_audit_*.json")))
    if not reports:
        print("[!] No prior audit reports found in reports/ to remediate.")
        return
    latest_report = reports[-1]
    print(f"[i] Loading latest audit report: {latest_report.name}")
    data = json.loads(latest_report.read_text(encoding="utf-8"))
    fixed_count = 0
    for rec in data.get("records", []):
        file_path = ROOT_DIR / rec["path"]
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
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    jdata = json.loads(content)
                    jdata["SchemaVersion"] = forced_ver
                    file_path.write_text(json.dumps(jdata, indent=2) + "\n", encoding="utf-8")
                    print(f"    [!] Forced SchemaVersion {forced_ver} into JSON schema {rec['path']}")
                    fixed_count += 1
                except Exception as e:
                    print(f"    [ERROR] Failed to update JSON schema {rec['path']}: {e}")
    print(f"[+] Remediation complete. Successfully resolved {fixed_count} issue(s) with forced 0.0.999 overrides.")
    if fixed_count > 0:
        print("[i] Refreshing configuration manifest...")
        generate_config()


def interactive_menu() -> None:
    """Runs the interactive TUI management console loop."""
    while True:
        print("\n" + "=" * 50)
        print(" GNA SYSTEM MANAGEMENT CONSOLE (v1.0.6)")
        print("=" * 50)
        print("[1] Run Full System Integrity Audit")
        print("[2] Generate / Refresh System Config (gda_config.json)")
        print("[3] Auto-Repair Discrepancies (Force UNKNOWN to 0.0.999)")
        print("[Q] Exit")
        print("=" * 50)
        choice = input("Select an option [1-3, Q]: ").strip()
        if choice == "" or choice.lower() == "q":
            print("Exiting GNA Management Console. Goodbye!")
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
        description="GNA System Manager: Genealogy Archive Configuration & Integrity Auditor.")
    parser.add_argument("-a", "--audit", action="store_true",
                        help="Run full system integrity audit and generate reports")
    parser.add_argument("-g", "--generate-config", action="store_true",
                        help="Generate or refresh gda_config.json baseline manifest")
    parser.add_argument("-r", "--report", choices=["json", "md", "all"], default="all",
                        help="Export audit report format")
    parser.add_argument("--repair", action="store_true", help="Attempt automated remediation using latest report")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debugging logs")
    args = parser.parse_args()
    if not ROOT_DIR.exists():
        log(f"Archive root not found: {ROOT_DIR}", is_error=True, verbose=True)
        sys.exit(1)
    log("Initialized GNA System Manager CLI.", verbose=args.verbose)
    if not args.audit and not args.generate_config and not args.repair:
        interactive_menu()
        return
    if args.generate_config:
        generate_config()
    if args.repair:
        remediate_latest_report()
    if args.audit:
        audit_system(format_type=args.report, verbose=args.verbose)


if __name__ == "__main__":
    main()