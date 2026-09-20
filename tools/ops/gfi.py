# Name: gfi.py
# Path: tools/ops/gfi.py
"""GFI (Genealogy Fact Intake)

Permanent operational tool for staging intake, semantic quarantine filtering,
auto-chunked batch aggregation, master facts appending, synchronized rollback backups,
workspace cleanup, and interactive console management.

Dependencies:
    - Standard Library: argparse, datetime, json, pathlib, re, shutil, sys
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Dict, List, Set, Tuple

ROOT_DIR = Path("G:/My Drive/genealogy-digital-archive")
ENTITIES_DIR = ROOT_DIR / "data" / "entities"
PEOPLE_FILE = ENTITIES_DIR / "people.json"
FACT_NEW_DIR = ENTITIES_DIR / "fact-new"
QUARANTINE_DIR = ENTITIES_DIR / "quarantine"
MASTER_FACTS_FILE = ENTITIES_DIR / "facts.json"
BACKUPS_DIR = ROOT_DIR / "backups"
LOGS_DIR = ROOT_DIR / "logs"

BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOGS_DIR / f"gfi-{TIMESTAMP}.log"


def log(msg: str, is_error: bool = False, verbose: bool = False) -> None:
    line = f"[{datetime.now().isoformat()}] {'ERROR: ' if is_error else ''}{msg}\n"
    if is_error:
        sys.stderr.write(line)
    elif verbose:
        sys.stdout.write(line)
    sys.stdout.flush()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def load_valid_person_ids() -> Set[str]:
    if not PEOPLE_FILE.exists():
        log(f"Warning: {PEOPLE_FILE} not found. Proceeding without registry lookup.", verbose=True)
        return set()
    try:
        data = json.loads(PEOPLE_FILE.read_text(encoding="utf-8-sig"))
        persons = data.get("persons", [])
        return {p["person_id"] for p in persons if isinstance(p, dict) and "person_id" in p}
    except Exception as e:
        log(f"Error reading people registry: {e}", is_error=True)
        return set()


def get_next_batch_index() -> int:
    if not FACT_NEW_DIR.exists():
        return 1
    existing_indices = []
    for p in FACT_NEW_DIR.glob("factoids-*.json"):
        match = re.search(r"factoids-(\d+)\.json$", p.name)
        if match:
            existing_indices.append(int(match.group(1)))
    for p in FACT_NEW_DIR.glob("batch-*"):
        match = re.search(r"batch-(\d+)$", p.name)
        if match and p.is_dir():
            existing_indices.append(int(match.group(1)))
    return max(existing_indices, default=0) + 1


def normalize_and_validate_fact(fact: Dict[str, Any], valid_person_ids: Set[str]) -> Tuple[bool, str, Dict[str, Any]]:
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
                    return False, f"Self-referencing loop: person_id '{person_id}' assigned to associated individual '{assoc_name}' as role '{rel}'", normalized

                if valid_person_ids and assoc_id not in valid_person_ids:
                    return False, f"associated person_id '{assoc_id}' does not exist in people.json", normalized

    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    if "created_at" not in normalized:
        normalized["created_at"] = now_iso
    if "updated_at" not in normalized:
        normalized["updated_at"] = now_iso

    return True, "Valid", normalized


def intake_and_batch(batch_size: int, verbose: bool = False) -> int:
    raw_files = sorted(list(ENTITIES_DIR.glob("factoid-*.json")))
    if not raw_files:
        print("[i] No unbatched 'factoid-*.json' files found in data/entities/.")
        log("No unbatched factoids found.", verbose=verbose)
        return 0

    valid_person_ids = load_valid_person_ids()
    FACT_NEW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[i] Found {len(raw_files)} unbatched file(s). (People registry loaded: {len(valid_person_ids)} identities).")

    valid_files: List[Tuple[Path, List[Dict[str, Any]]]] = []
    quarantined_count = 0

    for fpath in raw_files:
        try:
            content = json.loads(fpath.read_text(encoding="utf-8-sig"))
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
                target_quarantine = QUARANTINE_DIR / fpath.name
                shutil.move(str(fpath), str(target_quarantine))
                quarantined_count += 1
                msg = f"QUARANTINED: {fpath.name} -> {failure_reason}"
                print(f"  [!] {msg}")
                log(msg, is_error=True)
                continue

            valid_files.append((fpath, normalized_records))

        except Exception as e:
            target_quarantine = QUARANTINE_DIR / fpath.name
            shutil.move(str(fpath), str(target_quarantine))
            quarantined_count += 1
            msg = f"QUARANTINED: {fpath.name} -> Malformed JSON / Read failure ({e})"
            print(f"  [!] {msg}")
            log(msg, is_error=True)

    if not valid_files:
        print(f"[!] Batching halted: 0 valid files, {quarantined_count} file(s) quarantined.")
        return 0

    total_valid = len(valid_files)
    num_batches = (total_valid + batch_size - 1) // batch_size
    print(f"[+] Validation Summary: {total_valid} valid, {quarantined_count} quarantined.")
    print(f"[+] Generating {num_batches} batch(es) (Batch size limit: {batch_size})...")

    next_idx = get_next_batch_index()

    for b in range(num_batches):
        batch_id_str = f"{next_idx:04d}"
        batch_folder = FACT_NEW_DIR / f"batch-{batch_id_str}"
        batch_file = FACT_NEW_DIR / f"factoids-{batch_id_str}.json"
        batch_folder.mkdir(parents=True, exist_ok=True)

        chunk = valid_files[b * batch_size : (b + 1) * batch_size]
        batch_facts: List[Dict[str, Any]] = []

        for fpath, records in chunk:
            batch_facts.extend(records)
            shutil.move(str(fpath), str(batch_folder / fpath.name))
            if verbose:
                for r in records:
                    log(f"Batched into {batch_id_str}: {fpath.name} (Fact ID: {r.get('fact_id')} | Person: {r.get('person_id')})", verbose=True)

        envelope = {
            "$schema": "schemas/entities/fact_registry.schema.json",
            "schema_version": "1.0.1",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_facts": len(batch_facts),
            "facts": batch_facts
        }

        batch_file.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
        msg = f"Created batch-{batch_id_str}: {len(chunk)} files ({len(batch_facts)} facts) -> {batch_file.name}"
        print(f"  [+] {msg}")
        log(msg, verbose=verbose)
        next_idx += 1

    return total_valid


def append_and_cleanup(batch_size: int, verbose: bool = False) -> None:
    raw_files = list(ENTITIES_DIR.glob("factoid-*.json"))
    if raw_files:
        print(f"[i] Pre-ingestion check: Found {len(raw_files)} unbatched factoids in data/entities/.")
        print("[i] Forcing intake batching before master append...")
        intake_and_batch(batch_size=batch_size, verbose=verbose)

    if not FACT_NEW_DIR.exists():
        print("[i] No 'data/entities/fact-new/' workspace found. Nothing to ingest.")
        return

    batch_files = sorted(list(FACT_NEW_DIR.glob("factoids-*.json")))
    if not batch_files:
        print("[i] No 'factoids-*.json' batch envelopes found in fact-new/. Nothing to ingest.")
        return

    print(f"\n[i] Discovered {len(batch_files)} batch envelope(s) ready for master ingestion.")

    all_incoming_facts: List[Dict[str, Any]] = []
    for bf in batch_files:
        try:
            data = json.loads(bf.read_text(encoding="utf-8-sig"))
            facts = data.get("facts", [])
            all_incoming_facts.extend(facts)
        except Exception as e:
            log(f"Failed to read batch file {bf.name}: {e}", is_error=True)
            print(f"[!] Critical Error reading batch {bf.name}: {e}. Aborting append.")
            return

    if not all_incoming_facts:
        print("[!] No fact entries found across existing batch envelopes.")
        return

    if MASTER_FACTS_FILE.exists():
        master_data = json.loads(MASTER_FACTS_FILE.read_text(encoding="utf-8-sig"))
    else:
        master_data = {
            "$schema": "schemas/entities/fact_registry.schema.json",
            "schema_version": "1.0.1",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_facts": 0,
            "facts": []
        }

    master_list = master_data.get("facts", [])
    existing_ids: Set[str] = {f["fact_id"] for f in master_list if "fact_id" in f}

    clean_append: List[Dict[str, Any]] = []
    duplicate_count = 0

    for item in all_incoming_facts:
        fid = item.get("fact_id")
        if fid and fid in existing_ids:
            duplicate_count += 1
            if verbose:
                log(f"Skipped duplicate fact_id: {fid}", verbose=True)
        else:
            if fid:
                existing_ids.add(fid)
            clean_append.append(item)
            if verbose:
                log(f"Ingested fact: {fid} | {item.get('person_id')} | {item.get('fact_type')} | {item.get('description')}", verbose=True)

    print(f"[i] Evaluated {len(all_incoming_facts)} incoming facts: {len(clean_append)} unique, {duplicate_count} duplicate IDs skipped.")

    # Paired atomic snapshots with .bk extensions
    sync_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ingested_archive_backup = BACKUPS_DIR / f"factoids_ingested_{sync_stamp}.bk"
    facts_master_backup = BACKUPS_DIR / f"facts.json.{sync_stamp}.bk"

    ingested_payload = {
        "archive_description": "Combined factoids ingested during master sync",
        "sync_timestamp": sync_stamp,
        "total_facts": len(all_incoming_facts),
        "facts": all_incoming_facts
    }
    ingested_archive_backup.write_text(json.dumps(ingested_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Synchronized ingestion backup saved: {ingested_archive_backup.as_posix()}", verbose=True)

    if MASTER_FACTS_FILE.exists():
        shutil.copy2(MASTER_FACTS_FILE, facts_master_backup)
        log(f"Synchronized master pre-execution backup saved: {facts_master_backup.as_posix()}", verbose=True)

    master_data["facts"] = master_list + clean_append
    master_data["total_facts"] = len(master_data["facts"])
    master_data["last_modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    MASTER_FACTS_FILE.write_text(json.dumps(master_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[+] Successfully merged into master facts: {MASTER_FACTS_FILE.relative_to(ROOT_DIR)}")
    print(f"    Total facts in master: {master_data['total_facts']}")
    print(f"[+] Paired backups created with timestamp [{sync_stamp}]:")
    print(f"    - {ingested_archive_backup.name}")
    print(f"    - {facts_master_backup.name}")

    try:
        shutil.rmtree(FACT_NEW_DIR)
        print(f"[+] Cleaned up workspace: Purged {FACT_NEW_DIR.relative_to(ROOT_DIR)}")
        log("Removed fact-new workspace after successful master sync.", verbose=verbose)
    except Exception as e:
        log(f"Failed to delete fact-new directory: {e}", is_error=True)
        print(f"[!] Warning: Could not delete {FACT_NEW_DIR.name}: {e}")

    quarantine_files = list(QUARANTINE_DIR.glob("factoid-*.json"))
    if quarantine_files:
        print(f"[!] Status Alert: {len(quarantine_files)} file(s) currently held in {QUARANTINE_DIR.relative_to(ROOT_DIR)} for review.")


def restore_quarantine_files(verbose: bool = False) -> None:
    q_files = sorted(list(QUARANTINE_DIR.glob("factoid-*.json")))
    if not q_files:
        print("[i] Quarantine directory is already empty. Nothing to restore.")
        return

    print(f"[i] Restoring {len(q_files)} quarantined file(s) back to data/entities/...")
    for qf in q_files:
        target = ENTITIES_DIR / qf.name
        shutil.move(str(qf), str(target))
    print(f"[+] Successfully restored {len(q_files)} files to {ENTITIES_DIR.relative_to(ROOT_DIR)}")
    log(f"Restored {len(q_files)} files from quarantine to entities.", verbose=verbose)


def interactive_menu(batch_size: int, verbose: bool = False) -> None:
    while True:
        raw_count = len(list(ENTITIES_DIR.glob("factoid-*.json")))
        batch_count = len(list(FACT_NEW_DIR.glob("factoids-*.json"))) if FACT_NEW_DIR.exists() else 0
        quarantine_count = len(list(QUARANTINE_DIR.glob("factoid-*.json")))

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
            q_files = sorted(list(QUARANTINE_DIR.glob("factoid-*.json")))
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


def main():
    parser = argparse.ArgumentParser(
        description="GFI: Fact Intake, Quarantine Filter, Batching, and Master Append Sync."
    )
    parser.add_argument("-b", "--batch-size", type=int, choices=[75, 150, 300], default=75,
                        help="Factoids per batch container (default: 75)")
    parser.add_argument("-i", "--intake", action="store_true",
                        help="Execute intake: filter quarantine and generate batch containers")
    parser.add_argument("-a", "--append", action="store_true",
                        help="Execute ingestion: force batch unbatched, merge to master, dual backup, and clean fact-new")
    parser.add_argument("-r", "--restore", action="store_true",
                        help="Restore all files from quarantine back to data/entities/ for re-evaluation")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Output diagnostic runtime details and itemized fact ingestion logs")
    args = parser.parse_args()

    log("Initialized GFI CLI.", verbose=args.verbose)

    if args.restore:
        restore_quarantine_files(verbose=args.verbose)
    elif args.intake:
        intake_and_batch(batch_size=args.batch_size, verbose=args.verbose)
    elif args.append:
        append_and_cleanup(batch_size=args.batch_size, verbose=args.verbose)
    else:
        interactive_menu(batch_size=args.batch_size, verbose=args.verbose)


if __name__ == "__main__":
    main()