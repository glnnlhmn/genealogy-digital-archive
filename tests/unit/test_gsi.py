# Name: test_gsi.py
# Path: tests/unit/test_gsi.py
# Version: 1.0.1+build.20260927.01

"""Unit test suite for tools/ops/gsi.py (Genealogy Script Importer).

Operational Role:
    Validates metadata comment parsing across .py, .md, .ps1, .txt, and .json
    files, automatic directory appending, pre-write Safe Backup generation,
    path traversal defense, and contextual runner dispatch:
    - pytest for test_*.py
    - Google Chrome for *.md
    - PowerShell for *.ps1
    - Python interpreter for general *.py
    - Non-executable notification for static assets (.json, .txt).

Test Structure & Protocol:
    - Atomized tests: Dedicated isolated test per parser branch, security rule,
      and runner dispatcher.
    - Fully decorated: Classified with @pytest.mark.unit, @pytest.mark.smoke,
      and @pytest.mark.regression.
    - Dependencies: Isolated filesystem sandbox using tmp_path and monkeypatch.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

import tools.ops.gsi as gsi

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up an isolated repository root sandbox for GSI operations."""
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

@pytest.mark.smoke
def test_parse_metadata_header_python(mock_repo_root: Path) -> None:
    """Verify parsing of standard Python comment headers."""
    f = mock_repo_root / "gemini_script.py"
    f.write_text("# Name: task.py\n# Path: tools/ops/task.py\nprint('hello')", encoding="utf-8")
    name, dest = gsi.parse_metadata_header(f)
    assert name == "task.py"
    assert dest == (mock_repo_root / "tools" / "ops" / "task.py").resolve()


@pytest.mark.smoke
def test_parse_metadata_header_markdown_html(mock_repo_root: Path) -> None:
    """Verify parsing of Markdown HTML comment block headers."""
    f = mock_repo_root / "gemini_doc.md"
    f.write_text("<!--\nName: guide.md\nPath: docs/guide.md\n-->\n# Guide Title", encoding="utf-8")
    name, dest = gsi.parse_metadata_header(f)
    assert name == "guide.md"
    assert dest == (mock_repo_root / "docs" / "guide.md").resolve()


@pytest.mark.smoke
def test_parse_metadata_header_json_keys(mock_repo_root: Path) -> None:
    """Verify parsing of top-level JSON metadata keys."""
    f = mock_repo_root / "gemini_payload.json"
    f.write_text('{\n  "_name": "item.json",\n  "_path": "data/entities/item.json"\n}', encoding="utf-8")
    name, dest = gsi.parse_metadata_header(f)
    assert name == "item.json"
    assert dest == (mock_repo_root / "data" / "entities" / "item.json").resolve()


@pytest.mark.regression
def test_parse_metadata_header_directory_path_appends_filename(mock_repo_root: Path) -> None:
    """Verify that targeting an existing directory appends target_name."""
    f = mock_repo_root / "gemini_script.py"
    f.write_text("# Name: unit_test.py\n# Path: tests/unit\n", encoding="utf-8")
    name, dest = gsi.parse_metadata_header(f)
    assert name == "unit_test.py"
    assert dest == (mock_repo_root / "tests" / "unit" / "unit_test.py").resolve()


@pytest.mark.regression
def test_parse_metadata_header_trailing_slash_appends_filename(mock_repo_root: Path) -> None:
    """Verify that targeting a trailing slash directory appends target_name."""
    f_slash = mock_repo_root / "gemini_slash.py"
    f_slash.write_text("# Name: slash_test.py\n# Path: gtemp/\n", encoding="utf-8")
    name_slash, dest_slash = gsi.parse_metadata_header(f_slash)
    assert name_slash == "slash_test.py"
    assert dest_slash == (mock_repo_root / "gtemp" / "slash_test.py").resolve()


@pytest.mark.regression
def test_parse_metadata_header_unreadable_file(mock_repo_root: Path) -> None:
    """Verify read exceptions return (None, None)."""
    unreadable = mock_repo_root / "gemini_locked.py"
    with patch.object(Path, "read_text", side_effect=PermissionError("File locked")):
        assert gsi.parse_metadata_header(unreadable) == (None, None)


@pytest.mark.regression
def test_parse_metadata_header_empty_file(mock_repo_root: Path) -> None:
    """Verify missing headers return (None, None)."""
    f_empty = mock_repo_root / "gemini_empty.py"
    f_empty.write_text("print('no headers')", encoding="utf-8")
    assert gsi.parse_metadata_header(f_empty) == (None, None)


@pytest.mark.regression
def test_parse_metadata_header_partial_header(mock_repo_root: Path) -> None:
    """Verify partial headers lacking Path return (None, None)."""
    f_name_only = mock_repo_root / "gemini_partial.py"
    f_name_only.write_text("# Name: partial.py\nprint('no path')", encoding="utf-8")
    assert gsi.parse_metadata_header(f_name_only) == (None, None)


@pytest.mark.regression
def test_parse_metadata_header_exceeds_15_line_window(mock_repo_root: Path) -> None:
    """Verify headers positioned after line 15 are rejected."""
    f_late = mock_repo_root / "gemini_late.py"
    padding = "\n".join([f"# line {i}" for i in range(16)])
    f_late.write_text(f"{padding}\n# Name: late.py\n# Path: tools/ops/late.py", encoding="utf-8")
    assert gsi.parse_metadata_header(f_late) == (None, None)


# ----------------------------------------------------------------------
# Target Relocation & Safe Backup Tests
# ----------------------------------------------------------------------

