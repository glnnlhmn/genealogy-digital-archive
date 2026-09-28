# Name: test_gda_util.py
# Path: tests/unit/test_gda_util.py
# Version: 1.2.1+build.20260927.1

"""Consolidated unit test suite for GDAUtil core utilities.

Operational Role:
    Verifies Safe Backup Protocol handlers, atomic JSON read/write operations,
    canonical display name assembly, hashing, timestamps, quarantine routing,
    and workspace hygiene routines under GDAUtil.

Test Structure & Protocol:
    - Atomized tests: 1:1 mapping of single assertions per test function.
    - Fully decorated: Decorated with @pytest.mark.unit and @pytest.mark.smoke.
    - Dependencies: tmp_path fixture for isolated filesystem sandboxing.
"""

from datetime import datetime
import json
from pathlib import Path
import re
import shutil
from unittest.mock import PropertyMock
import pytest

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDAUtil import GDAUtil


@pytest.fixture
def workspace_setup(tmp_path: Path):
    """Provides an isolated sandbox workspace for file, backup, and temp tests."""
    data_dir = tmp_path / "data"
    backups_dir = tmp_path / "backups"
    temp_dir = tmp_path / "gtemp"
    quarantine_dir = tmp_path / "quarantine"

    data_dir.mkdir()
    backups_dir.mkdir()
    temp_dir.mkdir()
    quarantine_dir.mkdir()

    sample_file = data_dir / "records.json"
    sample_file.write_text(json.dumps({"version": 1, "items": ["a", "b"]}), encoding="utf-8")

    return {
        "sample": sample_file,
        "backups": backups_dir,
        "temp": temp_dir,
        "quarantine": quarantine_dir,
    }


# =============================================================================
# Safe Backup Protocol Tests
# =============================================================================

@pytest.mark.unit
def test_create_safe_backup_default_timestamp_creates_file(workspace_setup):
    """Ensures create_safe_backup generates a backup file on disk."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    bk = GDAUtil.create_safe_backup(sample, backup_dir=b_dir)
    assert bk.exists()


@pytest.mark.unit
def test_create_safe_backup_default_timestamp_prefix(workspace_setup):
    """Ensures create_safe_backup names file starting with target filename."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    bk = GDAUtil.create_safe_backup(sample, backup_dir=b_dir)
    assert bk.name.startswith("records.json.")


@pytest.mark.unit
def test_create_safe_backup_default_timestamp_suffix(workspace_setup):
    """Ensures create_safe_backup names file ending with .bk extension."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    bk = GDAUtil.create_safe_backup(sample, backup_dir=b_dir)
    assert bk.name.endswith(".bk")


@pytest.mark.unit
def test_create_safe_backup_custom_label_exact_name(workspace_setup):
    """Ensures create_safe_backup with a custom label adheres to naming format."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    bk = GDAUtil.create_safe_backup(sample, label="pre_merge_checkpoint", backup_dir=b_dir)
    assert bk.name == "records.json.pre_merge_checkpoint.bk"


@pytest.mark.unit
def test_create_safe_backup_custom_label_exists(workspace_setup):
    """Ensures create_safe_backup with a custom label exists on disk."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    bk = GDAUtil.create_safe_backup(sample, label="pre_merge_checkpoint", backup_dir=b_dir)
    assert bk.exists()


@pytest.mark.unit
def test_create_safe_backup_nonexistent_target_raises_filenotfound(workspace_setup):
    """Ensures create_safe_backup raises FileNotFoundError when source does not exist."""
    missing_file = workspace_setup["sample"].parent / "missing.json"
    b_dir = workspace_setup["backups"]

    with pytest.raises(FileNotFoundError, match="Cannot backup non-existent file"):
        GDAUtil.create_safe_backup(missing_file, backup_dir=b_dir)


@pytest.mark.unit
def test_list_backups_nonexistent_directory_returns_empty_list(workspace_setup):
    """Ensures list_backups returns an empty list when dest_dir does not exist."""
    sample = workspace_setup["sample"]
    missing_dir = workspace_setup["backups"] / "nonexistent_backups_subdir"

    backups = GDAUtil.list_backups(sample, backup_dir=missing_dir)
    assert backups == []


@pytest.mark.unit
def test_restore_backup_latest_restores_correct_backup_path(workspace_setup):
    """Ensures restore_backup returns path of the most recent backup."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    GDAUtil.create_safe_backup(sample, label="v1", backup_dir=b_dir)
    sample.write_text(json.dumps({"version": 2}), encoding="utf-8")

    restored_bk = GDAUtil.restore_backup(sample, backup_dir=b_dir)
    assert restored_bk.name == "records.json.v1.bk"


