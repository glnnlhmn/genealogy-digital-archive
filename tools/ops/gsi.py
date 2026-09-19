# Name: gsi.py
# Path: tools/ops/gsi.py
"""GSI (Genealogy Script Importer)

Permanent operational tool for scanning intake areas for executable scripts,
parsing mandatory header metadata (# Name:, # Path:), enforcing safe pre-overwrite
backups in backups/, routing to repository locations, and optional execution.

Public Interface:
    - import_scripts(source_dir: Path, pattern: str, force: bool, run: bool, passthrough_args: list)

Dependencies:
    - Standard Library: argparse, datetime, os, pathlib, re, shutil, subprocess, sys

Version: 1.0.2
"""

import argparse
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple

ROOT_DIR = Path("G:/My Drive/genealogy-digital-archive")
LOGS_DIR = ROOT_DIR / "logs"
BACKUPS_DIR = ROOT_DIR / "backups"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

SESSION_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOGS_DIR / f"gsi-{SESSION_TIMESTAMP}.log"


def log(msg: str, is_error: bool = False) -> None:
    """Writes a timestamped log entry to the session log file and mirrors to stdout/stderr.

    Args:
        msg (str): Message to log.
        is_error (bool): Flag indicating if message is an error.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {'[ERROR] ' if is_error else '[INFO] '}{msg}"
    if is_error:
        sys.stderr.write(formatted + "\n")
        sys.stderr.flush()
    else:
        print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def safe_backup_target(target_path: Path) -> Optional[Path]:
    """Creates a timestamped safe backup of an existing target in backups/.

    Args:
        target_path (Path): Path of the destination file about to be overwritten.

    Returns:
        Optional[Path]: Path to created backup file, or None if failed.
    """
    if not target_path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{target_path.name}.{timestamp}.bk"
    backup_path = BACKUPS_DIR / backup_filename

    try:
        shutil.copy2(target_path, backup_path)
        log(f"Safe Backup generated: {backup_path.relative_to(ROOT_DIR).as_posix()}")
        return backup_path
    except Exception as e:
        log(f"Failed to create safe backup for {target_path}: {e}", is_error=True)
        return None


def extract_script_headers(file_path: Path) -> Tuple[Optional[str], Optional[Path]]:
    """Parses script headers for mandatory '# Name:' and '# Path:' directives.

    Args:
        file_path (Path): Source script candidate.

    Returns:
        Tuple[Optional[str], Optional[Path]]: Declared name and resolved target Path.
    """
    script_name = None
    target_rel_path = None

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(15)]

        for line in lines:
            line_clean = line.strip()
            name_match = re.match(r"^#\s*Name:\s*(\S+)", line_clean, re.IGNORECASE)
            if name_match and not script_name:
                script_name = name_match.group(1).strip()

            path_match = re.match(r"^#\s*Path:\s*(\S+)", line_clean, re.IGNORECASE)
            if path_match and not target_rel_path:
                raw_path = path_match.group(1).strip().replace("\\", "/")
                target_rel_path = Path(raw_path)
    except Exception as e:
        log(f"Error reading headers from {file_path.name}: {e}", is_error=True)

    return script_name, target_rel_path


def get_python_interpreter() -> str:
    """Detects active venv or fallback Python executable."""
    venv_python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def execute_script(target_path: Path, passthrough_args: List[str]) -> int:
    """Executes target script without intercepting its internal stdout/stderr into importer logs.

    Args:
        target_path (Path): Script path to execute.
        passthrough_args (List[str]): Arguments forwarded directly to script.

    Returns:
        int: Process return code.
    """
    log(f"Spawning execution for {target_path.relative_to(ROOT_DIR).as_posix()}...")
    cmd = []
    if target_path.suffix.lower() == ".py":
        cmd = [get_python_interpreter(), str(target_path)] + passthrough_args
    elif target_path.suffix.lower() == ".ps1":
        cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(target_path)] + passthrough_args
    else:
        log(f"Unsupported executable format for direct run: {target_path.suffix}", is_error=True)
        return 1

    try:
        proc = subprocess.run(cmd, cwd=str(ROOT_DIR))
        log(f"Execution finished with exit code {proc.returncode}")
        return proc.returncode
    except Exception as e:
        log(f"Subprocess invocation failed: {e}", is_error=True)
        return 1


def process_import(
    source_dir: Path,
    pattern: str,
    force: bool,
    run_after: bool,
    passthrough_args: List[str]
) -> None:
    """Scans, verifies, backs up, relocates, and executes candidate scripts."""
    if not source_dir.exists():
        log(f"Source directory not found: {source_dir}", is_error=True)
        return

    log(f"Scanning '{source_dir.relative_to(ROOT_DIR).as_posix()}' for pattern: '{pattern}'")
    candidates = [
        p for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() in [".py", ".ps1"] and pattern.lower() in p.name.lower()
    ]

    if not candidates:
        log("No matching script candidates located.")
        return

    for item in candidates:
        log(f"Inspecting candidate: {item.name}")
        name_hdr, path_hdr = extract_script_headers(item)

        if not path_hdr:
            log(f"Skipping {item.name}: Missing valid '# Path:' header specification.", is_error=True)
            continue

        target_full_path = ROOT_DIR / path_hdr

        if target_full_path.resolve() == item.resolve():
            log(f"File {item.name} is already at designated destination: {path_hdr.as_posix()}")
            if run_after:
                execute_script(target_full_path, passthrough_args)
            continue

        if target_full_path.exists():
            log(f"Collision detected for destination: {path_hdr.as_posix()}")
            if not force:
                prompt = input(f"Destination {path_hdr.as_posix()} exists. Overwrite? [y/N]: ").strip().lower()
                if prompt not in ["y", "yes"]:
                    log(f"Import canceled by user for {item.name}")
                    continue

            backup_done = safe_backup_target(target_full_path)
            if not backup_done:
                log(f"Aborting replacement of {path_hdr.as_posix()} due to backup failure.", is_error=True)
                continue

        target_full_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(item), str(target_full_path))
            log(f"Successfully relocated: {item.name} -> {path_hdr.as_posix()}")
        except Exception as e:
            log(f"Failed to move {item.name} to {target_full_path}: {e}", is_error=True)
            continue

        if run_after:
            execute_script(target_full_path, passthrough_args)


def main() -> None:
    """CLI parameter parsing and router."""
    parser = argparse.ArgumentParser(
        description="GSI: Genealogy Script Importer and Deployment Utility."
    )
    parser.add_argument(
        "-s", "--source-dir",
        type=Path,
        default=ROOT_DIR,
        help="Source directory to scan (Default: root archive directory)"
    )
    parser.add_argument(
        "-p", "--pattern",
        type=str,
        default="gemini",
        help="Filename filter pattern (Default: 'gemini')"
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force overwrite of existing targets (always takes a safe backup)"
    )
    parser.add_argument(
        "-r", "--run",
        action="store_true",
        help="Execute the relocated script immediately post-import"
    )
    parser.add_argument(
        "passthrough",
        nargs=argparse.REMAINDER,
        help="Arguments to pass through to the executed script (use after --)"
    )

    args = parser.parse_args()

    passthrough = args.passthrough
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    source_path = args.source_dir
    if not source_path.is_absolute():
        source_path = ROOT_DIR / source_path

    process_import(
        source_dir=source_path,
        pattern=args.pattern,
        force=args.force,
        run_after=args.run,
        passthrough_args=passthrough
    )


if __name__ == "__main__":
    main()