# Name: gfi.py
# Path: tools/ops/gfi.py

"""GFI (Genealogy Fact Intake).

Permanent operational tool for staging intake, semantic quarantine filtering,
auto-chunked batch aggregation, master facts appending, synchronized rollback backups,
person unions synchronization, and interactive console management.
"""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil

__version__ = "1.0.2+build.20260925.2"


def load_valid_person_ids(
    people_path: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
    config: Optional[GDAConfig] = None,
) -> Set[str]:
    """Loads all person_ids currently in people.json."""
    if people_path is None:
        cfg = config or GDAConfig(REPO_ROOT)
        entities_dir = getattr(cfg, "entities_dir", REPO_ROOT / "data" / "entities")
        people_path = entities_dir / "people.json"

    if not people_path.is_file():
        if logger:
            logger.error("people.json not found at %s", people_path)
        return set()

    try:
        data = GDAUtil.load_json(people_path)
        return {p["person_id"] for p in data.get("persons", []) if "person_id" in p}
    except Exception as exc:
        if logger:
            logger.error("Failed to parse people.json: %s", exc)
        return set()


def sync_union_for_fact(
    people_payload: Dict[str, Any],
    fact: Dict[str, Any],
    logger: Optional[logging.Logger] = None,
) -> int:
    """Synchronizes Marriage or Divorce fact data into person unions symmetrically.

    Returns the number of person union endpoints updated or created.
    """
    ftype = fact.get("fact_type")
    if ftype not in ("Marriage", "Divorce"):
        return 0

    pid = fact.get("person_id")
    if not pid:
        return 0

    spouse_ids = [
        a.get("person_id")
        for a in fact.get("associated_people", [])
        if isinstance(a, dict) and a.get("person_id")
    ]
    if not spouse_ids:
        return 0

    person_map = {p["person_id"]: p for p in people_payload.get("persons", []) if "person_id" in p}
    if pid not in person_map:
        return 0

    updated_count = 0
    f_date = fact.get("date")
    f_place = fact.get("location")
    f_notes = fact.get("notes")

    for sid in spouse_ids:
        if sid not in person_map:
            continue

        p_a = person_map[pid]
        p_b = person_map[sid]

        if "unions" not in p_a:
            p_a["unions"] = []
        if "unions" not in p_b:
            p_b["unions"] = []

        u_a = next((u for u in p_a["unions"] if u.get("spouse_id") == sid), None)
        u_b = next((u for u in p_b["unions"] if u.get("spouse_id") == pid), None)

        if not u_a:
            u_a = {
                "spouse_id": sid,
                "status": "DIVORCED" if ftype == "Divorce" else "MARRIED",
                "marriage_date": f_date if ftype == "Marriage" else None,
                "end_date": f_date if ftype == "Divorce" else None,
                "place": f_place,
                "notes": f_notes,
            }
            p_a["unions"].append(u_a)
            updated_count += 1
        else:
            if ftype == "Marriage":
                u_a["status"] = "MARRIED" if u_a.get("status") != "DIVORCED" else u_a.get("status")
                u_a["marriage_date"] = f_date or u_a.get("marriage_date")
                if f_place:
                    u_a["place"] = f_place
            elif ftype == "Divorce":
                u_a["status"] = "DIVORCED"
                u_a["end_date"] = f_date or u_a.get("end_date")
            updated_count += 1

        if not u_b:
            u_b = {
                "spouse_id": pid,
                "status": "DIVORCED" if ftype == "Divorce" else "MARRIED",
                "marriage_date": f_date if ftype == "Marriage" else None,
                "end_date": f_date if ftype == "Divorce" else None,
                "place": f_place,
                "notes": f_notes,
            }
            p_b["unions"].append(u_b)
            updated_count += 1
        else:
            if ftype == "Marriage":
                u_b["status"] = "MARRIED" if u_b.get("status") != "DIVORCED" else u_b.get("status")
                u_b["marriage_date"] = f_date or u_b.get("marriage_date")
                if f_place:
                    u_b["place"] = f_place
            elif ftype == "Divorce":
                u_b["status"] = "DIVORCED"
                u_b["end_date"] = f_date or u_b.get("end_date")
            updated_count += 1

        if logger:
            logger.info("Synchronized %s union symmetrically between %s and %s", ftype, pid, sid)

    return updated_count


