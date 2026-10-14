# Name: util.py
# Path: tools/lib/gdacore/src/gdacore/util.py
# Version: 1.0.0+build.rc1

"""Provide centralized archive utility functions, note primitives, and filesystem safeguards.

Provides Safe Backup Protocol handlers, cryptographic hashing, standardized
timestamps, quarantine routing, workspace hygiene, atomic UTF-8 JSON I/O,
sequential numeric sequence discovery, graveyard redirect resolution,
multi-field fuzzy matching, string slugification, byte size formatting,
and memory-isolated entity note collection management.
"""

from __future__ import annotations

__version__ = "1.0.0+build.rc1"

from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
import unicodedata
from typing import Any

from gdacore import config
from gdacore.introspectable import IntrospectableMixin


@dataclass
class GDANote:
    """Represent an archival entity note record with structural isolation.

    Enforces the exact 4-key structural contract required across domain stores:
    note_id, note_type, note_text, and modified_date.

    Attributes:
        note_id: Sequential scoped identifier (e.g., 'NOT-00001').
        note_type: Categorical classification token (e.g., 'RESEARCH').
        note_text: Primary textual note narrative.
        modified_date: ISO-8601 UTC timestamp of creation or last modification.
    """

    note_id: str
    note_type: str
    note_text: str
    modified_date: str

    def to_dict(self) -> dict[str, str]:
        """Serialize note instance into a pure 4-key Python dictionary.

        Returns:
            Dictionary containing note_id, note_type, note_text, and modified_date.
        """
        return {
            "note_id": self.note_id,
            "note_type": self.note_type,
            "note_text": self.note_text,
            "modified_date": self.modified_date,
        }


