# Name: test_install_hooks.py
# Path: tests/unit/test_install_hooks.py

"""
================================================================================
Test Suite: tests/unit/test_install_hooks.py
Role: Unit tests for Git hook automation installer (tools/sys/install_hooks.py).
Markers: @pytest.mark.unit

Coverage Goals:
  - Repository presence validation (valid/invalid .git directory)
  - Pre-commit and pre-push hook installation and content correctness
  - POSIX / Git Bash executable permission bit enforcement (cross-platform safe)
  - Hook uninstallation and missing file tolerance
  - Status reporting output formatting
  - CLI argument parsing (--status, --uninstall, default install)
================================================================================
"""

from pathlib import Path
import stat
import sys
from unittest.mock import MagicMock, patch
import pytest

from tools.sys import install_hooks


@pytest.fixture
def hermetic_repo(tmp_path, monkeypatch):
    """Sets up a sandboxed repository with a fake .git directory."""
    repo_root = tmp_path / "repo"
    git_dir = repo_root / ".git"
    hooks_dir = git_dir / "hooks"
    git_dir.mkdir(parents=True)

    monkeypatch.setattr(install_hooks, "ROOT_DIR", repo_root)
    monkeypatch.setattr(install_hooks, "GIT_DIR", git_dir)
    monkeypatch.setattr(install_hooks, "HOOKS_DIR", hooks_dir)
    return repo_root, git_dir, hooks_dir


@pytest.mark.unit
def test_verify_git_repository_returns_true_when_dir_exists(hermetic_repo):
    """Verifies repository validation succeeds when .git directory exists."""
    assert install_hooks.verify_git_repository() is True


@pytest.mark.unit
def test_verify_git_repository_returns_false_when_missing(tmp_path, monkeypatch):
    """Verifies repository validation fails when .git directory does not exist."""
    missing_git = tmp_path / "nonexistent" / ".git"
    monkeypatch.setattr(install_hooks, "GIT_DIR", missing_git)
    assert install_hooks.verify_git_repository() is False


@pytest.mark.unit
def test_make_executable_sets_execute_bits(tmp_path):
    """Ensures executable bits (user, group, other) are applied across platforms."""
    test_file = tmp_path / "test_script.sh"
    test_file.write_text("#!/bin/sh\necho hi", encoding="utf-8")

    if sys.platform == "win32":
        # Windows NTFS ignores POSIX exec bits in stat(); verify chmod call invocation
        original_mode = test_file.stat().st_mode
        expected_mask = original_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH

        with patch.object(Path, "chmod", autospec=True) as mock_chmod:
            install_hooks.make_executable(test_file)
            mock_chmod.assert_called_once_with(test_file, expected_mask)
    else:
        test_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        install_hooks.make_executable(test_file)
        mode = test_file.stat().st_mode
        assert mode & stat.S_IXUSR
        assert mode & stat.S_IXGRP
        assert mode & stat.S_IXOTH


@pytest.mark.unit
def test_install_hooks_fails_when_not_a_git_repo(tmp_path, monkeypatch):
    """Ensures install_hooks aborts cleanly if git verification fails."""
    monkeypatch.setattr(install_hooks, "verify_git_repository", lambda: False)
    assert install_hooks.install_hooks() is False


@pytest.mark.unit
def test_install_hooks_creates_pre_commit_and_pre_push(hermetic_repo):
    """Verifies that both hooks are created with expected script templates."""
    _, _, hooks_dir = hermetic_repo
    success = install_hooks.install_hooks()

    assert success is True
    pre_commit = hooks_dir / "pre-commit"
    pre_push = hooks_dir / "pre-push"

    assert pre_commit.exists()
    assert pre_push.exists()
    assert pre_commit.read_text(encoding="utf-8") == install_hooks.PRE_COMMIT_SCRIPT
    assert pre_push.read_text(encoding="utf-8") == install_hooks.PRE_PUSH_SCRIPT