@pytest.mark.unit
def test_restore_backup_latest_restores_file_content(workspace_setup):
    """Ensures restore_backup overwrites target with original backup content."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    GDAUtil.create_safe_backup(sample, label="v1", backup_dir=b_dir)
    sample.write_text(json.dumps({"version": 2}), encoding="utf-8")

    GDAUtil.restore_backup(sample, backup_dir=b_dir)
    data = json.loads(sample.read_text(encoding="utf-8"))
    assert data["version"] == 1


@pytest.mark.unit
def test_restore_backup_with_explicit_label_restores_file(workspace_setup):
    """Ensures restore_backup targeting a specific label restores that version."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    GDAUtil.create_safe_backup(sample, label="snap_alpha", backup_dir=b_dir)
    sample.write_text(json.dumps({"version": 99}), encoding="utf-8")
    GDAUtil.create_safe_backup(sample, label="snap_beta", backup_dir=b_dir)

    target_backup = GDAUtil.restore_backup(sample, label_or_timestamp="snap_alpha", backup_dir=b_dir)
    assert target_backup.name == "records.json.snap_alpha.bk"


@pytest.mark.unit
def test_restore_backup_missing_label_raises_filenotfound(workspace_setup):
    """Ensures restore_backup raises FileNotFoundError when specified label is not found."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    with pytest.raises(FileNotFoundError, match="Requested backup does not exist"):
        GDAUtil.restore_backup(sample, label_or_timestamp="nonexistent_label", backup_dir=b_dir)


@pytest.mark.unit
def test_restore_backup_empty_backup_dir_raises_filenotfound(workspace_setup):
    """Ensures restore_backup raises FileNotFoundError when no backups exist to restore."""
    sample = workspace_setup["sample"]
    empty_b_dir = workspace_setup["temp"] / "empty_backups"
    empty_b_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="No backups found for"):
        GDAUtil.restore_backup(sample, backup_dir=empty_b_dir)


@pytest.mark.unit
def test_prune_backups_list_count_before_pruning(workspace_setup):
    """Ensures list_backups correctly counts total created backups."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    for i in range(1, 6):
        GDAUtil.create_safe_backup(sample, label=f"snap_{i}", backup_dir=b_dir)

    all_bks = GDAUtil.list_backups(sample, backup_dir=b_dir)
    assert len(all_bks) == 5


@pytest.mark.unit
def test_prune_backups_returns_pruned_list_count(workspace_setup):
    """Ensures prune_backups returns exact list of deleted paths."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    for i in range(1, 6):
        GDAUtil.create_safe_backup(sample, label=f"snap_{i}", backup_dir=b_dir)

    pruned = GDAUtil.prune_backups(sample, keep=2, backup_dir=b_dir)
    assert len(pruned) == 3


@pytest.mark.unit
def test_prune_backups_retains_expected_count(workspace_setup):
    """Ensures prune_backups leaves exactly `keep` backups remaining."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    for i in range(1, 6):
        GDAUtil.create_safe_backup(sample, label=f"snap_{i}", backup_dir=b_dir)

    GDAUtil.prune_backups(sample, keep=2, backup_dir=b_dir)
    remaining = GDAUtil.list_backups(sample, backup_dir=b_dir)
    assert len(remaining) == 2


