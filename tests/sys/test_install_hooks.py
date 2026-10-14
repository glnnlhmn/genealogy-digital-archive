# Name: test_install_hooks.py
# Path: tests/unit/test_install_hooks.py
# Version: 1.2.1+build.20260927.1

"""Consolidated unit test suite for Git hook automation installer.

Operational Role:
    Verifies git hook automation installer (tools/sys/install_hooks.py),
    including git repository existence validation, pre-commit and pre-push
    script file deployment, POSIX execution permissions enforcement,
    uninstallation routines, status reporting, and CLI entry point flags.

Test Structure & Protocol:
    - Atomized tests: 1:1 mapping of single assertions per test function.
    - Fully decorated: Decorated with @pytest.mark.unit.
    - Dependencies: tmp_path and monkeypatch for hermetic filesystem sandboxing.
"""

from pathlib import Path
import stat
import sys
from types import SimpleNamespace
from unittest.mock import patch
import pytest

from tools.sys import install_hooks


@pytest.fixture
def hermetic_repo(tmp_path, monkeypatch):
    """Sets up a sandboxed repository with an isolated .git directory."""
    repo_root = tmp_path / "repo"
    git_dir = repo_root / ".git"
    hooks_dir = git_dir / "hooks"
    git_dir.mkdir(parents=True)

    monkeypatch.setattr(install_hooks, "ROOT_DIR", repo_root)
    monkeypatch.setattr(install_hooks, "GIT_DIR", git_dir)
    monkeypatch.setattr(install_hooks, "HOOKS_DIR", hooks_dir)
    return repo_root, git_dir, hooks_dir


# =============================================================================
# Repository Presence Validation
# =============================================================================

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


# =============================================================================
# Permission Enforcement (Mocked for Cross-Platform Compatibility)
# =============================================================================

@pytest.mark.unit
def test_make_executable_invokes_chmod(tmp_path):
    """Ensures chmod is invoked on the target file path."""
    test_file = tmp_path / "test_script.sh"
    test_file.write_text("#!/bin/sh\necho hi", encoding="utf-8")

    with patch.object(Path, "chmod", autospec=True) as mock_chmod:
        install_hooks.make_executable(test_file)
        assert mock_chmod.call_count == 1


@pytest.mark.unit
def test_make_executable_sets_user_exec_bit(tmp_path):
    """Ensures user execution bit (S_IXUSR) is included in chmod mask."""
    test_file = tmp_path / "test_script.sh"
    test_file.write_text("#!/bin/sh\necho hi", encoding="utf-8")

    fake_stat = SimpleNamespace(st_mode=0o644)
    with patch.object(Path, "stat", return_value=fake_stat), patch.object(Path, "chmod") as mock_chmod:
        install_hooks.make_executable(test_file)
        called_mode = mock_chmod.call_args.args[0]
        assert bool(called_mode & stat.S_IXUSR) is True


@pytest.mark.unit
def test_make_executable_sets_group_exec_bit(tmp_path):
    """Ensures group execution bit (S_IXGRP) is included in chmod mask."""
    test_file = tmp_path / "test_script.sh"
    test_file.write_text("#!/bin/sh\necho hi", encoding="utf-8")

    fake_stat = SimpleNamespace(st_mode=0o644)
    with patch.object(Path, "stat", return_value=fake_stat), patch.object(Path, "chmod") as mock_chmod:
        install_hooks.make_executable(test_file)
        called_mode = mock_chmod.call_args.args[0]
        assert bool(called_mode & stat.S_IXGRP) is True


@pytest.mark.unit
def test_make_executable_sets_other_exec_bit(tmp_path):
    """Ensures other execution bit (S_IXOTH) is included in chmod mask."""
    test_file = tmp_path / "test_script.sh"
    test_file.write_text("#!/bin/sh\necho hi", encoding="utf-8")

    fake_stat = SimpleNamespace(st_mode=0o644)
    with patch.object(Path, "stat", return_value=fake_stat), patch.object(Path, "chmod") as mock_chmod:
        install_hooks.make_executable(test_file)
        called_mode = mock_chmod.call_args.args[0]
        assert bool(called_mode & stat.S_IXOTH) is True


