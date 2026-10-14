# Name: locations.py
# Path: tools/lib/gdadomain/src/gdadomain/locations.py
# Version: 1.0.0+build.r1

"""Master civil jurisdiction and administrative boundary registry manager.

Operational Role:
    Manages data/entities/locations.json with transactional safe backups,
    strictly system-minted sequential LOC-XXXXX identifier allocation,
    soft-delete record deprecation into an internal graveyard partition,
    US state normalization (via 'us' package), GDADates boundary integration,
    vocabulary validation via instantiated GDAVocabularyManager, consolidation
    (merge) with site cascading, and multi-field fuzzy discovery via GDAUtil.
"""

from __future__ import annotations

import copy
import fnmatch
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
from collections.abc import Collection, Iterator
import us

from gdacore.config import CONFIG, GDAConfig
from gdacore.introspectable import IntrospectableMixin
from gdacore.logger import GDALogger
from gdacore.reference_manager import GDAReferenceManager
from gdacore.util import GDANoteCollection, GDAUtil
from gdacore.vocabulary_manager import GDAVocabularyManager
from gdadomain.dates import GDADates

__version__ =  "1.0.0+build.r1"

LOC_ID_PATTERN: re.Pattern[str] = re.compile(r"^LOC-(\d{5})$")
VOCAB_MGR = GDAVocabularyManager()