@pytest.mark.unit
def test_prune_backups_invalid_keep_raises_valueerror(workspace_setup):
    """Ensures prune_backups raises ValueError when keep parameter is less than 1."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    with pytest.raises(ValueError, match="keep parameter must be at least 1"):
        GDAUtil.prune_backups(sample, keep=0, backup_dir=b_dir)


@pytest.mark.unit
def test_prune_backups_fewer_than_keep_leaves_unpruned(workspace_setup):
    """Ensures prune_backups returns an empty list when total backups is <= keep."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    GDAUtil.create_safe_backup(sample, label="snap_1", backup_dir=b_dir)
    pruned = GDAUtil.prune_backups(sample, keep=5, backup_dir=b_dir)
    assert pruned == []


@pytest.mark.unit
def test_prune_backups_handles_oserror_on_unlink(workspace_setup, monkeypatch):
    """Ensures prune_backups suppresses OSError when unlinking a stale backup fails."""
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    for i in range(1, 4):
        GDAUtil.create_safe_backup(sample, label=f"snap_{i}", backup_dir=b_dir)

    def failing_unlink(self):
        raise OSError("Permission denied")

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    pruned = GDAUtil.prune_backups(sample, keep=1, backup_dir=b_dir)
    assert pruned == []


# =============================================================================
# Workspace Hygiene Tests (clear_gtemp)
# =============================================================================

@pytest.mark.unit
def test_clear_gtemp_returns_zero_when_dir_missing(tmp_path, monkeypatch):
    """Ensures clear_gtemp returns 0 when the temp directory does not exist."""
    missing_temp = tmp_path / "nonexistent_temp"
    monkeypatch.setattr(type(CONFIG), "temp", PropertyMock(return_value=missing_temp))
    assert GDAUtil.clear_gtemp() == 0


@pytest.mark.unit
def test_clear_gtemp_deletes_unpreserved_files(workspace_setup, monkeypatch):
    """Ensures clear_gtemp unlinks normal transient files and increments count."""
    temp_dir = workspace_setup["temp"]
    monkeypatch.setattr(type(CONFIG), "temp", PropertyMock(return_value=temp_dir))

    file_a = temp_dir / "temp1.txt"
    file_b = temp_dir / "temp2.json"
    file_a.write_text("a", encoding="utf-8")
    file_b.write_text("{}", encoding="utf-8")

    deleted = GDAUtil.clear_gtemp()
    assert deleted == 2


@pytest.mark.unit
def test_clear_gtemp_removes_unpreserved_files_from_disk(workspace_setup, monkeypatch):
    """Ensures clear_gtemp physically removes unpreserved files from disk."""
    temp_dir = workspace_setup["temp"]
    monkeypatch.setattr(type(CONFIG), "temp", PropertyMock(return_value=temp_dir))

    target_file = temp_dir / "target.tmp"
    target_file.write_text("payload", encoding="utf-8")

    GDAUtil.clear_gtemp()
    assert not target_file.exists()


@pytest.mark.unit
def test_clear_gtemp_deletes_directories_recursively(workspace_setup, monkeypatch):
    """Ensures clear_gtemp removes subdirectories via shutil.rmtree."""
    temp_dir = workspace_setup["temp"]
    monkeypatch.setattr(type(CONFIG), "temp", PropertyMock(return_value=temp_dir))

    sub_dir = temp_dir / "scratch_dir"
    sub_dir.mkdir()
    (sub_dir / "nested.txt").write_text("nested", encoding="utf-8")

    GDAUtil.clear_gtemp()
    assert not sub_dir.exists()


