# Name: gfi.py
# Path: tools/ops/gfi.py
# Version: 1.1.0+build.20261006.15

"""GFI: Genealogy Fact Intake Operational CLI Pipeline.

Executes a multi-tier pipeline for staging intake, semantic triage,
batch packaging, and master fact integration:
- Staging Discovery: Scans for staged assertions (factoid-*.json).
- Referential Validation: Validates lowercase UUIDv4 format, valid subject
  IND-XXXXX pointers in people.json, and allowed fact types via GDAReferenceManager.
- Associative Handling: Gracefully permits ungrounded entities in associated_people.
- Union Synchronization: Automatically pairs and synchronizes Marriage and
  Divorce assertions across GDAPeople via update().
- Quarantine Routing: Isolates invalid records with timestamp prefixes and audit reasons.
- Atomic Commit & Safe Backups: Persists changes via GDAFacts and GDAPeople.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))  # pragma: no cover

from gdacore.config import CONFIG, GDAConfig
from gdacore.logger import get_logger, setup_logger
from gdacore.reference_manager import GDAReferenceManager
from gdacore.util import GDAUtil
from gdadomain.facts import GDAFacts
from gdadomain.people import GDAPeople

__version__ = "1.1.0+build.20261006.15"

RECOGNIZED_FACT_TYPES: Set[str] = {
    "Birth",
    "Death",
    "Marriage",
    "Divorce",
    "Burial",
    "Parentage",
    "Residence",
    "Census",
    "Occupation",
    "Military",
    "Immigration",
    "Emigration",
    "Naturalization",
    "Probate",
    "Will",
    "Education",
    "Baptism",
    "Christening",
    "Adoption",
    "Association",
}


def quarantine_factoid(
    file_path: Path,
    reason: str,
    logger: logging.Logger,
    quarantine_dir: Optional[Path] = None,
) -> Path:
    """Quarantines invalid staging file by prepending timestamp and writing reason."""
    q_dir = quarantine_dir or CONFIG.quarantine
    q_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_name = f"{ts}_{file_path.name}"
    dest_path = q_dir / dest_name

    meta_path = q_dir / f"{dest_name}.reason.txt"
    meta_path.write_text(reason, encoding="utf-8")

    file_path.rename(dest_path)
    logger.error("QUARANTINED: %s -> %s (Reason: %s)", file_path.name, dest_name, reason)
    return dest_path


def restore_quarantine(
    logger: logging.Logger,
    quarantine_dir: Optional[Path] = None,
    entities_dir: Optional[Path] = None,
) -> int:
    """Restores all quarantined factoid files back to the entities staging directory."""
    q_dir = quarantine_dir or CONFIG.quarantine
    target_dir = entities_dir or CONFIG.entities
    if not q_dir.exists():
        logger.info("Quarantine directory does not exist: %s", q_dir)
        return 0

    count = 0
    for q_file in q_dir.glob("*_factoid-*.json"):
        clean_name = re.sub(r"^\d{8}_\d{6}_", "", q_file.name)
        dest = target_dir / clean_name
        q_file.rename(dest)
        meta_file = q_dir / f"{q_file.name}.reason.txt"
        if meta_file.exists():
            meta_file.unlink()
        logger.info("RESTORED: %s -> %s", q_file.name, dest.name)
        count += 1
    return count


def discover_staged_factoids(staging_dir: Optional[Path] = None) -> List[Path]:
    """Finds all staged factoid-*.json files in staging directory."""
    s_dir = staging_dir or CONFIG.entities
    if not s_dir.exists():
        return []
    return sorted(s_dir.glob("factoid-*.json"))


def validate_factoid(
    factoid: Dict[str, Any],
    people_mgr: GDAPeople,
) -> Tuple[bool, str]:
    """Validates identifier formatting, subject existence, and controlled taxonomy.

    Ungrounded associated people (missing or non-IND IDs) are accepted cleanly.
    """
    if not isinstance(factoid, dict):
        return False, "Payload is not a valid JSON dictionary"

    fid = factoid.get("fact_id")
    if not fid:
        return False, "Missing required fact_id"
    if not GDAReferenceManager.is_valid_fact_id(fid):
        return False, f"Invalid fact_id format: '{fid}' must be lowercase UUIDv4"

    pid = factoid.get("person_id")
    if not pid:
        return False, "Missing required person_id"
    if not GDAReferenceManager.is_valid_person_id(pid):
        return False, f"Invalid person_id format: '{pid}' must conform to IND-XXXXX"
    if not people_mgr.exists(pid):
        return False, f"Referenced primary subject '{pid}' not found in master people registry"

    ftype = factoid.get("fact_type")
    if not ftype:
        return False, "Missing required fact_type"
    if ftype not in RECOGNIZED_FACT_TYPES:
        return False, f"Unrecognized fact_type: '{ftype}'"

    for assoc in factoid.get("associated_people", []):
        if isinstance(assoc, dict):
            a_id = assoc.get("person_id")
            if a_id:
                if not GDAReferenceManager.is_valid_person_id(a_id):
                    return False, f"Invalid associated person_id format: '{a_id}'"
                if not people_mgr.exists(a_id):
                    return False, f"Associated person '{a_id}' not found in master people registry"

    return True, "Valid"


def sync_unions_for_fact(
    fact: Dict[str, Any],
    people_mgr: GDAPeople,
    logger: logging.Logger,
) -> int:
    """Synchronizes Marriage and Divorce events symmetrically into GDAPeople."""
    ftype = fact.get("fact_type")
    if ftype not in ("Marriage", "Divorce"):
        return 0

    pid = fact.get("person_id")
    if not pid or not people_mgr.exists(pid):
        return 0

    spouse_ids = [
        a.get("person_id")
        for a in fact.get("associated_people", [])
        if isinstance(a, dict) and a.get("person_id") and people_mgr.exists(a.get("person_id"))
    ]
    if not spouse_ids:
        return 0

    status = "DIVORCED" if ftype == "Divorce" else "MARRIED"
    synced = 0
    date_val = fact.get("date")
    place_val = fact.get("location")

    for sid in spouse_ids:
        p_a = people_mgr.get_by_id(pid)
        p_b = people_mgr.get_by_id(sid)

        # Symmetrical Person A union update
        unions_a = list(p_a.get("unions", []))
        u_a = next((u for u in unions_a if u.get("spouse_id") == sid), None)
        if not u_a:
            unions_a.append({
                "spouse_id": sid,
                "status": status,
                "marriage_date": date_val if ftype == "Marriage" else None,
                "end_date": date_val if ftype == "Divorce" else None,
                "place": place_val,
            })
        else:
            u_a["status"] = status
            if ftype == "Marriage" and date_val:
                u_a["marriage_date"] = date_val
            elif ftype == "Divorce" and date_val:
                u_a["end_date"] = date_val
        people_mgr.update(pid, {"unions": unions_a})

        # Symmetrical Person B union update
        unions_b = list(p_b.get("unions", []))
        u_b = next((u for u in unions_b if u.get("spouse_id") == pid), None)
        if not u_b:
            unions_b.append({
                "spouse_id": pid,
                "status": status,
                "marriage_date": date_val if ftype == "Marriage" else None,
                "end_date": date_val if ftype == "Divorce" else None,
                "place": place_val,
            })
        else:
            u_b["status"] = status
            if ftype == "Marriage" and date_val:
                u_b["marriage_date"] = date_val
            elif ftype == "Divorce" and date_val:
                u_b["end_date"] = date_val
        people_mgr.update(sid, {"unions": unions_b})

        synced += 1
        logger.info("Synchronized %s union symmetrically between %s and %s", ftype, pid, sid)

    return synced


def process_intake_batch(
    staged_files: List[Path],
    facts_mgr: GDAFacts,
    people_mgr: GDAPeople,
    logger: logging.Logger,
    batch_size: int = 75,
    quarantine_dir: Optional[Path] = None,
    fact_new_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Triages, validates, batches, and stages factoids."""
    target_q = quarantine_dir or CONFIG.quarantine
    target_new = fact_new_dir or (CONFIG.entities / "fact-new")

    accepted_facts: List[Dict[str, Any]] = []
    quarantined_count = 0
    accepted_files: List[Path] = []

    for fpath in staged_files:
        try:
            payload = GDAUtil.load_json(fpath)
        except Exception as exc:
            if not dry_run:
                quarantine_factoid(fpath, f"JSON Parse Error: {exc}", logger, target_q)
            quarantined_count += 1
            continue

        valid, reason = validate_factoid(payload, people_mgr)
        if not valid:
            if not dry_run:
                quarantine_factoid(fpath, reason, logger, target_q)
            quarantined_count += 1
            continue

        fid = payload.get("fact_id")
        if fid in facts_mgr.existing_ids:
            if not dry_run:
                quarantine_factoid(fpath, f"Duplicate fact_id collision: '{fid}' already exists", logger, target_q)
            quarantined_count += 1
            continue

        accepted_facts.append(payload)
        accepted_files.append(fpath)

    if not accepted_facts:
        return {
            "total_processed": len(staged_files),
            "accepted": 0,
            "quarantined": quarantined_count,
            "batches_created": 0,
            "accepted_files": [],
            "accepted_facts": [],
        }

    batches_created = 0
    if not dry_run:
        target_new.mkdir(parents=True, exist_ok=True)
        for i in range(0, len(accepted_facts), batch_size):
            batch_slice = accepted_facts[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            b_dir = target_new / f"batch-{batch_num:04d}"
            b_dir.mkdir(parents=True, exist_ok=True)

            batch_envelope = {
                "batch_number": batch_num,
                "created_at": GDAUtil.iso_now(),
                "count": len(batch_slice),
                "facts": batch_slice,
            }
            GDAUtil.save_json(b_dir / f"factoids-{batch_num:04d}.json", batch_envelope)
            batches_created += 1
    else:
        batches_created = (len(accepted_facts) + batch_size - 1) // batch_size

    return {
        "total_processed": len(staged_files),
        "accepted": len(accepted_facts),
        "quarantined": quarantined_count,
        "batches_created": batches_created,
        "accepted_files": accepted_files,
        "accepted_facts": accepted_facts,
    }


def commit_fact_batches(
    facts_mgr: GDAFacts,
    people_mgr: GDAPeople,
    logger: logging.Logger,
    accepted_facts: Optional[List[Dict[str, Any]]] = None,
    accepted_files: Optional[List[Path]] = None,
    fact_new_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Appends accepted facts to master store, syncs unions, creates Safe Backups, and cleans up."""
    target_new = fact_new_dir or (CONFIG.entities / "fact-new")
    facts_to_commit: List[Dict[str, Any]] = []

    if accepted_facts is not None:
        facts_to_commit = accepted_facts
    elif target_new.exists():
        for b_file in target_new.glob("batch-*/factoids-*.json"):
            b_data = GDAUtil.load_json(b_file)
            facts_to_commit.extend(b_data.get("facts", []))

    if not facts_to_commit:
        logger.info("No batched facts found to commit.")
        return {"committed": 0, "unions_synced": 0}

    union_sync_count = 0
    for fact in facts_to_commit:
        facts_mgr.add_fact(fact)
        union_sync_count += sync_unions_for_fact(fact, people_mgr, logger)

    facts_mgr.save(create_backup=True)
    people_mgr.save(create_backup=True)

    if accepted_files:
        for f in accepted_files:
            if f.exists():
                f.unlink()

    if target_new.exists():
        shutil.rmtree(target_new)

    logger.info("Successfully committed %d fact(s) to master registry.", len(facts_to_commit))
    return {"committed": len(facts_to_commit), "unions_synced": union_sync_count}


def main() -> int:
    """Main CLI entry point for GFI pipeline."""
    parser = argparse.ArgumentParser(description="GFI: Genealogy Fact Intake Pipeline")
    parser.add_argument("-i", "--intake", action="store_true", help="Execute intake validation and batch container staging")
    parser.add_argument("-a", "--append", action="store_true", help="Perform end-to-end ingestion: validate, batch, commit, and purge")
    parser.add_argument("-r", "--restore", action="store_true", help="Restore quarantined factoids back to entities")
    parser.add_argument("-b", "--batch-size", type=int, choices=[75, 150, 300], default=75, help="Batch container size (Default: 75)")
    parser.add_argument("--dir", "-d", type=Path, default=None, help="Explicit directory containing staged factoids")
    parser.add_argument("--dry-run", action="store_true", help="Run validation without committing mutations")
    parser.add_argument("-v", "--verbose", action="store_true", help="Emit verbose logging traces")
    parser.add_argument("--debug", action="store_true", help="Route runtime traces directly to console/stderr")
    args = parser.parse_args()

    c_level = logging.DEBUG if args.debug else (logging.DEBUG if args.verbose else logging.INFO)
    logger = setup_logger("gfi", ephemeral=True, console_level=c_level)
    logger.info("GFI version %s initializing", __version__)

    if args.restore:
        restored = restore_quarantine(logger)
        logger.info("Restore complete: %d factoids recovered from quarantine", restored)
        return 0

    staged_files = discover_staged_factoids(args.dir)
    if not staged_files and not (args.append and (CONFIG.entities / "fact-new").exists()):
        logger.info("No staged factoids found to process. Exiting.")
        return 0

    facts_mgr = GDAFacts(CONFIG.entities / "facts.json")
    people_mgr = GDAPeople(filepath=CONFIG.entities / "people.json")

    if args.intake:
        results = process_intake_batch(
            staged_files=staged_files,
            facts_mgr=facts_mgr,
            people_mgr=people_mgr,
            logger=logger,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
        logger.info(
            "INTAKE SUMMARY: %d processed, %d accepted, %d quarantined, %d batch(es) staged",
            results["total_processed"],
            results["accepted"],
            results["quarantined"],
            results["batches_created"],
        )
        return 0

    if args.append or (not args.intake and not args.restore):
        if staged_files:
            b_res = process_intake_batch(
                staged_files=staged_files,
                facts_mgr=facts_mgr,
                people_mgr=people_mgr,
                logger=logger,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
            )
            if args.dry_run:
                logger.info("[DRY-RUN] Validation complete. 0 facts committed.")
                return 0
            c_res = commit_fact_batches(
                facts_mgr=facts_mgr,
                people_mgr=people_mgr,
                logger=logger,
                accepted_facts=b_res.get("accepted_facts"),
                accepted_files=b_res.get("accepted_files"),
            )
        else:
            if args.dry_run:
                logger.info("[DRY-RUN] Validation complete. 0 facts committed.")
                return 0
            c_res = commit_fact_batches(
                facts_mgr=facts_mgr,
                people_mgr=people_mgr,
                logger=logger,
            )

        logger.info("APPEND COMPLETE: %d facts committed, %d unions synced.", c_res["committed"], c_res["unions_synced"])
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover