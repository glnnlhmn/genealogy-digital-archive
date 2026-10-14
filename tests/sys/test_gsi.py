# Name: test_gsi.py
# Path: tests/unit/test_gsi.py
# Version: 1.2.0+build.20261003.5

"""Unit test suite for tools/sys/gsi.py (Genealogy Script Importer).

Operational Role:
    Validates metadata comment and notebook parsing across .py, .md, .ps1,
    .txt, .json, and .ipynb files, pre-write Safe Backup generation, path
    traversal defense, directory normalization, and contextual runner dispatch:
    - pytest for test_*.py with coverage parameters and isolated scratch basetemp
    - Google Chrome for *.md
    - PowerShell for *.ps1
    - Python interpreter for general *.py
    - Non-executable notifications for static assets and notebooks (.json, .txt, .ipynb).

Test Structure & Protocol:
    - Atomized tests: Dedicated isolated test per parser branch, security rule,
      and runner dispatcher.
    - Fully decorated: Classified with @pytest.mark.unit, @pytest.mark.smoke,
      and @pytest.mark.regression.
    - Dependencies: Isolated filesystem sandbox using tmp_path and monkeypatch.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

import tools.sys.gsi as gsi

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up an isolated repository root sandbox for GSI operations."""
    (tmp_path / "gda_config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "sys").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "ops").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "entities").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True, exist_ok=True)
    (tmp_path / "notebooks" / "exploration").mkdir(parents=True, exist_ok=True)
    (tmp_path / "notebooks" / "templates").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(gsi, "ROOT_DIR", tmp_path)
    return tmp_path


# ----------------------------------------------------------------------
# Header & Metadata Parsing Unit Tests
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


@pytest.mark.smoke
def test_parse_metadata_header_ipynb_metadata_dict(mock_repo_root: Path) -> None:
    """Verify parsing of Jupyter Notebook metadata dictionary attributes."""
    nb_payload = {
        "metadata": {
            "_name": "01_sites_tour.ipynb",
            "_path": "notebooks/exploration/01_sites_tour.ipynb"
        },
        "cells": []
    }
    f = mock_repo_root / "gemini_notebook.ipynb"
    f.write_text(json.dumps(nb_payload), encoding="utf-8")
    name, dest = gsi.parse_metadata_header(f)
    assert name == "01_sites_tour.ipynb"
    assert dest == (mock_repo_root / "notebooks" / "exploration" / "01_sites_tour.ipynb").resolve()


@pytest.mark.smoke
def test_parse_metadata_header_ipynb_first_cell_fallback(mock_repo_root: Path) -> None:
    """Verify parsing of Jupyter Notebook first cell comment headers when metadata is absent."""
    nb_payload = {
        "metadata": {},
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["<!-- Name: 02_tour.ipynb -->\n", "<!-- Path: notebooks/exploration/ -->"]
            }
        ]
    }
    f = mock_repo_root / "gemini_nb_fallback.ipynb"
    f.write_text(json.dumps(nb_payload), encoding="utf-8")
    name, dest = gsi.parse_metadata_header(f)
    assert name == "02_tour.ipynb"
    assert dest == (mock_repo_root / "notebooks" / "exploration" / "02_tour.ipynb").resolve()


@pytest.mark.regression
def test_parse_metadata_header_ipynb_corrupt_json(mock_repo_root: Path) -> None:
    """Verify unparseable corrupt notebook JSON returns (None, None)."""
    f = mock_repo_root / "gemini_corrupt.ipynb"
    f.write_text("{ unparseable json: true ", encoding="utf-8")
    name, dest = gsi.parse_metadata_header(f)
    assert name is None
    assert dest is None


@pytest.mark.regression
def test_parse_metadata_header_json_partial_falls_back_to_regex(mock_repo_root: Path) -> None:
    """Verify partial JSON (_name only) falls back to regex comment search."""
    f = mock_repo_root / "gemini_partial_json.json"
    f.write_text('{\n  "_name": "item.json",\n  "data": 123\n}', encoding="utf-8")
    name, dest = gsi.parse_metadata_header(f)
    assert name is None
    assert dest is None


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
def test_parse_metadata_header_partial_header_name_only(mock_repo_root: Path) -> None:
    """Verify partial headers lacking Path return (None, None)."""
    f_name_only = mock_repo_root / "gemini_partial_name.py"
    f_name_only.write_text("# Name: partial.py\nprint('no path')", encoding="utf-8")
    assert gsi.parse_metadata_header(f_name_only) == (None, None)


