# Name: consolidate_duplicate_facts.py
# Path: auto\op_tools\consolidate_duplicate_facts.py

import os
import sys
import json
import shutil
import argparse
from datetime import datetime
from collections import defaultdict

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Consolidate duplicate parentage and event facts into multi-URN array records.",
        add_help=False
    )
    parser.add_argument("-help", action="store_true", help="Display syntax, synopsis, and parameter guidance.")
    parser.add_argument("-debug", action="store_true", help="Routes diagnostics directly to screen.")
    parser.add_argument("-verbose", action="store_true", help="Routes runtime details to log file.")
    return parser.parse_args()

def main():
    args = parse_arguments()
    if args.help:
        print("Usage: python auto\\op_tools\\consolidate_duplicate_facts.py [-help] [-debug] [-verbose]")
        print("Consolidates identical (person_id, fact_type, date_start, description) facts into multi-URN arrays.")
        return 0

    root_anchor = r"G:\My Drive\genealogy-digital-archive"
    if not os.path.exists(root_anchor):
        root_anchor = "."
    os.chdir(root_anchor)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dir = "gtemp"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"consolidate_duplicate_facts-{timestamp}.log")

    log_entries = []
    def log(msg, is_debug=False):
        formatted = f"[{datetime.now().isoformat()}] {msg}"
        if args.verbose or not is_debug:
            log_entries.append(formatted)
        if args.debug or not is_debug:
            print(formatted)

    log("Starting fact consolidation routine...")

    facts_path = os.path.join("data", "entities", "facts.json")
    if not os.path.exists(facts_path):
        facts_path = "facts.json"

    if not os.path.exists(facts_path):
        log("ERROR: facts.json not found.")
        return 1

    # Pre-execution backup
    backup_path = os.path.join(log_dir, f"facts_backup_{timestamp}.json")
    shutil.copy(facts_path, backup_path)
    log(f"Pre-execution backup created: {backup_path}")

    with open(facts_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    facts = data.get("facts", [])
    initial_count = len(facts)
    log(f"Initial facts count: {initial_count}")

    # Grouping by composite signature: (person_id, fact_type, date_start, normalized_description)
    grouped = defaultdict(list)
    for f in facts:
        d = f.get("date", {})
        d_start = d.get("date_start") if isinstance(d, dict) else None
        desc = f.get("description", "").strip()
        key = (f.get("person_id"), f.get("fact_type"), d_start, desc)
        grouped[key].append(f)

    consolidated_facts = []
    merged_count = 0

    for key, group in grouped.items():
        if len(group) > 1:
            base_fact = group[0].copy()

            # Merge source_urn citations into sorted, unique array
            urns = set()
            for item in group:
                u = item.get("source_urn")
                if isinstance(u, list):
                    urns.update(u)
                elif u:
                    urns.add(u)

            if len(urns) > 1:
                base_fact["source_urn"] = sorted(list(urns))
                merged_count += len(group) - 1
            elif len(urns) == 1:
                base_fact["source_urn"] = list(urns)[0]

            # Merge distinct notes if present
            notes = set()
            for item in group:
                n = item.get("notes")
                if n:
                    notes.add(n)
            if notes:
                base_fact["notes"] = " | ".join(sorted(list(notes)))

            consolidated_facts.append(base_fact)
            log(f"Merged {len(group)} records for {key[0]} ({key[1]}, {key[2]}) into unified multi-URN array.", is_debug=True)
        else:
            consolidated_facts.append(group[0])

    final_count = len(consolidated_facts)
    data["total_facts"] = final_count
    data["facts"] = consolidated_facts
    data["last_modified"] = datetime.now().isoformat()

    with open(facts_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    log(f"Consolidation complete. Initial count: {initial_count}, Final count: {final_count}, Records merged: {merged_count}")

    with open(log_path, "w", encoding="utf-8") as lf:
        lf.write("\n".join(log_entries))

    log(f"Execution log written to: {log_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())