@pytest.mark.smoke
def test_run_intake_relocates_file(mock_repo_root: Path) -> None:
    """Verify GSI relocates candidate files successfully."""
    cand = mock_repo_root / "gemini_test_run.py"
    cand.write_text("# Name: runner.py\n# Path: tools/ops/runner.py\n", encoding="utf-8")
    exit_code = gsi.run_intake(run_target=False)
    assert exit_code == 0
    assert not cand.exists()
    assert (mock_repo_root / "tools" / "ops" / "runner.py").exists()


@pytest.mark.regression
def test_run_intake_ignores_non_candidates(mock_repo_root: Path) -> None:
    """Verify files without gemini_ prefix are left untouched in root."""
    ignored = mock_repo_root / "other_script.py"
    ignored.write_text("# Name: other.py\n# Path: tools/ops/other.py\n", encoding="utf-8")
    exit_code = gsi.run_intake(run_target=False)
    assert exit_code == 0
    assert ignored.exists()


@pytest.mark.smoke
@pytest.mark.regression
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


@pytest.mark.regression
def test_run_intake_security_escape_prevented(mock_repo_root: Path) -> None:
    """Verify paths attempting traversal outside the archive root are blocked."""
    cand = mock_repo_root / "gemini_escape.py"
    cand.write_text("# Name: escape.py\n# Path: ../../../outside.py\n", encoding="utf-8")
    exit_code = gsi.run_intake(run_target=False)
    assert exit_code == 0
    assert cand.exists()


@pytest.mark.regression
def test_run_intake_missing_headers_logged(mock_repo_root: Path) -> None:
    """Verify candidate files missing metadata headers are skipped with warning."""
    cand = mock_repo_root / "gemini_unheaded.py"
    cand.write_text("print('no metadata headers')", encoding="utf-8")
    exit_code = gsi.run_intake(run_target=False)
    assert exit_code == 0
    assert cand.exists()


@pytest.mark.regression
def test_run_intake_propagates_execution_failure(mock_repo_root: Path) -> None:
    """Verify non-zero return codes from executed targets abort intake."""
    cand = mock_repo_root / "gemini_failing.py"
    cand.write_text("# Name: failing.py\n# Path: gtemp/failing.py\nimport sys; sys.exit(3)", encoding="utf-8")
    with patch.object(gsi, "execute_relocated_target", return_value=3):
        exit_code = gsi.run_intake(run_target=True)
        assert exit_code == 3


# ----------------------------------------------------------------------
# Execution Runner Routing (-r) Tests
# ----------------------------------------------------------------------

@pytest.mark.smoke
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


@pytest.mark.smoke
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


@pytest.mark.smoke
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


@pytest.mark.regression
def test_execute_relocated_target_markdown_chrome_success(mock_repo_root: Path) -> None:
    """Verify Chrome launching when available."""
    md_file = mock_repo_root / "doc.md"
    md_file.touch()
    with patch("shutil.which", return_value="chrome.exe"), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("subprocess.Popen") as mock_popen:
        logger = MagicMock()
        ret = gsi.execute_relocated_target(md_file, logger)
        assert ret == 0
        mock_popen.assert_called_once()


@pytest.mark.regression
def test_execute_relocated_target_markdown_fallback_on_spawn_error(mock_repo_root: Path) -> None:
    """Verify Chrome popen error falls back to default browser."""
    md_file = mock_repo_root / "doc.md"
    md_file.touch()
    with patch("shutil.which", return_value="chrome.exe"), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("subprocess.Popen", side_effect=OSError("Spawn error")), \
         patch("webbrowser.open") as mock_browser:
        logger = MagicMock()
        ret = gsi.execute_relocated_target(md_file, logger)
        assert ret == 0
        mock_browser.assert_called_once_with(md_file.as_uri())


@pytest.mark.regression
def test_execute_relocated_target_markdown_fallback_no_chrome(mock_repo_root: Path) -> None:
    """Verify fallback to default browser when Chrome is absent."""
    md_file = mock_repo_root / "doc.md"
    md_file.touch()
    with patch("shutil.which", return_value=None), \
         patch("pathlib.Path.is_file", return_value=False), \
         patch.dict(os.environ, {}, clear=True), \
         patch("webbrowser.open") as mock_browser:
        logger = MagicMock()
        ret = gsi.execute_relocated_target(md_file, logger)
        assert ret == 0
        mock_browser.assert_called_once_with(md_file.as_uri())


@pytest.mark.regression
def test_intake_non_executable_with_run_flag(mock_repo_root: Path) -> None:
    """Verify JSON files emit '(Can not execute)' and skip runner execution when -r is used."""
    json_cand = mock_repo_root / "gemini_data.json"
    json_cand.write_text('{"_name": "data.json", "_path": "data/entities/data.json"}', encoding="utf-8")
    with patch.object(gsi, "execute_relocated_target") as mock_exec:
        exit_code = gsi.run_intake(run_target=True)
        assert exit_code == 0
        mock_exec.assert_not_called()
        assert (mock_repo_root / "data" / "entities" / "data.json").exists()


@pytest.mark.smoke
def test_main_cli_argument_handling() -> None:
    """Verify main() CLI argument parsing passes run flag correctly."""
    with patch("sys.argv", ["gsi.py", "-r"]), patch("tools.ops.gsi.run_intake", return_value=0) as mock_intake:
        ret = gsi.main()
        assert ret == 0
        mock_intake.assert_called_once_with(run_target=True)