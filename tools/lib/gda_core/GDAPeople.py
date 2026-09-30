# Name: GDAPeople.py
# Path: tools/lib/gda_core/GDAPeople.py
# Version: 1.0.0+build.20260929.1

"""Master person entity and kinship registry manager.

Operational Role:
    Manages data/entities/people.json with transactional backups,
    monotonic IND-XXXXX minting, reciprocal kinship edge maintenance,
    union state tracking, demographic plausibility checks, and view filtering.
"""

from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
import fnmatch
from pathlib import Path
import re
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDALogger import get_logger
from tools.lib.gda_core.GDAUtil import GDAUtil


class GDAPeople:
    """Master registry manager for person entities and kinship graphs.

    Manages data/entities/people.json with transactional backups, reciprocal
    kinship validation, fuzzy search, union pairing, and stateful filtering.
    """

    _PERSON_ID_REGEX = re.compile(r"^IND-[0-9]{5}$")
    _RECIPROCAL_ROLES = {
        "FATH": "CHIL",
        "MOTH": "CHIL",
        "SPOU": "SPOU",
        "SIBL": "SIBL",
    }

    def __init__(
        self,
        filepath: Optional[Union[str, Path]] = None,
        auto_load: bool = True,
    ) -> None:
        self._config = CONFIG
        self._logger = get_logger(__name__)
        self._filepath = Path(filepath) if filepath else self._config.entities / "people.json"

        self._registry_metadata: Dict[str, Any] = {
            "_name": "people.json",
            "_path": "data/entities/people.json",
            "$schema": "schemas/entities/person_registry.schema.json",
            "schema_version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_modified": datetime.now(timezone.utc).isoformat(),
            "total_people": 0,
        }
        self._people: Dict[str, Dict[str, Any]] = {}
        self._filtered_ids: Optional[List[str]] = None
        self._is_dirty: bool = False

        if auto_load:
            self.load()

    # -------------------------------------------------------------------------
    # Lifecycle & Persistence
    # -------------------------------------------------------------------------
    def load(self) -> None:
        """Load and parse people.json from disk, resetting dirty state and active filters."""
        if not self._filepath.exists():
            self._logger.info(f"[SYS] People registry not found at {self._filepath}. Initializing empty container.")
            self._people = {}
            self._filtered_ids = None
            self._is_dirty = False
            return

        try:
            data = GDAUtil.load_json(self._filepath)
            for meta_key in ["_name", "_path", "$schema", "schema_version", "created_at", "last_modified"]:
                if meta_key in data:
                    self._registry_metadata[meta_key] = data[meta_key]

            raw_people = data.get("people", [])
            self._people = {item["person_id"]: item for item in raw_people}
            self._filtered_ids = None
            self._is_dirty = False
            self._logger.info(f"[SYS] Loaded {len(self._people)} people from {self._filepath.name}.")
        except Exception as exc:
            self._logger.error(f"[SYS] Failed to load people from {self._filepath}: {exc}")
            raise

    def refresh(self) -> None:
        """Reload registry from disk, discarding in-memory modifications."""
        self.load()

    def save(
        self,
        output_path: Optional[Union[str, Path]] = None,
        force: bool = False,
        create_backup: bool = True,
    ) -> bool:
        """Persist registry to disk via GDAUtil atomic write with Safe Backup."""
        if not self._is_dirty and not force:
            return False

        target = Path(output_path) if output_path else self._filepath
        should_backup = create_backup if target == self._filepath else False

        self._registry_metadata["last_modified"] = datetime.now(timezone.utc).isoformat()
        self._registry_metadata["total_people"] = len(self._people)

        payload = dict(self._registry_metadata)
        sorted_people = sorted(
            self._people.values(),
            key=lambda item: int(item["person_id"].split("-")[1]),
        )
        payload["people"] = sorted_people

        GDAUtil.save_json(target, payload, create_backup=should_backup)
        if target == self._filepath:
            self._is_dirty = False

        self._logger.info(f"[SYS] Successfully persisted {len(sorted_people)} people to {target.name}.")
        return True

    # -------------------------------------------------------------------------
    # State Properties
    # -------------------------------------------------------------------------
    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    @property
    def count(self) -> int:
        return len(self._people)

    @property
    def filtered_count(self) -> int:
        if self._filtered_ids is None:
            return len(self._people)
        return len(self._filtered_ids)

    # -------------------------------------------------------------------------
    # ID Minting & Identity Helpers
    # -------------------------------------------------------------------------
    def _mint_next_id(self) -> str:
        if not self._people:
            return "IND-00001"
        highest_idx = 0
        for pid in self._people.keys():
            match = self._PERSON_ID_REGEX.match(pid)
            if match:
                val = int(pid.split("-")[1])
                if val > highest_idx:
                    highest_idx = val
        return f"IND-{highest_idx + 1:05d}"

    @staticmethod
    def build_display_name(canonical_name: Optional[Dict[str, Any]]) -> str:
        """Assembles a display name from a canonical_name dictionary, stripping trailing periods."""
        if not canonical_name or not isinstance(canonical_name, dict):
            return "UNKNOWN"

        parts: List[str] = []
        for key in ["given", "middle", "surname", "suffix"]:
            val = canonical_name.get(key)
            if val:
                parts.append(str(val).strip())

        raw_assembled = " ".join(p for p in parts if p)
        if not raw_assembled:
            raw = canonical_name.get("raw_name")
            raw_assembled = str(raw).strip() if raw and str(raw).strip() else "UNKNOWN"

        clean_name = raw_assembled.replace(".", "")
        return " ".join(clean_name.split())

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------
    def exists(self, person_id: str) -> bool:
        return person_id in self._people

    def get_by_id(self, person_id: str) -> Optional[Dict[str, Any]]:
        record = self._people.get(person_id)
        return dict(record) if record else None

    def add(
        self,
        canonical_name: Dict[str, Any],
        sex: str,
        person_id: Optional[str] = None,
        associated_people: Optional[List[Dict[str, Any]]] = None,
        unions: Optional[List[Dict[str, Any]]] = None,
        notes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        assigned_id = person_id.strip() if person_id else self._mint_next_id()
        if not self._PERSON_ID_REGEX.match(assigned_id):
            raise ValueError(f"Malformed person_id pattern: '{assigned_id}'")
        if assigned_id in self._people:
            raise KeyError(f"Person identifier '{assigned_id}' already exists in registry.")

        now_iso = datetime.now(timezone.utc).isoformat()
        display_name = self.build_display_name(canonical_name)

        record: Dict[str, Any] = {
            "person_id": assigned_id,
            "display_name": display_name,
            "canonical_name": canonical_name,
            "sex": sex.strip().upper(),
            "associated_people": associated_people or [],
            "unions": unions or [],
            "notes": notes or [],
            "last_updated": now_iso,
        }

        self._people[assigned_id] = record
        self._is_dirty = True
        self._logger.info(f"[SYS] Staged person addition: {assigned_id} ('{display_name}').")
        return assigned_id

    def edit(self, person_id: str, updates: Dict[str, Any], overwrite_none: bool = False) -> bool:
        if person_id not in self._people:
            raise KeyError(f"Person '{person_id}' does not exist in registry.")

        record = self._people[person_id]
        modified = False

        if "canonical_name" in updates:
            record["canonical_name"] = updates["canonical_name"]
            record["display_name"] = self.build_display_name(updates["canonical_name"])
            modified = True

        for field in ["sex", "associated_people", "unions", "notes"]:
            if field in updates:
                val = updates[field]
                if val is not None or overwrite_none:
                    if record.get(field) != val:
                        record[field] = val
                        modified = True

        if modified:
            record["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._is_dirty = True
            self._logger.info(f"[SYS] Staged edits for person {person_id}.")

        return modified

    def delete(self, person_id: str) -> bool:
        if person_id not in self._people:
            return False

        del self._people[person_id]
        if self._filtered_ids is not None and person_id in self._filtered_ids:
            self._filtered_ids.remove(person_id)

        self._is_dirty = True
        self._logger.warning(f"[SYS] Deleted person {person_id} from registry.")
        return True

    # -------------------------------------------------------------------------
    # View State & Filtering
    # -------------------------------------------------------------------------
    def set_filter(
        self,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
        surname: Optional[str] = None,
        sex: Optional[str] = None,
    ) -> int:
        matched_ids: List[str] = []
        for pid, item in self._people.items():
            if sex and item.get("sex", "").upper() != sex.strip().upper():
                continue
            if surname:
                sur = item.get("canonical_name", {}).get("surname", "")
                if not fnmatch.fnmatch(sur.lower(), surname.strip().lower()):
                    continue
            if predicate and not predicate(item):
                continue
            matched_ids.append(pid)

        self._filtered_ids = matched_ids
        return len(matched_ids)

    def clear_filter(self) -> None:
        self._filtered_ids = None

    def get_filtered(self) -> List[Dict[str, Any]]:
        if self._filtered_ids is None:
            return [dict(item) for item in self._people.values()]
        return [dict(self._people[pid]) for pid in self._filtered_ids]

    def update_filtered(self, updates: Dict[str, Any]) -> int:
        targets = list(self._filtered_ids) if self._filtered_ids is not None else list(self._people.keys())
        if not targets:
            return 0
        modified_count = sum(1 for pid in targets if self.edit(pid, updates))
        return modified_count

    # -------------------------------------------------------------------------
    # Dunder Protocols & Context Management
    # -------------------------------------------------------------------------
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        pool = self._filtered_ids if self._filtered_ids is not None else self._people.keys()
        for pid in pool:
            yield dict(self._people[pid])

    def __len__(self) -> int:
        return self.filtered_count

    def __contains__(self, person_id: str) -> bool:
        return person_id in self._people

    def __enter__(self) -> GDAPeople:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is None and self._is_dirty:
            self.save()