# =============================================================================
# Hook Installation Mechanics
# =============================================================================

@pytest.mark.unit
def test_install_hooks_fails_when_not_a_git_repo(tmp_path, monkeypatch):
    """Ensures install_hooks aborts cleanly if git verification fails."""
    monkeypatch.setattr(install_hooks, "verify_git_repository", lambda: False)
    assert install_hooks.install_hooks() is False


@pytest.mark.unit
def test_install_hooks_returns_true_on_success(hermetic_repo):
    """Verifies that install_hooks returns True on successful installation."""
    assert install_hooks.install_hooks() is True


@pytest.mark.unit
def test_install_hooks_creates_pre_commit_file(hermetic_repo):
    """Verifies that pre-commit hook file exists on disk after installation."""
    _, _, hooks_dir = hermetic_repo
    install_hooks.install_hooks()
    assert (hooks_dir / "pre-commit").exists()


@pytest.mark.unit
def test_install_hooks_writes_pre_commit_payload(hermetic_repo):
    """Verifies that pre-commit hook content matches PRE_COMMIT_SCRIPT."""
    _, _, hooks_dir = hermetic_repo
    install_hooks.install_hooks()
    assert (hooks_dir / "pre-commit").read_text(encoding="utf-8") == install_hooks.PRE_COMMIT_SCRIPT


@pytest.mark.unit
def test_install_hooks_creates_pre_push_file(hermetic_repo):
    """Verifies that pre-push hook file exists on disk after installation."""
    _, _, hooks_dir = hermetic_repo
    install_hooks.install_hooks()
    assert (hooks_dir / "pre-push").exists()


@pytest.mark.unit
def test_install_hooks_writes_pre_push_payload(hermetic_repo):
    """Verifies that pre-push hook content matches PRE_PUSH_SCRIPT."""
    _, _, hooks_dir = hermetic_repo
    install_hooks.install_hooks()
    assert (hooks_dir / "pre-push").read_text(encoding="utf-8") == install_hooks.PRE_PUSH_SCRIPT


# =============================================================================
# Hook Uninstallation Mechanics
# =============================================================================

@pytest.mark.unit
def test_uninstall_hooks_fails_when_not_a_git_repo(tmp_path, monkeypatch):
    """Ensures uninstall_hooks returns False when git repository check fails."""
    monkeypatch.setattr(install_hooks, "verify_git_repository", lambda: False)
    assert install_hooks.uninstall_hooks() is False


@pytest.mark.unit
def test_uninstall_hooks_returns_true_on_success(hermetic_repo):
    """Verifies uninstall_hooks returns True when hooks are uninstalled."""
    install_hooks.install_hooks()
    assert install_hooks.uninstall_hooks() is True


@pytest.mark.unit
def test_uninstall_hooks_removes_pre_commit_file(hermetic_repo):
    """Verifies existing pre-commit file is deleted from disk."""
    _, _, hooks_dir = hermetic_repo
    install_hooks.install_hooks()
    install_hooks.uninstall_hooks()
    assert not (hooks_dir / "pre-commit").exists()


@pytest.mark.unit
def test_uninstall_hooks_removes_pre_push_file(hermetic_repo):
    """Verifies existing pre-push file is deleted from disk."""
    _, _, hooks_dir = hermetic_repo
    install_hooks.install_hooks()
    install_hooks.uninstall_hooks()
    assert not (hooks_dir / "pre-push").exists()


@pytest.mark.unit
def test_uninstall_hooks_succeeds_when_hooks_already_absent(hermetic_repo):
    """Verifies uninstall runs without error even if hook files do not exist."""
    assert install_hooks.uninstall_hooks() is True


# =============================================================================
# Status Reporting
# =============================================================================