class GDANoteCollection(Sequence[GDANote]):
    """Manage memory-isolated collection governing entity note records.

    Maintains canonical 4-key note schemas, sequential auto-minting of note
    identifiers (e.g., 'NOT-00001'), vocabulary validation, in-memory CRUD operations,
    and automatic sequence renumbering upon removal while preserving timestamps.
    Operates strictly in memory with zero disk persistence side effects.
    """

    NOTE_ID_PATTERN: re.Pattern[str] = re.compile(r"^NOT-(\d{5})$")

    def __init__(
        self,
        notes_data: Sequence[dict[str, Any]] | Mapping[str, Any] | None = None,
        valid_types: Collection[str] | None = None,
    ) -> None:
        """Initialize collection from raw note records or parent entity dictionary.

        Args:
            notes_data: Sequence of note dictionaries or parent entity dict containing
                an optional 'notes' list key. If None, initializes empty.
            valid_types: Optional collection of approved note types
                (e.g., {'RESEARCH', 'TRANSCRIPTION', 'DISCREPANCY'}).

        Raises:
            ValueError: If an ingested note violates controlled vocabulary rules.
        """
        self._valid_types: set[str] | None = set(valid_types) if valid_types is not None else None
        self._notes: list[GDANote] = []

        raw_list: Sequence[Any] = []
        if isinstance(notes_data, Mapping):
            raw_list = notes_data.get("notes", []) or []
        elif isinstance(notes_data, Sequence) and not isinstance(notes_data, (str, bytes)):
            raw_list = notes_data

        if raw_list:
            self._load_notes(raw_list)

    def _load_notes(self, raw_list: Sequence[Any]) -> None:
        """Parse and validate raw note dictionaries into internal GDANote instances.

        Args:
            raw_list: Raw sequence of note candidate dictionaries.

        Raises:
            ValueError: If note_type is unapproved against active vocabulary.
        """
        for item in raw_list:
            if not isinstance(item, Mapping):
                continue
            item_copy = copy.deepcopy(dict(item))
            note_type = str(item_copy.get("note_type", "RESEARCH")).strip()
            if self._valid_types is not None and note_type not in self._valid_types:
                raise ValueError(
                    f"Invalid note_type '{note_type}'. Allowed types: {sorted(self._valid_types)}"
                )

            note_id = str(item_copy.get("note_id", "")).strip()
            note_text = str(item_copy.get("note_text") or item_copy.get("text") or "").strip()
            modified_date = str(
                item_copy.get("modified_date") or item_copy.get("created_at") or GDAUtil.iso_now()
            ).strip()

            self._notes.append(
                GDANote(
                    note_id=note_id,
                    note_type=note_type,
                    note_text=note_text,
                    modified_date=modified_date,
                )
            )

        # Ensure active sequence aligns to consecutive high-water mark if unassigned
        for idx, note in enumerate(self._notes, start=1):
            if not self.NOTE_ID_PATTERN.match(note.note_id):
                note.note_id = f"NOT-{idx:05d}"

    def __len__(self) -> int:
        """Return the count of active notes in the collection."""
        return len(self._notes)

    def __iter__(self) -> Iterator[GDANote]:
        """Yield isolated deep copies of GDANote instances."""
        for note in self._notes:
            yield copy.deepcopy(note)

    def __getitem__(self, index: int | slice) -> Any:
        """Retrieve a note or slice of notes as isolated deep copies.

        Args:
            index: Integer sequence index or slice.

        Returns:
            Deep copy of GDANote instance or list of GDANote instances.
        """
        if isinstance(index, slice):
            return [copy.deepcopy(note) for note in self._notes[index]]
        return copy.deepcopy(self._notes[index])

    def __contains__(self, item: Any) -> bool:
        """Check if a note or note identifier is present in collection."""
        if isinstance(item, str):
            return any(note.note_id == item for note in self._notes)
        if isinstance(item, GDANote):
            return any(note.note_id == item.note_id for note in self._notes)
        return False

    def mint_next_id(self) -> str:
        """Calculate and allocate the next sequential scoped note identifier.

        Returns:
            Formatted identifier string (e.g., 'NOT-00001').
        """
        raw_ids = [n.note_id for n in self._notes]
        max_val = GDAUtil.find_max_numeric_id(raw_ids)
        return f"NOT-{max_val + 1:05d}"

    def get(self, note_id: str) -> GDANote | None:
        """Retrieve a specific note by canonical note ID.

        Args:
            note_id: Scoped note identifier (e.g., 'NOT-00001').

        Returns:
            Deep copy of GDANote instance if matched; None otherwise.
        """
        for note in self._notes:
            if note.note_id == note_id:
                return copy.deepcopy(note)
        return None

    def add(
        self,
        note_text: str,
        note_type: str = "RESEARCH",
        modified_date: str | None = None,
    ) -> GDANote:
        """Add a single note to the collection with sequential ID minting.

        Args:
            note_text: Primary textual note narrative. Must not be empty.
            note_type: Categorical classification. Defaults to 'RESEARCH'.
            modified_date: Optional ISO-8601 UTC timestamp override; defaults to now.

        Returns:
            Newly created and appended GDANote instance.

        Raises:
            ValueError: If note_text is empty or note_type is invalid.
        """
        stripped_text = note_text.strip() if note_text else ""
        if not stripped_text:
            raise ValueError("Note text cannot be empty or whitespace.")

        cleaned_type = note_type.strip() if note_type else "RESEARCH"
        if self._valid_types is not None and cleaned_type not in self._valid_types:
            raise ValueError(
                f"Invalid note_type '{cleaned_type}'. Allowed types: {sorted(self._valid_types)}"
            )

        new_id = self.mint_next_id()
        stamp = modified_date or GDAUtil.iso_now()
        new_note = GDANote(
            note_id=new_id,
            note_type=cleaned_type,
            note_text=stripped_text,
            modified_date=stamp,
        )
        self._notes.append(new_note)
        return copy.deepcopy(new_note)

    def add_many(self, notes: Iterable[Mapping[str, Any]]) -> list[str]:
        """Batch append notes from an iterable of dictionaries.

        Args:
            notes: Iterable of note dictionaries containing note_text/text
                and optional note_type / modified_date.

        Returns:
            List of newly minted note_id strings in order of addition.

        Raises:
            ValueError: If any entry contains empty text or invalid note_type.
        """
        minted_ids: list[str] = []
        for entry in notes:
            if not isinstance(entry, Mapping):
                continue
            text = entry.get("note_text") or entry.get("text") or ""
            n_type = entry.get("note_type", "RESEARCH")
            m_date = entry.get("modified_date") or entry.get("created_at")
            created_note = self.add(note_text=str(text), note_type=str(n_type), modified_date=m_date)
            minted_ids.append(created_note.note_id)
        return minted_ids

    def update(
        self,
        note_id: str,
        note_text: str | None = None,
        note_type: str | None = None,
    ) -> bool:
        """Update an existing note in-place with an automated UTC modification timestamp.

        Args:
            note_id: Target identifier to mutate.
            note_text: Optional updated textual content.
            note_type: Optional updated classification token.

        Returns:
            True if the target note was found and modified; False otherwise.

        Raises:
            ValueError: If note_text is whitespace or note_type fails validation.
        """
        for note in self._notes:
            if note.note_id == note_id:
                if note_text is not None:
                    stripped = note_text.strip()
                    if not stripped:
                        raise ValueError("Updated note text cannot be empty or whitespace.")
                    note.note_text = stripped

                if note_type is not None:
                    cleaned_type = note_type.strip()
                    if self._valid_types is not None and cleaned_type not in self._valid_types:
                        raise ValueError(
                            f"Invalid note_type '{cleaned_type}'. Allowed types: {sorted(self._valid_types)}"
                        )
                    note.note_type = cleaned_type

                note.modified_date = GDAUtil.iso_now()
                return True
        return False

    def remove(self, note_id: str) -> bool:
        """Remove a note by note_id and renumber remaining notes consecutively.

        Existing modified_date timestamps are strictly preserved across renumbering.

        Args:
            note_id: Target identifier to excise.

        Returns:
            True if note was found, removed, and collection renumbered; False otherwise.
        """
        target_idx: int | None = None
        for idx, note in enumerate(self._notes):
            if note.note_id == note_id:
                target_idx = idx
                break

        if target_idx is None:
            return False

        del self._notes[target_idx]
        self._renumber()
        return True

    def _renumber(self) -> None:
        """Renumber all notes sequentially (NOT-00001..N) preserving modified_date."""
        for idx, note in enumerate(self._notes, start=1):
            note.note_id = f"NOT-{idx:05d}"

    def to_list(self) -> list[dict[str, str]]:
        """Export collection as an isolated list of pure 4-key note dictionaries.

        Returns:
            Deep-copied list of canonical note dictionaries.
        """
        return [note.to_dict() for note in self._notes]


