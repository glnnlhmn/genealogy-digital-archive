# Name: test_gda_util.py
# Path: tests/unit/test_gda_util.py

import json
import pytest
from pathlib import Path
from tools.lib.gda_core.GDAUtil import GDAUtil


@pytest.fixture
def workspace_setup(tmp_path: Path):
    """Provides an isolated sandbox workspace for file, backup, and temp tests."""
    data_dir = tmp_path / "data"
    backups_dir = tmp_path / "backups"
    temp_dir = tmp_path / "gtemp"

    data_dir.mkdir()
    backups_dir.mkdir()
    temp_dir.mkdir()

    sample_file = data_dir / "records.json"
    sample_file.write_text(json.dumps({"version": 1, "items": ["a", "b"]}), encoding="utf-8")

    return {
        "sample": sample_file,
        "backups": backups_dir,
        "temp": temp_dir,
    }


def test_create_safe_backup_default_timestamp(workspace_setup):
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    bk = GDAUtil.create_safe_backup(sample, backup_dir=b_dir)
    assert bk.exists()
    assert bk.name.startswith("records.json.")
    assert bk.name.endswith(".bk")


def test_create_safe_backup_custom_label(workspace_setup):
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    bk = GDAUtil.create_safe_backup(sample, label="pre_merge_checkpoint", backup_dir=b_dir)
    assert bk.name == "records.json.pre_merge_checkpoint.bk"
    assert bk.exists()


def test_restore_backup_latest(workspace_setup):
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    # Original state
    GDAUtil.create_safe_backup(sample, label="v1", backup_dir=b_dir)

    # Modify file
    sample.write_text(json.dumps({"version": 2}), encoding="utf-8")
    assert json.loads(sample.read_text(encoding="utf-8"))["version"] == 2

    # Restore latest
    restored_bk = GDAUtil.restore_backup(sample, backup_dir=b_dir)
    assert restored_bk.name == "records.json.v1.bk"

    data = json.loads(sample.read_text(encoding="utf-8"))
    assert data["version"] == 1


def test_prune_backups_retention(workspace_setup):
    sample = workspace_setup["sample"]
    b_dir = workspace_setup["backups"]

    # Create 5 labeled backups
    for i in range(1, 6):
        GDAUtil.create_safe_backup(sample, label=f"snap_{i}", backup_dir=b_dir)

    all_bks = GDAUtil.list_backups(sample, backup_dir=b_dir)
    assert len(all_bks) == 5

    # Retain only last 2
    pruned = GDAUtil.prune_backups(sample, keep=2, backup_dir=b_dir)
    assert len(pruned) == 3

    remaining = GDAUtil.list_backups(sample, backup_dir=b_dir)
    assert len(remaining) == 2


def test_json_load_and_atomic_save(workspace_setup):
    dest = workspace_setup["temp"] / "output.json"
    payload = {"records": [1, 2, 3], "status": "active"}

    saved_path = GDAUtil.save_json(dest, payload)
    assert saved_path.exists()

    loaded = GDAUtil.load_json(saved_path)
    assert loaded == payload