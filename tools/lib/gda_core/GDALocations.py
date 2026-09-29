# Name: GDALocations.py
# Path: tools/lib/gda_core/GDALocations.py
# Version: 1.0.1+build.20260929.1

"""Master civil jurisdiction and administrative boundary registry manager.

Operational Role:
    Manages data/entities/locations.json with transactional backups,
    US state normalization (via 'us' package), hierarchical search,
    temporal split/merger lineage tracking, schema validation, and view filtering.
"""

from datetime import datetime, timezone
from difflib import SequenceMatcher
import fnmatch
from pathlib import Path
import re
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union
import us

from tools.lib.gda_core.GDAConfig import CONFIG
import tools.lib.gda_core.GDALogger as gda_logger
from tools.lib.gda_core.GDAUtil import GDAUtil


class GDALocations:
    """Master registry manager for civil jurisdictions, counties, states, and countries.

    Manages data/entities/locations.json with transactional backups, offline US
    state verification via 'us', fuzzy search, temporal lineage tracking, and filtering.
    """

    _LOCATION_ID_REGEX = re.compile(r"^LOC-[0-9]{5}$")

    def __init__(
        self,
        filepath: Optional[Union[str, Path]] = None,
        auto_load: bool = True,
    ) -> None:
        """Initialize the GDALocations registry.

        Args:
            filepath: Optional custom path to locations.json. Defaults to
              data/entities/locations.json via GDAConfig.
            auto_load: If True, immediately loads and parses entities from disk.
        """
        self._config = CONFIG
        if hasattr(gda_logger, "get_logger"):
            self._logger = gda_logger.get_logger(__name__)
        elif hasattr(gda_logger, "LOGGER"):
            self._logger = getattr(gda_logger.LOGGER, "get_logger", lambda _: gda_logger.LOGGER)(__name__)
        else:
            import logging
            self._logger = logging.getLogger(__name__)

        if filepath:
            self._filepath = Path(filepath)
        else:
            self._filepath = self._config.entities_dir / "locations.json"

        self._registry_metadata: Dict[str, Any] = {
            "_name": "locations.json",
            "_path": "data/entities/locations.json",
            "$schema": "schemas/entities/location_registry.schema.json",
            "schema_version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_modified": datetime.now(timezone.utc).isoformat(),
            "total_locations": 0,
        }
        self._locations: Dict[str, Dict[str, Any]] = {}
        self._filtered_ids: Optional[List[str]] = None
        self._is_dirty: bool = False

        if auto_load:
            self.load()

    # -------------------------------------------------------------------------
    # Lifecycle & Persistence
    # -------------------------------------------------------------------------
    def load(self) -> None:
        """Load and parse locations.json from disk, resetting dirty state and active filters."""
        if not self._filepath.exists():
            self._logger.info(
                f"[SYS] Locations registry not found at {self._filepath}. Initializing empty container."
            )
            self._locations = {}
            self._filtered_ids = None
            self._is_dirty = False
            return

        try:
            data = GDAUtil.load_json(self._filepath)
            self._registry_metadata["_name"] = data.get("_name", "locations.json")
            self._registry_metadata["_path"] = data.get(
                "_path", "data/entities/locations.json"
            )
            self._registry_metadata["$schema"] = data.get(
                "$schema", "schemas/entities/location_registry.schema.json"
            )
            self._registry_metadata["schema_version"] = data.get(
                "schema_version", "1.0.0"
            )
            self._registry_metadata["created_at"] = data.get(
                "created_at", datetime.now(timezone.utc).isoformat()
            )
            self._registry_metadata["last_modified"] = data.get(
                "last_modified", datetime.now(timezone.utc).isoformat()
            )

            raw_locations = data.get("locations", [])
            self._locations = {item["location_id"]: item for item in raw_locations}
            self._filtered_ids = None
            self._is_dirty = False
            self._logger.info(
                f"[SYS] Loaded {len(self._locations)} locations from {self._filepath.name}."
            )
        except Exception as exc:
            self._logger.error(
                f"[SYS] Failed to load locations from {self._filepath}: {exc}"
            )
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
        """Persist registry to disk via GDAUtil atomic write.

        Args:
            output_path: Optional explicit target path (e.g. gtemp/ scratch target).
              If omitted, saves to canonical self._filepath.
            force: If True, writes even if is_dirty is False.
            create_backup: Governs Safe Backup Protocol snapshot creation. Default
              is True when persisting to canonical production store, False for scratch paths.

        Returns:
            True if persisted, False if skipped due to clean state.
        """
        if not self._is_dirty and not force:
            return False

        target = Path(output_path) if output_path else self._filepath
        should_backup = create_backup if target == self._filepath else False

        self._registry_metadata["last_modified"] = datetime.now(timezone.utc).isoformat()
        self._registry_metadata["total_locations"] = len(self._locations)

        payload = dict(self._registry_metadata)
        sorted_locations = sorted(
            self._locations.values(),
            key=lambda item: int(item["location_id"].split("-")[1]),
        )
        payload["locations"] = sorted_locations

        GDAUtil.save_json(target, payload, create_backup=should_backup)
        if target == self._filepath:
            self._is_dirty = False

        self._logger.info(
            f"[SYS] Successfully persisted {len(sorted_locations)} locations to {target.name}."
        )
        return True

    # -------------------------------------------------------------------------
    # State Properties
    # -------------------------------------------------------------------------
    @property
    def is_dirty(self) -> bool:
        """True if in-memory entities have been modified since last load/save."""
        return self._is_dirty

    @property
    def count(self) -> int:
        """Total count of registered locations in memory."""
        return len(self._locations)

    @property
    def filtered_count(self) -> int:
        """Count of records in the currently active filtered subset."""
        if self._filtered_ids is None:
            return len(self._locations)
        return len(self._filtered_ids)

    # -------------------------------------------------------------------------
    # State Normalization & ID Minting
    # -------------------------------------------------------------------------
    @staticmethod
    def normalize_state(country: str, state_or_province: Optional[str]) -> Optional[str]:
        """Normalize and validate US state strings using the offline 'us' package."""
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
        """Format a unified canonical place string: Local, County County, State, Country."""
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
        """Calculate and return the next zero-padded monotonic LOC-XXXXX identifier."""
        if not self._locations:
            return "LOC-00001"
        highest_idx = 0
        for lid in self._locations.keys():
            match = self._LOCATION_ID_REGEX.match(lid)
            if match:
                val = int(lid.split("-")[1])
                if val > highest_idx:
                    highest_idx = val
        return f"LOC-{highest_idx + 1:05d}"

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------
    def exists(self, location_id: str) -> bool:
        """Check if location_id is registered (used by GDASites referential checks)."""
        return location_id in self._locations

    def get_by_id(self, location_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an individual location entity by primary key."""
        record = self._locations.get(location_id)
        if record is None:
            return None
        return dict(record)

    def add(
        self,
        country: str,
        state_or_province: Optional[str] = None,
        county: Optional[str] = None,
        local_jurisdiction: Optional[str] = None,
        canonical_name: Optional[str] = None,
        location_id: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        date_established: Optional[str] = None,
        date_dissolved: Optional[str] = None,
        predecessor_location_id: Optional[str] = None,
        successor_location_id: Optional[str] = None,
        notes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Mint identifier (if omitted), normalize state, and stage a new location."""
        clean_country = country.strip()
        if not clean_country:
            raise ValueError("Country must not be empty.")

        clean_state = self.normalize_state(clean_country, state_or_province)
        clean_county = county.strip() if county else None
        clean_local = local_jurisdiction.strip() if local_jurisdiction else None

        c_name = canonical_name.strip() if canonical_name else self.build_canonical_name(
            country=clean_country,
            state_or_province=clean_state,
            county=clean_county,
            local_jurisdiction=clean_local,
        )

        assigned_id = location_id.strip() if location_id else self._mint_next_id()
        if not self._LOCATION_ID_REGEX.match(assigned_id):
            raise ValueError(f"Malformed location_id pattern: '{assigned_id}'")
        if assigned_id in self._locations:
            raise KeyError(f"Location identifier '{assigned_id}' already exists in registry.")

        if predecessor_location_id and not self._LOCATION_ID_REGEX.match(predecessor_location_id):
            raise ValueError(f"Malformed predecessor_location_id: '{predecessor_location_id}'")
        if successor_location_id and not self._LOCATION_ID_REGEX.match(successor_location_id):
            raise ValueError(f"Malformed successor_location_id: '{successor_location_id}'")

        now_iso = datetime.now(timezone.utc).isoformat()
        record: Dict[str, Any] = {
            "location_id": assigned_id,
            "canonical_name": c_name,
            "aliases": [a.strip() for a in (aliases or []) if a.strip()],
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
            "notes": notes or [],
            "last_updated": now_iso,
        }

        self._locations[assigned_id] = record
        self._is_dirty = True
        self._logger.info(f"[SYS] Staged location addition: {assigned_id} ('{c_name}').")
        return assigned_id

    def edit(
        self,
        location_id: str,
        updates: Dict[str, Any],
        overwrite_none: bool = False,
    ) -> bool:
        """Apply field-level modifications to an existing registered jurisdiction."""
        if location_id not in self._locations:
            raise KeyError(f"Location '{location_id}' does not exist in registry.")

        record = self._locations[location_id]
        modified = False

        if "canonical_name" in updates:
            c_name = updates["canonical_name"].strip()
            if not c_name:
                raise ValueError("canonical_name must not be empty.")
            if record["canonical_name"] != c_name:
                record["canonical_name"] = c_name
                modified = True

        if "aliases" in updates:
            new_aliases = [a.strip() for a in updates["aliases"] if a.strip()]
            if record["aliases"] != new_aliases:
                record["aliases"] = new_aliases
                modified = True

        if "jurisdiction" in updates:
            jur = updates["jurisdiction"]
            cur_jur = record["jurisdiction"]
            country = jur.get("country", cur_jur["country"])
            state = self.normalize_state(country, jur.get("state_or_province", cur_jur.get("state_or_province")))

            for key, val in [
                ("country", country),
                ("state_or_province", state),
                ("county", jur.get("county")),
                ("local_jurisdiction", jur.get("local_jurisdiction")),
            ]:
                if key in jur or key in ("country", "state_or_province"):
                    if val is not None or overwrite_none:
                        if cur_jur.get(key) != val:
                            cur_jur[key] = val
                            modified = True

        if "temporal_validity" in updates:
            temp = updates["temporal_validity"]
            cur_temp = record["temporal_validity"]
            for key in ["date_established", "date_dissolved", "predecessor_location_id", "successor_location_id"]:
                if key in temp:
                    val = temp[key]
                    if val is not None or overwrite_none:
                        if cur_temp.get(key) != val:
                            cur_temp[key] = val
                            modified = True

        if "notes" in updates:
            record["notes"] = updates["notes"]
            modified = True

        if modified:
            record["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._is_dirty = True
            self._logger.info(f"[SYS] Staged edits for location {location_id}.")

        return modified

    def delete(self, location_id: str) -> bool:
        """Remove a location by primary identifier."""
        if location_id not in self._locations:
            return False

        del self._locations[location_id]
        if self._filtered_ids is not None and location_id in self._filtered_ids:
            self._filtered_ids.remove(location_id)

        self._is_dirty = True
        self._logger.warning(
            f"[SYS] Deleted location {location_id} from registry. Ensure sites and facts are remediated."
        )
        return True

    # -------------------------------------------------------------------------
    # Alias Management Protocol
    # -------------------------------------------------------------------------
    def add_alias(self, location_id: str, alias: str) -> bool:
        """Append a unique alias to a location. Marks registry dirty."""
        if location_id not in self._locations:
            raise KeyError(f"Location '{location_id}' does not exist in registry.")

        clean_alias = alias.strip()
        if not clean_alias:
            return False

        record = self._locations[location_id]
        current_aliases = record.get("aliases", [])
        if clean_alias not in current_aliases:
            current_aliases.append(clean_alias)
            record["aliases"] = current_aliases
            record["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._is_dirty = True
            self._logger.info(f"[SYS] Added alias '{clean_alias}' to {location_id}.")
            return True
        return False

    def remove_alias(self, location_id: str, alias: str) -> bool:
        """Remove an alias from a location. Marks registry dirty."""
        if location_id not in self._locations:
            raise KeyError(f"Location '{location_id}' does not exist in registry.")

        clean_alias = alias.strip()
        record = self._locations[location_id]
        current_aliases = record.get("aliases", [])
        if clean_alias in current_aliases:
            current_aliases.remove(clean_alias)
            record["aliases"] = current_aliases
            record["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._is_dirty = True
            self._logger.info(f"[SYS] Removed alias '{clean_alias}' from {location_id}.")
            return True
        return False

    # -------------------------------------------------------------------------
    # Temporal & Hierarchical Queries
    # -------------------------------------------------------------------------
    def get_predecessor(self, location_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the predecessor jurisdiction entity for historical boundary changes."""
        rec = self.get_by_id(location_id)
        if not rec:
            return None
        pid = rec.get("temporal_validity", {}).get("predecessor_location_id")
        return self.get_by_id(pid) if pid else None

    def get_successor(self, location_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the successor jurisdiction entity for merged or split boundaries."""
        rec = self.get_by_id(location_id)
        if not rec:
            return None
        sid = rec.get("temporal_validity", {}).get("successor_location_id")
        return self.get_by_id(sid) if sid else None

    def is_valid_at_date(self, location_id: str, date_iso: str) -> bool:
        """Evaluate if the civil jurisdiction was legally extant at a given ISO date."""
        rec = self.get_by_id(location_id)
        if not rec:
            return False
        temp = rec.get("temporal_validity", {})
        est = temp.get("date_established")
        dis = temp.get("date_dissolved")

        if est and date_iso < est:
            return False
        if dis and date_iso > dis:
            return False
        return True

    def find_by_jurisdiction(
        self,
        country: str,
        state_or_province: Optional[str] = None,
        county: Optional[str] = None,
        local_jurisdiction: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find single exact match matching structured administrative components."""
        clean_country = country.strip().lower()
        norm_state = self.normalize_state(country, state_or_province)
        clean_state = norm_state.lower() if norm_state else None
        clean_county = county.strip().lower() if county else None
        clean_local = local_jurisdiction.strip().lower() if local_jurisdiction else None

        for item in self._locations.values():
            jur = item["jurisdiction"]
            if jur["country"].strip().lower() != clean_country:
                continue
            if clean_state and (jur.get("state_or_province") or "").strip().lower() != clean_state:
                continue
            if clean_county:
                cur_c = (jur.get("county") or "").strip().lower()
                if cur_c != clean_county and cur_c.replace(" county", "") != clean_county.replace(" county", ""):
                    continue
            if clean_local and (jur.get("local_jurisdiction") or "").strip().lower() != clean_local:
                continue
            return dict(item)
        return None

    # -------------------------------------------------------------------------
    # Search Engine (Exact, Wildcard, & Fuzzy)
    # -------------------------------------------------------------------------
    def find_one(
        self,
        query: str,
        country: Optional[str] = None,
        state_or_province: Optional[str] = None,
        fuzzy_threshold: float = 0.85,
    ) -> Optional[Dict[str, Any]]:
        """Return single highest-scoring match across canonical_name, civil parts, and aliases."""
        results = self.search(
            query=query,
            country=country,
            state_or_province=state_or_province,
            use_fuzzy=True,
            fuzzy_threshold=fuzzy_threshold,
        )
        return results[0] if results else None

    def search(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        state_or_province: Optional[str] = None,
        county: Optional[str] = None,
        use_fuzzy: bool = True,
        fuzzy_threshold: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """Search registered locations matching query against canonical_name, parts, or aliases."""
        scored_matches: List[Tuple[float, Dict[str, Any]]] = []
        clean_query = query.strip().lower() if query else None

        pool = (
            [self._locations[lid] for lid in self._filtered_ids]
            if self._filtered_ids is not None
            else list(self._locations.values())
        )

        for item in pool:
            jur = item.get("jurisdiction", {})
            if country and jur.get("country", "").strip().lower() != country.strip().lower():
                continue
            if state_or_province:
                norm_st = self.normalize_state(jur.get("country", ""), state_or_province)
                cur_st = jur.get("state_or_province")
                if norm_st and cur_st and norm_st.lower() != cur_st.lower():
                    continue
            if county:
                cur_c = (jur.get("county") or "").lower()
                req_c = county.strip().lower()
                if cur_c != req_c and cur_c.replace(" county", "") != req_c.replace(" county", ""):
                    continue

            if not clean_query:
                scored_matches.append((1.0, dict(item)))
                continue

            # Candidate evaluation includes canonical name, civil components, and aliases
            jur_components = [jur.get("local_jurisdiction"), jur.get("county")]
            candidates = (
                [item["canonical_name"]]
                + [c for c in jur_components if c]
                + item.get("aliases", [])
            )
            matched = False
            best_score = 0.0

            for cand in candidates:
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
                elif use_fuzzy:
                    ratio = SequenceMatcher(None, clean_query, cand_lower).ratio()
                    if ratio >= fuzzy_threshold:
                        matched = True
                        best_score = max(best_score, ratio)

            if matched:
                scored_matches.append((best_score, dict(item)))

        if clean_query:
            scored_matches.sort(key=lambda x: x[0], reverse=True)

        return [item for _, item in scored_matches]

    # -------------------------------------------------------------------------
    # View State & Filtering
    # -------------------------------------------------------------------------
    def set_filter(
        self,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
        country: Optional[str] = None,
        state_or_province: Optional[str] = None,
        county: Optional[str] = None,
        name_pattern: Optional[str] = None,
    ) -> int:
        """Apply constraint filter to working set. Subsequent queries respect this view."""
        matched_ids: List[str] = []

        for lid, item in self._locations.items():
            jur = item["jurisdiction"]
            if country and jur["country"].strip().lower() != country.strip().lower():
                continue
            if state_or_province:
                norm_st = self.normalize_state(jur["country"], state_or_province)
                if norm_st and (jur.get("state_or_province") or "").lower() != norm_st.lower():
                    continue
            if county:
                cur_c = (jur.get("county") or "").lower()
                if cur_c != county.lower() and cur_c.replace(" county", "") != county.lower().replace(" county", ""):
                    continue
            if name_pattern:
                cand_names = [item["canonical_name"]] + item.get("aliases", [])
                if not any(fnmatch.fnmatch(n.lower(), name_pattern.lower()) for n in cand_names):
                    continue
            if predicate and not predicate(item):
                continue
            matched_ids.append(lid)

        self._filtered_ids = matched_ids
        return len(matched_ids)

    def clear_filter(self) -> None:
        """Reset the active view state; all entities become active."""
        self._filtered_ids = None

    def get_filtered(self) -> List[Dict[str, Any]]:
        """Return records passing active filter (or entire registry if clean)."""
        if self._filtered_ids is None:
            return [dict(item) for item in self._locations.values()]
        return [dict(self._locations[lid]) for lid in self._filtered_ids]

    def update_filtered(self, updates: Dict[str, Any]) -> int:
        """Apply atomic modifications across all locations currently passing active filter."""
        targets = (
            list(self._filtered_ids)
            if self._filtered_ids is not None
            else list(self._locations.keys())
        )
        if not targets:
            return 0

        modified_count = 0
        for lid in targets:
            if self.edit(lid, updates):
                modified_count += 1
        return modified_count

    # -------------------------------------------------------------------------
    # Dunder Protocols
    # -------------------------------------------------------------------------
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        if self._filtered_ids is not None:
            for lid in self._filtered_ids:
                yield dict(self._locations[lid])
        else:
            for item in self._locations.values():
                yield dict(item)

    def __len__(self) -> int:
        return self.filtered_count

    def __contains__(self, location_id: str) -> bool:
        return location_id in self._locations