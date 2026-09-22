# Name: gfi.py
# Path: tools/ops/gfi.py

"""GFI (Genealogy Fact Intake).

Permanent operational tool for staging intake, semantic quarantine filtering,
auto-chunked batch aggregation, master facts appending, synchronized rollback backups,
workspace cleanup, and interactive console management.
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

# Ensure repository root is on sys.path for standalone invocation
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil

__version__ = "1.0.1+build.20260922.1"


def load_valid_person_ids(
    people_path: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
    verbose: bool = False,
) -> Set[str]:
    """Loads valid person identifiers from the master people registry[cite: 8].

    Args:
        people_path (Optional[Path]): Explicit path to people.json.
        logger (Optional[logging.Logger]): Operational logger.
        verbose (bool): Whether to log detailed diagnostic messages.

    Returns:
        Set[str]: Set of valid person identifiers.
    """
    target_people = people_path or CONFIG.people
    log = logger or logging.getLogger("gfi")

    if not target_people.exists():
        if verbose:
            log.warning(f"{target_people.name} not found. Proceeding without registry lookup.")
        return set()

    try:
        data = GDAUtil.load_json(target_people)
        persons = data.get("persons", [])
        return {p["person_id"] for p in persons if isinstance(p, dict) and "person_id" in p}
    except Exception as e:
        log.error(f"Error reading people registry: {e}")
        return set()


def get_next_batch_index(fact_new_dir: Optional[Path] = None) -> int:
    """Discovers the next sequential batch index in the staging directory.

    Args:
        fact_new_dir (Optional[Path]): Path to the fact-new workspace directory.

    Returns:
        int: Next integer batch index.
    """
    target_dir = fact_new_dir or (CONFIG.entities / "fact-new")
    if not target_dir.exists():
        return 1

    existing_indices = []
    for p in target_dir.glob("factoids-*.json"):
        match = re.search(r"factoids-(\d+)\.json$", p.name)
        if match:
            existing_indices.append(int(match.group(1)))
    for p in target_dir.glob("batch-*"):
        match = re.search(r"batch-(\d+)$", p.name)
        if match and p.is_dir():
            existing_indices.append(int(match.group(1)))

    return max(existing_indices, default=0) + 1


def normalize_and_validate_fact(
    fact: Dict[str, Any],
    valid_person_ids: Set[str],
) -> Tuple[bool, str, Dict[str, Any]]:
    """Normalizes field structure and verifies semantic validity of a single fact assertion.

    Args:
        fact (Dict[str, Any]): Fact payload to validate.
        valid_person_ids (Set[str]): Known valid person IDs for registry lookup.

    Returns:
        Tuple[bool, str, Dict[str, Any]]: Success boolean, diagnostic reason, and normalized payload.
    """
    normalized = fact.copy()

    person_id = normalized.get("person_id") or normalized.get("subject_person_id")
    if not person_id or not isinstance(person_id, str):
        return False, "Missing or invalid 'person_id' / 'subject_person_id'", normalized
    normalized["person_id"] = person_id
    normalized.pop("subject_person_id", None)

    if valid_person_ids and person_id not in valid_person_ids:
        return False, f"person_id '{person_id}' does not exist in people.json", normalized

    if not normalized.get("fact_type"):
        return False, "Missing required 'fact_type'", normalized

    if not normalized.get("source_urn"):
        citations = normalized.get("citations")
        if isinstance(citations, list) and citations:
            urns = []
            for c in citations:
                pub = c.get("publication_code", "GEN")
                dt = c.get("publication_date", "NODATE").replace("-", "")
                mf = c.get("media_file", "RECORD")
                urns.append(f"urn:cite:{pub}:{dt}:{mf}")
            normalized["source_urn"] = urns if len(urns) > 1 else urns[0]
        else:
            return False, "Missing required 'source_urn' or corroborating 'citations'", normalized

    if not normalized.get("description"):
        return False, "Missing required 'description'", normalized

    if "place" in normalized and "location" not in normalized:
        normalized["location"] = normalized.pop("place")

    associated = normalized.get("associated_people")
    if isinstance(associated, list):
        for assoc in associated:
            if not isinstance(assoc, dict):
                continue
            assoc_id = assoc.get("person_id")
            assoc_name = assoc.get("name", "Unknown")

            if assoc_id:
                if assoc_id == person_id and assoc_name != normalized.get("display_name"):
                    rel = assoc.get("role", "ASSOCIATE")
                    return (
                        False,
                        f"Self-referencing loop: person_id '{person_id}' assigned to associated individual '{assoc_name}' as role '{rel}'",
                        normalized,
                    )

                if valid_person_ids and assoc_id not in valid_person_ids:
                    return False, f"associated person_id '{assoc_id}' does not exist in people.json", normalized

    now_iso = GDAUtil.iso_now()
    if "created_at" not in normalized:
        normalized["created_at"] = now_iso
    if "updated_at" not in normalized:
        normalized["updated_at"] = now_iso

    return True, "Valid", normalized


def intake_and_batch(
    batch_size: int = 75,
    entities_dir: Optional[Path] = None,
    people_path: Optional[Path] = None,
    quarantine_dir: Optional[Path] = None,
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Filters incoming factoids, quarantines invalid records, and groups valid items into batches[cite: 7].

    Args:
        batch_size (int): Target maximum number of factoids per chunk.
        entities_dir (Optional[Path]): Directory containing staged assertions.
        people_path (Optional[Path]): Path to master people.json.
        quarantine_dir (Optional[Path]): Target quarantine directory[cite: 7].
        verbose (bool): Whether to log detailed item traces.
        logger (Optional[logging.Logger]): Operational logger.

    Returns:
        int: Total number of valid records batched.
    """
    log = logger or logging.getLogger("gfi")
    target_entities = entities_dir or CONFIG.entities
    target_quarantine = quarantine_dir or CONFIG.quarantine
    target_people = people_path or CONFIG.people
    fact_new_dir = target_entities / "fact-new"

    raw_files = sorted(list(target_entities.glob("factoid-*.json")))
    if not raw_files:
        print("[i] No unbatched 'factoid-*.json' files found in data/entities/.")
        log.info("No unbatched factoids found.", extra={"sys_event": True})
        return 0

    valid_person_ids = load_valid_person_ids(people_path=target_people, logger=log, verbose=verbose)
    fact_new_dir.mkdir(parents=True, exist_ok=True)
    print(f"[i] Found {len(raw_files)} unbatched file(s). (People registry loaded: {len(valid_person_ids)} identities).")

    valid_files: List[Tuple[Path, List[Dict[str, Any]]]] = []
    quarantined_count = 0

    for fpath in raw_files:
        try:
            content = GDAUtil.load_json(fpath)
            records = content.get("facts", [content]) if isinstance(content, dict) and "facts" in content else [content]
            if not isinstance(records, list) or len(records) == 0:
                raise ValueError("Empty or malformed fact payload")

            normalized_records: List[Dict[str, Any]] = []
            all_records_valid = True
            failure_reason = ""

            for r in records:
                if not isinstance(r, dict):
                    all_records_valid = False
                    failure_reason = "Fact record is not a valid JSON object"
                    break
                is_valid, reason, norm_rec = normalize_and_validate_fact(r, valid_person_ids)
                if not is_valid:
                    all_records_valid = False
                    failure_reason = reason
                    break
                normalized_records.append(norm_rec)

            if not all_records_valid:
                GDAUtil.quarantine_file(fpath, quarantine_dir=target_quarantine)
                quarantined_count += 1
                msg = f"QUARANTINED: {fpath.name} -> {failure_reason}"
                print(f"  [!] {msg}")
                log.error(msg)
                continue

            valid_files.append((fpath, normalized_records))

        except Exception as e:
            GDAUtil.quarantine_file(fpath, quarantine_dir=target_quarantine)
            quarantined_count += 1
            msg = f"QUARANTINED: {fpath.name} -> Malformed JSON / Read failure ({e})"
            print(f"  [!] {msg}")
            log.error(msg)

    if not valid_files:
        print(f"[!] Batching halted: 0 valid files, {quarantined_count} file(s) quarantined.")
        return 0

    total_valid = len(valid_files)
    num_batches = (total_valid + batch_size - 1) // batch_size
    print(f"[+] Validation Summary: {total_valid} valid, {quarantined_count} quarantined.")
    print(f"[+] Generating {num_batches} batch(es) (Batch size limit: {batch_size})...")

    next_idx = get_next_batch_index(fact_new_dir=fact_new_dir)

    for b in range(num_batches):
        batch_id_str = f"{next_idx:04d}"
        batch_folder = fact_new_dir / f"batch-{batch_id_str}"
        batch_file = fact_new_dir / f"factoids-{batch_id_str}.json"
        batch_folder.mkdir(parents=True, exist_ok=True)

        chunk = valid_files[b * batch_size : (b + 1) * batch_size]
        batch_facts: List[Dict[str, Any]] = []

        for fpath, records in chunk:
            batch_facts.extend(records)
            shutil.move(str(fpath), str(batch_folder / fpath.name))
            if verbose:
                for r in records:
                    log.info(f"Batched into {batch_id_str}: {fpath.name} (Fact ID: {r.get('fact_id')} | Person: {r.get('person_id')})")

        envelope = {
            "$schema": "schemas/entities/fact_registry.schema.json",
            "schema_version": "1.0.1",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_facts": len(batch_facts),
            "facts": batch_facts,
        }

        GDAUtil.save_json(batch_file, envelope)
        msg = f"Created batch-{batch_id_str}: {len(chunk)} files ({len(batch_facts)} facts) -> {batch_file.name}"
        print(f"  [+] {msg}")
        log.info(msg)
        next_idx += 1

    return total_valid


