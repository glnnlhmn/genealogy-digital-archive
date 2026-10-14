# Name: people.py
# Path: tools/lib/gdadomain/src/gdadomain/people.py
# Version: 1.0.0+build.r3

"""Master person registry manager and reciprocal kinship state machine.

Operational Role:
    Manages data/entities/people.json with transactional safe backups,
    strictly system-minted sequential IND-XXXXX identifier allocation,
    bidirectional reciprocal kinship edge synchronization, marital union
    pairing, canonical display name compilation, in-place entity tombstoning,
    and memory-isolated note collection governance via GDANoteCollection.
"""

from __future__ import annotations

import copy
from collections.abc import Collection, Iterator
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Union

from gdacore.config import CONFIG, GDAConfig
from gdacore.introspectable import IntrospectableMixin
from gdacore.logger import GDALogger
from gdacore.reference_manager import GDAReferenceManager
from gdacore.util import GDANoteCollection, GDAUtil
from gdacore.vocabulary_manager import GDAVocabularyManager

__version__ = "1.0.0+build.r3"

VOCAB_MGR = GDAVocabularyManager()

IND_ID_PATTERN: re.Pattern[str] = re.compile(r"^IND-(\d{5})$")

VALID_SEX: Set[str] = {"M", "F", "U"}
VALID_KINSHIP_ROLES: Set[str] = {
    "FATH",
    "MOTH",
    "CHIL",
    "SPOU",
    "SIBL",
    "WITN",
    "OFFICIANT",
    "PARENT",
}
VALID_UNION_STATUSES: Set[str] = {"MARRIED", "DIVORCED", "SEPARATED", "COMMON_LAW"}

RECIPROCAL_ROLES: Dict[str, Union[str, Dict[str, str]]] = {
    "FATH": "CHIL",
    "MOTH": "CHIL",
    "CHIL": {"M": "FATH", "F": "MOTH", "U": "PARENT"},
    "SPOU": "SPOU",
    "SIBL": "SIBL",
}


