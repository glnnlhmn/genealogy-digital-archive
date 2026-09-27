# Name: gsi.py
# Path: tools/ops/gsi.py
# Version: 1.0.5+build.20260926.04

"""Genealogy Script Importer (GSI).

Scan the repository root for intake candidate files matching 'gemini'
(*.py, *.md, *.ps1, *.txt, *.json), extract destination routing metadata
from headers, manage atomic Safe Backups, relocate files directly to their
designated archive paths, and provide contextual execution:
- Tests (test_*.py): pytest <file> -v
- Markdown (*.md): Google Chrome
- PowerShell (*.ps1): powershell.exe -ExecutionPolicy Bypass -File <file>
- Python (*.py): python <file>
- Non-executables (*.json, *.txt): Relocated with '(Can not execute)' suffix if -r is passed.
"""

import argparse
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import webbrowser

__version__ = "1.0.5+build.20260926.04"

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil


def parse_metadata_header(file_path: Path) -> tuple[str | None, Path | None]:
    """Extract target filename and relative path from the first 15 lines of a candidate file.

    Args:
        file_path: Absolute or relative Path pointing to candidate intake file.

    Returns:
        A tuple of (target_name, dest_path). If headers are missing, malformed,
        or unreadable, returns (None, None).
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return None, None

    lines = content.splitlines()[:15]
    header_block = "\n".join(lines)

    target_name = None
    target_path_str = None

    # 1. JSON-specific key parsing: "_name": "..." and "_path": "..."
    if file_path.suffix.lower() == ".json":
        name_json = re.search(r'"_?name"\s*:\s*"([^"]+)"', header_block, re.IGNORECASE)
        path_json = re.search(r'"_?path"\s*:\s*"([^"]+)"', header_block, re.IGNORECASE)
        if name_json and path_json:
            target_name = name_json.group(1).strip()
            target_path_str = path_json.group(1).strip()

    # 2. General comment pattern across #, <!--, //, /* or multi-line HTML comment interiors
    if not target_name or not target_path_str:
        name_match = re.search(
            r'^[ \t]*(?:#|<!--|//|/\*|\*)*[ \t]*Name:[ \t]*([^\r\n>*/]+)',
            header_block,
            re.MULTILINE | re.IGNORECASE,
        )
        path_match = re.search(
            r'^[ \t]*(?:#|<!--|//|/\*|\*)*[ \t]*Path:[ \t]*([^\r\n>]+)',
            header_block,
            re.MULTILINE | re.IGNORECASE,
        )
        if name_match:
            target_name = name_match.group(1).strip()
        if path_match:
            target_path_str = path_match.group(1).strip()

    if not target_name or not target_path_str:
        return None, None

    # Clean comment delimiters, quotes, and whitespace
    target_name = re.sub(r'\s*(-->|\*/).*$', '', target_name).strip().strip('"\'')
    target_path_str = re.sub(r'\s*(-->|\*/).*$', '', target_path_str).strip().strip('"\'')

    dest_raw = ROOT_DIR / Path(target_path_str)

    if dest_raw.is_dir() or target_path_str.endswith(("/", "\\")):
        dest_path = (dest_raw / target_name).resolve()
    else:
        dest_path = dest_raw.resolve()

    return target_name, dest_path


def execute_relocated_target(target_path: Path, logger: logging.Logger) -> int:
    """Execute target based on file extension and naming pattern.

    Args:
        target_path: Resolved Path pointing to the relocated file.
        logger: Active logging instance for execution traces.

    Returns:
        Integer process exit code (0 for success, non-zero for failure).
    """
    ext = target_path.suffix.lower()
    file_name = target_path.name.lower()

    if ext == ".py" and (file_name.startswith("test_") or file_name.endswith("_test.py")):
        cmd = [sys.executable, "-m", "pytest", str(target_path), "-v"]
        logger.info(f"Executing test target via pytest: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(ROOT_DIR))
        return res.returncode

    if ext == ".md":
        logger.info(f"Opening markdown target in Chrome: {target_path}")
        chrome_opened = False

        # Check standard PATH candidates and default Windows locations
        chrome_candidates = ["chrome", "chrome.exe", "google-chrome"]
        for env_var in ["ProgramFiles", "ProgramFiles(x86)", "LocalAppData"]:
            base = os.environ.get(env_var)
            if base:
                chrome_candidates.append(str(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"))

        for chrome_bin in chrome_candidates:
            if shutil.which(chrome_bin) or Path(chrome_bin).is_file():
                try:
                    subprocess.Popen([chrome_bin, str(target_path)])
                    chrome_opened = True
                    break
                except Exception:
                    pass

        if not chrome_opened:
            webbrowser.open(target_path.as_uri())
        return 0

    if ext == ".ps1":
        cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(target_path)]
        logger.info(f"Executing PowerShell script: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(ROOT_DIR))
        return res.returncode

    if ext == ".py":
        cmd = [sys.executable, str(target_path)]
        logger.info(f"Executing Python script: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(ROOT_DIR))
        return res.returncode

    return 0


def run_intake(run_target: bool = False) -> int:
    """Scan repository root for candidate files matching 'gemini' and relocate them.

    Args:
        run_target: Whether to invoke contextual execution immediately after relocation.

    Returns:
        Integer status code (0 if all operations succeed, non-zero if execution fails).
    """
    config = GDAConfig(root=ROOT_DIR)
    logger = setup_logger("gsi", log_dir=config.logs)
    logger.info("Initialized GSI CLI.")

    allowed_exts = {".py", ".md", ".ps1", ".txt", ".json"}
    candidates = [
        item for item in ROOT_DIR.iterdir()
        if item.is_file() and "gemini" in item.name.lower() and item.suffix.lower() in allowed_exts
    ]

    if not candidates:
        logger.info("No intake candidate files found in root directory.")
        return 0

    for cand in candidates:
        logger.info(f"Inspecting candidate: {cand.name}")
        target_name, dest_path = parse_metadata_header(cand)

        if not target_name or not dest_path:
            logger.warning(
                f"Skipping {cand.name}: Missing valid metadata headers ('# Name:' / '# Path:' or JSON '_name' / '_path') within first 15 lines."
            )
            continue

        try:
            dest_path.relative_to(ROOT_DIR)
        except ValueError:
            logger.error(f"Security error: Destination {dest_path} attempts escape outside repository root.")
            continue

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if dest_path.is_file():
            GDAUtil.create_safe_backup(dest_path, backup_dir=config.backups)

        shutil.move(str(cand), str(dest_path))

        rel_display = f".\\{dest_path.relative_to(ROOT_DIR)}"
        ext = dest_path.suffix.lower()

        if run_target and ext in [".json", ".txt"]:
            logger.info(f"Successfully relocated: {cand.name} -> {rel_display} (Can not execute)")
        else:
            logger.info(f"Successfully relocated: {cand.name} -> {rel_display}")

        if run_target and ext in [".py", ".md", ".ps1"]:
            ret = execute_relocated_target(dest_path, logger)
            if ret != 0:
                logger.error(f"Execution finished with non-zero exit code {ret}")
                return ret

    logger.info("GSI intake operation complete.")
    return 0


def main() -> int:
    """Parse CLI options and execute the GSI intake workflow.

    Returns:
        Integer status code indicating program execution success or failure.
    """
    parser = argparse.ArgumentParser(
        description="Genealogy Script Importer (GSI) - Relocates and executes staged files."
    )
    parser.add_argument(
        "-r", "--run",
        action="store_true",
        help="Execute relocated target (pytest for tests, Chrome for .md, PowerShell for .ps1, Python for .py)."
    )
    args = parser.parse_args()
    return run_intake(run_target=args.run)


if __name__ == "__main__":
    sys.exit(main())