@pytest.mark.unit
def test_check_status_aborts_silently_on_invalid_repo(tmp_path, monkeypatch, capsys):
    """Ensures check_status outputs nothing if not inside a valid git repo."""
    monkeypatch.setattr(install_hooks, "verify_git_repository", lambda: False)
    install_hooks.check_status()
    captured = capsys.readouterr()
    assert "Git Hooks Status" not in captured.out


@pytest.mark.unit
def test_check_status_reports_pre_commit_uninstalled(hermetic_repo, capsys):
    """Verifies status output reflects pre-commit uninstalled state."""
    install_hooks.check_status()
    captured = capsys.readouterr()
    assert "pre-commit     : NOT INSTALLED" in captured.out


@pytest.mark.unit
def test_check_status_reports_pre_push_uninstalled(hermetic_repo, capsys):
    """Verifies status output reflects pre-push uninstalled state."""
    install_hooks.check_status()
    captured = capsys.readouterr()
    assert "pre-push       : NOT INSTALLED" in captured.out


@pytest.mark.unit
def test_check_status_reports_pre_commit_installed(hermetic_repo, capsys):
    """Verifies status output reflects pre-commit installed active state."""
    install_hooks.install_hooks()
    install_hooks.check_status()
    captured = capsys.readouterr()
    assert "pre-commit     : INSTALLED (Active)" in captured.out


@pytest.mark.unit
def test_check_status_reports_pre_push_installed(hermetic_repo, capsys):
    """Verifies status output reflects pre-push installed active state."""
    install_hooks.install_hooks()
    install_hooks.check_status()
    captured = capsys.readouterr()
    assert "pre-push       : INSTALLED (Active)" in captured.out


# =============================================================================
# CLI Entry Point & Arguments Parsing
# =============================================================================

@pytest.mark.unit
def test_main_status_flag_exit_code(hermetic_repo):
    """Tests that main() exits 0 when invoked with --status."""
    with patch.object(sys, "argv", ["install_hooks.py", "--status"]):
        assert install_hooks.main() == 0


@pytest.mark.unit
def test_main_status_flag_output(hermetic_repo, capsys):
    """Tests that main() reports status output when invoked with --status."""
    with patch.object(sys, "argv", ["install_hooks.py", "--status"]):
        install_hooks.main()
        captured = capsys.readouterr()
        assert "Git Hooks Status" in captured.out


@pytest.mark.unit
def test_main_uninstall_flag_success(hermetic_repo):
    """Tests that main() exits 0 when invoking --uninstall on valid repository."""
    install_hooks.install_hooks()
    with patch.object(sys, "argv", ["install_hooks.py", "--uninstall"]):
        assert install_hooks.main() == 0


@pytest.mark.unit
def test_main_uninstall_flag_failure(tmp_path, monkeypatch):
    """Tests that main() exits 1 when --uninstall fails due to missing repository."""
    monkeypatch.setattr(install_hooks, "verify_git_repository", lambda: False)
    with patch.object(sys, "argv", ["install_hooks.py", "--uninstall"]):
        assert install_hooks.main() == 1


@pytest.mark.unit
def test_main_install_success_exit_code(hermetic_repo):
    """Tests that main() exits 0 on default installation success."""
    with patch.object(sys, "argv", ["install_hooks.py"]):
        assert install_hooks.main() == 0


@pytest.mark.unit
def test_main_install_success_creates_hooks(hermetic_repo):
    """Tests that main() default invocation successfully deploys hooks."""
    with patch.object(sys, "argv", ["install_hooks.py"]):
        install_hooks.main()
        _, _, hooks_dir = hermetic_repo
        assert (hooks_dir / "pre-commit").exists()


@pytest.mark.unit
def test_main_install_failure(tmp_path, monkeypatch):
    """Tests that main() exits 1 when default installation fails."""
    monkeypatch.setattr(install_hooks, "verify_git_repository", lambda: False)
    with patch.object(sys, "argv", ["install_hooks.py"]):
        assert install_hooks.main() == 1