@pytest.mark.regression
def test_parse_metadata_header_partial_header_path_only(mock_repo_root: Path) -> None:
    """Verify partial headers lacking Name return (None, None)."""
    f_path_only = mock_repo_root / "gemini_partial_path.py"
    f_path_only.write_text("# Path: tools/ops/partial.py\nprint('no name')", encoding="utf-8")
    assert gsi.parse_metadata_header(f_path_only) == (None, None)


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


@pytest.mark.smoke
def test_run_intake_relocates_notebook(mock_repo_root: Path) -> None:
    """Verify GSI relocates Jupyter notebook candidates to designated notebook directory."""
    nb_payload = {
        "metadata": {
            "_name": "tour.ipynb",
            "_path": "notebooks/exploration/tour.ipynb"
        },
        "cells": []
    }
    cand = mock_repo_root / "gemini_tour.ipynb"
    cand.write_text(json.dumps(nb_payload), encoding="utf-8")
    exit_code = gsi.run_intake(run_target=False)
    assert exit_code == 0
    assert not cand.exists()
    assert (mock_repo_root / "notebooks" / "exploration" / "tour.ipynb").exists()


@pytest.mark.regression
def test_run_intake_no_candidates(mock_repo_root: Path) -> None:
    """Verify run_intake logs informational message and returns 0 when root has no candidates."""
    exit_code = gsi.run_intake(run_target=False)
    assert exit_code == 0


@pytest.mark.regression
def test_run_intake_ignores_non_candidates(mock_repo_root: Path) -> None:
    """Verify files without gemini matching are left untouched in root."""
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

    with patch("tools.sys.gsi.GDAUtil.create_safe_backup") as mock_bk:
        exit_code = gsi.run_intake(run_target=False)
        assert exit_code == 0
        mock_bk.assert_called_once()
        assert dest.read_text(encoding="utf-8") == "# Name: existing.py\n# Path: tools/ops/existing.py\nnew content"


@pytest.mark.regression
def test_run_intake_config_fallback(mock_repo_root: Path) -> None:
    """Verify fallback instantiation when GDAConfig.load raises an exception."""
    cand = mock_repo_root / "gemini_fb.py"
    cand.write_text("# Name: fb.py\n# Path: gtemp/fb.py\n", encoding="utf-8")
    with patch("tools.sys.gsi.GDAConfig.load", side_effect=RuntimeError("Config load failure")):
        exit_code = gsi.run_intake(run_target=False)
        assert exit_code == 0
        assert (mock_repo_root / "gtemp" / "fb.py").exists()


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


@pytest.mark.regression
def test_run_intake_multiple_candidates_continue_on_success(mock_repo_root: Path) -> None:
    """Verify multiple candidates continue loop iteration when execution succeeds."""
    cand1 = mock_repo_root / "gemini_1.py"
    cand1.write_text("# Name: step1.py\n# Path: gtemp/step1.py\n", encoding="utf-8")
    cand2 = mock_repo_root / "gemini_2.py"
    cand2.write_text("# Name: step2.py\n# Path: gtemp/step2.py\n", encoding="utf-8")

    with patch.object(gsi, "execute_relocated_target", return_value=0) as mock_exec:
        exit_code = gsi.run_intake(run_target=True)
        assert exit_code == 0
        assert mock_exec.call_count == 2
        assert (mock_repo_root / "gtemp" / "step1.py").exists()
        assert (mock_repo_root / "gtemp" / "step2.py").exists()


