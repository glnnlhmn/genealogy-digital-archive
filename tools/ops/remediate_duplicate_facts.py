# Name: remediate_duplicate_facts.py
# Path: auto\op_tools\remediate_duplicate_facts.py

import os
import sys
import json
import shutil
import argparse
from datetime import datetime

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Remediate identified duplicate UUIDs, census duplicate enumerations, and obsolete 2018 pending survivor placeholders.",
        add_help=False
    )
    parser.add_argument("-help", action="store_true", help="Display syntax, synopsis, and parameter guidance.")
    parser.add_argument("-debug", action="store_true", help="Routes diagnostics directly to screen.")
    parser.add_argument("-verbose", action="store_true", help="Routes runtime details to log file.")
    return parser.parse_args()

def main():
    args = parse_arguments()
    if args.help:
        print("Usage: python auto\\op_tools\\remediate_duplicate_facts.py [-help] [-debug] [-verbose]")
        print("Remediates verified duplicates and obsolete unverified placeholders in facts.json.")
        return 0

    root_anchor = r"G:\My Drive\genealogy-digital-archive"
    if not os.path.exists(root_anchor):
        root_anchor = "."
    os.chdir(root_anchor)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dir = "gtemp"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"remediate_duplicate_facts-{timestamp}.log")

    log_entries = []
    def log(msg, is_debug=False):
        formatted = f"[{datetime.now().isoformat()}] {msg}"
        if args.verbose or not is_debug:
            log_entries.append(formatted)
        if args.debug or not is_debug:
            print(formatted)

    log("Starting duplicate remediation execution...")

    facts_path = os.path.join("data", "entities", "facts.json")
    if not os.path.exists(facts_path):
        facts_path = "facts.json"

    if not os.path.exists(facts_path):
        log("ERROR: facts.json not found.")
        return 1

    backup_path = os.path.join(log_dir, f"facts_backup_{timestamp}.json")
    shutil.copy(facts_path, backup_path)
    log(f"Pre-execution backup created: {backup_path}")

    with open(facts_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    facts = data.get("facts", [])
    initial_count = len(facts)

    ids_to_purge = {
        "fb686b39-14cd-445f-8a53-cf7197254d2c",  # IND-00085 1910 Census duplicate
        "b54b2895-bde5-4dd5-8c59-5e89b2e54790",  # IND-00000 2018 pending survivor placeholder
        "c9478845-76bb-42ba-a085-911bf64dfd95",  # IND-00021 2018 pending survivor placeholder
        "54782eb4-212a-4d60-b4e7-7f62116f14e5",  # IND-00022 2018 pending survivor placeholder
        "7de47ce8-cc9b-4b2b-ab65-a2eafa632936",  # IND-00023 2018 pending survivor placeholder
        "a280df1a-318a-41e6-a00d-036f2c7c4262",  # IND-00140 2018 pending survivor placeholder
    }

    new_facts = []
    seen_cbcc = False
    purged_count = 0

    for f in facts:
        fid = f.get("fact_id")
        if fid == "cbcc30d9-dd5d-5189-826f-a55f912f72fa":
            if not seen_cbcc and f.get("life_story") is not None:
                new_facts.append(f)
                seen_cbcc = True
            else:
                purged_count += 1
                log(f"Purged redundant duplicate UUID instance: {fid}", is_debug=True)
            continue

        if fid in ids_to_purge:
            purged_count += 1
            log(f"Purged target duplicate/placeholder fact: {fid} ({f.get('person_id')} - {f.get('fact_type')})", is_debug=True)
            continue

        new_facts.append(f)

    data["facts"] = new_facts
    data["total_facts"] = len(new_facts)
    data["last_modified"] = datetime.now().isoformat()

    with open(facts_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    log(f"Remediation complete. Initial count: {initial_count}, Purged: {purged_count}, Remaining: {len(new_facts)}")

    with open(log_path, "w", encoding="utf-8") as lf:
        lf.write("\n".join(log_entries))

    log(f"Log written to: {log_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())