@pytest.mark.unit
def test_uninstall_hooks_fails_when_not_a_git_repo(tmp_path, monkeypatch):
    """Ensures uninstall_hooks returns False when git repository check fails."""
    monkeypatch.setattr(install_hooks, "verify_git_repository", lambda: False)
    assert install_hooks.uninstall_hooks() is False


@pytest.mark.unit
def test_uninstall_hooks_removes_existing_hooks(hermetic_repo):
    """Verifies existing pre-commit and pre-push files are successfully removed."""
    _, _, hooks_dir = hermetic_repo
    install_hooks.install_hooks()

    pre_commit = hooks_dir / "pre-commit"
    pre_push = hooks_dir / "pre-push"
    assert pre_commit.exists() and pre_push.exists()

    result = install_hooks.uninstall_hooks()
    assert result is True
    assert not pre_commit.exists()
    assert not pre_push.exists()


@pytest.mark.unit
def test_uninstall_hooks_succeeds_when_hooks_already_absent(hermetic_repo):
    """Verifies uninstall runs without error even if hook files do not exist."""
    result = install_hooks.uninstall_hooks()
    assert result is True


@pytest.mark.unit
def test_check_status_aborts_silently_on_invalid_repo(tmp_path, monkeypatch, capsys):
    """Ensures check_status outputs nothing if not inside a valid git repo."""
    monkeypatch.setattr(install_hooks, "verify_git_repository", lambda: False)
    install_hooks.check_status()
    captured = capsys.readouterr()
    assert "Git Hooks Status" not in captured.out


@pytest.mark.unit
def test_check_status_reports_uninstalled(hermetic_repo, capsys):
    """Verifies status output reflects uninstalled state when files are absent."""
    install_hooks.check_status()
    captured = capsys.readouterr()
    assert "pre-commit     : NOT INSTALLED" in captured.out
    assert "pre-push       : NOT INSTALLED" in captured.out


@pytest.mark.unit
def test_check_status_reports_installed(hermetic_repo, capsys):
    """Verifies status output reflects installed active state when hooks exist."""
    install_hooks.install_hooks()
    install_hooks.check_status()
    captured = capsys.readouterr()
    assert "pre-commit     : INSTALLED (Active)" in captured.out
    assert "pre-push       : INSTALLED (Active)" in captured.out


@pytest.mark.unit
def test_main_status_flag(hermetic_repo, capsys):
    """Tests that main() exits 0 and reports status when invoked with --status."""
    with patch.object(sys, "argv", ["install_hooks.py", "--status"]):
        code = install_hooks.main()
        assert code == 0
        captured = capsys.readouterr()
        assert "Git Hooks Status" in captured.out


@pytest.mark.unit
def test_main_uninstall_flag_success(hermetic_repo):
    """Tests that main() exits 0 when invoking --uninstall on valid repository."""
    install_hooks.install_hooks()
    with patch.object(sys, "argv", ["install_hooks.py", "--uninstall"]):
        code = install_hooks.main()
        assert code == 0


@pytest.mark.unit
def test_main_uninstall_flag_failure(tmp_path, monkeypatch):
    """Tests that main() exits 1 when --uninstall fails due to missing repository."""
    monkeypatch.setattr(install_hooks, "verify_git_repository", lambda: False)
    with patch.object(sys, "argv", ["install_hooks.py", "--uninstall"]):
        code = install_hooks.main()
        assert code == 1


@pytest.mark.unit
def test_main_install_success(hermetic_repo):
    """Tests that main() defaults to installing hooks and exits 0 on success."""
    with patch.object(sys, "argv", ["install_hooks.py"]):
        code = install_hooks.main()
        assert code == 0
        _, _, hooks_dir = hermetic_repo
        assert (hooks_dir / "pre-commit").exists()
        assert (hooks_dir / "pre-push").exists()


@pytest.mark.unit
def test_main_install_failure(tmp_path, monkeypatch):
    """Tests that main() exits 1 when default installation fails."""
    monkeypatch.setattr(install_hooks, "verify_git_repository", lambda: False)
    with patch.object(sys, "argv", ["install_hooks.py"]):
        code = install_hooks.main()
        assert code == 1