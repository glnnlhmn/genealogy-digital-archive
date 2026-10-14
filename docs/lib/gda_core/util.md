<!--
Name: util.md
Path: docs/lib/gda_core/util.md
-->
# Technical Specification: GDAUtil (Core Archive Utilities)
<!-- Version: 1.1.0+build.20260930.1 -->

| Property | Value |
| :--- | :--- |
| **Module Name** | `util.py` |
| **Module Path** | `tools/lib/gda_core/util.py` |
| **Version** | `1.1.0+build.20260930.3` |
| **Test Suite** | `tests/gda_core/test_util.py` |
| **Package** | `tools.lib.gda_core` |
| **Dependencies** | `hashlib`, `json`, `pathlib`, `re`, `shutil`, `datetime` |

## 1. Developer Reference & API Specification

### Operational Intent
`GDAUtil` centralizes repository filesystem safeguards, transactional backup management, workspace hygiene, cryptographic hashing, and atomic UTF-8 JSON I/O routines.

### Core API Methods

* `create_safe_backup(target_file: Union[Path, str], label: Optional[str] = None, backup_dir: Optional[Path] = None) -> Path`
  * Creates an atomic pre-write snapshot named `[filename].[YYYYMMDD_HHMMSS].bk` inside `backups/`.
  * Raises `FileNotFoundError` if `target_file` does not exist.
* `list_backups(target_file: Union[Path, str], backup_dir: Optional[Path] = None) -> List[Path]`
  * Returns list of existing backup files ordered descending by modification time (newest first).
* `restore_backup(target_file: Union[Path, str], label_or_timestamp: Optional[str] = None, backup_dir: Optional[Path] = None) -> Path`
  * Overwrites `target_file` with the specified snapshot token, or defaults to the most recent backup.
* `prune_backups(target_file: Union[Path, str], keep: int = 5, backup_dir: Optional[Path] = None) -> List[Path]`
  * Retains the newest `keep` backups and unlinks older snapshots.
* `save_json(file_path: Union[Path, str], data: Any, indent: int = 2, create_backup: bool = False, backup_dir: Optional[Path] = None) -> Path`
  * Serializes JSON data to a `.tmp` file and atomically replaces destination file using `os.replace`.
  * Automatically creates parent directories; optionally triggers `create_safe_backup` prior to overwrite.
* `load_json(file_path: Union[Path, str]) -> Any`
  * Reads and deserializes JSON files supporting both standard UTF-8 and UTF-8 with BOM (`utf-8-sig`).
* `compute_sha256(file_path: Union[Path, str]) -> str`
  * Computes cryptographic SHA-256 digest using 64 KB block streaming.
* `quarantine_file(source_path: Union[Path, str], quarantine_dir: Optional[Path] = None) -> Path`
  * Relocates invalid, corrupted, or non-conforming payloads to `data/entities/quarantine/`.
* `clear_gtemp(preserve_patterns: Optional[List[str]] = None) -> int`
  * Cleans scratch files and directories from `gtemp/`, strictly preserving `.gitkeep` and `.gitignore`.