# ----------------------------------------------------------------------
# Execution Runner Routing (-r) Tests
# ----------------------------------------------------------------------
@pytest.mark.smoke
def test_execute_relocated_target_pytest_with_coverage(mock_repo_root: Path) -> None:
    """Verify test_*.py files execute via pytest with coverage parameters and basetemp."""
    test_file = mock_repo_root / "test_sample.py"
    test_file.touch()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        logger = MagicMock()
        ret = gsi.execute_relocated_target(test_file, logger)
        assert ret == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "-v",
            "--cov=gdacore",
            "--cov-branch",
            "--cov-report=term-missing",
            "--basetemp=gtemp/pytest_tmp",
        ]


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
    """Verify Chrome launching and loop exit via break when Chrome binary is found."""
    md_file = mock_repo_root / "doc.md"
    md_file.touch()
    with patch("shutil.which", return_value="chrome.exe"), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("subprocess.Popen") as mock_popen, \
         patch("webbrowser.open") as mock_browser:
        logger = MagicMock()
        ret = gsi.execute_relocated_target(md_file, logger)
        assert ret == 0
        mock_popen.assert_called_once()
        mock_browser.assert_not_called()


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
def test_execute_relocated_target_unhandled_extension_fallback(mock_repo_root: Path) -> None:
    """Verify unhandled target extensions return 0 directly."""
    unknown_file = mock_repo_root / "sample.xyz"
    unknown_file.touch()
    logger = MagicMock()
    ret = gsi.execute_relocated_target(unknown_file, logger)
    assert ret == 0


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


@pytest.mark.regression
def test_intake_notebook_non_executable_with_run_flag(mock_repo_root: Path) -> None:
    """Verify IPYNB files emit '(Can not execute)' and skip runner execution when -r is used."""
    nb_payload = {
        "metadata": {
            "_name": "template.ipynb",
            "_path": "notebooks/templates/template.ipynb"
        },
        "cells": []
    }
    nb_cand = mock_repo_root / "gemini_nb.ipynb"
    nb_cand.write_text(json.dumps(nb_payload), encoding="utf-8")
    with patch.object(gsi, "execute_relocated_target") as mock_exec:
        exit_code = gsi.run_intake(run_target=True)
        assert exit_code == 0
        mock_exec.assert_not_called()
        assert (mock_repo_root / "notebooks" / "templates" / "template.ipynb").exists()


@pytest.mark.smoke
def test_main_cli_argument_handling() -> None:
    """Verify main() CLI argument parsing passes run flag correctly."""
    with patch("sys.argv", ["gsi.py", "-r"]), patch("tools.sys.gsi.run_intake", return_value=0) as mock_intake:
        ret = gsi.main()
        assert ret == 0
        mock_intake.assert_called_once_with(run_target=True)


@pytest.mark.regression
def test_main_execution_entrypoint() -> None:
    """Verify execution of the top-level script entry point."""
    script_path = Path(gsi.__file__).resolve()
    with patch("sys.argv", ["gsi.py", "-h"]), pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(script_path), run_name="__main__")
    assert exc_info.value.code == 0

# Name: test_gsi_coverage_closing.py
# Path: tests/unit/test_gsi.py

@pytest.mark.regression
def test_parse_metadata_header_ipynb_corrupt_json(mock_repo_root: Path) -> None:
    """Verify unparseable corrupt notebook JSON returns (None, None)."""
    f = mock_repo_root / "gemini_corrupt.ipynb"
    f.write_text("{ unparseable json: true ", encoding="utf-8")
    name, dest = gsi.parse_metadata_header(f)
    assert name is None
    assert dest is None


@pytest.mark.regression
def test_execute_relocated_target_unhandled_extension_fallback(mock_repo_root: Path) -> None:
    """Verify unhandled target extensions return 0 directly."""
    unknown_file = mock_repo_root / "sample.xyz"
    unknown_file.touch()
    logger = MagicMock()
    ret = gsi.execute_relocated_target(unknown_file, logger)
    assert ret == 0


@pytest.mark.regression
def test_main_execution_entrypoint() -> None:
    """Verify execution of the top-level script entry point."""
    import runpy
    script_path = Path(gsi.__file__).resolve()
    with patch("sys.argv", ["gsi.py", "-h"]), pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(script_path), run_name="__main__")
    assert exc_info.value.code == 0