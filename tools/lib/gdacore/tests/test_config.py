# Name: test_config.py
# Path: tools/lib/gdacore/tests/test_config.py
# Version: 1.0.0+build.rc1

"""Unit test harness for GDAConfig filesystem configuration and root discovery.

Operational Role:
    Validates repository root discovery across explicit overrides, GDA_ROOT
    environment variables, parent traversal, working directory markers,
    directory property accessors, module-level fallback handling, and runtime
    introspection contracts.

Test Structure & Protocol:
    - Atomized tests: 1:1 assertion mapping per test function.
    - Fully decorated: Strictly marked with @pytest.mark.unit, @pytest.mark.smoke, @pytest.mark.regression.
    - Dependencies: Isolated hermetic tmp_path sandboxes.
"""

from __future__ import annotations

import importlib
import io
from pathlib import Path
from typing import Set
from unittest.mock import patch
import pytest

from gdacore import config
from gdacore.config import GDAConfig

__version__ = "1.0.0+build.rc1"


@pytest.fixture
def mock_repo_root(tmp_path: Path) -> Path:
    """Create a minimal mock repository structure with manifest marker."""
    root_dir = tmp_path / "mock_archive"
    root_dir.mkdir(parents=True, exist_ok=True)
    (root_dir / "gda_config.json").write_text("{}", encoding="utf-8")
    return root_dir


def _make_marker_exists_mock(allowed_roots: Set[Path]):
    """Create a Path.exists side-effect allowing markers only in specified directories."""
    orig_exists = Path.exists
    allowed = {p.resolve() for p in allowed_roots}

    def mock_exists(self: Path) -> bool:
        if self.name in ("gda_config.json", ".git"):
            return self.parent.resolve() in allowed
        return orig_exists(self)

    return mock_exists


# =============================================================================
# GROUP 1: Root Discovery & Traversal Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_config_load_explicit_custom_root_success(mock_repo_root: Path) -> None:
    """Verify load with valid explicit custom_root resolves correctly."""
    cfg = GDAConfig.load(custom_root=mock_repo_root)
    assert cfg.root == mock_repo_root.resolve()


@pytest.mark.unit
@pytest.mark.regression
def test_config_load_invalid_custom_root_raises_filenotfound(tmp_path: Path) -> None:
    """Verify load with invalid custom root missing markers raises FileNotFoundError."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="Provided custom root is invalid"):
        GDAConfig.load(custom_root=empty_dir)


@pytest.mark.unit
@pytest.mark.regression
def test_config_load_resolves_git_marker(tmp_path: Path) -> None:
    """Verify custom root is accepted if .git directory marker is present."""
    git_dir = tmp_path / "git_repo"
    git_dir.mkdir()
    (git_dir / ".git").mkdir()
    cfg = GDAConfig.load(custom_root=git_dir)
    assert cfg.root == git_dir.resolve()


@pytest.mark.unit
@pytest.mark.smoke
def test_config_load_from_gda_root_env_var(mock_repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify load resolves root from valid GDA_ROOT environment variable."""
    monkeypatch.setenv("GDA_ROOT", str(mock_repo_root))
    cfg = GDAConfig.load()
    assert cfg.root == mock_repo_root.resolve()


@pytest.mark.unit
@pytest.mark.regression
def test_config_load_ignores_nonexistent_gda_root_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify load falls through when GDA_ROOT points to a non-existent path."""
    fake_path = tmp_path / "ghost_env_root"
    monkeypatch.setenv("GDA_ROOT", str(fake_path))
    fallback_target = tmp_path / "fallback_mount"
    fallback_target.mkdir()
    (fallback_target / "gda_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(GDAConfig, "DEFAULT_PROD_ROOT", fallback_target)

    cfg = GDAConfig.load()
    assert cfg.root == fallback_target.resolve()


@pytest.mark.unit
@pytest.mark.smoke
def test_config_load_resolves_default_prod_root_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify load resolves DEFAULT_PROD_ROOT when environment variable is unset."""
    monkeypatch.delenv("GDA_ROOT", raising=False)
    prod_mock = tmp_path / "prod_root"
    prod_mock.mkdir()
    monkeypatch.setattr(GDAConfig, "DEFAULT_PROD_ROOT", prod_mock)

    cfg = GDAConfig.load()
    assert cfg.root == prod_mock.resolve()


