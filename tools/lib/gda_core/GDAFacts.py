# Name: GDAFacts.py
# Path: tools/lib/gda_core/GDAFacts.py

"""
Centralized facts registry management class for the Genealogy Digital Archive.

Provides in-memory indexing, foreign-key cross-referencing (_person_xref),
dirty-state tracking, transactional commit/rollback workflows, and Safe
Backup Protocol integration shared across facts_insp, facts_md, and facts_merge.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterator

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDAUtil import GDAUtil


class GDAFacts:
    """
    Transactional container and indexing engine for data/entities/facts.json.

    Supports context management for batch updates:
        with GDAFacts() as facts_mgr:
            fact = facts_mgr.get("...")
            fact["notes"] = "Updated"
            facts_mgr.mark_dirty(fact["fact_id"])
    """

    def __init__(
        self,
        facts_path: Path | None = None,
        auto_commit: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self.facts_path = facts_path or CONFIG.facts
        self.auto_commit = auto_commit
        self.log = logger or logging.getLogger("gda_core.facts")

        self.payload: dict[str, Any] = {}
        self.facts_list: list[dict[str, Any]] = []
        self._index: dict[str, dict[str, Any]] = {}
        self._person_xref: dict[str, list[dict[str, Any]]] = {}
        self.dirty_ids: set[str] = set()

        self._load()

    def __enter__(self) -> GDAFacts:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is None and self.auto_commit and self.is_dirty:
            self.commit()

    def __len__(self) -> int:
        return len(self.facts_list)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.facts_list)

    @property
    def is_dirty(self) -> bool:
        return len(self.dirty_ids) > 0

    @property
    def existing_ids(self) -> set[str]:
        return set(self._index.keys())

    def _load(self) -> None:
        """Loads and indexes facts from disk."""
        if not self.facts_path.exists():
            self.log.warning(f"Facts file not found at {self.facts_path}. Initializing empty registry.")
            self.payload = {"facts": []}
            self.facts_list = []
        else:
            raw_data = GDAUtil.load_json(self.facts_path)
            if isinstance(raw_data, dict):
                self.payload = raw_data
                self.facts_list = raw_data.get("facts", [])
            elif isinstance(raw_data, list):
                self.payload = {"facts": raw_data}
                self.facts_list = raw_data
            else:
                self.payload = {"facts": []}
                self.facts_list = []

        self._rebuild_indices()
        self.dirty_ids.clear()

    def _rebuild_indices(self) -> None:
        """Reconstructs internal primary and foreign key lookup mappings."""
        self._index = {}
        self._person_xref = {}

        for fact in self.facts_list:
            if not isinstance(fact, dict):
                continue
            fid = fact.get("fact_id")
            if fid:
                self._index[fid] = fact

            pid = fact.get("person_id")
            if pid:
                if pid not in self._person_xref:
                    self._person_xref[pid] = []
                self._person_xref[pid].append(fact)

    def get(self, fact_id: str) -> dict[str, Any] | None:
        """Resolves fact record by exact GUID or 8-character prefix match."""
        if fact_id in self._index:
            return self._index[fact_id]

        if len(fact_id) >= 8:
            matches = [
                fact for fid, fact in self._index.items()
                if fid.startswith(fact_id)
            ]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                self.log.warning(f"Ambiguous short fact_id prefix '{fact_id}' matched {len(matches)} records.")

        return None

    def get_by_person(self, person_id: str) -> list[dict[str, Any]]:
        """Returns all facts cross-referenced to a specific person_id."""
        return self._person_xref.get(person_id, [])

    def mark_dirty(self, fact_id: str) -> None:
        """Flags an existing fact record as modified."""
        if fact_id in self._index:
            self.dirty_ids.add(fact_id)

    def replace(self, fact_id: str, new_fact: dict[str, Any]) -> bool:
        """
        Replaces an existing fact record in-place with an updated fact dictionary.
        Enforces immutable fact_id: new_fact['fact_id'] must match the existing fact_id.
        """
        existing = self.get(fact_id)
        if not existing:
            return False

        canonical_id = existing["fact_id"]
        new_id = new_fact.get("fact_id")

        if not new_id:
            raise ValueError("Replacement fact record must contain a valid 'fact_id'.")

        if new_id != canonical_id:
            raise ValueError(
                f"fact_id is immutable. Cannot replace '{canonical_id}' with '{new_id}'."
            )

        # Swap in-place in facts_list to preserve ordering
        idx = self.facts_list.index(existing)
        self.facts_list[idx] = new_fact
        self._index[canonical_id] = new_fact

        # Re-synchronize foreign key cross-reference
        old_pid = existing.get("person_id")
        new_pid = new_fact.get("person_id")

        if old_pid != new_pid:
            if old_pid and old_pid in self._person_xref:
                self._person_xref[old_pid] = [
                    f for f in self._person_xref[old_pid] if f.get("fact_id") != canonical_id
                ]
            if new_pid:
                self._person_xref.setdefault(new_pid, []).append(new_fact)
        else:
            # Refresh object pointer in _person_xref list
            if new_pid and new_pid in self._person_xref:
                self._person_xref[new_pid] = [
                    new_fact if f.get("fact_id") == canonical_id else f
                    for f in self._person_xref[new_pid]
                ]

        self.dirty_ids.add(canonical_id)
        return True

    def add(self, fact: dict[str, Any]) -> bool:
        """Appends a new fact record and indexes it."""
        fid = fact.get("fact_id")
        if not fid:
            raise ValueError("Fact record must contain a valid 'fact_id'.")
        if fid in self._index:
            raise ValueError(f"Fact with ID '{fid}' already exists.")

        self.facts_list.append(fact)
        self._index[fid] = fact
        pid = fact.get("person_id")
        if pid:
            self._person_xref.setdefault(pid, []).append(fact)

        self.dirty_ids.add(fid)
        return True

    def remove(self, fact_id: str) -> bool:
        """Removes a fact record by ID."""
        fact = self.get(fact_id)
        if not fact:
            return False

        actual_id = fact["fact_id"]
        self.facts_list.remove(fact)
        del self._index[actual_id]

        pid = fact.get("person_id")
        if pid and pid in self._person_xref:
            self._person_xref[pid] = [f for f in self._person_xref[pid] if f.get("fact_id") != actual_id]

        self.dirty_ids.add(actual_id)
        return True

    def commit(self) -> bool:
        """Creates an atomic Safe Backup and persists staged changes to disk."""
        if not self.is_dirty:
            self.log.info("No staged changes to commit.")
            return True

        self.log.info(f"Safe Backup Protocol: creating pre-write snapshot for {self.facts_path.name}")
        backup_file = GDAUtil.create_safe_backup(self.facts_path)
        self.log.info(f"Safe Backup snapshot created at {backup_file}")

        self.payload["facts"] = self.facts_list
        GDAUtil.save_json(self.facts_path, self.payload)
        self.log.info(f"Committed {len(self.dirty_ids)} modified/added records to {self.facts_path.name}")
        self.dirty_ids.clear()
        return True

    def rollback(self) -> None:
        """Discards staged in-memory mutations and reloads clean disk state."""
        self.log.info("Rolling back staged changes and reloading from disk.")
        self._load()