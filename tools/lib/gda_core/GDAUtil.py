# Name: GDAUtil.py
# Path: tools/lib/gda_core/GDAUtil.py

import hashlib
import json
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone
from typing import Any, List, Optional, Union

from tools.lib.gda_core.GDAConfig import CONFIG

__version__ = "1.0.1+build.20260922.1"


class GDAUtil:
    """Centralized core utilities.

    Provides Safe Backup Protocol handlers, cryptographic hashing,
    standardized timestamps, quarantine routing, rollback management,
    workspace hygiene, and UTF-8 JSON I/O.
    """

    BACKUP_PATTERN = re.compile(r"^(.+?)\.(.+?)\.bk$")

    # -------------------------------------------------------------------------
    # Safe Backup Protocol Handlers
    # -------------------------------------------------------------------------
    @classmethod
    def create_safe_backup(
        cls,
        target_file: Union[Path, str],
        label: Optional[str] = None,
        backup_dir: Optional[Path] = None,
    ) -> Path:
        """Creates an atomic pre-execution backup copy of target_file.

        Naming format:
          - Default: [filename].[YYYYMMDD_HHMMSS].bk
          - Custom:  [filename].[label].bk (if label is provided)
        """
        source = Path(target_file).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Cannot backup non-existent file: {source}")

        dest_dir = backup_dir or CONFIG.backups
        dest_dir.mkdir(parents=True, exist_ok=True)

        token = label.strip() if label else datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{source.name}.{token}.bk"
        backup_path = dest_dir / backup_filename

        shutil.copy2(source, backup_path)
        return backup_path

    @classmethod
    def list_backups(
        cls,
        target_file: Union[Path, str],
        backup_dir: Optional[Path] = None,
    ) -> List[Path]:
        """Lists all available backups for a given file, sorted newest to oldest."""
        source_name = Path(target_file).name
        dest_dir = backup_dir or CONFIG.backups

        if not dest_dir.exists():
            return []

        backups = [
            f for f in dest_dir.glob(f"{source_name}.*.bk")
            if f.is_file() and cls.BACKUP_PATTERN.match(f.name)
        ]
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups

    @classmethod
    def restore_backup(
        cls,
        target_file: Union[Path, str],
        label_or_timestamp: Optional[str] = None,
        backup_dir: Optional[Path] = None,
    ) -> Path:
        """Restores target_file from a backup.

        If label_or_timestamp is None, restores the most recent backup.
        """
        source = Path(target_file).resolve()
        dest_dir = backup_dir or CONFIG.backups

        if label_or_timestamp:
            backup_candidate = dest_dir / f"{source.name}.{label_or_timestamp}.bk"
            if not backup_candidate.exists():
                raise FileNotFoundError(f"Requested backup does not exist: {backup_candidate}")
            target_backup = backup_candidate
        else:
            backups = cls.list_backups(source, backup_dir=dest_dir)
            if not backups:
                raise FileNotFoundError(f"No backups found for: {source.name} in {dest_dir}")
            target_backup = backups[0]

        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_backup, source)
        return target_backup

    @classmethod
    def prune_backups(
        cls,
        target_file: Union[Path, str],
        keep: int = 5,
        backup_dir: Optional[Path] = None,
    ) -> List[Path]:
        """Retains the most recent `keep` backups for target_file and removes older ones."""
        if keep < 1:
            raise ValueError(f"keep parameter must be at least 1, got {keep}")

        backups = cls.list_backups(target_file, backup_dir=backup_dir)
        pruned: List[Path] = []

        if len(backups) > keep:
            for stale_backup in backups[keep:]:
                try:
                    stale_backup.unlink()
                    pruned.append(stale_backup)
                except OSError:
                    pass

        return pruned

    # -------------------------------------------------------------------------
    # Workspace Hygiene & Quarantine Routing
    # -------------------------------------------------------------------------
    @classmethod
    def clear_gtemp(cls, preserve_patterns: Optional[List[str]] = None) -> int:
        """Safely clears transient scratch files from CONFIG.temp (gtemp/)."""
        temp_dir = CONFIG.temp
        if not temp_dir.exists():
            return 0

        preserve = set(preserve_patterns or [".gitkeep", ".gitignore"])
        deleted_count = 0

        for item in temp_dir.iterdir():
            if item.name in preserve:
                continue
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                deleted_count += 1
            except OSError:
                pass

        return deleted_count

    @classmethod
    def quarantine_file(
        cls,
        source_path: Union[Path, str],
        quarantine_dir: Optional[Path] = None,
    ) -> Path:
        """Safely moves a non-conforming or unverified entity file into quarantine.

        Defaults to CONFIG.quarantine (data/entities/quarantine/).
        """
        source = Path(source_path).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Cannot quarantine non-existent file: {source}")

        dest_dir = quarantine_dir or CONFIG.quarantine
        dest_dir.mkdir(parents=True, exist_ok=True)

        target_dest = dest_dir / source.name
        shutil.move(str(source), str(target_dest))
        return target_dest

    # -------------------------------------------------------------------------
    # Timestamp & Hash Utilities
    # -------------------------------------------------------------------------
    @classmethod
    def iso_now(cls) -> str:
        """Returns the current UTC timestamp formatted as ISO-8601 (e.g.

        '2026-09-22T11:05:00Z').
        """
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def compute_sha256(cls, file_path: Union[Path, str]) -> str:
        """Computes the SHA-256 cryptographic hash of a target file using 64 KB blocks."""
        path = Path(file_path).resolve()
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    # -------------------------------------------------------------------------
    # Standard UTF-8 JSON I/O
    # -------------------------------------------------------------------------
    @classmethod
    def load_json(cls, file_path: Union[Path, str]) -> Any:
        """Reads and parses a UTF-8 encoded JSON file (supporting utf-8-sig)."""
        path = Path(file_path).resolve()
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    @classmethod
    def save_json(cls, file_path: Union[Path, str], data: Any, indent: int = 2) -> Path:
        """Writes data to a UTF-8 encoded JSON file with atomic write protection."""
        path = Path(file_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        temp_dest = path.with_suffix(f"{path.suffix}.tmp")
        with open(temp_dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.write("\n")
        temp_dest.replace(path)
        return path