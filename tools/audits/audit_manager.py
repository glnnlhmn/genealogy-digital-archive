#!/usr/bin/env python3
# PATH: auto/audit_tools/audit_manager.py
"""
Archival Repository Schema & Prompt Protocol Audit Tool.
Crawls schemas and instructions, generates baseline reference snapshots,
and audits workspace files against baseline configurations.
"""

import sys
import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# -----------------------------------------------------------------------------
# Configuration & Paths
# -----------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
CONFIG_FILE = REPO_ROOT / ".audit_config.json"

SCHEMA_DIR = REPO_ROOT / "schemas"
PROMPT_DIR = REPO_ROOT / "prompts" / "gems"


def calculate_sha256(filepath: Path) -> str:
    """Calculate the SHA-256 hexadecimal hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_file_mtime_iso(filepath: Path) -> str:
    """Extract file modification time as an ISO-8601 UTC string."""
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()


# -----------------------------------------------------------------------------
# Crawlers & Parsers
# -----------------------------------------------------------------------------
def crawl_schemas() -> dict:
    """
    Crawls subfolders under schemas/ (ignoring files directly in schemas/).
    Extracts title, version, name (if applicable), file size, date, and sha256.
    """
    results = {}
    if not SCHEMA_DIR.exists():
        print(f"Directory not found: {SCHEMA_DIR}")
        return results

    for path in SCHEMA_DIR.rglob("*.json"):
        # Ignore files located directly in the root of schemas/
        if path.parent.resolve() == SCHEMA_DIR.resolve():
            continue

        rel_path = path.relative_to(REPO_ROOT).as_posix()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error parsing JSON {rel_path}: {e}")
            continue

        title = data.get("title") or data.get("name") or path.stem
        version = data.get("version", "UNKNOWN")
        size_bytes = path.stat().st_size
        mtime_iso = get_file_mtime_iso(path)
        content_hash = calculate_sha256(path)

        results[rel_path] = {
            "filename": path.name,
            "relative_path": rel_path,
            "title": title,
            "version": str(version),
            "size_bytes": size_bytes,
            "modified_at": mtime_iso,
            "sha256": content_hash
        }
    return results


def crawl_prompts() -> dict:
    """
    Crawls markdown files under prompts/gems/.
    Extracts Title from the first H1 header, Version from HTML comments,
    file size, date, and sha256.
    """
    results = {}
    if not PROMPT_DIR.exists():
        print(f"Directory not found: {PROMPT_DIR}")
        return results

    version_pattern = re.compile(r"<!--\s*Version:\s*([^\s>]+)\s*-->", re.IGNORECASE)
    h1_pattern = re.compile(r"^#\s+(.+)$", re.MULTILINE)

    for path in PROMPT_DIR.rglob("*.md"):
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading Markdown {rel_path}: {e}")
            continue

        # Extract Title from first H1
        h1_match = h1_pattern.search(content)
        title = h1_match.group(1).strip() if h1_match else path.stem

        # Extract Version from comment
        ver_match = version_pattern.search(content)
        version = ver_match.group(1).strip() if ver_match else "UNKNOWN"

        size_bytes = path.stat().st_size
        mtime_iso = get_file_mtime_iso(path)
        content_hash = calculate_sha256(path)

        results[rel_path] = {
            "filename": path.name,
            "relative_path": rel_path,
            "title": title,
            "version": str(version),
            "size_bytes": size_bytes,
            "modified_at": mtime_iso,
            "sha256": content_hash
        }
    return results


# -----------------------------------------------------------------------------
# Baseline Snapshot & Storage
# -----------------------------------------------------------------------------
def generate_reference_snapshot():
    """Generates a complete reference snapshot and saves to .audit_config.json."""
    print("\nScanning workspace for reference snapshot...")
    schemas = crawl_schemas()
    prompts = crawl_prompts()

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schemas": schemas,
        "prompts": prompts
    }

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        print(f"Baseline saved successfully: {CONFIG_FILE}")
        print(f"  - Indexed schemas:      {len(schemas)}")
        print(f"  - Indexed instructions:  {len(prompts)}")
    except Exception as e:
        print(f"Failed to write configuration: {e}")


def load_reference_snapshot() -> dict:
    """Loads the baseline reference snapshot from .audit_config.json."""
    if not CONFIG_FILE.exists():
        print(f"\nConfiguration file not found: {CONFIG_FILE}")
        print("Please run option 1 (Create/Update Reference Baseline) first.")
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {CONFIG_FILE}: {e}")
        return {}


# -----------------------------------------------------------------------------
# Verification Engine
# -----------------------------------------------------------------------------
def verify_collection(current: dict, baseline: dict, label: str):
    """
    Compares current state against baseline and outputs categorized findings:
    [ERROR]: Version mismatch
    [WARNING]: Hash/mtime changed without version increment
    [INFO]: Untracked new files or missing files
    """
    print(f"\n--- Auditing {label} ---")
    current_keys = set(current.keys())
    baseline_keys = set(baseline.keys())

    errors = 0
    warnings = 0
    infos = 0

    # Check for missing files
    missing = baseline_keys - current_keys
    for k in sorted(missing):
        print(f"  [INFO] Missing file: {k} (expected in baseline)")
        infos += 1

    # Check for new untracked files
    untracked = current_keys - baseline_keys
    for k in sorted(untracked):
        c = current[k]
        print(f"  [INFO] New unindexed file: {k} [v{c['version']}] - '{c['title']}'")
        infos += 1

    # Compare common files
    common = current_keys & baseline_keys
    for k in sorted(common):
        curr_item = current[k]
        base_item = baseline[k]

        version_match = curr_item["version"] == base_item["version"]
        hash_match = curr_item["sha256"] == base_item["sha256"]

        if not version_match:
            print(
                f"  [ERROR] Version mismatch in {k}:\n"
                f"          Current:  {curr_item['version']}\n"
                f"          Baseline: {base_item['version']}"
            )
            errors += 1
        elif not hash_match:
            print(
                f"  [WARNING] Content modified without version increment in {k} (v{curr_item['version']})"
            )
            warnings += 1

    print(f"\nSummary for {label}:")
    print(f"  Total Checked: {len(common)}")
    print(f"  Errors:   {errors}")
    print(f"  Warnings: {warnings}")
    print(f"  Info:     {infos}")


def run_audit(audit_schemas: bool, audit_prompts: bool):
    """Executes verification for requested target sets."""
    baseline_data = load_reference_snapshot()
    if not baseline_data:
        return

    if audit_schemas:
        current_schemas = crawl_schemas()
        base_schemas = baseline_data.get("schemas", {})
        verify_collection(current_schemas, base_schemas, "Schemas")

    if audit_prompts:
        current_prompts = crawl_prompts()
        base_prompts = baseline_data.get("prompts", {})
        verify_collection(current_prompts, base_prompts, "Prompt Instructions")


# -----------------------------------------------------------------------------
# Interactive CLI Menu
# -----------------------------------------------------------------------------
def main_menu():
    while True:
        print("\n" + "=" * 50)
        print(" Archival Repository Audit Manager")
        print("=" * 50)
        print("1. Create / Refresh Baseline Snapshot (.audit_config.json)")
        print("2. Verify Schemas against Baseline")
        print("3. Verify Instructions (Prompts) against Baseline")
        print("4. Verify Both Schemas & Instructions")
        print("Q. Quit")
        print("-" * 50)

        choice = input("Enter choice [1-4, Q]: ").strip().upper()

        if choice == "1":
            generate_reference_snapshot()
        elif choice == "2":
            run_audit(audit_schemas=True, audit_prompts=False)
        elif choice == "3":
            run_audit(audit_schemas=False, audit_prompts=True)
        elif choice == "4":
            run_audit(audit_schemas=True, audit_prompts=True)
        elif choice in ("Q", "QUIT", "EXIT"):
            print("Exiting Audit Manager.")
            sys.exit(0)
        else:
            print("Invalid selection. Please choose an option from the menu.")


if __name__ == "__main__":
    main_menu()