@pytest.mark.unit
def test_clear_gtemp_preserves_default_patterns(workspace_setup, monkeypatch):
    """Ensures clear_gtemp preserves default files (.gitkeep, .gitignore)."""
    temp_dir = workspace_setup["temp"]
    monkeypatch.setattr(type(CONFIG), "temp", PropertyMock(return_value=temp_dir))

    gitkeep = temp_dir / ".gitkeep"
    gitignore = temp_dir / ".gitignore"
    gitkeep.write_text("", encoding="utf-8")
    gitignore.write_text("", encoding="utf-8")

    GDAUtil.clear_gtemp()
    assert gitkeep.exists() and gitignore.exists()


@pytest.mark.unit
def test_clear_gtemp_preserves_custom_patterns(workspace_setup, monkeypatch):
    """Ensures clear_gtemp respects caller-provided preservation lists."""
    temp_dir = workspace_setup["temp"]
    monkeypatch.setattr(type(CONFIG), "temp", PropertyMock(return_value=temp_dir))

    keep_me = temp_dir / "pinned.log"
    keep_me.write_text("data", encoding="utf-8")

    GDAUtil.clear_gtemp(preserve_patterns=["pinned.log"])
    assert keep_me.exists()


@pytest.mark.unit
def test_clear_gtemp_handles_oserror_on_file_deletion(workspace_setup, monkeypatch):
    """Ensures clear_gtemp suppresses OSError when unlinking files fails."""
    temp_dir = workspace_setup["temp"]
    monkeypatch.setattr(type(CONFIG), "temp", PropertyMock(return_value=temp_dir))

    locked_file = temp_dir / "locked.txt"
    locked_file.write_text("locked", encoding="utf-8")

    def failing_unlink(self):
        raise OSError("File locked")

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    deleted = GDAUtil.clear_gtemp()
    assert deleted == 0


@pytest.mark.unit
def test_clear_gtemp_handles_oserror_on_dir_deletion(workspace_setup, monkeypatch):
    """Ensures clear_gtemp suppresses OSError when rmtree fails on a folder."""
    temp_dir = workspace_setup["temp"]
    monkeypatch.setattr(type(CONFIG), "temp", PropertyMock(return_value=temp_dir))

    sub_dir = temp_dir / "locked_dir"
    sub_dir.mkdir()

    def failing_rmtree(path):
        raise OSError("Dir locked")

    monkeypatch.setattr(shutil, "rmtree", failing_rmtree)
    deleted = GDAUtil.clear_gtemp()
    assert deleted == 0


# =============================================================================
# Quarantine Routing Tests
# =============================================================================

@pytest.mark.unit
def test_quarantine_file_nonexistent_source_raises_filenotfound(workspace_setup):
    """Ensures quarantine_file raises FileNotFoundError when source does not exist."""
    missing = workspace_setup["sample"].parent / "ghost.json"
    q_dir = workspace_setup["quarantine"]

    with pytest.raises(FileNotFoundError, match="Cannot quarantine non-existent file"):
        GDAUtil.quarantine_file(missing, quarantine_dir=q_dir)


@pytest.mark.unit
def test_quarantine_file_moves_file_to_destination(workspace_setup):
    """Ensures quarantine_file removes source and creates target in quarantine directory."""
    sample = workspace_setup["sample"]
    q_dir = workspace_setup["quarantine"]

    quarantined_path = GDAUtil.quarantine_file(sample, quarantine_dir=q_dir)
    assert quarantined_path.exists()


@pytest.mark.unit
def test_quarantine_file_removes_original_source(workspace_setup):
    """Ensures quarantine_file unlinks or removes original source file location."""
    sample = workspace_setup["sample"]
    q_dir = workspace_setup["quarantine"]

    GDAUtil.quarantine_file(sample, quarantine_dir=q_dir)
    assert not sample.exists()


# =============================================================================
# Timestamp & Cryptographic Hashing Tests
# =============================================================================