def append_and_cleanup(
    batch_size: int = 75,
    entities_dir: Optional[Path] = None,
    master_facts_path: Optional[Path] = None,
    backups_dir: Optional[Path] = None,
    quarantine_dir: Optional[Path] = None,
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Merges batched factoids into facts.json with Safe Backup snapshots and workspace cleanup[cite: 8, 10].

    Args:
        batch_size (int): Chunk size for pre-ingestion batching.
        entities_dir (Optional[Path]): Directory containing entities and fact-new.
        master_facts_path (Optional[Path]): Path to canonical facts.json.
        backups_dir (Optional[Path]): Target backup directory[cite: 10].
        quarantine_dir (Optional[Path]): Target quarantine directory[cite: 7].
        verbose (bool): Whether to log detailed diagnostic traces.
        logger (Optional[logging.Logger]): Operational logger.
    """
    log = logger or logging.getLogger("gfi")
    target_entities = entities_dir or CONFIG.entities
    target_facts = master_facts_path or CONFIG.facts
    target_backups = backups_dir or CONFIG.backups
    target_quarantine = quarantine_dir or CONFIG.quarantine
    fact_new_dir = target_entities / "fact-new"

    raw_files = list(target_entities.glob("factoid-*.json"))
    if raw_files:
        print(f"[i] Pre-ingestion check: Found {len(raw_files)} unbatched factoids in {target_entities.name}.")
        print("[i] Forcing intake batching before master append...")
        intake_and_batch(
            batch_size=batch_size,
            entities_dir=target_entities,
            quarantine_dir=target_quarantine,
            verbose=verbose,
            logger=log,
        )

    if not fact_new_dir.exists():
        print(f"[i] No '{fact_new_dir.name}' workspace found. Nothing to ingest.")
        return

    batch_files = sorted(list(fact_new_dir.glob("factoids-*.json")))
    if not batch_files:
        print(f"[i] No 'factoids-*.json' batch envelopes found in {fact_new_dir.name}. Nothing to ingest.")
        return

    print(f"\n[i] Discovered {len(batch_files)} batch envelope(s) ready for master ingestion.")

    all_incoming_facts: List[Dict[str, Any]] = []
    for bf in batch_files:
        try:
            data = GDAUtil.load_json(bf)
            facts = data.get("facts", [])
            all_incoming_facts.extend(facts)
        except Exception as e:
            log.error(f"Failed to read batch file {bf.name}: {e}")
            print(f"[!] Critical Error reading batch {bf.name}: {e}. Aborting append.")
            return

    if not all_incoming_facts:
        print("[!] No fact entries found across existing batch envelopes.")
        return

    if target_facts.exists():
        master_data = GDAUtil.load_json(target_facts)
    else:
        master_data = {
            "$schema": "schemas/entities/fact_registry.schema.json",
            "schema_version": "1.0.1",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_facts": 0,
            "facts": [],
        }

    master_list = master_data.get("facts", [])
    existing_ids: Set[str] = {f["fact_id"] for f in master_list if isinstance(f, dict) and "fact_id" in f}

    clean_append: List[Dict[str, Any]] = []
    duplicate_count = 0

    for item in all_incoming_facts:
        fid = item.get("fact_id")
        if fid and fid in existing_ids:
            duplicate_count += 1
            if verbose:
                log.info(f"Skipped duplicate fact_id: {fid}")
        else:
            if fid:
                existing_ids.add(fid)
            clean_append.append(item)
            if verbose:
                log.info(f"Ingested fact: {fid} | {item.get('person_id')} | {item.get('fact_type')} | {item.get('description')}")

    print(f"[i] Evaluated {len(all_incoming_facts)} incoming facts: {len(clean_append)} unique, {duplicate_count} duplicate IDs skipped.")

    sync_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ingested_archive_backup = target_backups / f"factoids_ingested_{sync_stamp}.bk"

    ingested_payload = {
        "archive_description": "Combined factoids ingested during master sync",
        "sync_timestamp": sync_stamp,
        "total_facts": len(all_incoming_facts),
        "facts": all_incoming_facts,
    }
    GDAUtil.save_json(ingested_archive_backup, ingested_payload)
    log.info(f"Synchronized ingestion backup saved: {ingested_archive_backup.name}")

    if target_facts.exists():
        master_bk = GDAUtil.create_safe_backup(target_facts, backup_dir=target_backups)
        log.info(f"Synchronized master pre-execution backup saved: {master_bk.name}")

    master_data["facts"] = master_list + clean_append
    master_data["total_facts"] = len(master_data["facts"])
    master_data["last_modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    GDAUtil.save_json(target_facts, master_data)

    print(f"[+] Successfully merged into master facts: {target_facts.name}")
    print(f"    Total facts in master: {master_data['total_facts']}")
    print(f"[+] Paired backups created with timestamp [{sync_stamp}]:")
    print(f"    - {ingested_archive_backup.name}")

    try:
        shutil.rmtree(fact_new_dir)
        print(f"[+] Cleaned up workspace: Purged {fact_new_dir.name}")
        log.info("Removed fact-new workspace after successful master sync.")
    except Exception as e:
        log.error(f"Failed to delete fact-new directory: {e}")
        print(f"[!] Warning: Could not delete {fact_new_dir.name}: {e}")

    quarantine_files = list(target_quarantine.glob("factoid-*.json"))
    if quarantine_files:
        print(f"[!] Status Alert: {len(quarantine_files)} file(s) currently held in {target_quarantine.name} for review.")


def restore_quarantine_files(
    entities_dir: Optional[Path] = None,
    quarantine_dir: Optional[Path] = None,
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Restores all quarantined factoid files back to data/entities/ for re-evaluation[cite: 7].

    Args:
        entities_dir (Optional[Path]): Directory to restore factoids to.
        quarantine_dir (Optional[Path]): Directory containing quarantined factoids[cite: 7].
        verbose (bool): Whether to log individual restore actions.
        logger (Optional[logging.Logger]): Operational logger.
    """
    log = logger or logging.getLogger("gfi")
    target_entities = entities_dir or CONFIG.entities
    target_quarantine = quarantine_dir or CONFIG.quarantine

    q_files = sorted(list(target_quarantine.glob("factoid-*.json")))
    if not q_files:
        print("[i] Quarantine directory is already empty. Nothing to restore.")
        return

    print(f"[i] Restoring {len(q_files)} quarantined file(s) back to {target_entities.name}...")
    for qf in q_files:
        target = target_entities / qf.name
        shutil.move(str(qf), str(target))
    print(f"[+] Successfully restored {len(q_files)} files to {target_entities.name}")
    log.info(f"Restored {len(q_files)} files from quarantine to entities.", extra={"sys_event": True})


def interactive_menu(batch_size: int = 75, verbose: bool = False) -> None:
    """Renders the interactive command console for fact intake and batch management.

    Args:
        batch_size (int): Default chunk size.
        verbose (bool): Diagnostic output flag.
    """
    fact_new_dir = CONFIG.entities / "fact-new"
    while True:
        raw_count = len(list(CONFIG.entities.glob("factoid-*.json")))
        batch_count = len(list(fact_new_dir.glob("factoids-*.json"))) if fact_new_dir.exists() else 0
        quarantine_count = len(list(CONFIG.quarantine.glob("factoid-*.json")))

        print("\n" + "=" * 55)
        print(f" GFI FACT INTAKE CONSOLE (Active Batch Size: {batch_size})")
        print("=" * 55)
        print(f" Status: Unbatched: {raw_count} | Batches Ready: {batch_count} | Quarantine: {quarantine_count}")
        print("-" * 55)
        print(" [1] Batch Staged Factoids (Quarantine & Chunk)")
        print(" [2] Ingest to Master Facts (Force Batch & Purge Staging)")
        print(" [3] Review Quarantine Directory Status")
        print(" [4] Restore Quarantined Files to Ingestion Pool")
        print(" [Q] Exit Console")
        print("=" * 55)

        choice = input("Select an option [1-4, Q]: ").strip().lower()
        if choice in ["q", "exit", ""]:
            print("Exiting GFI Console. Goodbye!")
            break
        elif choice == "1":
            intake_and_batch(batch_size=batch_size, verbose=verbose)
        elif choice == "2":
            append_and_cleanup(batch_size=batch_size, verbose=verbose)
        elif choice == "3":
            q_files = sorted(list(CONFIG.quarantine.glob("factoid-*.json")))
            print(f"\n--- Quarantine Inspector ({len(q_files)} files) ---")
            if not q_files:
                print("Quarantine directory is clean. Zero faulty records found.")
            else:
                for qf in q_files:
                    print(f"  [QUARANTINE] {qf.name}")
        elif choice == "4":
            restore_quarantine_files(verbose=verbose)
        else:
            print("[!] Invalid option. Please select 1, 2, 3, 4, or Q.")


def main() -> None:
    """CLI parameter parsing and router for Fact Intake operations."""
    parser = argparse.ArgumentParser(
        description=f"GFI ({__version__}): Fact Intake, Quarantine Filter, Batching, and Master Append Sync."
    )
    parser.add_argument(
        "-b", "--batch-size", type=int, choices=[75, 150, 300], default=75,
        help="Factoids per batch container (default: 75)",
    )
    parser.add_argument(
        "-i", "--intake", action="store_true",
        help="Execute intake: filter quarantine and generate batch containers",
    )
    parser.add_argument(
        "-a", "--append", action="store_true",
        help="Execute ingestion: force batch unbatched, merge to master, dual backup, and clean fact-new",
    )
    parser.add_argument(
        "-r", "--restore", action="store_true",
        help="Restore all files from quarantine back to data/entities/ for re-evaluation",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Output diagnostic runtime details and itemized fact ingestion logs",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Route runtime traces directly to console/stderr",
    )
    args = parser.parse_args()

    c_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logger("gfi", console_level=c_level, file_level=logging.DEBUG)
    logger.info(f"Initialized GFI CLI ({__version__}).", extra={"sys_event": True})

    if args.restore:
        restore_quarantine_files(verbose=args.verbose, logger=logger)
    elif args.intake:
        intake_and_batch(batch_size=args.batch_size, verbose=args.verbose, logger=logger)
    elif args.append:
        append_and_cleanup(batch_size=args.batch_size, verbose=args.verbose, logger=logger)
    else:
        interactive_menu(batch_size=args.batch_size, verbose=args.verbose)


if __name__ == "__main__":
    main()