# Name: test_gda_util.py
# Path: tests/unit/test_gda_util.py
# Version: 1.0.5+build.20260929.1

"""Unit test suite verifying GDAUtil framework utility methods.

Operational Role:
    Validates atomic JSON I/O, unified pre-write safe backup creation,
    backup rotation and pruning, rollback restoration, SHA-256 calculation,
    and display name formatting.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly marked with @pytest.mark.unit.
    - Dependencies: Hermetic tmp_path sandboxes without production disk I/O.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import pytest
from tools.lib.gda_core.GDAUtil import GDAUtil


@pytest.mark.unit
def test_gda_util_save_json_atomic(tmp_path: Path) -> None:
    """Verifies save_json serializes JSON payloads atomically to disk."""
    target_file = tmp_path / "sample.json"
    data = {"status": "active", "count": 42}
    result_path = GDAUtil.save_json(target_file, data)
    assert result_path == target_file
    assert result_path.exists()
    loaded = GDAUtil.load_json(target_file)
    assert loaded == data


@pytest.mark.unit
def test_gda_util_save_json_skip_backup_when_not_requested(tmp_path: Path) -> None:
    """Verifies save_json does not create a backup when create_backup is False."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "entity.json"
    GDAUtil.save_json(target_file, {"version": 1})
    GDAUtil.save_json(target_file, {"version": 2}, create_backup=False, backup_dir=backup_dir)
    assert not backup_dir.exists()


@pytest.mark.unit
def test_gda_util_save_json_skip_backup_for_new_file(tmp_path: Path) -> None:
    """Verifies save_json skips backup creation if target file does not yet exist on disk."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "brand_new.json"
    GDAUtil.save_json(target_file, {"initial": True}, create_backup=True, backup_dir=backup_dir)
    assert target_file.exists()
    backups = GDAUtil.list_backups(target_file, backup_dir=backup_dir)
    assert len(backups) == 0


@pytest.mark.unit
def test_gda_util_save_json_creates_backup_when_file_exists(tmp_path: Path) -> None:
    """Verifies save_json executes a safe backup prior to overwriting an existing file."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "sites.json"
    GDAUtil.save_json(target_file, {"state": "original"}, create_backup=False)
    GDAUtil.save_json(target_file, {"state": "mutated"}, create_backup=True, backup_dir=backup_dir)
    backups = GDAUtil.list_backups(target_file, backup_dir=backup_dir)
    assert len(backups) == 1
    backed_up_data = GDAUtil.load_json(backups[0])
    assert backed_up_data == {"state": "original"}


@pytest.mark.unit
def test_gda_util_create_safe_backup_missing_file_raises(tmp_path: Path) -> None:
    """Verifies create_safe_backup raises FileNotFoundError when target does not exist."""
    missing_file = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError, match="Cannot backup non-existent file"):
        GDAUtil.create_safe_backup(missing_file)


@pytest.mark.unit
def test_gda_util_create_safe_backup_with_label(tmp_path: Path) -> None:
    """Verifies create_safe_backup accepts a custom label token in the filename."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "registry.json"
    GDAUtil.save_json(target_file, {"data": True})
    backup_path = GDAUtil.create_safe_backup(target_file, label="pre_ingest", backup_dir=backup_dir)
    assert backup_path.name == "registry.json.pre_ingest.bk"
    assert backup_path.exists()


@pytest.mark.unit
def test_gda_util_list_backups_sorted_chronological(tmp_path: Path) -> None:
    """Verifies list_backups returns snapshots ordered newest to oldest."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "test.json"
    GDAUtil.save_json(target_file, {"v": 0})
    b1 = GDAUtil.create_safe_backup(target_file, label="snap_1", backup_dir=backup_dir)
    b2 = GDAUtil.create_safe_backup(target_file, label="snap_2", backup_dir=backup_dir)
    
    now = datetime.now(timezone.utc).timestamp()
    os.utime(b1, (now - 300, now - 300))
    os.utime(b2, (now - 100, now - 100))
    
    backups = GDAUtil.list_backups(target_file, backup_dir=backup_dir)
    assert backups[0].name == b2.name
    assert backups[1].name == b1.name


@pytest.mark.unit
def test_gda_util_restore_backup_most_recent(tmp_path: Path) -> None:
    """Verifies restore_backup restores the latest backup when label is omitted."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "config.json"
    GDAUtil.save_json(target_file, {"step": 1})
    b1 = GDAUtil.create_safe_backup(target_file, label="first", backup_dir=backup_dir)
    GDAUtil.save_json(target_file, {"step": 2})
    b2 = GDAUtil.create_safe_backup(target_file, label="second", backup_dir=backup_dir)
    
    now = datetime.now(timezone.utc).timestamp()
    os.utime(b1, (now - 300, now - 300))
    os.utime(b2, (now - 100, now - 100))
    
    GDAUtil.save_json(target_file, {"step": "corrupted"})
    GDAUtil.restore_backup(target_file, backup_dir=backup_dir)
    restored = GDAUtil.load_json(target_file)
    assert restored == {"step": 2}


@pytest.mark.unit
def test_gda_util_restore_backup_specific_label(tmp_path: Path) -> None:
    """Verifies restore_backup restores a targeted snapshot by label token."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "locations.json"
    GDAUtil.save_json(target_file, {"version": "golden"})
    GDAUtil.create_safe_backup(target_file, label="golden_tag", backup_dir=backup_dir)
    GDAUtil.save_json(target_file, {"version": "dirty"})
    GDAUtil.restore_backup(target_file, label_or_timestamp="golden_tag", backup_dir=backup_dir)
    restored = GDAUtil.load_json(target_file)
    assert restored == {"version": "golden"}


@pytest.mark.unit
def test_gda_util_prune_backups_retention_limit(tmp_path: Path) -> None:
    """Verifies prune_backups removes older snapshots exceeding retention limit."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "archive.json"
    GDAUtil.save_json(target_file, {"seed": True})
    now = datetime.now(timezone.utc).timestamp()
    for idx in range(5):
        b = GDAUtil.create_safe_backup(target_file, label=f"snap_{idx}", backup_dir=backup_dir)
        ts = now - (500 - idx * 100)
        os.utime(b, (ts, ts))
    pruned = GDAUtil.prune_backups(target_file, keep=2, backup_dir=backup_dir)
    assert len(pruned) == 3
    remaining = GDAUtil.list_backups(target_file, backup_dir=backup_dir)
    assert len(remaining) == 2


@pytest.mark.unit
def test_gda_util_compute_sha256(tmp_path: Path) -> None:
    """Verifies compute_sha256 calculates accurate cryptographic hash across raw bytes."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"Genealogy Digital Archive")
    expected_hash = "cf38f6bcbce5a530e1dc71e8bed91337cf80fdffc0a7dcc74c208c0bec058519"
    calculated = GDAUtil.compute_sha256(test_file)
    assert calculated == expected_hash


@pytest.mark.unit
def test_gda_util_build_display_name_strips_periods() -> None:
    """Verifies build_display_name strips all periods and collapses whitespace."""
    canonical = {
        "given": "Daniel",
        "middle": "W.",
        "surname": "Lehman",
        "suffix": "Jr.",
    }
    result = GDAUtil.build_display_name(canonical)
    assert result == "Daniel W Lehman Jr"