@pytest.mark.unit
@pytest.mark.regression
def test_config_load_discovers_marker_via_parent_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify load finds root marker in parent directories."""
    monkeypatch.delenv("GDA_ROOT", raising=False)
    monkeypatch.setattr(GDAConfig, "DEFAULT_PROD_ROOT", tmp_path / "nonexistent_prod")

    parent_root = tmp_path / "traversal_archive"
    parent_root.mkdir()
    (parent_root / "gda_config.json").write_text("{}", encoding="utf-8")

    sub_dir = parent_root / "tools" / "lib" / "gdacore"
    sub_dir.mkdir(parents=True)
    fake_config_file = sub_dir / "config.py"
    fake_config_file.touch()

    monkeypatch.setattr(config, "__file__", str(fake_config_file))
    monkeypatch.chdir(tmp_path)

    side_effect = _make_marker_exists_mock({parent_root})
    with patch.object(Path, "exists", autospec=True, side_effect=side_effect):
        cfg = GDAConfig.load()
        assert cfg.root == parent_root.resolve()


@pytest.mark.unit
@pytest.mark.regression
def test_config_load_discovers_marker_in_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify load finds root marker in current working directory."""
    monkeypatch.delenv("GDA_ROOT", raising=False)
    monkeypatch.setattr(GDAConfig, "DEFAULT_PROD_ROOT", tmp_path / "nonexistent_prod")

    isolated_dir = tmp_path / "isolated" / "deep"
    isolated_dir.mkdir(parents=True)
    fake_config_file = isolated_dir / "config.py"
    fake_config_file.touch()
    monkeypatch.setattr(config, "__file__", str(fake_config_file))

    cwd_archive = tmp_path / "cwd_archive"
    cwd_archive.mkdir()
    (cwd_archive / "gda_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(cwd_archive)

    side_effect = _make_marker_exists_mock({cwd_archive})
    with patch.object(Path, "exists", autospec=True, side_effect=side_effect):
        cfg = GDAConfig.load()
        assert cfg.root == cwd_archive.resolve()


@pytest.mark.unit
@pytest.mark.regression
def test_config_load_failure_raises_filenotfound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify load raises FileNotFoundError when no markers, env var, or mounts exist."""
    monkeypatch.delenv("GDA_ROOT", raising=False)
    monkeypatch.setattr(GDAConfig, "DEFAULT_PROD_ROOT", tmp_path / "nonexistent_prod")

    isolated_dir = tmp_path / "empty_sandbox" / "sub"
    isolated_dir.mkdir(parents=True)
    fake_config_file = isolated_dir / "config.py"
    fake_config_file.touch()
    monkeypatch.setattr(config, "__file__", str(fake_config_file))

    empty_cwd = tmp_path / "empty_cwd"
    empty_cwd.mkdir()
    monkeypatch.chdir(empty_cwd)

    side_effect = _make_marker_exists_mock(set())
    with patch.object(Path, "exists", autospec=True, side_effect=side_effect):
        with pytest.raises(FileNotFoundError, match="Could not resolve valid GDA repository root"):
            GDAConfig.load()


# =============================================================================
# GROUP 2: Workspace & Ephemeral Path Accessors
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_config_temp_property(mock_repo_root: Path) -> None:
    """Verify temp directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.temp == mock_repo_root / "gtemp"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_logs_property(mock_repo_root: Path) -> None:
    """Verify logs directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.logs == mock_repo_root / "logs"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_backups_property(mock_repo_root: Path) -> None:
    """Verify backups directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.backups == mock_repo_root / "backups"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_reports_property(mock_repo_root: Path) -> None:
    """Verify reports directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.reports == mock_repo_root / "reports"


# =============================================================================
# GROUP 3: Intake Pipeline Path Accessors
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_config_intake_property(mock_repo_root: Path) -> None:
    """Verify intake root directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.intake == mock_repo_root / "import"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_intake_hold_property(mock_repo_root: Path) -> None:
    """Verify intake quarantined holding buffer directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.intake_hold == mock_repo_root / "import" / "hold"


# =============================================================================
# GROUP 4: Production Data Store Path Accessors
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_config_data_property(mock_repo_root: Path) -> None:
    """Verify data directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.data == mock_repo_root / "data"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_archival_records_property(mock_repo_root: Path) -> None:
    """Verify archival records directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.archival_records == mock_repo_root / "data" / "archival_records"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_entities_property(mock_repo_root: Path) -> None:
    """Verify entities directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.entities == mock_repo_root / "data" / "entities"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_quarantine_property(mock_repo_root: Path) -> None:
    """Verify quarantine directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.quarantine == mock_repo_root / "data" / "entities" / "quarantine"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_indexes_property(mock_repo_root: Path) -> None:
    """Verify indexes directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.indexes == mock_repo_root / "data" / "indexes"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_media_property(mock_repo_root: Path) -> None:
    """Verify media directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.media == mock_repo_root / "data" / "media"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_profiles_property(mock_repo_root: Path) -> None:
    """Verify profiles directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.profiles == mock_repo_root / "data" / "profiles"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_reference_property(mock_repo_root: Path) -> None:
    """Verify static reference directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.reference == mock_repo_root / "data" / "reference"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_stories_property(mock_repo_root: Path) -> None:
    """Verify narrative stories directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.stories == mock_repo_root / "data" / "stories"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_transcript_property(mock_repo_root: Path) -> None:
    """Verify full-text transcript directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.transcript == mock_repo_root / "data" / "transcript"


# =============================================================================
# GROUP 5: Schema & Specification Path Accessors
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_config_schemas_property(mock_repo_root: Path) -> None:
    """Verify schemas directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.schemas == mock_repo_root / "schemas"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_schema_defs_property(mock_repo_root: Path) -> None:
    """Verify schema_defs directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.schema_defs == mock_repo_root / "schemas" / "defs"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_schema_entities_property(mock_repo_root: Path) -> None:
    """Verify schema_entities directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.schema_entities == mock_repo_root / "schemas" / "entities"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_schema_indexes_property(mock_repo_root: Path) -> None:
    """Verify schema_indexes directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.schema_indexes == mock_repo_root / "schemas" / "indexes"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_token_registry_property(mock_repo_root: Path) -> None:
    """Verify token_registry specification path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.token_registry == mock_repo_root / "schemas" / "naming" / "_token_registry.json"


# =============================================================================
# GROUP 6: Tooling & Manifest Path Accessors
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_config_tools_property(mock_repo_root: Path) -> None:
    """Verify tools directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.tools == mock_repo_root / "tools"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_tools_ops_property(mock_repo_root: Path) -> None:
    """Verify operational tools directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.tools_ops == mock_repo_root / "tools" / "ops"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_tools_sys_property(mock_repo_root: Path) -> None:
    """Verify system administration tools directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.tools_sys == mock_repo_root / "tools" / "sys"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_tools_lib_property(mock_repo_root: Path) -> None:
    """Verify shared framework libraries directory property path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.tools_lib == mock_repo_root / "tools" / "lib"


@pytest.mark.unit
@pytest.mark.smoke
def test_config_manifest_path_property(mock_repo_root: Path) -> None:
    """Verify manifest_path file path."""
    cfg = GDAConfig(root=mock_repo_root)
    assert cfg.manifest_path == mock_repo_root / "gda_config.json"


# =============================================================================
# GROUP 7: Introspection & Runtime Resilience Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_config_introspectable_help_output(mock_repo_root: Path) -> None:
    """Verify IntrospectableMixin generates documentation directory without errors."""
    cfg = GDAConfig(root=mock_repo_root)
    buffer = io.StringIO()
    with patch("sys.stdout", buffer):
        cfg.help()
    output = buffer.getvalue()
    assert "GDAConfig" in output
    assert "load" in output
    assert "data" in output


@pytest.mark.unit
@pytest.mark.regression
def test_config_module_fallback_on_filenotfound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify module reload executes fallback CONFIG when load raises FileNotFoundError."""
    monkeypatch.delenv("GDA_ROOT", raising=False)
    isolated_dir = tmp_path / "empty_env"
    isolated_dir.mkdir()
    monkeypatch.chdir(isolated_dir)

    orig_exists = Path.exists

    def mock_all_nonexistent(self: Path) -> bool:
        # Deny production mount points, gda_config.json, and .git markers
        if self.name in ("gda_config.json", ".git") or "genealogy-digital-archive" in str(self):
            return False
        return orig_exists(self)

    with patch.object(Path, "exists", autospec=True, side_effect=mock_all_nonexistent):
        reloaded = importlib.reload(config)
        assert reloaded.CONFIG.root == isolated_dir.resolve()

    # Re-establish clean module state
    importlib.reload(config)