<!--
Name: GDAUtil.md
Path: docs/lib/gda_core/GDAUtil.md
-->
# Technical Specification: GDAUtil (Core Archive Utilities)

| Property | Value |
| :--- | :--- |
| **Module Name** | `GDAUtil.py` |
| **Module Path** | `tools/lib/gda_core/GDAUtil.py` |
| **Version** | `1.0.2+build.20260922.2` |
| **Test Suite** | `tests/unit/test_gda_util.py` |
| **Package** | `tools.lib.gda_core` |
| **Dependencies** | `GDAConfig`, `hashlib`, `json`, `pathlib`, `re`, `shutil`, `datetime` |

---

## 1. Developer Reference & API Specification

### Operational Intent
`GDAUtil` provides centralized, static and class-level core utility methods supporting repository-wide infrastructure. It guarantees transactional filesystem safety via the Safe Backup Protocol, standardizes ISO-8601 UTC timestamps, implements deterministic SHA-256 cryptographic chunked hashing, enforces atomic UTF-8 JSON I/O, isolates unverified entity payloads via quarantine routing, and cleans transient scratch workspaces.

### Core API Methods

#### Safe Backup Protocol Handlers
* `create_safe_backup(target_file: Union[Path, str], label: Optional[str] = None, backup_dir: Optional[Path] = None) -> Path`
  * Creates an atomic pre-execution snapshot in `backups/` (or caller-supplied `backup_dir`).
  * Filename structure: `[filename].[YYYYMMDD_HHMMSS].bk` or `[filename].[label].bk`.
  * Raises `FileNotFoundError` if the target source does not exist.
* `list_backups(target_file: Union[Path, str], backup_dir: Optional[Path] = None) -> List[Path]`
  * Discovers all backup files matching `^(.+?)\.(.+?)\.bk$` for the target file.
  * Returns paths sorted descending by modification time (newest to oldest). Returns `[]` if directory is missing.
* `restore_backup(target_file: Union[Path, str], label_or_timestamp: Optional[str] = None, backup_dir: Optional[Path] = None) -> Path`
  * Overwrites `target_file` using the specified snapshot label or defaults to the latest backup.
  * Raises `FileNotFoundError` if the specified candidate does not exist or if no backups exist.
* `prune_backups(target_file: Union[Path, str], keep: int = 5, backup_dir: Optional[Path] = None) -> List[Path]`
  * Retains the newest `keep` backups and unlinks older files.
  * Raises `ValueError` if `keep < 1`. Silently ignores OS-level unlinking errors. Returns list of deleted paths.

#### Workspace Hygiene & Quarantine Routing
* `clear_gtemp(preserve_patterns: Optional[List[str]] = None) -> int`
  * Purges transient scratch files and directories from `CONFIG.temp` (`gtemp/`).
  * Preserves `.gitkeep` and `.gitignore` by default, alongside optional custom filenames.
  * Recursively removes subdirectories using `shutil.rmtree` and deletes loose files. Returns count of deleted items.
* `quarantine_file(source_path: Union[Path, str], quarantine_dir: Optional[Path] = None) -> Path`
  * Atomically relocates non-conforming, corrupted, or unverified payload files into `CONFIG.quarantine` (`data/entities/quarantine/`).
  * Raises `FileNotFoundError` if `source_path` does not exist.

#### Timestamp & Hashing Routines
* `iso_now() -> str`
  * Generates the current UTC timestamp formatted strictly to ISO-8601 UTC (`%Y-%m-%dT%H:%M:%SZ`, e.g., `2026-09-27T20:42:00Z`).
* `compute_sha256(file_path: Union[Path, str]) -> str`
  * Computes the hex digest of the target file using 64 KB chunk buffered reads to prevent memory exhaustion on large media/records.

#### Standard UTF-8 JSON I/O
* `load_json(file_path: Union[Path, str]) -> Any`
  * Reads and parses UTF-8 JSON files, natively supporting Byte Order Marks (`utf-8-sig`).
* `save_json(file_path: Union[Path, str], data: Any, indent: int = 2) -> Path`
  * Atomically writes JSON data via a temporary file swap (`.tmp` to target destination) with trailing newline and `ensure_ascii=False`.

#### Canonical Identity Utilities
* `build_display_name(canonical_name: Optional[dict]) -> str`
  * Constructs a normalized display string in `given + middle + surname + suffix` order.
  * Strictly strips all periods from initials and suffixes (e.g., `Jacob S. Lehman Jr.` becomes `Jacob S Lehman Jr`).
  * Falls back to `raw_name` when structured components are absent, or `"UNKNOWN"` if missing.

---

## 2. Technical Architecture & Invariants

### Safe Backup Protocol Integration
Operational tools executing write or consolidation workflows (`facts_merge.py`, `gpi.py`, `gfi.py`, `gsi.py`) invoke `GDAUtil.create_safe_backup()` prior to modifying entities. The backup snapshot preserves the pre-mutation baseline on disk, allowing immediate zero-data-loss rollback via `GDAUtil.restore_backup()`.

### Atomic JSON Replacement Mechanics
To prevent file corruption during execution interruptions, power loss, or write failures, `GDAUtil.save_json` never performs in-place writes on live files:
1. Resolves destination path and creates missing parent folders.
2. Writes formatted JSON to a transient sibling (`<filename>.tmp`).
3. Uses atomic filesystem replacement (`Path.replace()`) to swap the temporary file over the target destination.

### Workspace Isolation Policy
Transient analysis scripts, intermediate data dumps, and debug outputs reside in `gtemp/`. `GDAUtil.clear_gtemp()` serves as the automated sweeper across batch pipelines, maintaining repository hygiene while strictly protecting repository control anchors (`.gitkeep`).

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/unit/test_gda_util.py`
* **Coverage Scope:** 100% atomized coverage of Safe Backup handlers, pruning error cascades, `clear_gtemp` recursion and pattern filters, quarantine unlinking, SHA-256 block reading, and display name normalization.
* **Execution:**
```powershell
# Fast unit validation
pytest -m unit tests/unit/test_gda_util.py -v

# Verification with coverage metrics
pytest tests/unit/test_gda_util.py --cov=tools.lib.gda_core.GDAUtil --cov-report=term-missing
```

### Diagnostic Matrix

| Diagnostic / Error Signature | Root Cause & Resolution |
| :--- | :--- |
| `FileNotFoundError: Cannot backup non-existent file` | The source file path passed to `create_safe_backup()` does not exist on disk. Validate file existence prior to calling. |
| `FileNotFoundError: Requested backup does not exist` | The specified label or timestamp candidate is absent from the backup store. Verify backup listing before restoring. |
| `FileNotFoundError: No backups found for [file]` | Attempted to restore the latest backup from an empty backup directory. |
| `ValueError: keep parameter must be at least 1` | Retention count passed to `prune_backups()` is less than 1. Provide an integer >= 1. |
| `FileNotFoundError: Cannot quarantine non-existent file` | Source file to quarantine does not exist at the specified path. |
