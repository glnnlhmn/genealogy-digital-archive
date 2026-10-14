# Name: deploy_refactor.ps1
# Path: tools/sys/deploy_refactor.ps1

$targetPath = "tools/lib/gdadomain/src/gdadomain/facts.py"
$backupDir = "backups"

# Enforce Safe Backup Protocol
if (Test-Path $targetPath) {
    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    }
    $timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
    $backupPath = Join-Path $backupDir "facts.py.$timestamp.bk"
    Copy-Item -Path $targetPath -Destination $backupPath -Force
    Write-Host "[BACKUP] Created atomic snapshot: $backupPath" -ForegroundColor Green
}

$refactoredFactsContent = @'
# Name: facts.py
# Path: tools/lib/gdadomain/src/gdadomain/facts.py
# Version: 1.2.0+build.20261011.17

"""Centralized facts registry management class for the Genealogy Digital Archive.

Operational Role:
    Manages data/entities/facts.json with in-place entity tombstoning,
    dual-indexing, secondary indexing by location and fact_type,
    foreign-key cross-referencing (_person_xref), dirty-state tracking,
    reciprocal kinship fact verification/addition, transparent graveyard
    redirection, and Safe Backup Protocol integration.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import uuid

from gdacore.config import CONFIG, GDAConfig
from gdacore.introspectable import IntrospectableMixin
from gdacore.logger import GDALogger
from gdacore.reference_manager import GDAReferenceManager
from gdacore.util import GDAUtil
from gdacore.vocabulary_manager import GDAVocabularyManager

__version__ = "1.2.0+build.20261011.17"

VOCAB_MGR = GDAVocabularyManager()


class GDAFacts(IntrospectableMixin, Collection[Dict[str, Any]]):
    """Manage transactional operations and cross-referencing for facts.json.

    Attributes:
        facts_path: Canonical filesystem path to facts.json.
        auto_commit: If True, commits dirty changes upon clean context manager exit.
        dirty_ids: Set of modified fact identifiers staged for persistence.
        is_dirty: True if active assertions or graveyard stores have unpersisted changes.
        count: Count of active fact assertions in memory.
        total_count: Total count of all fact records across active and graveyard partitions.
        graveyard: Dictionary mapping tombstone identifiers to record payloads.
        existing_ids: Set of all active canonical fact IDs.
    """

    def __init__(
        self,
        filepath: Optional[Union[str, Path]] = None,
        config: Optional[GDAConfig] = None,
        auto_commit: bool = True,
    ) -> None:
        """Initialize the GDAFacts container and load active and tombstoned assertions.

        Args:
            filepath: Path to facts.json. Defaults to canonical CONFIG.entities / "facts.json".
            config: Optional GDAConfig instance override. Defaults to global CONFIG.
            auto_commit: If True, commits dirty changes upon clean context manager exit.
        """
        self._config = config or CONFIG
        self._logger = GDALogger.get_logger("gda_facts")

        self._filepath = Path(filepath) if filepath is not None else (self._config.entities / "facts.json")
        self.facts_path = self._filepath
        self.auto_commit = auto_commit

        self._facts: Dict[str, Dict[str, Any]] = {}
        self._graveyard: Dict[str, Dict[str, Any]] = {}
        self._person_xref: Dict[str, List[Dict[str, Any]]] = {}
        self._location_xref: Dict[str, List[Dict[str, Any]]] = {}
        self._type_xref: Dict[str, List[Dict[str, Any]]] = {}

        self.dirty_ids: Set[str] = set()
        self._is_dirty: bool = False

        self.load()

    def __enter__(self) -> GDAFacts:
        """Enter runtime context manager returning the active container instance.

        Returns:
            The initialized GDAFacts instance.
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit runtime context manager and commit staged mutations if execution is clean.

        Args:
            exc_type: Exception class raised within the context, if any.
            exc_val: Exception instance raised within the context, if any.
            exc_tb: Traceback object associated with the exception, if any.
        """
        if exc_type is None and self.auto_commit and self.is_dirty:
            self.save()

    def __len__(self) -> int:
        """Return the count of active, non-deprecated fact assertions.

        Returns:
            Integer count of active assertions.
        """
        return self.count

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over active facts yielding independent deep copies.

        Yields:
            Deep-copied fact assertion dictionary.
        """
        for fact in self._facts.values():
            yield copy.deepcopy(fact)

    def __contains__(self, fact_id: Any) -> bool:
        """Check whether a canonical fact_id exists in the active index.

        Args:
            fact_id: Exact identifier to query.

        Returns:
            True if identifier exists in active index; False otherwise.
        """
        if not isinstance(fact_id, str):
            return False
        return self.exists(fact_id, include_graveyard=False)

    def __getitem__(self, fact_id: str) -> Dict[str, Any]:
        """Retrieve an active fact by exact ID with transparent graveyard redirection.

        Args:
            fact_id: Canonical UUIDv4 identifier.

        Returns:
            Deep-copied fact dictionary matching identifier or its successor.

        Raises:
            KeyError: If fact_id is unregistered or resolves to an unredirected tombstone.
        """
        fact = self.get(fact_id, resolve_redirects=True)
        if fact is None:
            raise KeyError(f"Fact ID '{fact_id}' not found in active registry or resolvable graveyard.")
        return fact

    @property
    def is_dirty(self) -> bool:
        """Return True if active assertions or graveyard stores have unpersisted changes."""
        return self._is_dirty or len(self.dirty_ids) > 0

    @property
    def count(self) -> int:
        """Return count of active fact assertions in memory."""
        return len(self._facts)

    @property
    def total_count(self) -> int:
        """Return total count of all fact records across active and graveyard partitions."""
        return len(self._facts) + len(self._graveyard)

    @property
    def graveyard(self) -> Dict[str, Dict[str, Any]]:
        """Return deep copy of all graveyard tombstones keyed by fact_id."""
        return copy.deepcopy(self._graveyard)

    @property
    def existing_ids(self) -> Set[str]:
        """Return the set of all active canonical fact IDs."""
        return set(self._facts.keys())

    def load(self) -> None:
        """Load active assertions and tombstoned records from disk into memory partitions.

        Raises:
            Exception: If JSON parsing fails or disk read encounters errors.
        """
        if not self._filepath.exists():
            self._logger.warning(f"[FACTS] Facts file not found at {self._filepath}. Initializing empty registry.")
            self._facts = {}
            self._graveyard = {}
            self._is_dirty = True
        else:
            try:
                raw_data = GDAUtil.load_json(self._filepath)
                if isinstance(raw_data, dict):
                    raw_facts = raw_data.get("facts", [])
                elif isinstance(raw_data, list):
                    raw_facts = raw_data
                else:
                    raw_facts = []

                self._facts = {}
                self._graveyard = {}

                for fact in raw_facts:
                    fid = fact.get("fact_id")
                    if not fid:
                        continue
                    if fact.get("is_deprecated", False):
                        self._graveyard[fid] = fact
                    else:
                        self._facts[fid] = fact

                self._is_dirty = False
            except Exception as exc:
                self._logger.error(f"[FACTS] Failed loading {self._filepath}: {exc}")
                raise

        self._rebuild_indices()
        self.dirty_ids.clear()
        self._logger.info(
            f"[FACTS] Loaded {len(self._facts)} active facts and {len(self._graveyard)} "
            f"tombstones from {self._filepath.name}."
        )

    def refresh(self) -> None:
        """Discard in-memory mutations and reload active and graveyard stores from disk."""
        self.load()

    def _rebuild_indices(self) -> None:
        """Rebuild primary, person, location, and type cross-reference lookup structures."""
        self._person_xref = {}
        self._location_xref = {}
        self._type_xref = {}

        for fact in self._facts.values():
            pid = fact.get("person_id")
            if pid:
                self._person_xref.setdefault(pid, []).append(fact)

            assoc = fact.get("associated_people")
            if isinstance(assoc, list):
                for person_entry in assoc:
                    if isinstance(person_entry, dict):
                        apid = person_entry.get("person_id")
                        if apid:
                            self._person_xref.setdefault(apid, []).append(fact)

            loc_id = fact.get("location_id")
            if loc_id:
                self._location_xref.setdefault(loc_id, []).append(fact)

            ftype = fact.get("fact_type")
            if ftype:
                self._type_xref.setdefault(ftype, []).append(fact)

    def resolve_id(self, fact_id: str) -> Optional[str]:
        """Trace deprecation redirect chain through graveyard to canonical active fact ID.

        Args:
            fact_id: Initial fact identifier to evaluate.

        Returns:
            Active canonical UUIDv4 string if resolved; None if defunct or trapped in cycle.
        """
        try:
            target = GDAUtil.resolve_superseded_id(
                entity_id=fact_id,
                graveyard=self._graveyard,
            )
        except RecursionError:
            self._logger.warning(f"[FACTS] Circular graveyard redirect detected for '{fact_id}'.")
            return None

        return target if (target and target in self._facts) else None

    def validate_fact_schema(self, fact_data: Dict[str, Any]) -> List[str]:
        """Validate fact schema structure, identifiers, and controlled vocabularies.

        Args:
            fact_data: Dictionary representing the fact payload to validate.

        Returns:
            List of diagnostic violation messages. Empty list indicates validity.
        """
        errors: List[str] = []
        if not isinstance(fact_data, dict):
            return ["Fact payload must be a dictionary."]

        fid = fact_data.get("fact_id")
        if fid is not None and not GDAReferenceManager.is_valid_fact_id(str(fid)):
            errors.append(f"Invalid fact_id format: '{fid}'. Must be a valid lowercase UUIDv4.")

        pid = fact_data.get("person_id")
        if not pid:
            errors.append("Fact missing required 'person_id'.")
        elif not GDAReferenceManager.is_valid_person_id(str(pid)):
            errors.append(f"Invalid person_id format: '{pid}'. Must follow IND-XXXXX pattern.")

        ftype = fact_data.get("fact_type")
        if not ftype:
            errors.append("Fact missing required 'fact_type'.")
        else:
            valid_types = VOCAB_MGR["fact_type"] if "fact_type" in VOCAB_MGR else None
            if valid_types and ftype not in valid_types:
                errors.append(f"Invalid fact_type: '{ftype}'. Must be in controlled vocabulary.")

        assoc = fact_data.get("associated_people")
        if assoc is not None:
            if not isinstance(assoc, list):
                errors.append("'associated_people' must be a list.")
            else:
                for idx, entry in enumerate(assoc):
                    if not isinstance(entry, dict):
                        errors.append(f"Entry {idx} in 'associated_people' must be a dictionary.")
                        continue
                    apid = entry.get("person_id")
                    if apid and not GDAReferenceManager.is_valid_person_id(str(apid)):
                        errors.append(f"Invalid person_id '{apid}' in associated_people[{idx}].")

        return errors

    def exists(self, fact_id: str, include_graveyard: bool = False) -> bool:
        """Check whether a fact assertion exists by exact ID.

        Args:
            fact_id: Exact canonical UUIDv4 identifier.
            include_graveyard: If True, checks active and graveyard stores.

        Returns:
            True if matching fact exists in designated store; False otherwise.
        """
        if fact_id in self._facts:
            return True
        return include_graveyard and (fact_id in self._graveyard)

    def get(
        self,
        fact_id: str,
        include_graveyard: bool = False,
        resolve_redirects: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a fact record by exact canonical ID.

        Args:
            fact_id: Exact canonical UUIDv4 identifier.
            include_graveyard: If True, returns tombstone payload if unredirected.
            resolve_redirects: If True, traces superseded_by chains to active record.

        Returns:
            Deep-copied fact dictionary or None if not found.
        """
        if fact_id in self._facts:
            return copy.deepcopy(self._facts[fact_id])

        if resolve_redirects:
            canonical_id = self.resolve_id(fact_id)
            if canonical_id and canonical_id in self._facts:
                return copy.deepcopy(self._facts[canonical_id])

        if include_graveyard and fact_id in self._graveyard:
            return copy.deepcopy(self._graveyard[fact_id])

        return None

    def get_facts_for_person(self, person_id: str, include_roles: bool = True) -> List[Dict[str, Any]]:
        """Retrieve all facts where person_id is primary subject or involved in associated_people.

        Args:
            person_id: Canonical person identifier (IND-XXXXX).
            include_roles: If True, includes facts where person is listed in associated_people.
                If False, restricts strictly to primary subject facts.

        Returns:
            List of deep-copied matching fact dictionaries.
        """
        if not include_roles:
            return [copy.deepcopy(f) for f in self._facts.values() if f.get("person_id") == person_id]

        facts = self._person_xref.get(person_id, [])
        return [copy.deepcopy(f) for f in facts]

    def get_facts_by_location(self, location_id: str) -> List[Dict[str, Any]]:
        """Retrieve all facts that occurred at the specified location identifier.

        Args:
            location_id: Canonical location identifier (LOC-XXXXX).

        Returns:
            List of deep-copied matching fact dictionaries.
        """
        return [copy.deepcopy(f) for f in self._location_xref.get(location_id, [])]

    def get_facts_by_type(self, fact_type: str) -> List[Dict[str, Any]]:
        """Retrieve all facts of a specific fact_type.

        Args:
            fact_type: Controlled fact type name.

        Returns:
            List of deep-copied matching fact dictionaries.
        """
        return [copy.deepcopy(f) for f in self._type_xref.get(fact_type, [])]

    def mark_dirty(self, fact_id: str) -> None:
        """Mark an active or tombstoned fact ID as modified, staging changes for persistence.

        Args:
            fact_id: Canonical identifier of modified fact.
        """
        if fact_id in self._facts or fact_id in self._graveyard:
            self.dirty_ids.add(fact_id)
            self._is_dirty = True

    def add(self, fact_data: Dict[str, Any]) -> str:
        """Add a new fact assertion to the active registry.

        If 'fact_id' is omitted, mints a valid lowercase UUIDv4. Validates schema
        conformance and uniqueness.

        Args:
            fact_data: Dictionary containing fact attributes.

        Returns:
            Minted or validated fact_id string.

        Raises:
            ValueError: If schema validation fails or fact_id already exists.
        """
        fact = copy.deepcopy(fact_data)
        fid = fact.get("fact_id")
        if not fid:
            fid = str(uuid.uuid4()).lower()
            fact["fact_id"] = fid

        errors = self.validate_fact_schema(fact)
        if errors:
            raise ValueError(f"Fact schema validation failed: {'; '.join(errors)}")

        if fid in self._facts or fid in self._graveyard:
            raise ValueError(f"Fact with ID '{fid}' already exists.")

        fact.setdefault("is_deprecated", False)
        fact.setdefault("superseded_by", None)
        fact["last_updated"] = GDAUtil.iso_now()

        self._facts[fid] = fact
        self._rebuild_indices()
        self.dirty_ids.add(fid)
        self._is_dirty = True
        return fid

    def edit(self, fact_id: str, new_fact: Dict[str, Any]) -> bool:
        """Replace an existing active fact record in-place.

        Enforces fact_id immutability and re-indexes cross-references.

        Args:
            fact_id: Canonical identifier of the fact to replace.
            new_fact: New fact dictionary payload.

        Returns:
            True if replaced; False if target fact was not found.

        Raises:
            KeyError: If fact_id resides in graveyard.
            ValueError: If replacement is invalid or attempts to modify fact_id.
        """
        if fact_id in self._graveyard:
            raise KeyError(f"Cannot edit deprecated fact '{fact_id}' residing in graveyard.")

        existing = self.get(fact_id, include_graveyard=False, resolve_redirects=False)
        if not existing:
            return False

        canonical_id = existing["fact_id"]
        new_id = new_fact.get("fact_id")

        if not new_id:
            raise ValueError("Replacement fact record must contain a valid 'fact_id'.")
        if new_id != canonical_id:
            raise ValueError(f"fact_id is immutable. Cannot replace '{canonical_id}' with '{new_id}'.")

        if new_fact.get("is_deprecated") is True:
            superseded_target = new_fact.get("superseded_by")
            return self.delete(canonical_id, hard_delete=False, superseded_by=superseded_target)

        errors = self.validate_fact_schema(new_fact)
        if errors:
            raise ValueError(f"Replacement fact schema validation failed: {'; '.join(errors)}")

        mutated_fact = copy.deepcopy(new_fact)
        mutated_fact["last_updated"] = GDAUtil.iso_now()

        self._facts[canonical_id] = mutated_fact
        self._rebuild_indices()
        self.dirty_ids.add(canonical_id)
        self._is_dirty = True
        return True

    def delete(
        self,
        fact_id: str,
        hard_delete: bool = False,
        superseded_by: Optional[str] = None,
    ) -> bool:
        """Soft-delete an active fact to the graveyard, or permanently purge from memory.

        Args:
            fact_id: Canonical identifier of the fact to remove.
            hard_delete: If True, purges record entirely from active and graveyard memory.
            superseded_by: Optional UUIDv4 successor identifier for redirect tracking.

        Returns:
            True if removed or updated; False if not found.

        Raises:
            ValueError: If superseded_by does not conform to lowercase UUIDv4.
            KeyError: If superseded_by ID is not registered in active or graveyard store.
        """
        existing = self.get(fact_id, include_graveyard=True, resolve_redirects=False)
        if not existing:
            return False

        actual_id = existing["fact_id"]

        if hard_delete:
            self._facts.pop(actual_id, None)
            self._graveyard.pop(actual_id, None)
            self._rebuild_indices()
            self.dirty_ids.add(actual_id)
            self._is_dirty = True
            return True

        if superseded_by:
            if not GDAReferenceManager.is_valid_fact_id(superseded_by):
                raise ValueError(f"Invalid superseded_by fact_id '{superseded_by}': must be a lowercase UUIDv4.")
            if not self.exists(superseded_by, include_graveyard=True):
                raise KeyError(f"Target superseded_by fact_id '{superseded_by}' not found in registry.")

        if actual_id in self._graveyard:
            if superseded_by:
                self._graveyard[actual_id]["superseded_by"] = superseded_by
                self._graveyard[actual_id]["last_updated"] = GDAUtil.iso_now()
                self.dirty_ids.add(actual_id)
                self._is_dirty = True
            return True

        record = self._facts.pop(actual_id)
        record["is_deprecated"] = True
        record["superseded_by"] = superseded_by
        record["last_updated"] = GDAUtil.iso_now()

        self._graveyard[actual_id] = record
        self._rebuild_indices()
        self.dirty_ids.add(actual_id)
        self._is_dirty = True
        return True

    def verify_reciprocal_facts(self, fact_id: str) -> tuple[bool, List[Dict[str, Any]]]:
        """Verify whether reciprocal kinship facts exist for associated persons.

        Inspects kinship roles per domain pairing specifications (FATH/MOTH <-> CHIL,
        SPOU <-> SPOU, SIBL <-> SIBL). Does not mutate memory or active store.

        Args:
            fact_id: Canonical identifier of the kinship fact to verify.

        Returns:
            Tuple of (is_reciprocated: bool, missing_facts: list[dict[str, Any]]).
            missing_facts contains fully structured candidate templates ready for addition.

        Raises:
            KeyError: If fact_id is not found in active registry.
        """
        fact = self.get(fact_id, include_graveyard=False, resolve_redirects=True)
        if not fact:
            raise KeyError(f"Fact with ID '{fact_id}' not found.")

        primary_pid = fact.get("person_id")
        ftype = fact.get("fact_type")
        assoc = fact.get("associated_people")

        if not primary_pid or not assoc or not isinstance(assoc, list):
            return True, []

        missing: List[Dict[str, Any]] = []

        reciprocal_role_map = {
            "FATH": "CHIL",
            "MOTH": "CHIL",
            "CHIL": "FATH",
            "SPOU": "SPOU",
            "SIBL": "SIBL",
        }

        for person_entry in assoc:
            if not isinstance(person_entry, dict):
                continue
            partner_pid = person_entry.get("person_id")
            role = person_entry.get("role")
            if not partner_pid or role not in reciprocal_role_map:
                continue

            expected_role = reciprocal_role_map[role]
            partner_facts = self.get_facts_for_person(partner_pid, include_roles=False)
            has_reciprocal = False

            for pf in partner_facts:
                if pf.get("fact_type") != ftype:
                    continue
                p_assoc = pf.get("associated_people")
                if isinstance(p_assoc, list):
                    for pa in p_assoc:
                        if isinstance(pa, dict) and pa.get("person_id") == primary_pid:
                            pa_role = pa.get("role")
                            if pa_role == expected_role or (role == "CHIL" and pa_role in ("FATH", "MOTH")):
                                has_reciprocal = True
                                break
                if has_reciprocal:
                    break

            if not has_reciprocal:
                template = {
                    "fact_id": str(uuid.uuid4()).lower(),
                    "person_id": partner_pid,
                    "fact_type": ftype,
                    "date": fact.get("date", {}),
                    "location_id": fact.get("location_id"),
                    "associated_people": [
                        {
                            "person_id": primary_pid,
                            "role": expected_role,
                        }
                    ],
                    "notes": [f"Reciprocal kinship assertion for fact {fact.get('fact_id')}."],
                }
                missing.append(template)

        return (len(missing) == 0), missing

    def add_reciprocal_facts(self, fact_id: str) -> List[str]:
        """Discover and add missing reciprocal kinship facts for a given assertion.

        Args:
            fact_id: Canonical identifier of the kinship fact.

        Returns:
            List of minted fact_id strings for newly created reciprocal facts.
        """
        is_recip, missing = self.verify_reciprocal_facts(fact_id)
        if is_recip:
            return []

        created_ids: List[str] = []
        for template in missing:
            new_id = self.add(template)
            created_ids.append(new_id)

        return created_ids

    def save(
        self,
        output_path: Optional[Union[str, Path]] = None,
        force: bool = False,
        create_backup: bool = True,
    ) -> bool:
        """Persist dirty active and graveyard registries to disk under Safe Backup Protocol.

        Args:
            output_path: Optional explicit output destination. Defaults to configured backing file.
            force: If True, writes to disk even when is_dirty evaluates to False.
            create_backup: If True, creates atomic pre-write backups in backups/.

        Returns:
            True upon successful persistence; False if clean and unforced.
        """
        if not self.is_dirty and not force:
            self._logger.info("[FACTS] No staged changes to commit; save skipped.")
            return False

        target_file = Path(output_path) if output_path else self._filepath
        combined_facts = list(self._facts.values()) + list(self._graveyard.values())
        sorted_facts = sorted(combined_facts, key=lambda f: str(f.get("fact_id", "")))

        payload: Dict[str, Any] = {
            "_name": target_file.name,
            "_path": target_file.as_posix(),
            "$schema": "schemas/entities/fact_registry.schema.json",
            "schema_version": "1.2.0",
            "last_updated": GDAUtil.iso_now(),
            "total_facts": len(sorted_facts),
            "facts": sorted_facts,
        }

        GDAUtil.save_json(
            file_path=target_file,
            data=payload,
            indent=2,
            create_backup=create_backup,
            backup_dir=self._config.backups,
        )

        self.dirty_ids.clear()
        self._is_dirty = False
        self._logger.info(
            f"[FACTS] Persisted {len(sorted_facts)} facts ({len(self._facts)} active, "
            f"{len(self._graveyard)} graveyard) to {target_file.as_posix()}."
        )
        return True
'@

[System.IO.File]::WriteAllText($targetPath, $refactoredFactsContent, [System.Text.Encoding]::UTF8)

$finalCount = (Get-Content $targetPath).Count
Write-Host "[DEPLOY] facts.py successfully written ($finalCount lines)." -ForegroundColor Cyan