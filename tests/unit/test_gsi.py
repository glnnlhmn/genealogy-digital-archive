# Name: test_gsi.py
# Path: tests/unit/test_gsi.py

"""Unit test suite for tools/ops/gsi.py (v1.0.5+build.20260926.04).

Validates metadata parsing across .py, .md, .ps1, .txt, and .json files,
directory resolution and automatic filename appending, Safe Backup generation,
Windows-style path reporting, edge-case error trapping, and contextual runner dispatch:
- pytest for test_*.py
- Google Chrome for *.md
- PowerShell for *.ps1
- Python interpreter for general *.py
- '(Can not execute)' logging for non-executable types (.json, .txt).
"""

import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

import tools.ops.gsi as gsi


@pytest.fixture
def mock_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up an isolated repository root sandbox for GSI operations.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        Path pointing to the prepared sandbox root.
    """
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "ops").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "entities").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(gsi, "ROOT_DIR", tmp_path)
    return tmp_path


# ----------------------------------------------------------------------
# Header Parsing Unit Tests
# ----------------------------------------------------------------------

def test_parse_metadata_header_python(mock_repo_root: Path) -> None:
    """Verify parsing of standard Python comment headers."""
    f = mock_repo_root / "gemini_script.py"
    f.write_text("# Name: task.py\n# Path: tools/ops/task.py\nprint('hello')", encoding="utf-8")

    name, dest = gsi.parse_metadata_header(f)
    assert name == "task.py"
    assert dest == (mock_repo_root / "tools" / "ops" / "task.py").resolve()


def test_parse_metadata_header_markdown_html(mock_repo_root: Path) -> None:
    """Verify parsing of Markdown HTML comment block headers."""
    f = mock_repo_root / "gemini_doc.md"
    f.write_text("<!--\nName: guide.md\nPath: docs/guide.md\n-->\n# Guide Title", encoding="utf-8")

    name, dest = gsi.parse_metadata_header(f)
    assert name == "guide.md"
    assert dest == (mock_repo_root / "docs" / "guide.md").resolve()


def test_parse_metadata_header_json_keys(mock_repo_root: Path) -> None:
    """Verify parsing of top-level JSON metadata keys."""
    f = mock_repo_root / "gemini_payload.json"
    f.write_text('{\n  "_name": "item.json",\n  "_path": "data/entities/item.json"\n}', encoding="utf-8")

    name, dest = gsi.parse_metadata_header(f)
    assert name == "item.json"
    assert dest == (mock_repo_root / "data" / "entities" / "item.json").resolve()


def test_parse_metadata_header_directory_path_appends_filename(mock_repo_root: Path) -> None:
    """Verify that targeting an existing directory or trailing slash appends target_name."""
    f = mock_repo_root / "gemini_script.py"
    f.write_text("# Name: unit_test.py\n# Path: tests/unit\n", encoding="utf-8")

    name, dest = gsi.parse_metadata_header(f)
    assert name == "unit_test.py"
    assert dest == (mock_repo_root / "tests" / "unit" / "unit_test.py").resolve()

    f_slash = mock_repo_root / "gemini_slash.py"
    f_slash.write_text("# Name: slash_test.py\n# Path: gtemp/\n", encoding="utf-8")
    name_slash, dest_slash = gsi.parse_metadata_header(f_slash)
    assert name_slash == "slash_test.py"
    assert dest_slash == (mock_repo_root / "gtemp" / "slash_test.py").resolve()


def test_parse_metadata_header_exceptions_and_fallbacks(mock_repo_root: Path) -> None:
    """Verify that file read exceptions and missing/partial headers return (None, None)."""
    unreadable = mock_repo_root / "gemini_locked.py"
    with patch.object(Path, "read_text", side_effect=PermissionError("File locked")):
        assert gsi.parse_metadata_header(unreadable) == (None, None)

    f_empty = mock_repo_root / "gemini_empty.py"
    f_empty.write_text("print('no headers')", encoding="utf-8")
    assert gsi.parse_metadata_header(f_empty) == (None, None)

    f_name_only = mock_repo_root / "gemini_partial.py"
    f_name_only.write_text("# Name: partial.py\nprint('no path')", encoding="utf-8")
    assert gsi.parse_metadata_header(f_name_only) == (None, None)

    f_late = mock_repo_root / "gemini_late.py"
    padding = "\n".join([f"# line {i}" for i in range(16)])
    f_late.write_text(f"{padding}\n# Name: late.py\n# Path: tools/ops/late.py", encoding="utf-8")
    assert gsi.parse_metadata_header(f_late) == (None, None)


# ----------------------------------------------------------------------
# Target Relocation & Safe Backup Tests
# ----------------------------------------------------------------------

def test_run_intake_relocates_file_and_ignores_non_candidates(mock_repo_root: Path) -> None:
    """Verify GSI relocates candidate files and leaves non-matching files untouched."""
    cand = mock_repo_root / "gemini_test_run.py"
    cand.write_text("# Name: runner.py\n# Path: tools/ops/runner.py\n", encoding="utf-8")

    ignored = mock_repo_root / "other_script.py"
    ignored.write_text("# Name: other.py\n# Path: tools/ops/other.py\n", encoding="utf-8")

    exit_code = gsi.run_intake(run_target=False)
    assert exit_code == 0

    assert not cand.exists()
    assert (mock_repo_root / "tools" / "ops" / "runner.py").exists()
    assert ignored.exists()


def test_run_intake_triggers_safe_backup_on_overwrite(mock_repo_root: Path) -> None:
    """Verify an existing target file triggers GDAUtil.create_safe_backup."""
    dest = mock_repo_root / "tools" / "ops" / "existing.py"
    dest.write_text("original content", encoding="utf-8")

    cand = mock_repo_root / "gemini_existing.py"
    cand.write_text("# Name: existing.py\n# Path: tools/ops/existing.py\nnew content", encoding="utf-8")

    with patch("tools.lib.gda_core.GDAUtil.GDAUtil.create_safe_backup") as mock_bk:
        exit_code = gsi.run_intake(run_target=False)
        assert exit_code == 0
        mock_bk.assert_called_once()
        assert dest.read_text(encoding="utf-8") == "# Name: existing.py\n# Path: tools/ops/existing.py\nnew content"


def test_run_intake_security_escape_prevented(mock_repo_root: Path) -> None:
    """Verify paths attempting traversal outside the archive root are blocked."""
    cand = mock_repo_root / "gemini_escape.py"
    cand.write_text("# Name: escape.py\n# Path: ../../../outside.py\n", encoding="utf-8")

    exit_code = gsi.run_intake(run_target=False)
    assert exit_code == 0
    assert cand.exists()


def test_run_intake_missing_headers_logged(mock_repo_root: Path) -> None:
    """Verify candidate files missing metadata headers are skipped with warning."""
    cand = mock_repo_root / "gemini_unheaded.py"
    cand.write_text("print('no metadata headers')", encoding="utf-8")

    exit_code = gsi.run_intake(run_target=False)
    assert exit_code == 0
    assert cand.exists()


def test_run_intake_propagates_execution_failure(mock_repo_root: Path) -> None:
    """Verify non-zero return codes from executed targets abort intake and propagate."""
    cand = mock_repo_root / "gemini_failing.py"
    cand.write_text("# Name: failing.py\n# Path: gtemp/failing.py\nimport sys; sys.exit(3)", encoding="utf-8")

    with patch.object(gsi, "execute_relocated_target", return_value=3):
        exit_code = gsi.run_intake(run_target=True)
        assert exit_code == 3


# ----------------------------------------------------------------------
# Execution Runner Routing (-r) Tests
# ----------------------------------------------------------------------

def test_execute_relocated_target_pytest(mock_repo_root: Path) -> None:
    """Verify test_*.py files execute via pytest -v."""
    test_file = mock_repo_root / "test_sample.py"
    test_file.touch()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        logger = MagicMock()
        ret = gsi.execute_relocated_target(test_file, logger)

        assert ret == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[1:] == ["-m", "pytest", str(test_file), "-v"]


def test_execute_relocated_target_python(mock_repo_root: Path) -> None:
    """Verify standard .py files execute via the Python interpreter."""
    script_file = mock_repo_root / "sample_script.py"
    script_file.touch()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        logger = MagicMock()
        ret = gsi.execute_relocated_target(script_file, logger)

        assert ret == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == [sys.executable, str(script_file)]


def test_execute_relocated_target_powershell(mock_repo_root: Path) -> None:
    """Verify .ps1 files execute via PowerShell with Bypass."""
    ps_file = mock_repo_root / "sample.ps1"
    ps_file.touch()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1)
        logger = MagicMock()
        ret = gsi.execute_relocated_target(ps_file, logger)

        assert ret == 1
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(ps_file)]


def test_execute_relocated_target_markdown_chrome_and_fallback(mock_repo_root: Path) -> None:
    """Verify Chrome launching, popen failure recovery, and browser fallback."""
    md_file = mock_repo_root / "doc.md"
    md_file.touch()

    # 1. Successful Chrome execution via shutil.which
    with patch("shutil.which", return_value="chrome.exe"), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("subprocess.Popen") as mock_popen:
        logger = MagicMock()
        ret = gsi.execute_relocated_target(md_file, logger)
        assert ret == 0
        mock_popen.assert_called_once()

    # 2. Chrome binary throws exception; falls back to webbrowser.open
    with patch("shutil.which", return_value="chrome.exe"), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("subprocess.Popen", side_effect=OSError("Spawn error")), \
         patch("webbrowser.open") as mock_browser:
        logger = MagicMock()
        ret = gsi.execute_relocated_target(md_file, logger)
        assert ret == 0
        mock_browser.assert_called_once_with(md_file.as_uri())

    # 3. No Chrome candidate found; falls back to webbrowser.open
    with patch("shutil.which", return_value=None), \
         patch("pathlib.Path.is_file", return_value=False), \
         patch.dict(os.environ, {}, clear=True), \
         patch("webbrowser.open") as mock_browser:
        logger = MagicMock()
        ret = gsi.execute_relocated_target(md_file, logger)
        assert ret == 0
        mock_browser.assert_called_once_with(md_file.as_uri())


def test_intake_non_executable_with_run_flag(mock_repo_root: Path) -> None:
    """Verify JSON files emit '(Can not execute)' and skip runner execution when -r is used."""
    json_cand = mock_repo_root / "gemini_data.json"
    json_cand.write_text('{"_name": "data.json", "_path": "data/entities/data.json"}', encoding="utf-8")

    with patch.object(gsi, "execute_relocated_target") as mock_exec:
        exit_code = gsi.run_intake(run_target=True)
        assert exit_code == 0
        mock_exec.assert_not_called()
        assert (mock_repo_root / "data" / "entities" / "data.json").exists()


def test_main_cli_argument_handling() -> None:
    """Verify main() CLI argument parsing passes run flag correctly."""
    with patch("sys.argv", ["gsi.py", "-r"]), patch("tools.ops.gsi.run_intake", return_value=0) as mock_intake:
        ret = gsi.main()
        assert ret == 0
        mock_intake.assert_called_once_with(run_target=True)