class GDALocations(IntrospectableMixin, Collection[Dict[str, Any]]):
    """Authoritative domain manager for civil jurisdictions and locations.

    Attributes:
        ALLOWED_PROPERTIES: Frozenset of top-level record keys permissible in edit mutations.
        is_dirty: Return True if in-memory mutations remain unpersisted to disk.
        count: Return count of active location records in memory.
        total_count: Return total count of all location records across active and graveyard partitions.
        graveyard: Return deep copy of all graveyard tombstones keyed by location_id.
    """

    ALLOWED_PROPERTIES: frozenset[str] = frozenset({
        "canonical_name",
        "aliases",
        "jurisdiction",
        "temporal_validity",
        "historical_periods",
        "notes",
        "operational_status",
        "is_deprecated",
        "superseded_by",
        "dissolution_date",
    })

    def __init__(
        self,
        filepath: Optional[Union[str, Path]] = None,
        config: Optional[GDAConfig] = None,
    ) -> None:
        """Initialize the locations domain manager.

        Args:
            filepath: Optional path to the locations JSON backing file. Defaults to
                canonical locations.json configured in GDAConfig.
            config: Optional GDAConfig instance override. Defaults to global CONFIG.
        """
        self._config = config or CONFIG
        self._logger = GDALogger.get_logger("gda_locations")
        self._filepath = Path(filepath) if filepath else self._config.entities / "locations.json"

        self._locations: Dict[str, Dict[str, Any]] = {}
        self._graveyard: Dict[str, Dict[str, Any]] = {}
        self._max_location_num: int = 0
        self._is_dirty: bool = False

        self.load()

    @property
    def is_dirty(self) -> bool:
        """Return True if in-memory mutations remain unpersisted to disk.

        Returns:
            True if unsaved modifications exist in memory; False otherwise.
        """
        return self._is_dirty

    @property
    def count(self) -> int:
        """Return count of active location records in memory.

        Returns:
            Integer count of active, non-deprecated locations.
        """
        return len(self._locations)

    @property
    def total_count(self) -> int:
        """Return total count of all location records (active and graveyard).

        Returns:
            Integer sum of active records and graveyard tombstones.
        """
        return len(self._locations) + len(self._graveyard)

    @property
    def graveyard(self) -> Dict[str, Dict[str, Any]]:
        """Return deep copy of all graveyard tombstones keyed by location_id.

        Returns:
            Dictionary mapping tombstone location IDs to deep-copied record dictionaries.
        """
        return copy.deepcopy(self._graveyard)

    def __len__(self) -> int:
        """Return the count of active location entities.

        Returns:
            Total active record count excluding graveyard tombstones.
        """
        return self.count

    def __contains__(self, location_id: Any) -> bool:
        """Check active registry membership for a location identifier.

        Args:
            location_id: Identifier token to test for active presence.

        Returns:
            True if location_id represents an active entity; False otherwise.
        """
        if not isinstance(location_id, str):
            return False
        return self.exists(location_id, include_graveyard=False)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate strictly over active, non-deprecated locations.

        Yields:
            Deep copies of active location entity dictionaries.
        """
        for loc in self._locations.values():
            yield copy.deepcopy(loc)

    def __getitem__(self, location_id: str) -> Dict[str, Any]:
        """Retrieve an active location by ID with transparent graveyard redirection.

        Args:
            location_id: Canonical LOC-XXXXX identifier.

        Returns:
            Deep-copied record dictionary matching the identifier or its canonical successor.

        Raises:
            KeyError: If location_id is unregistered or resolves to a defunct tombstone without successor.
        """
        loc = self.get_by_id(location_id, resolve_redirects=True)
        if loc is None:
            raise KeyError(f"Location ID '{location_id}' not found in active registry or resolvable graveyard.")
        return loc

    def load(self) -> None:
        """Load and partition location records from disk into active and graveyard stores.

        Raises:
            Exception: If reading or parsing the underlying JSON file fails.
        """
        if not self._filepath.exists():
            self._logger.warning(f"[LOC] File not found: {self._filepath}; initializing empty envelope.")
            self._locations = {}
            self._graveyard = {}
            self._max_location_num = 0
            self._is_dirty = True
            return

        try:
            payload: Dict[str, Any] = GDAUtil.load_json(self._filepath)
            raw_locations: List[Dict[str, Any]] = payload.get("locations", [])
            self._locations = {}
            self._graveyard = {}

            for loc in raw_locations:
                lid = loc.get("location_id", "")
                if not lid:
                    continue
                if loc.get("is_deprecated", False):
                    self._graveyard[lid] = loc
                else:
                    self._locations[lid] = loc

            all_ids = list(self._locations.keys()) + list(self._graveyard.keys())
            self._max_location_num = GDAUtil.find_max_numeric_id(all_ids)
            self._is_dirty = False
            self._logger.info(
                f"[LOC] Loaded {len(self._locations)} active locations and {len(self._graveyard)} "
                f"graveyard tombstones from {self._filepath.name} (Max LOC: {self._max_location_num:05d})."
            )
        except Exception as exc:
            self._logger.error(f"[LOC] Failed loading {self._filepath}: {exc}")
            raise

    def refresh(self) -> None:
        """Discard unstaged memory mutations and reload state cleanly from disk."""
        self.load()

    def resolve_id(self, location_id: str) -> Optional[str]:
        """Trace deprecation redirect chain through graveyard to canonical active ID.

        Args:
            location_id: Initial location identifier to evaluate.

        Returns:
            Active canonical LOC-XXXXX string if resolved; None if target is defunct,
            unregistered, or trapped in a circular loop.
        """
        try:
            target = GDAUtil.resolve_superseded_id(
                entity_id=location_id,
                graveyard=self._graveyard,
            )
        except RecursionError:
            self._logger.warning(f"[LOC] Circular graveyard redirect detected for '{location_id}'.")
            return None

        return target if (target and target in self._locations) else None

    def exists(self, location_id: str, include_graveyard: bool = False) -> bool:
        """Return True if location_id exists in registry.

        Args:
            location_id: Canonical LOC-XXXXX identifier.
            include_graveyard: If True, returns True if ID exists as a graveyard tombstone.

        Returns:
            True if entity is registered within designated scope; False otherwise.
        """
        if location_id in self._locations:
            return True
        if include_graveyard and location_id in self._graveyard:
            return True
        return False

    def get_by_id(
        self,
        location_id: str,
        include_graveyard: bool = False,
        resolve_redirects: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve location entity record by ID with optional graveyard redirection.

        Args:
            location_id: Canonical LOC-XXXXX identifier.
            include_graveyard: If True and record is not redirected, returns tombstone payload.
            resolve_redirects: If True, traces superseded_by chains to the active record.

        Returns:
            Deep-copied record dictionary if located; None otherwise.
        """
        if location_id in self._locations:
            return copy.deepcopy(self._locations[location_id])

        if resolve_redirects:
            canonical_id = self.resolve_id(location_id)
            if canonical_id and canonical_id in self._locations:
                return copy.deepcopy(self._locations[canonical_id])

        if include_graveyard and location_id in self._graveyard:
            return copy.deepcopy(self._graveyard[location_id])

        return None

    def iter_graveyard(self) -> Iterator[Dict[str, Any]]:
        """Yield all soft-deleted/deprecated location tombstones.

        Yields:
            Deep copies of tombstoned graveyard record dictionaries.
        """
        for loc in self._graveyard.values():
            yield copy.deepcopy(loc)

    def iter_all(self) -> Iterator[Dict[str, Any]]:
        """Yield all location records across both active registry and graveyard.

        Yields:
            Deep copies of every active and tombstoned location record.
        """
        for loc in self._locations.values():
            yield copy.deepcopy(loc)
        for loc in self._graveyard.values():
            yield copy.deepcopy(loc)

    @staticmethod
    def _strip_county_suffix(county: Optional[str]) -> str:
        """Normalize county strings by trimming whitespace and removing trailing 'county'.

        Args:
            county: Raw county string or None.

        Returns:
            Lowercased base county string without 'county' suffix, or empty string.
        """
        if not county or not isinstance(county, str):
            return ""
        c = county.strip().lower()
        if c.endswith(" county"):
            return c[:-7].strip()
        return c

    @classmethod
    def _matches_jurisdiction(
        cls,
        candidate_jur: Dict[str, Any],
        country: Optional[str] = None,
        state_or_province: Optional[str] = None,
        county: Optional[str] = None,
        local_jurisdiction: Optional[str] = None,
    ) -> bool:
        """Evaluate if candidate jurisdiction matches query constraints.

        Args:
            candidate_jur: Jurisdiction dict of candidate record.
            country: National jurisdiction filter.
            state_or_province: State or province filter.
            county: County or regional district filter.
            local_jurisdiction: Municipal jurisdiction filter.

        Returns:
            True if all provided constraints match; False otherwise.
        """
        if country:
            cand_country = candidate_jur.get("country", "").strip().lower()
            if cand_country != country.strip().lower():
                return False

        if state_or_province:
            norm_st = cls.normalize_state(candidate_jur.get("country", ""), state_or_province)
            cur_st = (candidate_jur.get("state_or_province") or "").strip().lower()
            if not norm_st or cur_st != norm_st.lower():
                return False

        if county:
            cur_county = candidate_jur.get("county")
            cur_c_base = cls._strip_county_suffix(cur_county)
            req_c_base = cls._strip_county_suffix(county)
            if cur_c_base != req_c_base:
                return False

        if local_jurisdiction:
            cur_local = (candidate_jur.get("local_jurisdiction") or "").strip().lower()
            if cur_local != local_jurisdiction.strip().lower():
                return False

        return True

    @staticmethod
    def _clean_aliases(aliases: Optional[Iterable[Any]]) -> List[str]:
        """Sanitize an iterable of alias objects into non-empty, stripped strings.

        Args:
            aliases: Raw collection of candidate alias strings or objects.

        Returns:
            List of valid, non-empty, stripped string aliases.
        """
        cleaned: List[str] = []
        if not aliases:
            return cleaned

        for item in aliases:
            if isinstance(item, str):
                val = item.strip()
                if val:
                    cleaned.append(val)
        return cleaned

    @staticmethod
    def normalize_state(country: str, state_or_province: Optional[str]) -> Optional[str]:
        """Normalize United States state names and abbreviations.

        Args:
            country: Jurisdiction country string.
            state_or_province: State or province name, abbreviation, or None.

        Returns:
            Normalized full official state name for US jurisdictions; unchanged string
            for non-US or unrecognized regions; None if input is empty or None.
        """
        if not state_or_province:
            return None
        clean_state = state_or_province.strip()
        clean_country = country.strip().upper()

        if clean_country in ("USA", "UNITED STATES", "UNITED STATES OF AMERICA"):
            lookup = us.states.lookup(clean_state)
            if lookup:
                return lookup.name
        return clean_state

    @staticmethod
    def build_canonical_name(
        country: str,
        state_or_province: Optional[str] = None,
        county: Optional[str] = None,
        local_jurisdiction: Optional[str] = None,
    ) -> str:
        """Construct standard comma-delimited jurisdiction canonical name.

        Args:
            country: National jurisdiction (e.g., USA).
            state_or_province: Normalized state or province name.
            county: County or regional district name.
            local_jurisdiction: Municipal entity (borough, township, city).

        Returns:
            Comma-delimited canonical string hierarchical from local to country.
        """
        parts = []
        if local_jurisdiction:
            parts.append(local_jurisdiction.strip())
        if county:
            c = county.strip()
            if not c.lower().endswith("county"):
                c = f"{c} County"
            parts.append(c)
        if state_or_province:
            parts.append(state_or_province.strip())
        if country:
            parts.append(country.strip())
        return ", ".join(parts)

    def _mint_next_id(self) -> str:
        """Auto-mint sequential LOC-XXXXX identifier using monotonic high-water mark.

        Returns:
            Formally minted LOC-XXXXX identifier string.
        """
        if self._max_location_num == 0:
            all_ids = list(self._locations.keys()) + list(self._graveyard.keys())
            self._max_location_num = GDAUtil.find_max_numeric_id(all_ids)
        self._max_location_num += 1
        return f"LOC-{self._max_location_num:05d}"

    def add(
        self,
        country: str,
        state_or_province: Optional[str] = None,
        county: Optional[str] = None,
        local_jurisdiction: Optional[str] = None,
        canonical_name: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        date_established: Optional[str] = None,
        date_dissolved: Optional[str] = None,
        predecessor_location_id: Optional[str] = None,
        successor_location_id: Optional[str] = None,
        notes: Optional[List[Dict[str, Any]]] = None,
        operational_status: str = "ACTIVE",
    ) -> str:
        """Add a new civil location entity with strictly system-minted sequential LOC-XXXXX.

        Args:
            country: Primary national authority (mandatory).
            state_or_province: State or province name or abbreviation.
            county: County or regional administrative jurisdiction.
            local_jurisdiction: Municipal jurisdiction (township, borough, parish).
            canonical_name: Explicit canonical name override. If omitted, built automatically.
            aliases: Alternate names, colloquial designations, or historic spellings.
            date_established: ISO 8601 date or year boundary of jurisdiction creation.
            date_dissolved: ISO 8601 date or year boundary of jurisdiction dissolution.
            predecessor_location_id: Valid LOC-XXXXX identifier for parent entity.
            successor_location_id: Valid LOC-XXXXX identifier for successor entity.
            notes: List of annotation dicts to append.
            operational_status: Controlled vocabulary status. Defaults to 'ACTIVE'.

        Returns:
            The canonical location_id assigned to the new record.

        Raises:
            ValueError: If country is empty, operational_status is invalid, predecessor/successor
                ID syntax is invalid, or notes payload is malformed.
        """
        clean_country = country.strip() if isinstance(country, str) else ""
        if not clean_country:
            raise ValueError("Country must not be empty.")

        clean_state = self.normalize_state(clean_country, state_or_province)
        
        clean_county: Optional[str] = None
        if isinstance(county, str) and county.strip():
            clean_county = county.strip()

        clean_local: Optional[str] = None
        if isinstance(local_jurisdiction, str) and local_jurisdiction.strip():
            clean_local = local_jurisdiction.strip()

        if isinstance(canonical_name, str) and canonical_name.strip():
            c_name = canonical_name.strip()
        else:
            c_name = self.build_canonical_name(
                country=clean_country,
                state_or_province=clean_state,
                county=clean_county,
                local_jurisdiction=clean_local,
            )

        assigned_id = self._mint_next_id()

        if predecessor_location_id:
            if not GDAReferenceManager.is_valid_gda_id(predecessor_location_id, "LOCATION"):
                raise ValueError(f"Malformed predecessor_location_id: '{predecessor_location_id}'")

        if successor_location_id:
            if not GDAReferenceManager.is_valid_gda_id(successor_location_id, "LOCATION"):
                raise ValueError(f"Malformed successor_location_id: '{successor_location_id}'")

        if operational_status not in VOCAB_MGR["operational_status"]:
            allowed_statuses = sorted(VOCAB_MGR["operational_status"])
            raise ValueError(f"Invalid operational_status '{operational_status}'. Allowed: {allowed_statuses}")

        notes_collection = GDANoteCollection(notes_data=notes, valid_types=VOCAB_MGR["note_type"])
        clean_aliases = self._clean_aliases(aliases)

        record: Dict[str, Any] = {
            "location_id": assigned_id,
            "canonical_name": c_name,
            "aliases": clean_aliases,
            "jurisdiction": {
                "country": clean_country,
                "state_or_province": clean_state,
                "county": clean_county,
                "local_jurisdiction": clean_local,
            },
            "temporal_validity": {
                "date_established": date_established,
                "date_dissolved": date_dissolved,
                "predecessor_location_id": predecessor_location_id,
                "successor_location_id": successor_location_id,
            },
            "historical_periods": [],
            "operational_status": operational_status,
            "is_deprecated": False,
            "superseded_by": None,
            "dissolution_date": date_dissolved,
            "notes": notes_collection.to_list(),
            "last_updated": GDAUtil.iso_now(),
        }

        self._locations[assigned_id] = record
        self._is_dirty = True
        return assigned_id

    def edit(self, location_id: str, updates: Dict[str, Any], overwrite_none: bool = False) -> bool:
        """Update an existing active location entity.

        Args:
            location_id: Canonical LOC-XXXXX identifier.
            updates: Dictionary of schema properties to modify.
            overwrite_none: If True, explicitly overwrite existing values when dict key is None.

        Returns:
            True if one or more fields were modified; False if values were identical.

        Raises:
            KeyError: If location_id is not in active store or resides in graveyard.
            ValueError: If updates contain disallowed property keys, an empty canonical_name,
                or an invalid operational_status value.
        """
        if location_id not in self._locations:
            if location_id in self._graveyard:
                raise KeyError(f"Cannot edit deprecated location '{location_id}' residing in graveyard.")
            raise KeyError(f"Location '{location_id}' does not exist in registry.")

        disallowed_keys = set(updates.keys()) - self.ALLOWED_PROPERTIES - {"location_id"}
        if disallowed_keys:
            raise ValueError(f"Disallowed property updates for location: {sorted(disallowed_keys)}")

        record = self._locations[location_id]
        modified = False

        if "canonical_name" in updates:
            c_name = updates["canonical_name"].strip() if isinstance(updates["canonical_name"], str) else ""
            if not c_name:
                raise ValueError("canonical_name must not be empty.")
            if record["canonical_name"] != c_name:
                record["canonical_name"] = c_name
                modified = True

        if "aliases" in updates:
            new_aliases = self._clean_aliases(updates.get("aliases"))
            if record["aliases"] != new_aliases:
                record["aliases"] = new_aliases
                modified = True

        if "operational_status" in updates:
            new_status = updates["operational_status"]
            if new_status not in VOCAB_MGR["operational_status"]:
                raise ValueError(f"Invalid operational_status '{new_status}'.")
            if record.get("operational_status") != new_status:
                record["operational_status"] = new_status
                modified = True

        if "jurisdiction" in updates:
            jur = updates["jurisdiction"]
            cur_jur = record["jurisdiction"]

            if "country" in jur:
                new_country = jur["country"]
                if (new_country is not None or overwrite_none) and cur_jur.get("country") != new_country:
                    cur_jur["country"] = new_country
                    modified = True

            country_ref = cur_jur.get("country", "")
            if "state_or_province" in jur:
                raw_st = jur["state_or_province"]
                new_state = self.normalize_state(country_ref, raw_st) if raw_st is not None else None
                if (raw_st is not None or overwrite_none) and cur_jur.get("state_or_province") != new_state:
                    cur_jur["state_or_province"] = new_state
                    modified = True

            for field in ["county", "local_jurisdiction"]:
                if field in jur:
                    val = jur[field]
                    if (val is not None or overwrite_none) and cur_jur.get(field) != val:
                        cur_jur[field] = val
                        modified = True

        if "temporal_validity" in updates:
            temp = updates["temporal_validity"]
            cur_temp = record["temporal_validity"]
            for field in ["date_established", "date_dissolved", "predecessor_location_id", "successor_location_id"]:
                if field in temp:
                    val = temp[field]
                    if (val is not None or overwrite_none) and cur_temp.get(field) != val:
                        cur_temp[field] = val
                        modified = True

        if "notes" in updates:
            new_notes = GDANoteCollection(notes_data=updates["notes"], valid_types=VOCAB_MGR["note_type"]).to_list()
            if record.get("notes") != new_notes:
                record["notes"] = new_notes
                modified = True

        if updates.get("is_deprecated") is True:
            superseded_target = updates.get("superseded_by")
            self.delete(location_id, hard_delete=False, superseded_by=superseded_target)
            return True

        if modified:
            record["last_updated"] = GDAUtil.iso_now()
            self._is_dirty = True

        return modified

    def delete(self, location_id: str, hard_delete: bool = False, superseded_by: Optional[str] = None) -> bool:
        """Soft-delete an active location to the graveyard, or permanently purge from memory.

        Args:
            location_id: Canonical LOC-XXXXX identifier.
            hard_delete: If True, purges record entirely from active and graveyard memory.
            superseded_by: Optional LOC-XXXXX successor identifier for redirect tracking.

        Returns:
            True if location was found and deleted or updated; False if ID not found.

        Raises:
            ValueError: If superseded_by does not match LOC-XXXXX pattern.
            KeyError: If superseded_by ID is not registered in active or graveyard store.
        """
        if not self.exists(location_id, include_graveyard=True):
            return False

        if hard_delete:
            self._locations.pop(location_id, None)
            self._graveyard.pop(location_id, None)
            self._is_dirty = True
            return True

        if superseded_by:
            if not LOC_ID_PATTERN.match(superseded_by):
                raise ValueError(f"Invalid superseded_by location_id '{superseded_by}': must conform to '^LOC-\\d{{5}}$'.")
            if not self.exists(superseded_by, include_graveyard=True):
                raise KeyError(f"Target superseded_by location_id '{superseded_by}' not found in registry.")

        if location_id in self._graveyard:
            if superseded_by:
                self._graveyard[location_id]["superseded_by"] = superseded_by
                self._graveyard[location_id]["last_updated"] = GDAUtil.iso_now()
                self._is_dirty = True
            return True

        record = self._locations.pop(location_id)
        record["is_deprecated"] = True
        record["operational_status"] = "DEFUNCT"
        record["superseded_by"] = superseded_by
        record["last_updated"] = GDAUtil.iso_now()

        self._graveyard[location_id] = record
        self._is_dirty = True
        return True

    def add_alias(self, location_id: str, alias: str) -> bool:
        """Add an alternative name to an active location.

        Args:
            location_id: Canonical LOC-XXXXX identifier.
            alias: Non-empty alias string to register.

        Returns:
            True if alias was novel and appended; False if empty, non-string, or duplicate.

        Raises:
            KeyError: If location_id does not exist in active registry.
        """
        if location_id not in self._locations:
            raise KeyError(f"Location '{location_id}' does not exist in registry.")

        if isinstance(alias, str) and alias.strip():
            clean_alias = alias.strip()
        else:
            return False

        aliases: List[str] = self._locations[location_id].setdefault("aliases", [])
        if clean_alias not in aliases:
            aliases.append(clean_alias)
            self._locations[location_id]["last_updated"] = GDAUtil.iso_now()
            self._is_dirty = True
            return True
        return False

    def remove_alias(self, location_id: str, alias: str) -> bool:
        """Remove an alternative name from an active location.

        Args:
            location_id: Canonical LOC-XXXXX identifier.
            alias: Alias string to remove.

        Returns:
            True if alias was found and removed; False if alias did not exist or invalid.

        Raises:
            KeyError: If location_id does not exist in active registry.
        """
        if location_id not in self._locations:
            raise KeyError(f"Location '{location_id}' does not exist in registry.")

        if isinstance(alias, str) and alias.strip():
            clean_alias = alias.strip()
        else:
            return False

        aliases: List[str] = self._locations[location_id].get("aliases", [])
        if clean_alias in aliases:
            aliases.remove(clean_alias)
            self._locations[location_id]["last_updated"] = GDAUtil.iso_now()
            self._is_dirty = True
            return True
        return False

    def add_note(self, location_id: str, text: str, note_type: str = "RESEARCH") -> str:
        """Ergonomically append a new note entry to an active location.

        Args:
            location_id: Canonical LOC-XXXXX identifier.
            text: Non-empty annotation text.
            note_type: Note type category from controlled vocabulary. Defaults to 'RESEARCH'.

        Returns:
            Assigned NOT-XXXXX note identifier.

        Raises:
            KeyError: If location_id does not exist in active registry.
            ValueError: If text is empty, not a string, or note_type is invalid.
        """
        if location_id not in self._locations:
            raise KeyError(f"Active location ID '{location_id}' not found.")

        if not isinstance(text, str) or not text.strip():
            raise ValueError("Note text must be a non-empty string.")

        record = self._locations[location_id]
        collection = GDANoteCollection(
            notes_data=record.get("notes", []),
            valid_types=VOCAB_MGR["note_type"],
        )
        created_note = collection.add(note_text=text, note_type=note_type)
        record["notes"] = collection.to_list()
        record["last_updated"] = GDAUtil.iso_now()
        self._is_dirty = True
        return created_note.note_id

    def remove_note(self, location_id: str, note_id: str) -> bool:
        """Remove a note entry from an active location by its note_id.

        Args:
            location_id: Canonical LOC-XXXXX identifier.
            note_id: Canonical NOT-XXXXX note identifier.

        Returns:
            True if note was found and removed; False if note_id did not match.

        Raises:
            KeyError: If location_id does not exist in active registry.
        """
        if location_id not in self._locations:
            raise KeyError(f"Active location ID '{location_id}' not found.")

        record = self._locations[location_id]
        collection = GDANoteCollection(notes_data=record.get("notes", []))
        removed = collection.remove(note_id)

        if removed:
            record["notes"] = collection.to_list()
            record["last_updated"] = GDAUtil.iso_now()
            self._is_dirty = True
            return True
        return False

    def get_predecessor(self, location_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the predecessor location entity if recorded.

        Args:
            location_id: Canonical LOC-XXXXX identifier.

        Returns:
            Deep-copied entity record of the predecessor if found; None otherwise.
        """
        rec = self.get_by_id(location_id, include_graveyard=True, resolve_redirects=False)
        if not rec:
            return None
        pid = rec.get("temporal_validity", {}).get("predecessor_location_id")
        return self.get_by_id(pid, include_graveyard=True, resolve_redirects=True) if pid else None

    def get_successor(self, location_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the successor location entity if recorded.

        Args:
            location_id: Canonical LOC-XXXXX identifier.

        Returns:
            Deep-copied entity record of the successor if found; None otherwise.
        """
        rec = self.get_by_id(location_id, include_graveyard=True, resolve_redirects=False)
        if not rec:
            return None
        sid = rec.get("temporal_validity", {}).get("successor_location_id")
        return self.get_by_id(sid, include_graveyard=True, resolve_redirects=True) if sid else None

    def is_valid_at_date(self, location_id: str, date_iso: str) -> bool:
        """Verify whether target location was historically active at date_iso.

        Args:
            location_id: Canonical LOC-XXXXX identifier.
            date_iso: ISO 8601 date string, year string, or approximate date text.

        Returns:
            True if date falls between date_established and date_dissolved, or if
            boundaries are unrecorded or unparseable; False if definitively out of range.
        """
        rec = self.get_by_id(location_id, resolve_redirects=True)
        if not rec:
            return False
        temp = rec.get("temporal_validity", {})
        est = temp.get("date_established")
        dis = temp.get("date_dissolved")

        target_year = GDADates.extract_year(date_iso)
        if target_year is None:
            return True

        if est:
            est_year = GDADates.extract_year(est)
            if est_year is not None and target_year < est_year:
                return False
        if dis:
            dis_year = GDADates.extract_year(dis)
            if dis_year is not None and target_year > dis_year:
                return False
        return True

    def validate_location(self, location_data: Dict[str, Any]) -> List[str]:
        """Validate structural completeness and integrity of a location record.

        Args:
            location_data: Dictionary record payload to validate against rules.

        Returns:
            List of violation strings describing detected defects, empty if compliant.
        """
        violations: List[str] = []

        if not isinstance(location_data, dict):
            return ["Location payload must be a dictionary."]

        lid = location_data.get("location_id")
        if not lid or not GDAReferenceManager.is_valid_gda_id(str(lid), "LOCATION"):
            violations.append(f"Invalid or missing location_id: '{lid}'")

        cname = location_data.get("canonical_name")
        if not isinstance(cname, str) or not cname.strip():
            violations.append("canonical_name must be a non-empty string.")

        jur = location_data.get("jurisdiction")
        if not isinstance(jur, dict):
            violations.append("jurisdiction must be a dictionary.")
        else:
            country = jur.get("country")
            if not isinstance(country, str) or not country.strip():
                violations.append("jurisdiction country must be a non-empty string.")

        temp = location_data.get("temporal_validity")
        if temp is not None:
            if not isinstance(temp, dict):
                violations.append("temporal_validity must be a dictionary.")
            else:
                est = temp.get("date_established")
                dis = temp.get("date_dissolved")
                pred = temp.get("predecessor_location_id")
                succ = temp.get("successor_location_id")

                if pred:
                    if not GDAReferenceManager.is_valid_gda_id(pred, "LOCATION"):
                        violations.append(f"Invalid predecessor_location_id: '{pred}'")
                    elif pred == lid:
                        violations.append("predecessor_location_id cannot reference own location_id.")

                if succ:
                    if not GDAReferenceManager.is_valid_gda_id(succ, "LOCATION"):
                        violations.append(f"Invalid successor_location_id: '{succ}'")
                    elif succ == lid:
                        violations.append("successor_location_id cannot reference own location_id.")

                if est and dis:
                    y_est = GDADates.extract_year(est)
                    y_dis = GDADates.extract_year(dis)
                    if y_est is not None and y_dis is not None and y_est > y_dis:
                        violations.append(f"date_established ({est}) cannot be later than date_dissolved ({dis}).")

        aliases = location_data.get("aliases")
        if aliases is not None:
            if not isinstance(aliases, list):
                violations.append("Aliases must be a list of strings.")
            else:
                for a in aliases:
                    if not isinstance(a, str) or not a.strip():
                        violations.append("All alias entries must be non-empty strings.")
                        break

        return violations

    def validate_all(self) -> Dict[str, List[str]]:
        """Validate all active locations, returning dictionary mapping location_id to violations.

        Returns:
            Dictionary mapping invalid location IDs to their list of defect strings.
        """
        results: Dict[str, List[str]] = {}
        for lid, loc in self._locations.items():
            errs = self.validate_location(loc)
            if errs:
                results[lid] = errs
        return results

    def merge_locations(
        self,
        primary_id: str,
        *secondary_ids: str,
        sites_provider: Optional[Any] = None,
        keep_secondary_aliases: bool = True,
    ) -> Dict[str, Any]:
        """Merge one or more secondary locations into a primary location.

        Args:
            primary_id: Canonical LOC-XXXXX identifier retaining master authority.
            *secondary_ids: One or more LOC-XXXXX identifiers to absorb and deprecate.
            sites_provider: Optional provider object implementing repoint_locations()
                to cascade foreign key reassignments across sites.json.
            keep_secondary_aliases: If True, preserves secondary aliases on primary entity.

        Returns:
            Deep copy of the consolidated primary location entity dictionary.

        Raises:
            KeyError: If primary_id or any secondary_id does not exist in active registry.
            ValueError: If secondary_ids is empty or contains primary_id directly.
        """
        if primary_id not in self._locations:
            raise KeyError(f"Primary location '{primary_id}' not found in registry.")

        clean_secondaries = [s.strip() for s in secondary_ids if s.strip()]
        if not clean_secondaries:
            raise ValueError("At least one secondary location_id must be provided for merge.")

        primary = self._locations[primary_id]
        primary_jur = primary["jurisdiction"]
        primary_temp = primary["temporal_validity"]
        merged_ids: List[str] = []

        primary_notes_collection = GDANoteCollection(
            notes_data=primary.get("notes", []),
            valid_types=VOCAB_MGR["note_type"],
        )

        for sec_id in clean_secondaries:
            if sec_id == primary_id:
                raise ValueError(f"Cannot merge primary location '{primary_id}' into itself.")
            if sec_id not in self._locations:
                raise KeyError(f"Secondary location '{sec_id}' not found in registry.")

            sec = self._locations[sec_id]
            merged_ids.append(sec_id)

            if sec["canonical_name"] != primary["canonical_name"] and sec["canonical_name"] not in primary["aliases"]:
                primary["aliases"].append(sec["canonical_name"])

            if keep_secondary_aliases:
                for alias in sec.get("aliases", []):
                    if alias not in primary["aliases"] and alias != primary["canonical_name"]:
                        primary["aliases"].append(alias)

            sec_jur = sec.get("jurisdiction", {})
            for field in ["state_or_province", "county", "local_jurisdiction"]:
                if primary_jur.get(field) is None and sec_jur.get(field) is not None:
                    primary_jur[field] = sec_jur[field]

            sec_temp = sec.get("temporal_validity", {})
            for field in ["date_established", "date_dissolved", "predecessor_location_id", "successor_location_id"]:
                if primary_temp.get(field) is None and sec_temp.get(field) is not None:
                    primary_temp[field] = sec_temp[field]

            for note in sec.get("notes", []):
                n_text = note.get("note_text") or note.get("text") or ""
                candidate_type = note.get("note_type") or note.get("type") or note.get("category")
                n_type = candidate_type if candidate_type in VOCAB_MGR["note_type"] else "RESEARCH"
                n_date = note.get("modified_date") or note.get("created_at")
                if n_text:
                    primary_notes_collection.add(note_text=n_text, note_type=n_type, modified_date=n_date)

            self.delete(sec_id, hard_delete=False, superseded_by=primary_id)

        repointed_sites_count = 0
        if sites_provider is not None:
            repoint_func = getattr(sites_provider, "repoint_locations", None)
            if callable(repoint_func):
                repointed_sites_count = repoint_func(primary_id, merged_ids)

        audit_text = (
            f"Merged duplicate locations {merged_ids} into {primary_id} on "
            f"{GDAUtil.iso_now()}. Cascaded {repointed_sites_count} sites."
        )
        primary_notes_collection.add(note_text=audit_text, note_type="RESEARCH")
        primary["notes"] = primary_notes_collection.to_list()
        primary["last_updated"] = GDAUtil.iso_now()
        self._is_dirty = True

        return copy.deepcopy(primary)

    def find_by_jurisdiction(
        self,
        country: str,
        state_or_province: Optional[str] = None,
        county: Optional[str] = None,
        local_jurisdiction: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Exact match search across hierarchical civil jurisdictions.

        Args:
            country: Required country name to match.
            state_or_province: Optional state/province name or abbreviation.
            county: Optional county name (matches with or without 'County' suffix).
            local_jurisdiction: Optional township, borough, or city name.

        Returns:
            Deep-copied record dictionary if an exact jurisdiction match is found; None otherwise.
        """
        for item in self._locations.values():
            if self._matches_jurisdiction(
                candidate_jur=item["jurisdiction"],
                country=country,
                state_or_province=state_or_province,
                county=county,
                local_jurisdiction=local_jurisdiction,
            ):
                return copy.deepcopy(item)
        return None

    def search(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        state_or_province: Optional[str] = None,
        county: Optional[str] = None,
        include_graveyard: bool = False,
        use_fuzzy: bool = True,
        fuzzy_threshold: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """Filter and search locations across active records and optionally the graveyard.

        Args:
            query: Free-text search term or wildcard glob (*, ?, []).
            country: Filter results strictly by national jurisdiction.
            state_or_province: Filter results strictly by state/province boundary.
            county: Filter results strictly by county boundary.
            include_graveyard: If True, searches graveyard tombstones alongside active records.
            use_fuzzy: If True, evaluates difflib fuzzy string similarity.
            fuzzy_threshold: Minimum SequenceMatcher similarity ratio (0.0 to 1.0).

        Returns:
            List of deep-copied matching location records sorted descending by relevance score.
        """
        scored_matches: List[Tuple[float, Dict[str, Any]]] = []
        clean_query = query.strip().lower() if query else None

        candidates = list(self._locations.values())
        if include_graveyard:
            candidates.extend(list(self._graveyard.values()))

        for item in candidates:
            jur = item.get("jurisdiction", {})
            if not self._matches_jurisdiction(
                candidate_jur=jur,
                country=country,
                state_or_province=state_or_province,
                county=county,
            ):
                continue

            if not clean_query:
                scored_matches.append((1.0, copy.deepcopy(item)))
                continue

            cand_strings = (
                [item["canonical_name"]]
                + [c for c in [jur.get("local_jurisdiction"), jur.get("county")] if c]
                + item.get("aliases", [])
            )
            matched = False
            best_score = 0.0

            for cand in cand_strings:
                cand_lower = cand.lower()
                if any(char in clean_query for char in ["*", "?", "["]):
                    if fnmatch.fnmatch(cand_lower, clean_query):
                        matched = True
                        best_score = max(best_score, 1.0)
                        break
                elif clean_query == cand_lower:
                    matched = True
                    best_score = max(best_score, 1.0)
                    break
                elif clean_query in cand_lower:
                    matched = True
                    score = len(clean_query) / len(cand_lower)
                    best_score = max(best_score, score)
                elif use_fuzzy and GDAUtil.match_text(clean_query, cand_lower, min_ratio=fuzzy_threshold):
                    matched = True
                    best_score = max(best_score, fuzzy_threshold)

            if matched:
                scored_matches.append((best_score, copy.deepcopy(item)))

        if clean_query:
            scored_matches.sort(key=lambda x: x[0], reverse=True)

        return [item for _, item in scored_matches]

    def find_one(
        self,
        query: str,
        country: Optional[str] = None,
        state_or_province: Optional[str] = None,
        county: Optional[str] = None,
        include_graveyard: bool = False,
        fuzzy_threshold: float = 0.85,
    ) -> Optional[Dict[str, Any]]:
        """Find the single closest matching location entity.

        Args:
            query: Free-text search term or pattern.
            country: Optional national jurisdiction filter.
            state_or_province: Optional state/province filter.
            county: Optional county filter.
            include_graveyard: If True, evaluates graveyard tombstones as candidates.
            fuzzy_threshold: Minimum SequenceMatcher similarity ratio. Defaults to 0.85.

        Returns:
            The single highest-scoring deep-copied record dictionary, or None if no match.
        """
        clean_query = query.strip() if query else ""
        if not clean_query:
            return None

        candidates = self.search(
            query=clean_query,
            country=country,
            state_or_province=state_or_province,
            county=county,
            include_graveyard=include_graveyard,
            use_fuzzy=True,
            fuzzy_threshold=fuzzy_threshold,
        )
        return candidates[0] if candidates else None

    def save(
        self,
        output_path: Optional[Union[str, Path]] = None,
        force: bool = False,
        create_backup: bool = True,
    ) -> bool:
        """Persist active locations and graveyard tombstones to disk under Safe Backup Protocol.

        Args:
            output_path: Optional explicit output destination. Defaults to configured backing file.
            force: If True, writes to disk even when is_dirty is False.
            create_backup: If True, creates an atomic backup copy before committing write.

        Returns:
            True if persistence occurred; False if skipped due to clean state without force.

        Raises:
            Exception: If an underlying filesystem or serialization error occurs.
        """
        if not self._is_dirty and not force:
            self._logger.info("[LOC] No memory mutations detected; save skipped.")
            return False

        target_file = Path(output_path) if output_path else self._filepath
        combined_locations = list(self._locations.values()) + list(self._graveyard.values())
        sorted_locations = sorted(combined_locations, key=lambda loc: str(loc.get("location_id", "")))

        payload: Dict[str, Any] = {
            "_name": target_file.name,
            "_path": target_file.as_posix(),
            "$schema": "schemas/entities/location_registry.schema.json",
            "schema_version": "1.2.0",
            "last_updated": GDAUtil.iso_now(),
            "total_locations": len(sorted_locations),
            "locations": sorted_locations,
        }

        GDAUtil.save_json(
            file_path=target_file,
            data=payload,
            indent=2,
            create_backup=create_backup,
            backup_dir=self._config.backups,
        )

        self._is_dirty = False
        self._logger.info(
            f"[LOC] Persisted {len(sorted_locations)} records ({len(self._locations)} active, "
            f"{len(self._graveyard)} graveyard) to {target_file.as_posix()}."
        )
        return True