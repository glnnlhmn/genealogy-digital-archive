# Name: sites.py
# Path: tools/lib/gdadomain/src/gdadomain/sites.py
# Version: 1.0.0+build.r1

"""Master physical site, landmark, cemetery, and facility directory manager.

Operational Role:
    Manages data/entities/sites.json with transactional safe backups,
    strictly system-minted sequential SID-XXXXX identifier allocation,
    soft-delete record deprecation into an internal graveyard partition,
    mandatory foreign key synchronization against GDALocations via loc,
    normalized note/address builders, vocabulary validation via instantiated
    GDAVocabularyManager, and multi-field fuzzy discovery via GDAUtil.
"""

from __future__ import annotations

import copy
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Union
from collections.abc import Collection, Iterator, Sequence

from gdacore.config import CONFIG, GDAConfig
from gdacore.introspectable import IntrospectableMixin
from gdacore.logger import GDALogger
from gdacore.util import GDANoteCollection, GDAUtil
from gdacore.vocabulary_manager import GDAVocabularyManager

__version__ = "1.0.0+build.r1"

SID_ID_PATTERN: re.Pattern[str] = re.compile(r"^SID-(\d{5})$")
VOCAB_MGR = GDAVocabularyManager()


class GDASites(IntrospectableMixin, Collection[Dict[str, Any]]):
    """Authoritative domain manager for physical sites and landmarks.

    Attributes:
        ALLOWED_PROPERTIES: Frozenset of top-level record keys permissible in edit mutations.
        is_dirty: Return True if in-memory mutations remain unpersisted to disk.
        count: Return count of active site records in memory.
        total_count: Return total count of all site records across active and graveyard partitions.
        graveyard: Return deep copy of all graveyard tombstones keyed by site_id.
    """

    ALLOWED_PROPERTIES: frozenset[str] = frozenset({
        "site_type",
        "name",
        "aliases",
        "location_id",
        "address",
        "operational_status",
        "is_deprecated",
        "superseded_by",
        "dissolution_date",
        "notes",
    })

    def __init__(
        self,
        locations_provider: Any,
        filepath: Optional[Union[str, Path]] = None,
        config: Optional[GDAConfig] = None,
    ) -> None:
        """Initialize the physical sites domain manager with foreign key synchronization.

        Args:
            locations_provider: Authority implementing the exists(location_id) protocol
                for foreign key validation (typically an instantiated GDALocations manager).
            filepath: Optional path to the sites JSON backing file. Defaults to
                canonical sites.json configured in GDAConfig.
            config: Optional GDAConfig instance override. Defaults to global CONFIG.

        Raises:
            ValueError: If locations_provider is None or fails to implement the exists() method.
        """
        self._config = config or CONFIG
        self._logger = GDALogger.get_logger("gda_sites")
        self._filepath = Path(filepath) if filepath else self._config.entities / "sites.json"

        if locations_provider is None or not hasattr(locations_provider, "exists"):
            self._logger.error("[SITES] Failed to load locations_provider; must implement exists().")
            raise ValueError(
                "GDASites requires a valid locations_provider implementing the exists(location_id) protocol."
            )

        self._loc = locations_provider
        self._logger.info("[SITES] locations_provider (aliased as loc) successfully loaded.")

        self._sites: Dict[str, Dict[str, Any]] = {}
        self._graveyard: Dict[str, Dict[str, Any]] = {}
        self._max_site_num: int = 0
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
        """Return count of active site records in memory.

        Returns:
            Integer count of active, non-deprecated sites.
        """
        return len(self._sites)

    @property
    def total_count(self) -> int:
        """Return total count of all site records (active and graveyard).

        Returns:
            Integer sum of active records and graveyard tombstones.
        """
        return len(self._sites) + len(self._graveyard)

    @property
    def graveyard(self) -> Dict[str, Dict[str, Any]]:
        """Return deep copy of all graveyard tombstones keyed by site_id.

        Returns:
            Dictionary mapping tombstone site IDs to deep-copied record dictionaries.
        """
        return copy.deepcopy(self._graveyard)

    def __len__(self) -> int:
        """Return the count of active site entities.

        Returns:
            Total active record count excluding graveyard tombstones.
        """
        return self.count

    def __contains__(self, site_id: Any) -> bool:
        """Check active registry membership for a site identifier.

        Args:
            site_id: Identifier token to test for active presence.

        Returns:
            True if site_id represents an active entity; False otherwise.
        """
        if not isinstance(site_id, str):
            return False
        return self.exists(site_id, include_graveyard=False)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate strictly over active, non-deprecated sites.

        Yields:
            Deep copies of active site entity dictionaries.
        """
        for site in self._sites.values():
            yield copy.deepcopy(site)

    def __getitem__(self, site_id: str) -> Dict[str, Any]:
        """Retrieve an active site by ID with transparent graveyard redirection.

        Args:
            site_id: Canonical SID-XXXXX identifier.

        Returns:
            Deep-copied record dictionary matching the identifier or its canonical successor.

        Raises:
            KeyError: If site_id is unregistered or resolves to a defunct tombstone without successor.
        """
        site = self.get_by_id(site_id, resolve_redirects=True)
        if site is None:
            raise KeyError(f"Site ID '{site_id}' not found in active registry or resolvable graveyard.")
        return site

    def load(self) -> None:
        """Load and partition site records from disk into active and graveyard stores.

        Raises:
            Exception: If reading or parsing the underlying JSON file fails.
        """
        if not self._filepath.exists():
            self._logger.warning(f"[SITES] File not found: {self._filepath}; initializing empty envelope.")
            self._sites = {}
            self._graveyard = {}
            self._max_site_num = 0
            self._is_dirty = True
            return

        try:
            payload: Dict[str, Any] = GDAUtil.load_json(self._filepath)
            raw_sites: List[Dict[str, Any]] = payload.get("sites", [])
            self._sites = {}
            self._graveyard = {}

            for site in raw_sites:
                sid = site.get("site_id", "")
                if not sid:
                    continue
                if site.get("is_deprecated", False):
                    self._graveyard[sid] = site
                else:
                    self._sites[sid] = site

            all_ids = list(self._sites.keys()) + list(self._graveyard.keys())
            self._max_site_num = GDAUtil.find_max_numeric_id(all_ids)
            self._is_dirty = False
            self._logger.info(
                f"[SITES] Loaded {len(self._sites)} active sites and {len(self._graveyard)} "
                f"graveyard tombstones from {self._filepath.name} (Max SID: {self._max_site_num:05d})."
            )
        except Exception as exc:
            self._logger.error(f"[SITES] Failed loading {self._filepath}: {exc}")
            raise

    def refresh(self) -> None:
        """Discard unstaged memory mutations and reload state cleanly from disk."""
        self.load()

    def resolve_id(self, site_id: str) -> Optional[str]:
        """Trace deprecation redirect chain through graveyard to canonical active ID.

        Args:
            site_id: Initial site identifier to evaluate.

        Returns:
            Active canonical SID-XXXXX string if resolved; None if target is defunct,
            unregistered, or trapped in a circular loop.
        """
        try:
            target = GDAUtil.resolve_superseded_id(
                entity_id=site_id,
                graveyard=self._graveyard,
            )
        except RecursionError:
            self._logger.warning(f"[SITES] Circular graveyard redirect detected for '{site_id}'.")
            return None

        return target if (target and target in self._sites) else None

    def exists(self, site_id: str, include_graveyard: bool = False) -> bool:
        """Return True if site_id exists in registry.

        Args:
            site_id: Canonical SID-XXXXX identifier.
            include_graveyard: If True, returns True if ID exists as a graveyard tombstone.

        Returns:
            True if entity is registered within designated scope; False otherwise.
        """
        if site_id in self._sites:
            return True
        if include_graveyard and site_id in self._graveyard:
            return True
        return False

    def get_by_id(
        self,
        site_id: str,
        include_graveyard: bool = False,
        resolve_redirects: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve site entity record by ID with optional graveyard redirection.

        Args:
            site_id: Canonical SID-XXXXX identifier.
            include_graveyard: If True and record is not redirected, returns tombstone payload.
            resolve_redirects: If True, traces superseded_by chains to the active record.

        Returns:
            Deep-copied record dictionary if located; None otherwise.
        """
        if site_id in self._sites:
            return copy.deepcopy(self._sites[site_id])

        if resolve_redirects:
            canonical_id = self.resolve_id(site_id)
            if canonical_id and canonical_id in self._sites:
                return copy.deepcopy(self._sites[canonical_id])

        if include_graveyard and site_id in self._graveyard:
            return copy.deepcopy(self._graveyard[site_id])

        return None

    def get_by_location(self, location_id: str, include_graveyard: bool = False) -> List[Dict[str, Any]]:
        """Return all sites associated with a parent civil location.

        Args:
            location_id: Canonical LOC-XXXXX parent jurisdiction identifier.
            include_graveyard: If True, includes tombstoned site records matching location_id.

        Returns:
            List of deep-copied site record dictionaries bound to the target location.
        """
        results: List[Dict[str, Any]] = [
            copy.deepcopy(site)
            for site in self._sites.values()
            if site.get("location_id") == location_id
        ]
        if include_graveyard:
            results.extend([
                copy.deepcopy(site)
                for site in self._graveyard.values()
                if site.get("location_id") == location_id
            ])
        return results

    def iter_graveyard(self) -> Iterator[Dict[str, Any]]:
        """Yield all soft-deleted/deprecated site tombstones.

        Yields:
            Deep copies of tombstoned graveyard record dictionaries.
        """
        for site in self._graveyard.values():
            yield copy.deepcopy(site)

    def iter_all(self) -> Iterator[Dict[str, Any]]:
        """Yield all site records across both active registry and graveyard.

        Yields:
            Deep copies of every active and tombstoned site record.
        """
        for site in self._sites.values():
            yield copy.deepcopy(site)
        for site in self._graveyard.values():
            yield copy.deepcopy(site)

    @staticmethod
    def _clean_aliases(aliases: Optional[Iterable[Any]]) -> List[str]:
        """Sanitize an iterable of alias objects into non-empty, stripped strings.

        Args:
            aliases: Raw collection of candidate alias strings or objects.

        Returns:
            List of valid, non-empty, stripped string aliases.
        """
        if not aliases:
            return []
        cleaned: List[str] = []
        for item in aliases:
            if isinstance(item, str):
                val = item.strip()
                if val:
                    cleaned.append(val)
        return cleaned

    @staticmethod
    def _validate_notes_input(notes: Optional[List[Dict[str, Any]]]) -> None:
        """Validate structural compliance of raw notes list before collection building.

        Args:
            notes: Raw collection of candidate note dictionaries.

        Raises:
            ValueError: If notes is not a list, contains non-dict elements, or contains
                empty note text.
        """
        if notes is None:
            return
        if not isinstance(notes, list):
            raise ValueError("Notes payload must be a list of dictionaries.")

        for idx, entry in enumerate(notes):
            if not isinstance(entry, dict):
                raise ValueError(f"Note entry at index {idx} must be a dictionary.")
            text_val = entry.get("note_text") if "note_text" in entry else entry.get("text")
            if not isinstance(text_val, str) or not text_val.strip():
                raise ValueError(f"Note entry at index {idx} missing required non-empty string.")

    def _mint_next_id(self) -> str:
        """Auto-mint sequential SID-XXXXX identifier using monotonic high-water mark.

        Returns:
            Formally minted SID-XXXXX identifier string.
        """
        if self._max_site_num == 0:
            all_ids = list(self._sites.keys()) + list(self._graveyard.keys())
            self._max_site_num = GDAUtil.find_max_numeric_id(all_ids)
        self._max_site_num += 1
        return f"SID-{self._max_site_num:05d}"

    @staticmethod
    def _normalize_address(address: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate and construct schema-compliant street address dictionary.

        Args:
            address: Optional street address dictionary containing address lines,
                postal code, and geographic coordinates.

        Returns:
            Schema-compliant address dictionary, or None if address input is None.

        Raises:
            ValueError: If address payload is not a dictionary, contains disallowed properties,
                or has malformed non-numeric coordinates.
        """
        if address is None:
            return None
        if not isinstance(address, dict):
            raise ValueError("Address payload must be a dictionary.")

        allowed_keys = {"address_line_1", "address_line_2", "postal_code", "coordinates"}
        extra_keys = set(address.keys()) - allowed_keys
        if extra_keys:
            raise ValueError(f"Disallowed properties in address dictionary: {sorted(extra_keys)}")

        def _clean_str(val: Any) -> Optional[str]:
            if isinstance(val, str) and val.strip():
                return val.strip()
            return None

        line1 = _clean_str(address.get("address_line_1"))
        line2 = _clean_str(address.get("address_line_2"))
        postal = _clean_str(address.get("postal_code"))

        coords_in = address.get("coordinates")
        coords_out: Optional[Dict[str, float]] = None

        if coords_in is not None:
            if not isinstance(coords_in, dict):
                raise ValueError("Address coordinates must be a dictionary.")
            extra_coords = set(coords_in.keys()) - {"latitude", "longitude"}
            if extra_coords:
                raise ValueError(f"Disallowed properties in coordinates dictionary: {sorted(extra_coords)}")

            lat = coords_in.get("latitude")
            lon = coords_in.get("longitude")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                coords_out = {
                    "latitude": float(lat),
                    "longitude": float(lon),
                }
            else:
                raise ValueError("Address coordinates must contain numeric 'latitude' and 'longitude'.")

        return {
            "address_line_1": line1,
            "address_line_2": line2,
            "postal_code": postal,
            "coordinates": coords_out,
        }

    def add(
        self,
        name: str,
        site_type: str,
        location_id: str,
        aliases: Optional[List[str]] = None,
        address: Optional[Dict[str, Any]] = None,
        operational_status: str = "ACTIVE",
        notes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Add a new physical site entity with system-minted sequential SID-XXXXX.

        Args:
            name: Primary canonical name of the site (mandatory).
            site_type: Controlled vocabulary classification (e.g., CEMETERY, CHURCH, HOSPITAL).
            location_id: Canonical LOC-XXXXX parent civil jurisdiction identifier.
            aliases: Alternate names, historical designations, or colloquial references.
            address: Optional street address dictionary with optional coordinates.
            operational_status: Controlled status string. Defaults to 'ACTIVE'.
            notes: List of annotation dicts to append.

        Returns:
            The canonical site_id assigned to the new record.

        Raises:
            ValueError: If name is empty, location_id fails foreign key validation,
                site_type is invalid, operational_status is unlisted, or address/notes
                structures are malformed.
        """
        if isinstance(name, str) and name.strip():
            clean_name = name.strip()
        else:
            raise ValueError("Site 'name' must be a non-empty string.")

        if location_id and self._loc.exists(location_id):
            clean_loc_id = location_id
        else:
            raise ValueError(f"Foreign key validation failed: location_id '{location_id}' not found.")

        if site_type in VOCAB_MGR["site_type"]:
            clean_site_type = site_type
        else:
            allowed_types = sorted(VOCAB_MGR["site_type"])
            raise ValueError(f"Invalid site_type '{site_type}'. Allowed: {allowed_types}")

        if operational_status in VOCAB_MGR["operational_status"]:
            clean_status = operational_status
        else:
            allowed_statuses = sorted(VOCAB_MGR["operational_status"])
            raise ValueError(f"Invalid operational_status '{operational_status}'. Allowed: {allowed_statuses}")

        self._validate_notes_input(notes)
        assigned_id = self._mint_next_id()
        validated_address = self._normalize_address(address)
        notes_collection = GDANoteCollection(notes_data=notes, valid_types=VOCAB_MGR["note_type"])
        clean_aliases = self._clean_aliases(aliases)

        site_record: Dict[str, Any] = {
            "site_id": assigned_id,
            "site_type": clean_site_type,
            "name": clean_name,
            "aliases": clean_aliases,
            "location_id": clean_loc_id,
            "address": validated_address,
            "operational_status": clean_status,
            "is_deprecated": False,
            "superseded_by": None,
            "dissolution_date": None,
            "notes": notes_collection.to_list(),
            "last_updated": GDAUtil.iso_now(),
        }

        self._sites[assigned_id] = site_record
        self._is_dirty = True
        return assigned_id

    def edit(self, site_id: str, updates: Dict[str, Any], overwrite_none: bool = False) -> bool:
        """Update an existing active site entity.

        Args:
            site_id: Canonical SID-XXXXX identifier.
            updates: Dictionary of schema properties to modify.
            overwrite_none: If True, explicitly overwrite existing values when dict key is None.

        Returns:
            True if modifications were staged; False if updates resulted in identical state.

        Raises:
            KeyError: If site_id does not exist or resides in the graveyard.
            ValueError: If updates contain disallowed property keys, unlisted vocabularies,
                or unregistered location_id foreign keys.
        """
        if site_id not in self._sites:
            if site_id in self._graveyard:
                raise KeyError(f"Cannot edit deprecated site '{site_id}' residing in graveyard.")
            raise KeyError(f"Site ID '{site_id}' not found.")

        disallowed_keys = set(updates.keys()) - self.ALLOWED_PROPERTIES - {"site_id"}
        if disallowed_keys:
            raise ValueError(f"Disallowed property updates for site: {sorted(disallowed_keys)}")

        if "site_type" in updates:
            new_type = updates["site_type"]
            if new_type not in VOCAB_MGR["site_type"]:
                raise ValueError(f"Invalid site_type '{new_type}'.")

        if "operational_status" in updates:
            new_status = updates["operational_status"]
            if new_status not in VOCAB_MGR["operational_status"]:
                raise ValueError(f"Invalid operational_status '{new_status}'.")

        if "location_id" in updates:
            new_loc = updates["location_id"]
            if not new_loc or not self._loc.exists(new_loc):
                raise ValueError(f"Foreign key validation failed: location_id '{new_loc}' not found.")

        if "notes" in updates:
            self._validate_notes_input(updates["notes"])

        record = self._sites[site_id]
        modified = False

        normalized_updates: Dict[str, Any] = {}
        for k, v in updates.items():
            if k == "site_id":
                continue
            if k == "name" and isinstance(v, str):
                normalized_updates[k] = v.strip()
            elif k == "aliases":
                normalized_updates[k] = self._clean_aliases(v)
            elif k == "address":
                normalized_updates[k] = self._normalize_address(v) if v is not None else None
            elif k == "notes":
                normalized_updates[k] = (
                    GDANoteCollection(notes_data=v, valid_types=VOCAB_MGR["note_type"]).to_list()
                    if v is not None
                    else None
                )
            else:
                normalized_updates[k] = v

        for field, target_val in normalized_updates.items():
            if field in ("is_deprecated", "superseded_by"):
                continue
            if target_val is not None or overwrite_none:
                if record.get(field) != target_val:
                    record[field] = target_val
                    modified = True

        if updates.get("is_deprecated") is True:
            superseded_target = updates.get("superseded_by")
            self.delete(site_id, hard_delete=False, superseded_by=superseded_target)
            return True

        if modified:
            record["last_updated"] = GDAUtil.iso_now()
            self._is_dirty = True

        return modified

    def delete(self, site_id: str, hard_delete: bool = False, superseded_by: Optional[str] = None) -> bool:
        """Soft-delete an active site to the graveyard, or permanently purge from memory.

        Args:
            site_id: Canonical SID-XXXXX identifier.
            hard_delete: If True, purges record entirely from active and graveyard memory.
            superseded_by: Optional SID-XXXXX successor identifier for redirect tracking.

        Returns:
            True if site was found and deleted or updated; False if ID not found.

        Raises:
            ValueError: If superseded_by does not match SID-XXXXX pattern.
            KeyError: If superseded_by ID is not registered in active or graveyard store.
        """
        if not self.exists(site_id, include_graveyard=True):
            return False

        if hard_delete:
            self._sites.pop(site_id, None)
            self._graveyard.pop(site_id, None)
            self._is_dirty = True
            return True

        if superseded_by:
            if not SID_ID_PATTERN.match(superseded_by):
                raise ValueError(f"Invalid superseded_by site_id '{superseded_by}': must conform to '^SID-\\d{{5}}$'.")
            if not self.exists(superseded_by, include_graveyard=True):
                raise KeyError(f"Target superseded_by site_id '{superseded_by}' not found in registry.")

        if site_id in self._graveyard:
            if superseded_by:
                self._graveyard[site_id]["superseded_by"] = superseded_by
                self._graveyard[site_id]["last_updated"] = GDAUtil.iso_now()
                self._is_dirty = True
            return True

        record = self._sites.pop(site_id)
        record["is_deprecated"] = True
        record["operational_status"] = "DEFUNCT"
        record["superseded_by"] = superseded_by
        record["last_updated"] = GDAUtil.iso_now()

        self._graveyard[site_id] = record
        self._is_dirty = True
        return True

    def add_alias(self, site_id: str, alias: str) -> bool:
        """Add an alternative name to an active site.

        Args:
            site_id: Canonical SID-XXXXX identifier.
            alias: Non-empty alias string to register.

        Returns:
            True if alias was novel and appended; False if empty, non-string, or duplicate.

        Raises:
            KeyError: If site_id does not exist in active registry.
        """
        if site_id not in self._sites:
            raise KeyError(f"Active site ID '{site_id}' not found.")
        if isinstance(alias, str) and alias.strip():
            clean_alias = alias.strip()
        else:
            return False

        aliases: List[str] = self._sites[site_id].setdefault("aliases", [])
        if clean_alias not in aliases:
            aliases.append(clean_alias)
            self._sites[site_id]["last_updated"] = GDAUtil.iso_now()
            self._is_dirty = True
            return True
        return False

    def remove_alias(self, site_id: str, alias: str) -> bool:
        """Remove an alternative name from an active site.

        Args:
            site_id: Canonical SID-XXXXX identifier.
            alias: Alias string to remove.

        Returns:
            True if alias was found and removed; False if alias did not exist or invalid.

        Raises:
            KeyError: If site_id does not exist in active registry.
        """
        if site_id not in self._sites:
            raise KeyError(f"Active site ID '{site_id}' not found.")
        if isinstance(alias, str) and alias.strip():
            clean_alias = alias.strip()
        else:
            return False

        aliases: List[str] = self._sites[site_id].get("aliases", [])
        if clean_alias in aliases:
            aliases.remove(clean_alias)
            self._sites[site_id]["last_updated"] = GDAUtil.iso_now()
            self._is_dirty = True
            return True
        return False

    def add_note(self, site_id: str, text: str, note_type: str = "RESEARCH") -> str:
        """Ergonomically append a new note entry to an active site.

        Args:
            site_id: Canonical SID-XXXXX identifier.
            text: Non-empty annotation text.
            note_type: Note type category from controlled vocabulary. Defaults to 'RESEARCH'.

        Returns:
            Assigned NOT-XXXXX note identifier.

        Raises:
            KeyError: If site_id does not exist in active registry.
            ValueError: If text is empty, not a string, or note_type is invalid.
        """
        if site_id not in self._sites:
            raise KeyError(f"Active site ID '{site_id}' not found.")

        if not isinstance(text, str) or not text.strip():
            raise ValueError("Note text must be a non-empty string.")

        record = self._sites[site_id]
        collection = GDANoteCollection(
            notes_data=record.get("notes", []),
            valid_types=VOCAB_MGR["note_type"],
        )
        resolved_type = note_type if note_type in VOCAB_MGR["note_type"] else "RESEARCH"
        created_note = collection.add(note_text=text.strip(), note_type=resolved_type)
        record["notes"] = collection.to_list()
        record["last_updated"] = GDAUtil.iso_now()
        self._is_dirty = True
        return created_note.note_id

    def remove_note(self, site_id: str, note_id: str) -> bool:
        """Remove a note entry from an active site by its note_id.

        Args:
            site_id: Canonical SID-XXXXX identifier.
            note_id: Canonical NOT-XXXXX note identifier.

        Returns:
            True if note was found and removed; False if note_id did not match.

        Raises:
            KeyError: If site_id does not exist in active registry.
        """
        if site_id not in self._sites:
            raise KeyError(f"Active site ID '{site_id}' not found.")

        record = self._sites[site_id]
        collection = GDANoteCollection(notes_data=record.get("notes", []))
        removed = collection.remove(note_id)

        if removed:
            record["notes"] = collection.to_list()
            record["last_updated"] = GDAUtil.iso_now()
            self._is_dirty = True
            return True
        return False

    def repoint_locations(
        self,
        new_location_id: str,
        old_location_ids: Union[List[str], Set[str], Sequence[str]],
    ) -> int:
        """Cascade foreign key changes across both active and graveyard site records.

        Args:
            new_location_id: Canonical LOC-XXXXX target replacing obsolete references.
            old_location_ids: Collection of obsolete LOC-XXXXX identifiers to reassign.

        Returns:
            Total count of active and graveyard site records repointed.

        Raises:
            ValueError: If new_location_id fails foreign key validation against locations_provider.
        """
        if new_location_id and self._loc.exists(new_location_id):
            clean_new_loc = new_location_id
        else:
            raise ValueError(f"Foreign key validation failed: new_location_id '{new_location_id}' not found.")

        repointed_count = 0
        old_set = set(old_location_ids)

        for site in self._sites.values():
            if site.get("location_id") in old_set:
                site["location_id"] = clean_new_loc
                site["last_updated"] = GDAUtil.iso_now()
                repointed_count += 1

        for site in self._graveyard.values():
            if site.get("location_id") in old_set:
                site["location_id"] = clean_new_loc
                site["last_updated"] = GDAUtil.iso_now()
                repointed_count += 1

        if repointed_count > 0:
            self._is_dirty = True
        return repointed_count

    def search(
        self,
        query: Optional[str] = None,
        location_id: Optional[str] = None,
        site_type: Optional[str] = None,
        has_coordinates: Optional[bool] = None,
        include_graveyard: bool = False,
        use_fuzzy: bool = True,
        fuzzy_threshold: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """Filter and search sites across active records and optionally the graveyard.

        Args:
            query: Free-text search term matched against name and aliases.
            location_id: Filter results strictly by parent civil location ID.
            site_type: Filter results strictly by controlled vocabulary site type.
            has_coordinates: If True, filters for sites with geographic coordinates;
                if False, filters for sites lacking coordinates; if None, no coordinate filter.
            include_graveyard: If True, evaluates graveyard tombstones alongside active records.
            use_fuzzy: If True, evaluates difflib fuzzy string similarity via GDAUtil.
            fuzzy_threshold: Minimum SequenceMatcher similarity ratio (0.0 to 1.0).

        Returns:
            List of deep-copied matching site records.
        """
        candidates = list(self._sites.values())
        if include_graveyard:
            candidates.extend(list(self._graveyard.values()))

        if location_id:
            candidates = [c for c in candidates if c.get("location_id") == location_id]

        if site_type:
            candidates = [c for c in candidates if c.get("site_type") == site_type]

        if has_coordinates is not None:
            def _has_coords(item: Dict[str, Any]) -> bool:
                addr = item.get("address")
                if not isinstance(addr, dict):
                    return False
                coords = addr.get("coordinates")
                if not isinstance(coords, dict):
                    return False
                return (
                    isinstance(coords.get("latitude"), (int, float))
                    and isinstance(coords.get("longitude"), (int, float))
                )

            candidates = [c for c in candidates if _has_coords(c) is has_coordinates]

        if not query:
            return [copy.deepcopy(c) for c in candidates]

        q = query.lower().strip()
        matched: List[Dict[str, Any]] = []

        for site in candidates:
            name = site.get("name", "").lower()
            aliases = [a.lower() for a in site.get("aliases", [])]

            if q in name or any(q in alias for alias in aliases):
                matched.append(copy.deepcopy(site))
                continue

            if use_fuzzy:
                if GDAUtil.match_text(q, name, min_ratio=fuzzy_threshold):
                    matched.append(copy.deepcopy(site))
                    continue

                if any(GDAUtil.match_text(q, alias, min_ratio=fuzzy_threshold) for alias in aliases):
                    matched.append(copy.deepcopy(site))

        return matched

    def find_one(
        self,
        query: str,
        location_id: Optional[str] = None,
        site_type: Optional[str] = None,
        has_coordinates: Optional[bool] = None,
        include_graveyard: bool = False,
        fuzzy_threshold: float = 0.85,
    ) -> Optional[Dict[str, Any]]:
        """Find the single closest matching site entity.

        Args:
            query: Free-text search term or pattern.
            location_id: Optional parent civil location ID filter.
            site_type: Optional controlled vocabulary site type filter.
            has_coordinates: Optional boolean coordinate existence filter.
            include_graveyard: If True, evaluates graveyard tombstones as candidates.
            fuzzy_threshold: Minimum SequenceMatcher similarity ratio. Defaults to 0.85.

        Returns:
            The single highest-scoring deep-copied record dictionary, or None if no match.
        """
        matches = self.search(
            query=query,
            location_id=location_id,
            site_type=site_type,
            has_coordinates=has_coordinates,
            include_graveyard=include_graveyard,
            use_fuzzy=True,
            fuzzy_threshold=fuzzy_threshold,
        )
        if matches:
            return matches[0]
        return None

    def save(
        self,
        output_path: Optional[Union[str, Path]] = None,
        force: bool = False,
        create_backup: bool = True,
    ) -> bool:
        """Persist active sites and graveyard tombstones to disk under Safe Backup Protocol.

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
            self._logger.info("[SITES] No memory mutations detected; save skipped.")
            return False

        target_file = Path(output_path) if output_path else self._filepath
        combined_sites = list(self._sites.values()) + list(self._graveyard.values())
        sorted_sites = sorted(combined_sites, key=lambda s: str(s.get("site_id", "")))

        payload: Dict[str, Any] = {
            "_name": target_file.name,
            "_path": target_file.as_posix(),
            "$schema": "schemas/entities/site_registry.schema.json",
            "version": "1.2.0",
            "last_updated": GDAUtil.iso_now(),
            "sites": sorted_sites,
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
            f"[SITES] Persisted {len(sorted_sites)} records ({len(self._sites)} active, "
            f"{len(self._graveyard)} graveyard) to {target_file.as_posix()}."
        )
        return True