class FactIntakeEngine:
    """Manages intake, quarantine triage, batch appending, and union sync."""

    def __init__(
        self,
        config: GDAConfig,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.logger = logger
        self.entities_dir = getattr(config, "entities_dir", config.root / "data" / "entities")
        self.quarantine_dir = getattr(config, "quarantine_dir", self.entities_dir / "quarantine")
        self.facts_path = self.entities_dir / "facts.json"
        self.people_path = self.entities_dir / "people.json"
        self.backups_dir = getattr(config, "backups_dir", config.root / "backups")

    def _relocate_to_quarantine(self, source_file: Path) -> Path:
        """Safely moves a failed or invalid factoid file into the quarantine directory."""
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        dest_file = self.quarantine_dir / source_file.name
        shutil.copy2(source_file, dest_file)
        source_file.unlink(missing_ok=True)
        return dest_file

    def validate_factoid(
        self,
        factoid: Dict[str, Any],
        valid_pids: Set[str],
    ) -> Tuple[bool, str]:
        """Validates schema conformance and person reference validity."""
        if not isinstance(factoid, dict):
            return False, "Payload is not a valid JSON dictionary"

        fid = factoid.get("fact_id")
        if not fid:
            return False, "Missing required fact_id"

        pid = factoid.get("person_id")
        if not pid:
            return False, "Missing required person_id"

        if pid not in valid_pids:
            return False, f"Referenced person_id '{pid}' not found in registry"

        ftype = factoid.get("fact_type")
        if not ftype:
            return False, "Missing required fact_type"

        return True, "Valid"

    def process_staged_factoids(self, staging_files: List[Path]) -> Dict[str, Any]:
        """Triage staged factoids: appends valid facts and routes invalid to quarantine."""
        valid_pids = load_valid_person_ids(self.people_path, self.logger, self.config)

        facts_payload = (
            GDAUtil.load_json(self.facts_path)
            if self.facts_path.is_file()
            else {
                "$schema": "schemas/entities/fact_registry.schema.json",
                "schema_version": "1.0.1",
                "facts": [],
            }
        )
        people_payload = (
            GDAUtil.load_json(self.people_path)
            if self.people_path.is_file()
            else {"persons": []}
        )

        existing_fids = {f["fact_id"] for f in facts_payload.get("facts", []) if "fact_id" in f}

        accepted_facts: List[Dict[str, Any]] = []
        quarantined_files: List[Path] = []
        union_sync_count = 0

        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        for sfile in staging_files:
            try:
                content = GDAUtil.load_json(sfile)
            except Exception as exc:
                self.logger.warning("Unreadable factoid file %s: %s", sfile.name, exc)
                q_dest = self._relocate_to_quarantine(sfile)
                quarantined_files.append(q_dest)
                continue

            valid, reason = self.validate_factoid(content, valid_pids)
            if not valid:
                self.logger.warning("Quarantining %s: %s", sfile.name, reason)
                q_dest = self._relocate_to_quarantine(sfile)
                quarantined_files.append(q_dest)
                continue

            fid = content["fact_id"]
            if fid in existing_fids:
                self.logger.warning("Quarantining %s: Duplicate fact_id '%s'", sfile.name, fid)
                q_dest = self._relocate_to_quarantine(sfile)
                quarantined_files.append(q_dest)
                continue

            accepted_facts.append(content)
            existing_fids.add(fid)
            sfile.unlink(missing_ok=True)

        if accepted_facts:
            # Safe Backup Protocol
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.facts_path.is_file():
                shutil.copy2(self.facts_path, self.backups_dir / f"facts.json.{ts}.bk")
            if self.people_path.is_file():
                shutil.copy2(self.people_path, self.backups_dir / f"people.json.{ts}.bk")

            for fact in accepted_facts:
                facts_payload.setdefault("facts", []).append(fact)
                u_synced = sync_union_for_fact(people_payload, fact, self.logger)
                union_sync_count += u_synced

            facts_payload["last_modified"] = datetime.now().isoformat()
            people_payload["last_modified"] = datetime.now().isoformat()

            GDAUtil.save_json(self.facts_path, facts_payload)
            GDAUtil.save_json(self.people_path, people_payload)

        return {
            "processed": len(staging_files),
            "accepted": len(accepted_facts),
            "quarantined": len(quarantined_files),
            "unions_synced": union_sync_count,
        }


def run_cli() -> int:
    parser = argparse.ArgumentParser(description="Genealogy Fact Intake (GFI)")
    parser.add_argument("--dir", "-d", type=Path, default=None, help="Directory containing staged factoids")
    parser.add_argument("--verbose", "-v", action="store_true", help="Emit verbose logging traces")
    args = parser.parse_args()

    logger = setup_logger("gfi", ephemeral=True, console_level=logging.DEBUG if args.verbose else logging.INFO)
    logger.info("GFI version %s initializing", __version__)

    config = GDAConfig(REPO_ROOT)
    staging_dir = args.dir or (getattr(config, "entities_dir", REPO_ROOT / "data" / "entities") / "quarantine")

    if not staging_dir.is_dir():
        logger.error("Staging directory not found: %s", staging_dir)
        return 1

    staging_files = sorted(list(staging_dir.glob("factoid-*.json")))
    if not staging_files:
        logger.info("No staged factoids found to process in %s", staging_dir)
        return 0

    engine = FactIntakeEngine(config, logger)
    results = engine.process_staged_factoids(staging_files)

    logger.info("==========================================")
    logger.info("GFI INTAKE EXECUTION SUMMARY")
    logger.info("==========================================")
    logger.info("Total Factoids Examined:  %d", results["processed"])
    logger.info("Accepted & Appended:      %d", results["accepted"])
    logger.info("Quarantined:              %d", results["quarantined"])
    logger.info("Union Endpoints Synced:   %d", results["unions_synced"])
    logger.info("==========================================")

    return 0


if __name__ == "__main__":
    sys.exit(run_cli())