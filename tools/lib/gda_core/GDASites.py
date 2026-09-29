# Name: GDASites.py
# Path: tools/lib/gda_core/GDASites.py
# Version: 1.1.0+build.20260929.1

"""Master physical site and landmark registry manager.

Operational Role:
    Manages data/entities/sites.json with transactional backups,
    fuzzy and wildcard search, alias management, stateful filtering,
    referential integrity checking against GDALocations, and decoupled
    scratch persistence via save(output_path=...).
"""

from datetime import datetime, timezone
from difflib import SequenceMatcher
import fnmatch
from pathlib import Path
import re
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

from tools.lib.gda_core.GDAConfig import CONFIG
import tools.lib.gda_core.GDALogger as gda_logger
from tools.lib.gda_core.GDAUtil import GDAUtil


class GDASites:
    """Master registry manager for physical sites, facilities, cemeteries, and landmarks.

    Manages data/entities/sites.json with transactional backups, fuzzy search,
    wildcard resolution, schema validation, and stateful filtering.
    """

    _LOCATION_ID_REGEX = re.compile(r"^LOC-[0-9]{5}$")
    _SITE_ID_REGEX = re.compile(r"^SITE-[0-9]{5}$")
    _VALID_SITE_TYPES = {
        "FACILITY",
        "CEMETERY",
        "CHURCH",
        "LANDMARK",
        "RESIDENCE",
        "ORGANIZATION",
    }

    def __init__(
        self,
        filepath: Optional[Union[str, Path]] = None,
        auto_load: bool = True,
        locations_provider: Optional[Any] = None,
    ) -> None:
        """Initialize the GDASites registry.

        Args:
            filepath: Optional custom path to sites.json. Defaults to
              data/entities/sites.json via GDAConfig.
            auto_load: If True, immediately load and parse sites from disk.
            locations_provider: Optional GDALocations instance for referential
              integrity validation.
        """
        self._config = CONFIG
        if hasattr(gda_logger, "get_logger"):
            self._logger = gda_logger.get_logger(__name__)
        elif hasattr(gda_logger, "LOGGER"):
            self._logger = getattr(gda_logger.LOGGER, "get_logger", lambda _: gda_logger.LOGGER)(__name__)
        elif hasattr(gda_logger, "GDALogger") and hasattr(gda_logger.GDALogger, "get_logger"):
            self._logger = gda_logger.GDALogger.get_logger(__name__)
        else:
            import logging
            self._logger = logging.getLogger(__name__)

        self._locations_provider = locations_provider

        if filepath:
            self._filepath = Path(filepath)
        else:
            self._filepath = self._config.entities_dir / "sites.json"

        self._registry_metadata: Dict[str, Any] = {
            "_name": "sites.json",
            "_path": "data/entities/sites.json",
            "$schema": "schemas/entities/site_registry.schema.json",
            "schema_version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_modified": datetime.now(timezone.utc).isoformat(),
            "total_sites": 0,
        }
        self._sites: Dict[str, Dict[str, Any]] = {}
        self._filtered_ids: Optional[List[str]] = None
        self._is_dirty: bool = False

        if auto_load:
            self.load()

    # -------------------------------------------------------------------------
    # Lifecycle & Persistence
    # -------------------------------------------------------------------------
    def load(self) -> None:
        """Load and parse sites.json from disk, resetting dirty state and filters."""
        if not self._filepath.exists():
            self._logger.info(
                f"[SYS] Sites registry not found at {self._filepath}. Initializing empty container."
            )
            self._sites = {}
            self._filtered_ids = None
            self._is_dirty = False
            return

        try:
            data = GDAUtil.load_json(self._filepath)
            self._registry_metadata["_name"] = data.get("_name", "sites.json")
            self._registry_metadata["_path"] = data.get(
                "_path", "data/entities/sites.json"
            )
            self._registry_metadata["$schema"] = data.get(
                "$schema", "schemas/entities/site_registry.schema.json"
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

            raw_sites = data.get("sites", [])
            self._sites = {item["site_id"]: item for item in raw_sites}
            self._filtered_ids = None
            self._is_dirty = False
            self._logger.info(
                f"[SYS] Loaded {len(self._sites)} sites from {self._filepath.name}."
            )
        except Exception as exc:
            self._logger.error(
                f"[SYS] Failed to load sites from {self._filepath}: {exc}"
            )
            raise

    def refresh(self) -> None:
        """Reload registry from disk, discarding any unsaved in-memory mutations."""
        self.load()

    def save(
        self,
        output_path: Optional[Union[str, Path]] = None,
        force: bool = False,
        create_backup: bool = True,
    ) -> bool:
        """Persist registry to disk via unified GDAUtil atomic write.

        Args:
            output_path: Optional explicit output destination. If omitted, writes
              to canonical self._filepath.
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

        self._registry_metadata["last_modified"] = datetime.now(
            timezone.utc
        ).isoformat()
        self._registry_metadata["total_sites"] = len(self._sites)

        payload = dict(self._registry_metadata)
        sorted_sites = sorted(
            self._sites.values(),
            key=lambda item: int(item["site_id"].split("-")[1]),
        )
        payload["sites"] = sorted_sites

        GDAUtil.save_json(target, payload, create_backup=should_backup)
        if target == self._filepath:
            self._is_dirty = False

        self._logger.info(
            f"[SYS] Successfully persisted {len(sorted_sites)} sites to {target.name}."
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
        """Total count of registered sites in memory."""
        return len(self._sites)

    @property
    def filtered_count(self) -> int:
        """Count of records in the currently active filtered subset."""
        if self._filtered_ids is None:
            return len(self._sites)
        return len(self._filtered_ids)

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------
    def _mint_next_id(self) -> str:
        """Calculate and return the next zero-padded monotonic identifier."""
        if not self._sites:
            return "SITE-00001"
        highest_idx = 0
        for sid in self._sites.keys():
            match = self._SITE_ID_REGEX.match(sid)
            if match:
                val = int(sid.split("-")[1])
                if val > highest_idx:
                    highest_idx = val
        return f"SITE-{highest_idx + 1:05d}"

    def _validate_location_reference(self, location_id: str) -> None:
        """Enforce format and optional referential integrity against GDALocations."""
        if not self._LOCATION_ID_REGEX.match(location_id):
            raise ValueError(f"Malformed location_id pattern: '{location_id}'")
        if self._locations_provider is not None:
            exists = getattr(self._locations_provider, "exists", None)
            if callable(exists):
                if not exists(location_id):
                    raise KeyError(
                        f"Foreign key violation: location_id '{location_id}' not found in locations registry."
                    )
            else:
                loc = getattr(self._locations_provider, "get_by_id", lambda _: None)(
                    location_id
                )
                if loc is None:
                    raise KeyError(
                        f"Foreign key violation: location_id '{location_id}' not found in locations registry."
                    )

    def get_by_id(self, site_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an individual site entity by primary key."""
        record = self._sites.get(site_id)
        if record is None:
            return None
        return dict(record)

    def add(
        self,
        site_type: str,
        name: str,
        location_id: str,
        site_id: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        address_line_1: Optional[str] = None,
        address_line_2: Optional[str] = None,
        postal_code: Optional[str] = None,
        coordinates: Optional[Dict[str, float]] = None,
        notes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Mint identifier (if omitted), validate, and stage a new site entity."""
        clean_type = site_type.strip().upper()
        if clean_type not in self._VALID_SITE_TYPES:
            raise ValueError(
                f"Invalid site_type '{site_type}'. Must be one of {sorted(self._VALID_SITE_TYPES)}"
            )

        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Site name must not be empty.")

        clean_loc = location_id.strip()
        self._validate_location_reference(clean_loc)

        assigned_id = site_id.strip() if site_id else self._mint_next_id()
        if not self._SITE_ID_REGEX.match(assigned_id):
            raise ValueError(f"Malformed site_id pattern: '{assigned_id}'")
        if assigned_id in self._sites:
            raise KeyError(
                f"Site identifier '{assigned_id}' already exists in registry."
            )

        clean_coords = None
        if coordinates is not None:
            if "latitude" not in coordinates or "longitude" not in coordinates:
                raise ValueError(
                    "Coordinates dictionary must specify both 'latitude' and 'longitude'."
                )
            clean_coords = {
                "latitude": float(coordinates["latitude"]),
                "longitude": float(coordinates["longitude"]),
            }

        now_iso = datetime.now(timezone.utc).isoformat()
        record: Dict[str, Any] = {
            "site_id": assigned_id,
            "site_type": clean_type,
            "name": clean_name,
            "aliases": [a.strip() for a in (aliases or []) if a.strip()],
            "location_id": clean_loc,
            "address": {
                "address_line_1": (
                    address_line_1.strip() if address_line_1 else None
                ),
                "address_line_2": (
                    address_line_2.strip() if address_line_2 else None
                ),
                "postal_code": postal_code.strip() if postal_code else None,
                "coordinates": clean_coords,
            },
            "notes": notes or [],
            "last_updated": now_iso,
        }

        self._sites[assigned_id] = record
        self._is_dirty = True
        self._logger.info(
            f"[SYS] Staged site addition: {assigned_id} ('{clean_name}')."
        )
        return assigned_id

    def edit(
        self, site_id: str, updates: Dict[str, Any], overwrite_none: bool = False
    ) -> bool:
        """Apply field-level modifications to an existing registered site."""
        if site_id not in self._sites:
            raise KeyError(f"Site '{site_id}' does not exist in registry.")

        record = self._sites[site_id]
        modified = False

        if "site_type" in updates:
            clean_type = updates["site_type"].strip().upper()
            if clean_type not in self._VALID_SITE_TYPES:
                raise ValueError(f"Invalid site_type '{clean_type}'")
            if record["site_type"] != clean_type:
                record["site_type"] = clean_type
                modified = True

        if "name" in updates:
            clean_name = updates["name"].strip()
            if not clean_name:
                raise ValueError("Site name must not be empty.")
            if record["name"] != clean_name:
                record["name"] = clean_name
                modified = True

        if "location_id" in updates:
            clean_loc = updates["location_id"].strip()
            self._validate_location_reference(clean_loc)
            if record["location_id"] != clean_loc:
                record["location_id"] = clean_loc
                modified = True

        if "aliases" in updates:
            new_aliases = [a.strip() for a in updates["aliases"] if a.strip()]
            if record["aliases"] != new_aliases:
                record["aliases"] = new_aliases
                modified = True

        if "address" in updates:
            addr_updates = updates["address"]
            current_addr = record["address"]
            for key in [
                "address_line_1",
                "address_line_2",
                "postal_code",
                "coordinates",
            ]:
                if key in addr_updates:
                    val = addr_updates[key]
                    if key == "coordinates" and val is not None:
                        val = {
                            "latitude": float(val["latitude"]),
                            "longitude": float(val["longitude"]),
                        }
                    if val is not None or overwrite_none:
                        if current_addr.get(key) != val:
                            current_addr[key] = val
                            modified = True

        if "notes" in updates:
            record["notes"] = updates["notes"]
            modified = True

        if modified:
            record["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._is_dirty = True
            self._logger.info(f"[SYS] Staged edits for site {site_id}.")

        return modified

    def delete(self, site_id: str) -> bool:
        """Remove a site by primary identifier.

        Caller must ensure referential safety across facts/people.
        """
        if site_id not in self._sites:
            return False

        del self._sites[site_id]
        if self._filtered_ids is not None and site_id in self._filtered_ids:
            self._filtered_ids.remove(site_id)

        self._is_dirty = True
        self._logger.warning(
            f"[SYS] Deleted site {site_id} from registry. Ensure fact assertions are remediated."
        )
        return True

    # -------------------------------------------------------------------------
    # Alias Management Protocol
    # -------------------------------------------------------------------------
    def add_alias(self, site_id: str, alias: str) -> bool:
        """Append a unique alias string to a site entity. Marks registry dirty."""
        if site_id not in self._sites:
            raise KeyError(f"Site '{site_id}' does not exist in registry.")

        clean_alias = alias.strip()
        if not clean_alias:
            return False

        record = self._sites[site_id]
        current_aliases = record.get("aliases", [])
        if clean_alias not in current_aliases:
            current_aliases.append(clean_alias)
            record["aliases"] = current_aliases
            record["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._is_dirty = True
            self._logger.info(f"[SYS] Added alias '{clean_alias}' to {site_id}.")
            return True
        return False

    def remove_alias(self, site_id: str, alias: str) -> bool:
        """Remove an alias from a site entity. Marks registry dirty."""
        if site_id not in self._sites:
            raise KeyError(f"Site '{site_id}' does not exist in registry.")

        clean_alias = alias.strip()
        record = self._sites[site_id]
        current_aliases = record.get("aliases", [])
        if clean_alias in current_aliases:
            current_aliases.remove(clean_alias)
            record["aliases"] = current_aliases
            record["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._is_dirty = True
            self._logger.info(f"[SYS] Removed alias '{clean_alias}' from {site_id}.")
            return True
        return False

    # -------------------------------------------------------------------------
    # Search Engine (Exact, Wildcard, & Fuzzy)
    # -------------------------------------------------------------------------
    def find_one(
        self,
        query: str,
        location_id: Optional[str] = None,
        site_type: Optional[str] = None,
        fuzzy_threshold: float = 0.85,
    ) -> Optional[Dict[str, Any]]:
        """Return the single highest-scoring match for a name/alias query."""
        results = self.search(
            query=query,
            location_id=location_id,
            site_type=site_type,
            use_fuzzy=True,
            fuzzy_threshold=fuzzy_threshold,
        )
        return results[0] if results else None

    def search(
        self,
        query: Optional[str] = None,
        location_id: Optional[str] = None,
        site_type: Optional[str] = None,
        has_coordinates: Optional[bool] = None,
        use_fuzzy: bool = True,
        fuzzy_threshold: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """Search registered sites matching query against name, aliases, or filters."""
        matches: List[Dict[str, Any]] = []
        clean_query = query.strip().lower() if query else None

        pool = (
            [self._sites[sid] for sid in self._filtered_ids]
            if self._filtered_ids is not None
            else list(self._sites.values())
        )

        for item in pool:
            if location_id and item["location_id"] != location_id:
                continue
            if site_type and item["site_type"] != site_type.upper():
                continue
            if has_coordinates is not None:
                coords_exist = item["address"].get("coordinates") is not None
                if coords_exist != has_coordinates:
                    continue

            if not clean_query:
                matches.append(dict(item))
                continue

            candidates = [item["name"]] + item.get("aliases", [])
            matched = False

            for cand in candidates:
                cand_lower = cand.lower()

                if any(char in clean_query for char in ["*", "?", "["]):
                    if fnmatch.fnmatch(cand_lower, clean_query):
                        matched = True
                        break
                elif clean_query in cand_lower:
                    matched = True
                    break
                elif use_fuzzy:
                    ratio = SequenceMatcher(None, clean_query, cand_lower).ratio()
                    if ratio >= fuzzy_threshold:
                        matched = True
                        break

            if matched:
                matches.append(dict(item))

        return matches

    # -------------------------------------------------------------------------
    # View State & Batch Operations
    # -------------------------------------------------------------------------
    def set_filter(
        self,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
        location_id: Optional[str] = None,
        site_type: Optional[str] = None,
        name_pattern: Optional[str] = None,
    ) -> int:
        """Apply constraint filter to working set. Subsequent queries respect this view."""
        matched_ids: List[str] = []

        for sid, item in self._sites.items():
            if location_id and item["location_id"] != location_id:
                continue
            if site_type and item["site_type"] != site_type.upper():
                continue
            if name_pattern:
                cand_names = [item["name"]] + item.get("aliases", [])
                if not any(
                    fnmatch.fnmatch(name.lower(), name_pattern.lower())
                    for name in cand_names
                ):
                    continue
            if predicate and not predicate(item):
                continue
            matched_ids.append(sid)

        self._filtered_ids = matched_ids
        return len(matched_ids)

    def clear_filter(self) -> None:
        """Reset the active view state; all entities become active."""
        self._filtered_ids = None

    def get_filtered(self) -> List[Dict[str, Any]]:
        """Return records passing active filter (or entire registry if clean)."""
        if self._filtered_ids is None:
            return [dict(item) for item in self._sites.values()]
        return [dict(self._sites[sid]) for sid in self._filtered_ids]

    def update_filtered(
        self, updates: Dict[str, Any], validate_location: bool = True
    ) -> int:
        """Apply atomic modifications across all sites currently passing active filter."""
        targets = (
            list(self._filtered_ids)
            if self._filtered_ids is not None
            else list(self._sites.keys())
        )
        if not targets:
            return 0

        if "location_id" in updates and validate_location:
            self._validate_location_reference(updates["location_id"].strip())

        modified_count = 0
        for sid in targets:
            if self.edit(sid, updates):
                modified_count += 1

        return modified_count

    # -------------------------------------------------------------------------
    # Dunder Protocols
    # -------------------------------------------------------------------------
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over active working set (respects filter)."""
        if self._filtered_ids is not None:
            for sid in self._filtered_ids:
                yield dict(self._sites[sid])
        else:
            for item in self._sites.values():
                yield dict(item)

    def __len__(self) -> int:
        """Return count of active working set."""
        return self.filtered_count

    def __contains__(self, site_id: str) -> bool:
        """Evaluate 'if "SITE-00001" in sites_registry:'."""
        return site_id in self._sites