class GDAUtil(IntrospectableMixin):
    """Centralize core utilities and filesystem safeguards for the archive framework."""

    BACKUP_PATTERN: re.Pattern[str] = re.compile(r"^(.+?)\.(.+?)\.bk$")
    TRAILING_DIGIT_PATTERN: re.Pattern[str] = re.compile(r"(\d+)$")

    # -------------------------------------------------------------------------
    # Identifier, Redirection & Search Primitives
    # -------------------------------------------------------------------------
    @classmethod
    def find_max_numeric_id(cls, id_list: Sequence[str] | Any) -> int:
        """Extract the numeric high-water mark sequence from a list of ID strings.

        Parses hyphen-delimited suffixes or trailing numeric digit tokens.

        Args:
            id_list: Sequence of raw identifier strings.

        Returns:
            Highest integer sequence discovered, or 0 if empty or invalid.
        """
        if not isinstance(id_list, Sequence) or isinstance(id_list, (str, bytes)) or not id_list:
            return 0

        max_val = 0
        for item in id_list:
            if not isinstance(item, str):
                continue

            val = 0
            if "-" in item:
                token = item.split("-")[-1].strip()
                val = int(token) if token.isdigit() else 0
            else:
                match = cls.TRAILING_DIGIT_PATTERN.search(item.strip())
                val = int(match.group(1)) if match else 0

            max_val = max(max_val, val)

        return max_val

    @classmethod
    def resolve_superseded_id(
        cls,
        entity_id: str,
        graveyard: Mapping[str, Mapping[str, Any]],
        hop: int = 0,
        entity_trail: Sequence[str] | None = None,
        max_hops: int = 10,
    ) -> str:
        """Trace tombstone redirects recursively across graveyard registries to canonical target.

        Args:
            entity_id: Starting identifier candidate.
            graveyard: Mapping of deprecated entity IDs to tombstone dict payloads.
            hop: Current recursion depth counter. Defaults to 0.
            entity_trail: Historical traversal sequence for circular loop detection.
            max_hops: Circuit-breaker threshold for circular reference detection.

        Returns:
            Resolved canonical identifier. Returns original entity_id if not tombstoned
            or if superseded_by target is omitted.

        Raises:
            RecursionError: If circular superseding chains or max_hops threshold are exceeded.
        """
        trail = list(entity_trail) if entity_trail is not None else []

        if entity_id in trail:
            raise RecursionError(f"Circular graveyard reference detected: {entity_id}")

        if hop >= max_hops:
            raise RecursionError(
                f"Graveyard redirect loop exceeded max_hops={max_hops} for: {trail[0] if trail else entity_id}"
            )

        if entity_id not in graveyard:
            return entity_id

        meta = graveyard[entity_id]
        if not isinstance(meta, Mapping):
            return entity_id

        next_id = meta.get("superseded_by")
        if not isinstance(next_id, str) or not next_id.strip():
            return entity_id

        trail.append(entity_id)
        return cls.resolve_superseded_id(
            entity_id=next_id.strip(),
            graveyard=graveyard,
            hop=hop + 1,
            entity_trail=trail,
            max_hops=max_hops,
        )

    @classmethod
    def match_text(
        cls,
        target: str,
        candidate: str,
        min_ratio: float = 0.8,
    ) -> bool:
        """Perform normalized fuzzy text matching against two strings.

        Args:
            target: Reference query string.
            candidate: Evaluated target string.
            min_ratio: Minimum SequenceMatcher similarity ratio (0.0 to 1.0).

        Returns:
            True if normalized substring or similarity ratio meets criteria; False otherwise.
        """
        if not target or not candidate:
            return False

        t_norm = target.strip().lower()
        c_norm = candidate.strip().lower()

        if t_norm in c_norm or c_norm in t_norm:
            return True

        ratio = difflib.SequenceMatcher(None, t_norm, c_norm).ratio()
        return ratio >= min_ratio

    # -------------------------------------------------------------------------
    # String, Timestamp & Hash Utilities
    # -------------------------------------------------------------------------
    @classmethod
    def normalize_slug(cls, text: str, delimiter: str = "_") -> str:
        """Generate a normalized ASCII filesystem and token slug from input text.

        Args:
            text: Raw input string.
            delimiter: Separator token to join alphanumeric chunks. Defaults to '_'.

        Returns:
            Normalized lowercase ASCII slug.
        """
        if not text:
            return ""
        normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        tokens = re.findall(r"[A-Za-z0-9]+", normalized.lower())
        return delimiter.join(tokens)

    @classmethod
    def parse_iso_timestamp(cls, timestamp_str: str) -> datetime:
        """Parse an ISO-8601 timestamp string into a timezone-aware UTC datetime object.

        Args:
            timestamp_str: ISO-8601 formatted timestamp string.

        Returns:
            Timezone-aware datetime instance pinned to UTC.

        Raises:
            ValueError: If timestamp string cannot be parsed as valid ISO-8601.
        """
        if not timestamp_str or not isinstance(timestamp_str, str):
            raise ValueError(f"Invalid timestamp candidate: {timestamp_str!r}")

        clean_str = timestamp_str.strip()
        if clean_str.endswith("Z"):
            clean_str = clean_str[:-1] + "+00:00"

        try:
            dt = datetime.fromisoformat(clean_str)
        except ValueError as err:
            raise ValueError(f"Invalid timestamp candidate: {timestamp_str!r}") from err

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def format_file_size(cls, size_bytes: int) -> str:
        """Format an integer byte count into a human-readable size string.

        Args:
            size_bytes: Non-negative file size in bytes.

        Returns:
            Human-readable representation (e.g., '128 B', '4.50 KB', '12.20 MB').
        """
        if size_bytes < 0:
            raise ValueError(f"File size cannot be negative: {size_bytes}")

        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        val = float(size_bytes)
        for unit in units[:-1]:
            if val < 1024.0:
                if unit == "B":
                    return f"{int(val)} B"
                return f"{val:.2f} {unit}"
            val /= 1024.0
        return f"{val:.2f} PB"

    @classmethod
    def compute_text_hash(cls, text: str) -> str:
        """Compute the SHA-256 cryptographic digest of a normalized UTF-8 string.

        Args:
            text: Input string payload.

        Returns:
            Hexadecimal SHA-256 digest string.
        """
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    @classmethod
    def iso_now(cls) -> str:
        """Return the current UTC timestamp formatted as ISO-8601.

        Returns:
            An ISO-8601 formatted UTC timestamp string ending with 'Z'.
        """
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def compute_sha256(cls, file_path: Path | str) -> str:
        """Compute the SHA-256 cryptographic hash of a target file using 64 KB blocks.

        Args:
            file_path: Path or string path to the binary or text file to hash.

        Returns:
            Hexadecimal SHA-256 digest string.
        """
        path = Path(file_path).resolve()
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    # -------------------------------------------------------------------------
    # Note Collection Factory
    # -------------------------------------------------------------------------
    @classmethod
    def create_note_collection(
        cls,
        notes_data: Sequence[dict[str, Any]] | Mapping[str, Any] | None = None,
        valid_types: Collection[str] | None = None,
    ) -> GDANoteCollection:
        """Instantiate a memory-isolated GDANoteCollection primitive.

        Args:
            notes_data: Parent entity dictionary or list of note dictionaries.
            valid_types: Optional controlled vocabulary set of allowed note types.

        Returns:
            A populated GDANoteCollection instance.
        """
        return GDANoteCollection(notes_data=notes_data, valid_types=valid_types)

    # -------------------------------------------------------------------------
    # Safe Backup Protocol Handlers
    # -------------------------------------------------------------------------
    @classmethod
    def create_safe_backup(
        cls,
        target_file: Path | str,
        label: str | None = None,
        backup_dir: Path | None = None,
    ) -> Path:
        """Create an atomic pre-execution backup copy of target_file.

        Args:
            target_file: Path or string path to the file requiring backup.
            label: Optional custom alphanumeric token to embed in the backup filename.
            backup_dir: Destination directory. Defaults to config.CONFIG.backups.

        Returns:
            Path to the newly created backup snapshot.

        Raises:
            FileNotFoundError: If target_file does not exist on disk.
        """
        source = Path(target_file).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Cannot backup non-existent file: {source}")

        dest_dir = backup_dir or config.CONFIG.backups
        dest_dir.mkdir(parents=True, exist_ok=True)

        token = label.strip() if label else datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{source.name}.{token}.bk"
        backup_path = dest_dir / backup_filename

        shutil.copy2(source, backup_path)
        return backup_path

    @classmethod
    def list_backups(
        cls,
        target_file: Path | str,
        backup_dir: Path | None = None,
    ) -> list[Path]:
        """List all available backups for a given file, sorted newest to oldest.

        Args:
            target_file: Path or string path to the target file.
            backup_dir: Target backup directory. Defaults to config.CONFIG.backups.

        Returns:
            List of Path objects for matching backup files ordered by descending
            modification time. Returns an empty list if backup_dir does not exist.
        """
        source_name = Path(target_file).name
        dest_dir = backup_dir or config.CONFIG.backups

        if not dest_dir.exists():
            return []

        backups = [
            f
            for f in dest_dir.glob(f"{source_name}.*.bk")
            if f.is_file() and cls.BACKUP_PATTERN.match(f.name)
        ]
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups

    @classmethod
    def restore_backup(
        cls,
        target_file: Path | str,
        label_or_timestamp: str | None = None,
        backup_dir: Path | None = None,
    ) -> Path:
        """Restore target_file from an existing backup snapshot.

        Args:
            target_file: Path or string path to the destination file being restored.
            label_or_timestamp: Specific label or timestamp to restore. If None,
                restores the most recent backup available.
            backup_dir: Directory containing backups. Defaults to config.CONFIG.backups.

        Returns:
            Path of the backup snapshot that was copied to target_file.

        Raises:
            FileNotFoundError: If the specified backup token does not exist, or if
                no backups exist for target_file.
        """
        source = Path(target_file).resolve()
        dest_dir = backup_dir or config.CONFIG.backups

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
        target_file: Path | str,
        keep: int = 5,
        backup_dir: Path | None = None,
    ) -> list[Path]:
        """Retain the most recent `keep` backups for target_file and unlink older ones.

        Args:
            target_file: Path or string path to the file whose backups are being rotated.
            keep: Minimum number of recent backups to retain. Must be >= 1.
            backup_dir: Directory containing backups. Defaults to config.CONFIG.backups.

        Returns:
            List of Path objects representing the unlinked backup files.

        Raises:
            ValueError: If keep is less than 1.
        """
        if keep < 1:
            raise ValueError(f"keep parameter must be at least 1, got {keep}")

        backups = cls.list_backups(target_file, backup_dir=backup_dir)
        pruned: list[Path] = []

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
    def clear_gtemp(cls, preserve_patterns: Sequence[str] | None = None) -> int:
        """Safely clear transient scratch files and directories from config.CONFIG.temp.

        Args:
            preserve_patterns: Sequence of filenames to preserve. Defaults to
                ['.gitkeep', '.gitignore'].

        Returns:
            Total count of deleted files and subdirectories.
        """
        temp_dir = config.CONFIG.temp
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
        source_path: Path | str,
        quarantine_dir: Path | None = None,
    ) -> Path:
        """Safely relocate a non-conforming or unverified entity file into quarantine.

        Args:
            source_path: Path or string path to the file to quarantine.
            quarantine_dir: Target quarantine directory. Defaults to
                config.CONFIG.quarantine (data/entities/quarantine/).

        Returns:
            Path to the relocated file in the quarantine directory.

        Raises:
            FileNotFoundError: If source_path does not exist on disk.
        """
        source = Path(source_path).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Cannot quarantine non-existent file: {source}")

        dest_dir = quarantine_dir or config.CONFIG.quarantine
        dest_dir.mkdir(parents=True, exist_ok=True)

        target_dest = dest_dir / source.name
        shutil.move(str(source), str(target_dest))
        return target_dest

    # -------------------------------------------------------------------------
    # Standard UTF-8 JSON I/O with Atomic Single Touch-Point Persistence
    # -------------------------------------------------------------------------
    @classmethod
    def read_json(cls, file_path: Path | str, default: Any = None) -> Any:
        """Safely load and parse a JSON file, returning a default value if missing.

        Args:
            file_path: Path or string path to the target JSON file.
            default: Fallback value returned if the file does not exist. Defaults to None.

        Returns:
            Parsed data structure, or `default` if the file does not exist.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            return default
        return cls.load_json(path)

    @classmethod
    def load_json(cls, file_path: Path | str) -> Any:
        """Read and parse a UTF-8 encoded JSON file supporting BOM (utf-8-sig).

        Args:
            file_path: Path or string path to the JSON file.

        Returns:
            Deserialized Python data structure (dict, list, etc.).

        Raises:
            FileNotFoundError: If the specified file does not exist.
            ValueError: If the file contains malformed JSON syntax.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except json.JSONDecodeError as err:
            raise ValueError(
                f"Malformed JSON in {path} (line {err.lineno}, col {err.colno}): {err.msg}"
            ) from err

    @classmethod
    def save_json(
        cls,
        file_path: Path | str,
        data: Any,
        indent: int = 2,
        create_backup: bool = False,
        backup_dir: Path | None = None,
    ) -> Path:
        """Write data to a UTF-8 encoded JSON file with atomic write protection.

        If create_backup is True and file_path already exists, triggers
        create_safe_backup before executing atomic replacement. Cleans up
        the temporary scratch file if serialization fails.

        Args:
            file_path: Path or string path to the target destination JSON file.
            data: JSON-serializable Python data structure to persist.
            indent: Indentation level for pretty-printing. Defaults to 2.
            create_backup: If True and target file exists, creates an atomic safe backup.
            backup_dir: Optional custom directory for the backup snapshot.

        Returns:
            Resolved Path of the written destination file.

        Raises:
            TypeError: If data contains non-JSON-serializable objects.
            OSError: If destination path is inaccessible or filesystem write fails.
        """
        path = Path(file_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        if create_backup and path.exists():
            cls.create_safe_backup(path, backup_dir=backup_dir)

        temp_dest = path.with_suffix(f"{path.suffix}.tmp")
        try:
            with open(temp_dest, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
                f.write("\n")

            # Windows-resilient atomic replace with retry on transient lock
            last_err: Exception | None = None
            for attempt in range(3):
                try:
                    temp_dest.replace(path)
                    break
                except (PermissionError, OSError) as err:
                    last_err = err
                    if attempt < 2:
                        time.sleep(0.05)
            else:
                raise last_err or OSError(f"Failed to replace {path}")

        except Exception:
            if temp_dest.exists():
                try:
                    temp_dest.unlink()
                except OSError:
                    pass
            raise

        return path