@pytest.mark.unit
def test_iso_now_format_conforms_to_iso8601_utc():
    """Ensures iso_now produces a valid ISO-8601 UTC timestamp format."""
    now_str = GDAUtil.iso_now()
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    assert pattern.match(now_str) is not None


@pytest.mark.unit
def test_compute_sha256_known_payload(workspace_setup):
    """Ensures compute_sha256 calculates expected digest for known payload."""
    test_file = workspace_setup["temp"] / "hash_target.txt"
    test_file.write_bytes(b"test string payload\n")

    expected_hash = "08d389d95f49f4e39aae4f3cfe4ee93b082b36d412ca9abe556d46f15aee0c0b"
    assert GDAUtil.compute_sha256(test_file) == expected_hash


@pytest.mark.unit
def test_compute_sha256_large_file_multi_chunk(workspace_setup):
    """Ensures compute_sha256 processes files larger than the 64 KB read buffer."""
    test_file = workspace_setup["temp"] / "large_file.bin"
    chunk = b"A" * 1024
    test_file.write_bytes(chunk * 70)

    digest = GDAUtil.compute_sha256(test_file)
    assert isinstance(digest, str)
    assert len(digest) == 64


# =============================================================================
# JSON I/O Tests
# =============================================================================

@pytest.mark.unit
def test_json_atomic_save_creates_file(workspace_setup):
    """Ensures save_json successfully creates file on disk."""
    dest = workspace_setup["temp"] / "output.json"
    payload = {"records": [1, 2, 3], "status": "active"}

    saved_path = GDAUtil.save_json(dest, payload)
    assert saved_path.exists()


@pytest.mark.unit
@pytest.mark.smoke
def test_json_load_recovers_saved_payload(workspace_setup):
    """Ensures load_json correctly deserializes payload saved via save_json."""
    dest = workspace_setup["temp"] / "output.json"
    payload = {"records": [1, 2, 3], "status": "active"}

    saved_path = GDAUtil.save_json(dest, payload)
    loaded = GDAUtil.load_json(saved_path)
    assert loaded == payload


# =============================================================================
# Canonical Display Name Assembly Tests
# =============================================================================

@pytest.mark.unit
def test_build_display_name_full_strips_periods():
    """Ensures periods in middle initials and suffixes are strictly stripped."""
    name_obj = {
        "given": "Jacob",
        "middle": "S.",
        "surname": "Lehman",
        "suffix": "Jr."
    }
    assert GDAUtil.build_display_name(name_obj) == "Jacob S Lehman Jr"


@pytest.mark.unit
def test_build_display_name_initial_given():
    """Ensures leading initials strip periods and retain proper spacing."""
    name_obj = {
        "given": "D.",
        "middle": "Smiley",
        "surname": "Lehman"
    }
    assert GDAUtil.build_display_name(name_obj) == "D Smiley Lehman"


@pytest.mark.unit
def test_build_display_name_no_middle_or_suffix():
    """Ensures given and surname are assembled cleanly when middle/suffix absent."""
    name_obj = {
        "given": "Anna",
        "surname": "Baer"
    }
    assert GDAUtil.build_display_name(name_obj) == "Anna Baer"


@pytest.mark.unit
def test_build_display_name_raw_fallback():
    """Ensures raw_name fallback is used and stripped of periods if parts absent."""
    name_obj = {
        "raw_name": "Old Uncle Jacob.",
        "given": None,
        "surname": None
    }
    assert GDAUtil.build_display_name(name_obj) == "Old Uncle Jacob"


@pytest.mark.unit
def test_build_display_name_none_input():
    """Ensures None input yields 'UNKNOWN' fallback."""
    assert GDAUtil.build_display_name(None) == "UNKNOWN"


@pytest.mark.unit
def test_build_display_name_empty_dict():
    """Ensures empty dictionary yields 'UNKNOWN' fallback."""
    assert GDAUtil.build_display_name({}) == "UNKNOWN"