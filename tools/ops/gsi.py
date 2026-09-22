# Name: gsi.py
# Path: tools/ops/gsi.py

"""GSI (Genealogy Script Importer).

Permanent operational tool for scanning intake areas for executable scripts,
parsing mandatory header metadata (# Name:, # Path:), enforcing safe pre-overwrite
backups in backups/, routing to repository locations, and optional execution.
"""

import argparse
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple

# Ensure repository root is on sys.path for standalone invocation
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil

__version__ = "1.0.3+build.20260922.2"


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
        sys.stderr.write(f"Error reading headers from {file_path.name}: {e}\n")

    return script_name, target_rel_path


def get_python_interpreter() -> str:
    """Detects active virtual environment or fallback Python executable."""
    venv_python = CONFIG.root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def execute_script(target_path: Path, passthrough_args: List[str], logger: Optional[logging.Logger] = None) -> int:
    """Executes target script post-import.

    Args:
        target_path (Path): Script path to execute.
        passthrough_args (List[str]): Arguments forwarded directly to script.
        logger (Optional[logging.Logger]): Operational logger.

    Returns:
        int: Process return code.
    """
    log = logger or logging.getLogger("gsi")
    log.info(f"Spawning execution for {target_path.relative_to(CONFIG.root).as_posix()}...")
    cmd = []
    if target_path.suffix.lower() == ".py":
        cmd = [get_python_interpreter(), str(target_path)] + passthrough_args
    elif target_path.suffix.lower() == ".ps1":
        cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(target_path)] + passthrough_args
    else:
        log.error(f"Unsupported executable format for direct run: {target_path.suffix}")
        return 1

    try:
        proc = subprocess.run(cmd, cwd=str(CONFIG.root))
        log.info(f"Execution finished with exit code {proc.returncode}")
        return proc.returncode
    except Exception as e:
        log.error(f"Subprocess invocation failed: {e}")
        return 1


def process_import(
    source_dir: Path,
    pattern: str,
    force: bool,
    run_after: bool,
    passthrough_args: List[str],
    logger: Optional[logging.Logger] = None,
) -> None:
    """Scans, verifies, backs up, relocates, and optionally executes candidate scripts.

    Args:
        source_dir (Path): Intake directory to scan.
        pattern (str): Filename substring filter pattern.
        force (bool): Bypasses interactive overwrite prompt if True.
        run_after (bool): Spawns script post-import if True.
        passthrough_args (List[str]): Forwarded CLI parameters.
        logger (Optional[logging.Logger]): Operational logger.
    """
    log = logger or logging.getLogger("gsi")
    if not source_dir.exists():
        log.error(f"Source directory not found: {source_dir}")
        return

    rel_source = source_dir.relative_to(CONFIG.root).as_posix() if source_dir.is_relative_to(CONFIG.root) else str(source_dir)
    log.info(f"Scanning '{rel_source}' for pattern: '{pattern}'")

    candidates = [
        p for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() in [".py", ".ps1"] and pattern.lower() in p.name.lower()
    ]

    if not candidates:
        log.info("No matching script candidates located.")
        return

    for item in candidates:
        log.info(f"Inspecting candidate: {item.name}")
        name_hdr, path_hdr = extract_script_headers(item)

        if not path_hdr:
            log.error(f"Skipping {item.name}: Missing valid '# Path:' header specification.")
            continue

        target_full_path = CONFIG.root / path_hdr

        if target_full_path.resolve() == item.resolve():
            log.info(f"File {item.name} is already at designated destination: {path_hdr.as_posix()}")
            if run_after:
                execute_script(target_full_path, passthrough_args, logger=log)
            continue

        if target_full_path.exists():
            log.info(f"Collision detected for destination: {path_hdr.as_posix()}")
            if not force:
                prompt = input(f"Destination {path_hdr.as_posix()} exists. Overwrite? [Y/n]: ").strip().lower()
                if prompt in ["n", "no"]:
                    log.info(f"Import canceled by user for {item.name}")
                    continue

            try:
                backup_path = GDAUtil.create_safe_backup(target_full_path)
                log.info(f"Safe Backup generated: {backup_path.name}")
            except Exception as e:
                log.error(f"Aborting replacement of {path_hdr.as_posix()} due to backup failure: {e}")
                continue

        target_full_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(item), str(target_full_path))
            log.info(f"Successfully relocated: {item.name} -> {path_hdr.as_posix()}")
        except Exception as e:
            log.error(f"Failed to move {item.name} to {target_full_path}: {e}")
            continue

        if run_after:
            execute_script(target_full_path, passthrough_args, logger=log)


def main() -> None:
    """CLI parameter parsing and router."""
    parser = argparse.ArgumentParser(
        description="GSI: Genealogy Script Importer and Deployment Utility."
    )
    parser.add_argument(
        "-s", "--source-dir",
        type=Path,
        default=CONFIG.root,
        help="Source directory to scan (Default: root archive directory)",
    )
    parser.add_argument(
        "-p", "--pattern",
        type=str,
        default="gemini",
        help="Filename filter pattern (Default: 'gemini')",
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force overwrite of existing targets without prompting (always takes a safe backup)",
    )
    parser.add_argument(
        "-r", "--run",
        action="store_true",
        help="Execute the relocated script immediately post-import",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Route runtime traces directly to console/stderr",
    )
    parser.add_argument(
        "passthrough",
        nargs=argparse.REMAINDER,
        help="Arguments to pass through to the executed script (use after --)",
    )

    args = parser.parse_args()

    c_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logger("gsi", console_level=c_level, file_level=logging.DEBUG)
    logger.info("Initialized GSI CLI.", extra={"sys_event": True})

    passthrough = args.passthrough
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    source_path = args.source_dir
    if not source_path.is_absolute():
        source_path = CONFIG.root / source_path

    process_import(
        source_dir=source_path,
        pattern=args.pattern,
        force=args.force,
        run_after=args.run,
        passthrough_args=passthrough,
        logger=logger,
    )


if __name__ == "__main__":
    main()