class GDAPeople(IntrospectableMixin, Collection[Dict[str, Any]]):
    """Authoritative master person registry and reciprocal kinship manager.

    Attributes:
        ALLOWED_PROPERTIES: Frozenset of top-level record keys permissible in edit mutations.
        people_path: Canonical filesystem path to people.json.
        auto_commit: If True, commits dirty changes upon clean context manager exit.
        dirty_ids: Set of modified person identifiers staged for persistence.
        is_dirty: True if active people or graveyard stores have unpersisted changes.
        count: Count of active person records in memory.
        total_count: Total count of all person records across active and graveyard partitions.
        graveyard: Dictionary mapping tombstone identifiers to record payloads.
        existing_ids: Set of all active canonical person IDs.
    """

    ALLOWED_PROPERTIES: frozenset[str] = frozenset({
        "canonical_name",
        "display_name",
        "sex",
        "associated_people",
        "unions",
        "notes",
        "is_deprecated",
        "superseded_by",
    })

    def __init__(
        self,
        filepath: Optional[Union[str, Path]] = None,
        auto_load: bool = True,
        config: Optional[GDAConfig] = None,
        auto_commit: bool = True,
    ) -> None:
        """Initialize the master person registry manager.

        Args:
            filepath: Optional path to the backing JSON file. Defaults to
                canonical people.json configured in GDAConfig.
            auto_load: If True, loads person records from disk immediately. Defaults to True.
            config: Optional GDAConfig instance override. Defaults to global CONFIG.
            auto_commit: If True, commits dirty changes upon clean context manager exit. Defaults to True.
        """
        self._config = config or CONFIG
        self._logger = GDALogger.get_logger("gda_people")
        self._filepath = Path(filepath) if filepath else self._config.entities / "people.json"
        self.people_path = self._filepath
        self.auto_commit = auto_commit

        self._registry_metadata: Dict[str, Any] = {
            "_name": "people.json",
            "_path": "data/entities/people.json",
            "schema_version": "1.0.0",
            "created_at": GDAUtil.iso_now(),
            "last_modified": GDAUtil.iso_now(),
            "total_people": 0,
        }
        self._people: Dict[str, Dict[str, Any]] = {}
        self._graveyard: Dict[str, Dict[str, Any]] = {}
        self._max_person_num: int = 0

        self.dirty_ids: Set[str] = set()
        self._is_dirty: bool = False

        if auto_load:
            self.load()

    def __enter__(self) -> GDAPeople:
        """Context manager entry point returning the manager instance.

        Returns:
            The initialized GDAPeople instance.
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit point committing unpersisted state on clean exit.

        Args:
            exc_type: Exception type if raised, else None.
            exc_val: Exception value if raised, else None.
            exc_tb: Exception traceback if raised, else None.
        """
        if exc_type is None and self.auto_commit and self.is_dirty:
            self.save(create_backup=False)

    @property
    def is_dirty(self) -> bool:
        """Return True if in-memory mutations remain unpersisted to disk."""
        return self._is_dirty or len(self.dirty_ids) > 0

    @property
    def count(self) -> int:
        """Return count of registered active person records in memory."""
        return len(self._people)

    @property
    def total_count(self) -> int:
        """Return total count of all person records across active and graveyard partitions."""
        return len(self._people) + len(self._graveyard)

    @property
    def graveyard(self) -> Dict[str, Dict[str, Any]]:
        """Return deep copy of all graveyard tombstones keyed by person_id."""
        return copy.deepcopy(self._graveyard)

    @property
    def existing_ids(self) -> Set[str]:
        """Return the set of all active canonical person IDs."""
        return set(self._people.keys())

    def __len__(self) -> int:
        """Return the count of registered active person entities."""
        return self.count

    def __contains__(self, person_id: Any) -> bool:
        """Check active registry membership for a person identifier.

        Args:
            person_id: Identifier token to query.

        Returns:
            True if person_id exists in active registry; False otherwise.
        """
        if not isinstance(person_id, str):
            return False
        return self.exists(person_id, include_graveyard=False)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over all active registered person records.

        Yields:
            Deep copies of registered person record dictionaries.
        """
        for person in self._people.values():
            yield copy.deepcopy(person)

    def __getitem__(self, person_id: str) -> Dict[str, Any]:
        """Retrieve an active person record by ID with transparent graveyard redirection.

        Args:
            person_id: Canonical IND-XXXXX identifier.

        Returns:
            Deep-copied record dictionary matching identifier or its successor.

        Raises:
            KeyError: If person_id is unregistered or resolves to an unredirected tombstone.
        """
        rec = self.get(person_id, resolve_redirects=True)
        if rec is None:
            raise KeyError(f"Person ID '{person_id}' not found in registry.")
        return rec

    @staticmethod
    def build_display_name(canonical_name: Optional[Dict[str, Any]]) -> str:
        """Assemble canonical name components into a normalized display name.

        Args:
            canonical_name: Dictionary containing name parts (given, middle, surname, suffix)
                or raw_name string.

        Returns:
            Normalized display name string, or 'UNKNOWN' if unresolvable.
        """
        if not isinstance(canonical_name, dict) or not canonical_name:
            return "UNKNOWN"

        parts: List[str] = []
        for key in ("given", "middle", "surname", "suffix"):
            val = canonical_name.get(key)
            if val and isinstance(val, str):
                cleaned = val.replace(".", "").strip()
                if cleaned:
                    parts.append(cleaned)

        if parts:
            return " ".join(parts)

        raw = canonical_name.get("raw_name")
        if raw and isinstance(raw, str) and raw.strip():
            return raw.strip()

        return "UNKNOWN"

    def load(self) -> None:
        """Load active person records and tombstoned records from disk into memory partitions.

        Raises:
            Exception: If JSON parsing fails or disk read encounters errors.
        """
        if not self._filepath.exists():
            self._logger.info(
                f"[SYS] People registry not found at {self._filepath}. Initializing empty container."
            )
            self._people = {}
            self._graveyard = {}
            self._max_person_num = 0
            self._is_dirty = False
            self.dirty_ids.clear()
            return

        try:
            data = GDAUtil.load_json(self._filepath)
            for meta_key in [
                "_name",
                "_path",
                "$schema",
                "schema_version",
                "created_at",
                "last_modified",
            ]:
                if isinstance(data, dict) and meta_key in data:
                    self._registry_metadata[meta_key] = data[meta_key]

            if isinstance(data, dict):
                raw_people = data.get("persons", data.get("people", []))
            elif isinstance(data, list):
                raw_people = data
            else:
                raw_people = []

            self._people = {}
            self._graveyard = {}

            for item in raw_people:
                if not isinstance(item, dict):
                    continue
                pid = item.get("person_id", "")
                if not pid:
                    continue

                if item.get("is_deprecated", False):
                    self._graveyard[pid] = item
                else:
                    self._people[pid] = item

            all_ids = list(self._people.keys()) + list(self._graveyard.keys())
            self._max_person_num = GDAUtil.find_max_numeric_id(all_ids)
            self._is_dirty = False
            self.dirty_ids.clear()
            self._logger.info(
                f"[PEOPLE] Loaded {len(self._people)} active people and {len(self._graveyard)} "
                f"tombstones from {self._filepath.name} (Max IND: {self._max_person_num:05d})."
            )
        except Exception as exc:
            self._logger.error(f"[PEOPLE] Failed loading {self._filepath}: {exc}")
            raise

    def refresh(self) -> None:
        """Discard unstaged memory mutations and reload state cleanly from disk."""
        self.load()

    def reload(self) -> None:
        """Discard uncommitted modifications and reload from disk."""
        self.refresh()

    def resolve_id(self, person_id: str) -> Optional[str]:
        """Trace deprecation redirect chain through graveyard to canonical active person ID.

        Args:
            person_id: Initial person identifier to evaluate.

        Returns:
            Active canonical IND-XXXXX string if resolved; None if defunct or trapped in cycle.
        """
        try:
            target = GDAUtil.resolve_superseded_id(
                entity_id=person_id,
                graveyard=self._graveyard,
            )
        except RecursionError:
            self._logger.warning(f"[PEOPLE] Circular graveyard redirect detected for '{person_id}'.")
            return None

        return target if (target and target in self._people) else None

    def validate_person_schema(self, person_data: Dict[str, Any]) -> List[str]:
        """Validate person schema structure, identifiers, and controlled vocabularies.

        Args:
            person_data: Dictionary representing the person payload to validate.

        Returns:
            List of diagnostic violation messages. Empty list indicates validity.
        """
        errors: List[str] = []
        if not isinstance(person_data, dict):
            return ["Person payload must be a dictionary."]

        pid = person_data.get("person_id")
        if pid is not None and not IND_ID_PATTERN.match(str(pid)):
            errors.append(f"Invalid person_id format: '{pid}'. Must follow IND-XXXXX pattern.")

        sex = person_data.get("sex")
        if sex is not None:
            valid_genders = VOCAB_MGR["gender"] if "gender" in VOCAB_MGR else VALID_SEX
            if valid_genders and sex not in valid_genders:
                errors.append(f"Invalid sex/gender: '{sex}'. Must be in controlled vocabulary.")

        assoc = person_data.get("associated_people")
        if assoc is not None:
            if not isinstance(assoc, list):
                errors.append("'associated_people' must be a list.")
            else:
                for idx, entry in enumerate(assoc):
                    if not isinstance(entry, dict):
                        errors.append(f"associated_people[{idx}] must be a dictionary.")
                        continue
                    apid = entry.get("person_id")
                    if apid and not IND_ID_PATTERN.match(str(apid)):
                        errors.append(f"Invalid person_id '{apid}' in associated_people[{idx}].")
                    role = entry.get("role")
                    valid_roles = VOCAB_MGR["associated_role"] if "associated_role" in VOCAB_MGR else VALID_KINSHIP_ROLES
                    if valid_roles and role and role not in valid_roles:
                        errors.append(f"Invalid role '{role}' in associated_people[{idx}].")

        unions = person_data.get("unions")
        if unions is not None:
            if not isinstance(unions, list):
                errors.append("'unions' must be a list.")
            else:
                for idx, u in enumerate(unions):
                    if not isinstance(u, dict):
                        errors.append(f"unions[{idx}] must be a dictionary.")
                        continue
                    sp_id = u.get("spouse_id")
                    if sp_id and not IND_ID_PATTERN.match(str(sp_id)):
                        errors.append(f"Invalid spouse_id '{sp_id}' in unions[{idx}].")

        notes = person_data.get("notes")
        if notes is not None and not isinstance(notes, list):
            errors.append("'notes' must be a list.")

        return errors

    def _mint_next_id(self) -> str:
        """Auto-mint sequential IND-XXXXX identifier using monotonic high-water mark.

        Returns:
            Formally minted IND-XXXXX identifier string.
        """
        all_ids = set(self._people.keys()) | set(self._graveyard.keys())
        highest_num = GDAUtil.find_max_numeric_id(list(all_ids)) if all_ids else 0
        if highest_num > self._max_person_num:
            self._max_person_num = highest_num
        self._max_person_num += 1
        return f"IND-{self._max_person_num:05d}"

    def mint_next_person_id(self) -> str:
        """Calculate and return the next sequential IND-XXXXX identifier.

        Returns:
            Minted IND-XXXXX identifier string.
        """
        return self._mint_next_id()

    def exists(self, person_id: str, include_graveyard: bool = False) -> bool:
        """Verify if person identifier is registered.

        Args:
            person_id: Canonical IND-XXXXX identifier.
            include_graveyard: If True, checks active and graveyard stores. Defaults to False.

        Returns:
            True if identifier exists in designated store; False otherwise.
        """
        if person_id in self._people:
            return True
        return include_graveyard and (person_id in self._graveyard)

    def get(
        self,
        person_id: str,
        include_graveyard: bool = False,
        resolve_redirects: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a defensive copy of a person record by identifier.

        Args:
            person_id: Canonical IND-XXXXX identifier.
            include_graveyard: If True, returns tombstone payload if unredirected. Defaults to False.
            resolve_redirects: If True, traces superseded_by chains to active record. Defaults to True.

        Returns:
            Deep copy of person record dictionary if found; None otherwise.
        """
        if person_id in self._people:
            return copy.deepcopy(self._people[person_id])

        if resolve_redirects:
            canonical_id = self.resolve_id(person_id)
            if canonical_id and canonical_id in self._people:
                return copy.deepcopy(self._people[canonical_id])

        if include_graveyard and person_id in self._graveyard:
            return copy.deepcopy(self._graveyard[person_id])

        return None

    def get_by_id(self, person_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a person record by canonical identifier.

        Args:
            person_id: Canonical IND-XXXXX identifier.

        Returns:
            Deep copy of person record dictionary if found; None otherwise.
        """
        return self.get(person_id, resolve_redirects=False)

    def mark_dirty(self, person_id: str) -> None:
        """Mark an active or tombstoned person ID as modified, staging changes for persistence.

        Args:
            person_id: Canonical identifier of modified person.
        """
        if person_id in self._people or person_id in self._graveyard:
            self.dirty_ids.add(person_id)
            self._is_dirty = True

    def add(
        self,
        canonical_name: Optional[Dict[str, Any]] = None,
        sex: Optional[str] = "U",
        person_id: Optional[str] = None,
        associated_people: Optional[List[Dict[str, Any]]] = None,
        unions: Optional[List[Dict[str, Any]]] = None,
        notes: Optional[List[Dict[str, Any]]] = None,
        **extra_fields: Any,
    ) -> str:
        """Register a new person in the master registry.

        Accepts either positional or keyword parameters, or an existing payload dictionary.

        Args:
            canonical_name: Dictionary containing structured name components.
            sex: Biological or recorded sex token (M, F, U). Defaults to 'U'.
            person_id: Optional explicit IND-XXXXX identifier. Defaults to auto-minted next ID.
            associated_people: Optional list of kinship edge dictionaries.
            unions: Optional list of union relationship dictionaries.
            notes: Optional list of note dictionaries.
            **extra_fields: Additional arbitrary attributes to persist on the entity.

        Returns:
            Canonical person_id string assigned to the record.

        Raises:
            ValueError: If schema validation fails or ID is malformed.
            KeyError: If person_id already exists in registry.
        """
        if isinstance(canonical_name, dict) and "canonical_name" in canonical_name:
            payload = copy.deepcopy(canonical_name)
            pid = payload.get("person_id") or person_id or self._mint_next_id()
            c_name = payload.get("canonical_name", {})
            raw_sex = payload.get("sex", sex)
            assoc = payload.get("associated_people", associated_people)
            u_list = payload.get("unions", unions)
            n_list = payload.get("notes", notes)
            extras = {
                k: v
                for k, v in payload.items()
                if k not in {
                    "person_id",
                    "canonical_name",
                    "sex",
                    "associated_people",
                    "unions",
                    "notes",
                    "display_name",
                }
            }
            extras.update(extra_fields)
        else:
            pid = person_id or self._mint_next_id()
            c_name = canonical_name or {}
            raw_sex = sex
            assoc = associated_people
            u_list = unions
            n_list = notes
            extras = extra_fields

        if not IND_ID_PATTERN.match(pid):
            raise ValueError(f"Malformed person_id pattern: '{pid}'")
        if pid in self._people or pid in self._graveyard:
            raise KeyError(f"Person ID '{pid}' already exists in registry.")

        clean_sex = raw_sex.strip().upper() if isinstance(raw_sex, str) and raw_sex.strip() else "U"
        display_name = self.build_display_name(c_name)

        note_collection = GDANoteCollection(notes_data=n_list)

        now_iso = GDAUtil.iso_now()
        record: Dict[str, Any] = {
            "person_id": pid,
            "display_name": display_name,
            "canonical_name": copy.deepcopy(c_name),
            "sex": clean_sex,
            "associated_people": copy.deepcopy(assoc) if assoc is not None else [],
            "unions": copy.deepcopy(u_list) if u_list is not None else [],
            "notes": note_collection.to_list(),
            "is_deprecated": False,
            "superseded_by": None,
            "created_at": now_iso,
            "last_updated": now_iso,
        }
        record.update(copy.deepcopy(extras))

        errors = self.validate_person_schema(record)
        if errors:
            raise ValueError(f"Person schema validation failed: {'; '.join(errors)}")

        self._people[pid] = record
        self.dirty_ids.add(pid)
        self._is_dirty = True
        return pid

    def edit(
        self,
        person_id: str,
        updates: Dict[str, Any],
        overwrite_none: bool = False,
    ) -> bool:
        """Apply mutation dictionary to an existing person record in-place.

        Args:
            person_id: Canonical IND-XXXXX identifier.
            updates: Dictionary containing property modifications.
            overwrite_none: If True, overwrites existing values when update value is None.

        Returns:
            True if changes were staged; False if updates resulted in identical state.

        Raises:
            KeyError: If person_id resides in graveyard or does not exist.
            ValueError: If updates attempt to mutate immutable person_id or fail validation.
        """
        if person_id in self._graveyard:
            raise KeyError(f"Cannot edit deprecated person '{person_id}' residing in graveyard.")
        if person_id not in self._people:
            raise KeyError(f"Person '{person_id}' does not exist in registry.")

        if not updates:
            return False

        record = self._people[person_id]

        new_id = updates.get("person_id")
        if new_id and new_id != person_id:
            raise ValueError("person_id is immutable.")

        if updates.get("is_deprecated") is True:
            superseded_target = updates.get("superseded_by")
            return self.delete(person_id, hard_delete=False, superseded_by=superseded_target)

        modified = False
        candidate = copy.deepcopy(record)

        for key, val in updates.items():
            if key == "person_id":
                continue

            if val is None and not overwrite_none:
                continue

            if key == "notes" and isinstance(val, list):
                new_notes = GDANoteCollection(notes_data=val).to_list()
                if candidate.get("notes") != new_notes:
                    candidate["notes"] = new_notes
                    modified = True
                continue

            if candidate.get(key) != val:
                candidate[key] = copy.deepcopy(val)
                modified = True

        if modified:
            if "canonical_name" in updates:
                candidate["display_name"] = self.build_display_name(candidate.get("canonical_name"))

            errors = self.validate_person_schema(candidate)
            if errors:
                raise ValueError(f"Person schema validation failed: {'; '.join(errors)}")

            candidate["last_updated"] = GDAUtil.iso_now()
            self._people[person_id] = candidate
            self.dirty_ids.add(person_id)
            self._is_dirty = True

        return modified

    def update(
        self,
        person_id: str,
        updates: Dict[str, Any],
        overwrite_none: bool = False,
    ) -> bool:
        """Apply mutation dictionary to an existing person record.

        Args:
            person_id: Canonical IND-XXXXX identifier.
            updates: Dictionary containing property modifications.
            overwrite_none: If True, overwrites existing values when update value is None.

        Returns:
            True if changes were staged; False otherwise.
        """
        return self.edit(person_id, updates, overwrite_none=overwrite_none)

    def delete(
        self,
        person_id: str,
        hard_delete: bool = True,
        superseded_by: Optional[str] = None,
    ) -> bool:
        """Delete or deprecate a person and scrub reciprocal associations and unions.

        Args:
            person_id: Canonical IND-XXXXX identifier.
            hard_delete: If True, purges record entirely from active and graveyard memory. Defaults to True.
            superseded_by: Optional IND-XXXXX successor identifier for redirect tracking.

        Returns:
            True if record was located and deleted; False otherwise.

        Raises:
            ValueError: If superseded_by does not conform to canonical IND-XXXXX.
            KeyError: If superseded_by ID is not registered in active or graveyard store.
        """
        existing = self.get(person_id, include_graveyard=True, resolve_redirects=False)
        if not existing:
            return False

        actual_id = existing["person_id"]

        if hard_delete:
            self._people.pop(actual_id, None)
            self._graveyard.pop(actual_id, None)

            for other in self._people.values():
                other["associated_people"] = [
                    rel for rel in other.get("associated_people", []) if rel.get("person_id") != actual_id
                ]
                other["unions"] = [
                    u for u in other.get("unions", []) if u.get("spouse_id") != actual_id
                ]

            self.dirty_ids.add(actual_id)
            self._is_dirty = True
            return True

        if superseded_by:
            if not IND_ID_PATTERN.match(superseded_by):
                raise ValueError(f"Invalid superseded_by person_id '{superseded_by}': must follow IND-XXXXX pattern.")
            if not self.exists(superseded_by, include_graveyard=True):
                raise KeyError(f"Target superseded_by person_id '{superseded_by}' not found in registry.")

        if actual_id in self._graveyard:
            if superseded_by:
                self._graveyard[actual_id]["superseded_by"] = superseded_by
                self._graveyard[actual_id]["last_updated"] = GDAUtil.iso_now()
                self.dirty_ids.add(actual_id)
                self._is_dirty = True
            return True

        record = self._people.pop(actual_id)
        record["is_deprecated"] = True
        record["superseded_by"] = superseded_by
        record["last_updated"] = GDAUtil.iso_now()

        self._graveyard[actual_id] = record
        self.dirty_ids.add(actual_id)
        self._is_dirty = True
        return True

    def link_kinship(
        self,
        person_a_id: str,
        person_b_id: str,
        role_a_to_b: str,
    ) -> None:
        """Create or update a bidirectional kinship edge between two persons.

        Args:
            person_a_id: Origin person identifier.
            person_b_id: Target person identifier.
            role_a_to_b: Kinship role of person A relative to person B.

        Raises:
            KeyError: If either person_a_id or person_b_id is unregistered.
        """
        if person_a_id not in self._people or person_b_id not in self._people:
            raise KeyError("Both persons must exist in registry to establish kinship.")

        p_a = self._people[person_a_id]
        p_b = self._people[person_b_id]

        mapping = RECIPROCAL_ROLES.get(role_a_to_b)
        if isinstance(mapping, dict):
            reciprocal_role = mapping.get(p_b.get("sex", "U"), "PARENT")
        else:
            reciprocal_role = mapping

        assoc_a = p_a.setdefault("associated_people", [])
        edge_a = next((e for e in assoc_a if e.get("person_id") == person_b_id), None)
        if edge_a:
            edge_a["role"] = role_a_to_b
        else:
            assoc_a.append({"person_id": person_b_id, "role": role_a_to_b})

        if reciprocal_role:
            assoc_b = p_b.setdefault("associated_people", [])
            edge_b = next((e for e in assoc_b if e.get("person_id") == person_a_id), None)
            if edge_b:
                edge_b["role"] = reciprocal_role
            else:
                assoc_b.append({"person_id": person_a_id, "role": reciprocal_role})

        now_iso = GDAUtil.iso_now()
        p_a["last_updated"] = now_iso
        p_b["last_updated"] = now_iso
        self.dirty_ids.add(person_a_id)
        self.dirty_ids.add(person_b_id)
        self._is_dirty = True

    def unlink_kinship(self, person_a_id: str, person_b_id: str) -> None:
        """Remove reciprocal kinship associations between two persons.

        Args:
            person_a_id: First person identifier.
            person_b_id: Second person identifier.
        """
        if person_a_id not in self._people or person_b_id not in self._people:
            return

        p_a = self._people[person_a_id]
        p_b = self._people[person_b_id]

        p_a["associated_people"] = [
            e for e in p_a.get("associated_people", []) if e.get("person_id") != person_b_id
        ]
        p_b["associated_people"] = [
            e for e in p_b.get("associated_people", []) if e.get("person_id") != person_a_id
        ]

        now_iso = GDAUtil.iso_now()
        p_a["last_updated"] = now_iso
        p_b["last_updated"] = now_iso
        self.dirty_ids.add(person_a_id)
        self.dirty_ids.add(person_b_id)
        self._is_dirty = True

    def add_union(
        self,
        person_a_id: str,
        person_b_id: str,
        status: str = "MARRIED",
        marriage_date: Optional[str] = None,
        marriage_location_id: Optional[str] = None,
    ) -> None:
        """Pair two persons in mutual union records and reciprocal SPOU kinship.

        Args:
            person_a_id: First spouse identifier.
            person_b_id: Second spouse identifier.
            status: Marital status classification. Defaults to 'MARRIED'.
            marriage_date: Optional recorded date string.
            marriage_location_id: Optional LOC-XXXXX location identifier.

        Raises:
            KeyError: If either person_a_id or person_b_id is unregistered.
        """
        if person_a_id not in self._people or person_b_id not in self._people:
            raise KeyError("Both persons must exist in registry to establish union.")

        p_a = self._people[person_a_id]
        p_b = self._people[person_b_id]

        clean_status = status.strip().upper()
        union_a = {
            "spouse_id": person_b_id,
            "status": clean_status,
            "marriage_date": marriage_date,
            "marriage_location_id": marriage_location_id,
        }
        union_b = {
            "spouse_id": person_a_id,
            "status": clean_status,
            "marriage_date": marriage_date,
            "marriage_location_id": marriage_location_id,
        }

        unions_a = p_a.setdefault("unions", [])
        idx_a = next((i for i, u in enumerate(unions_a) if u.get("spouse_id") == person_b_id), None)
        if idx_a is not None:
            unions_a[idx_a] = union_a
        else:
            unions_a.append(union_a)

        unions_b = p_b.setdefault("unions", [])
        idx_b = next((i for i, u in enumerate(unions_b) if u.get("spouse_id") == person_a_id), None)
        if idx_b is not None:
            unions_b[idx_b] = union_b
        else:
            unions_b.append(union_b)

        self.dirty_ids.add(person_a_id)
        self.dirty_ids.add(person_b_id)
        self._is_dirty = True
        self.link_kinship(person_a_id, person_b_id, "SPOU")

    def add_note(
        self,
        person_id: str,
        note_text: str,
        note_type: str = "RESEARCH",
    ) -> str:
        """Append an annotation note to a person record using GDANoteCollection.

        Args:
            person_id: Canonical IND-XXXXX identifier.
            note_text: Narrative text for the note.
            note_type: Categorical classification. Defaults to 'RESEARCH'.

        Returns:
            Minted note_id string.

        Raises:
            KeyError: If person_id does not exist in registry.
        """
        if person_id not in self._people:
            raise KeyError(f"Person '{person_id}' does not exist in registry.")

        record = self._people[person_id]
        collection = GDANoteCollection(notes_data=record.get("notes", []))
        created_note = collection.add(note_text=note_text, note_type=note_type)
        record["notes"] = collection.to_list()
        record["last_updated"] = GDAUtil.iso_now()
        self.dirty_ids.add(person_id)
        self._is_dirty = True
        return created_note.note_id

    def remove_note(self, person_id: str, note_id: str) -> bool:
        """Remove a note entry from a person record by its note_id.

        Args:
            person_id: Canonical IND-XXXXX identifier.
            note_id: Canonical NOT-XXXXX note identifier.

        Returns:
            True if note was found and excised; False otherwise.

        Raises:
            KeyError: If person_id does not exist in registry.
        """
        if person_id not in self._people:
            raise KeyError(f"Person '{person_id}' does not exist in registry.")

        record = self._people[person_id]
        collection = GDANoteCollection(notes_data=record.get("notes", []))
        removed = collection.remove(note_id)
        if removed:
            record["notes"] = collection.to_list()
            record["last_updated"] = GDAUtil.iso_now()
            self.dirty_ids.add(person_id)
            self._is_dirty = True
            return True
        return False

    def save(
        self,
        output_path: Optional[Union[str, Path]] = None,
        force: bool = False,
        create_backup: bool = True,
    ) -> bool:
        """Persist registered people to JSON using Safe Backup Protocol.

        Args:
            output_path: Optional destination path override. Defaults to configured filepath.
            force: If True, commits write even if is_dirty is False.
            create_backup: If True, creates a pre-write backup snapshot. Defaults to True.

        Returns:
            True if write occurred; False if skipped due to clean state without force.
        """
        if not self.is_dirty and not force:
            return False

        target = Path(output_path) if output_path else self._filepath
        should_backup = create_backup if target == self._filepath else False

        self._registry_metadata["last_modified"] = GDAUtil.iso_now()
        self._registry_metadata["total_people"] = len(self._people)

        payload = dict(self._registry_metadata)

        def _sort_key(item: Dict[str, Any]) -> tuple[int, str]:
            pid = item.get("person_id", "")
            match = IND_ID_PATTERN.match(pid)
            if match:
                return (0, f"{int(match.group(1)):010d}")
            return (1, pid)

        combined_people = list(self._people.values()) + list(self._graveyard.values())
        sorted_people = sorted(combined_people, key=_sort_key)
        payload["people"] = sorted_people

        GDAUtil.save_json(
            file_path=target,
            data=payload,
            indent=2,
            create_backup=should_backup,
            backup_dir=self._config.backups,
        )

        if target == self._filepath:
            self.dirty_ids.clear()
            self._is_dirty = False
        return True