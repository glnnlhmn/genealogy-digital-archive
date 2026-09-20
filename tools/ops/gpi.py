# Name: gpi.py
# Path: tools/ops/gpi.py

"""
Genealogy Person Intake Pipeline (GPI)
Version: 1.0.3

Description:
    Automated 7-stage state machine and pipeline for discovering, validating, 
    canonicalizing, and committing individual person entities (pep-lets) to the 
    master person registry (people.json) within the digital archive.

Dependencies:
    - Python 3.10+
    - jsonschema (v4.18.0+)
    - Standard libraries: argparse, glob, json, re, shutil, sys, datetime, pathlib, typing
"""

import argparse
import glob
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import jsonschema

ROOT_DIR = Path("G:/My Drive/genealogy-digital-archive")
PEOPLE_FILE = ROOT_DIR / "data/entities/people.json"
LOCATIONS_FILE = ROOT_DIR / "data/entities/locations.json"
LOCATION_INDEX_FILE = ROOT_DIR / "data/indexes/location_index.json"
PERSON_SCHEMA_FILE = ROOT_DIR / "schemas/entities/person.schema.json"
REGISTRY_SCHEMA_FILE = ROOT_DIR / "schemas/entities/person_registry.schema.json"

STAGING_GLOB = "data/entities/pep-let-*.json"
HOLD_DIR = ROOT_DIR / "data/entities/hold"
BACKUPS_DIR = ROOT_DIR / "backups"
LOGS_DIR = ROOT_DIR / "logs"

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOGS_DIR / f"gpi-{TIMESTAMP}.log"


def log(msg: str, level: str = "INFO", verbose: bool = False) -> None:
    entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}\n"
    if level in ["INFO", "ERROR", "WARN"] or verbose:
        print(entry.strip())
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


def load_json(filepath: Path) -> Any:
    return json.loads(filepath.read_text(encoding="utf-8-sig"))


def save_json(filepath: Path, data: Any) -> None:
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def quarantine_file(file_path: Path, reason: str) -> None:
    HOLD_DIR.mkdir(parents=True, exist_ok=True)
    target = HOLD_DIR / file_path.name
    log(f"Quarantining {file_path.name} to {HOLD_DIR}: {reason}", level="WARN")
    if file_path.exists():
        try:
            shutil.copy(str(file_path), str(target))
            file_path.unlink()
        except Exception as e:
            log(f"Failed to quarantine file {file_path.name}: {e}", level="ERROR")


# ----------------------------------------------------------------------
# PIPELINE STAGES
# ----------------------------------------------------------------------

def stage_0_discovery() -> List[Path]:
    files = [Path(p) for p in glob.glob(str(ROOT_DIR / STAGING_GLOB))]
    return sorted(files)


def stage_1_validate_syntax(files: List[Path], verbose: bool = False) -> Tuple[List[Dict[str, Any]], List[Path]]:
    valid_records: List[Dict[str, Any]] = []
    valid_files: List[Path] = []

    if not PERSON_SCHEMA_FILE.exists():
        log(f"Schema not found: {PERSON_SCHEMA_FILE}", level="ERROR")
        return [], []

    shared_schema_file = PERSON_SCHEMA_FILE.parent.parent / "defs/_shared_definitions.schema.json"
    schema_data = load_json(PERSON_SCHEMA_FILE)
    shared_data = load_json(shared_schema_file)

    store = {
        shared_data.get("$id", "https://genealogy.archive/schemas/defs/_shared_definitions.schema.json"): shared_data,
        shared_schema_file.as_uri(): shared_data,
        "../defs/_shared_definitions.schema.json": shared_data
    }

    resolver = jsonschema.RefResolver(
        base_uri=f"{PERSON_SCHEMA_FILE.parent.as_uri()}/",
        referrer=schema_data,
        store=store
    )
    validator = jsonschema.Draft202012Validator(schema_data, resolver=resolver)

    for file_path in files:
        try:
            record = load_json(file_path)
            validator.validate(instance=record)
            valid_records.append(record)
            valid_files.append(file_path)
            log(f"Syntax valid: {file_path.name}", verbose=verbose)
        except jsonschema.ValidationError as ve:
            quarantine_file(file_path, f"Schema validation error: {ve.message}")
        except Exception as e:
            quarantine_file(file_path, f"Reference/Parse error: {e}")

    return valid_records, valid_files


def stage_2_verify_graph_topology(
    staged_records: List[Dict[str, Any]],
    staged_files: List[Path],
    existing_people: List[Dict[str, Any]],
    verbose: bool = False
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    existing_ids: Set[str] = {p["person_id"] for p in existing_people}
    staged_ids: Set[str] = {p["person_id"] for p in staged_records}

    adj: Dict[str, Set[str]] = {}

    def add_edge(u: str, v: str) -> None:
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)

    for p in existing_people:
        pid = p["person_id"]
        adj.setdefault(pid, set())
        for rel in p.get("associated_people") or []:
            t_id = rel.get("person_id")
            if t_id and t_id in existing_ids:
                add_edge(pid, t_id)

    for p in staged_records:
        pid = p["person_id"]
        adj.setdefault(pid, set())
        for rel in p.get("associated_people") or []:
            t_id = rel.get("person_id")
            if t_id and (t_id in existing_ids or t_id in staged_ids):
                add_edge(pid, t_id)

    reachable: Set[str] = set()
    if "IND-00000" in adj:
        queue = ["IND-00000"]
        reachable.add("IND-00000")
        while queue:
            curr = queue.pop(0)
            for neighbor in adj.get(curr, set()):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)

    verified_records: List[Dict[str, Any]] = []
    verified_files: List[Path] = []

    for p, f in zip(staged_records, staged_files):
        pid = p["person_id"]
        if pid in reachable:
            verified_records.append(p)
            verified_files.append(f)
            log(f"Graph topology verified for item: {pid}", verbose=verbose)
        else:
            quarantine_file(f, f"Graph topology error: Person {pid} has no path to root IND-00000")

    log(f"Graph topology passed for {len(verified_records)}/{len(staged_records)} entities.", verbose=verbose)
    return verified_records, verified_files


def stage_3_deduplication_drift(
    staged_records: List[Dict[str, Any]],
    staged_files: List[Path],
    existing_people: List[Dict[str, Any]],
    verbose: bool = False
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    existing_fingerprints: Set[str] = set()
    for p in existing_people:
        name_obj = p.get("canonical_name") or {}
        g = (name_obj.get("given") or "").strip().lower()
        s = (name_obj.get("surname") or "").strip().lower()
        b_year = (name_obj.get("birth_year") or {}).get("year")
        existing_fingerprints.add(f"{g}|{s}|{b_year}")

    accepted_records: List[Dict[str, Any]] = []
    accepted_files: List[Path] = []

    for p, f in zip(staged_records, staged_files):
        name_obj = p.get("canonical_name") or {}
        g = (name_obj.get("given") or "").strip().lower()
        s = (name_obj.get("surname") or "").strip().lower()
        b_year = (name_obj.get("birth_year") or {}).get("year")
        fp = f"{g}|{s}|{b_year}"

        if fp in existing_fingerprints and b_year is not None:
            quarantine_file(f, f"Collision: Candidate duplicate matching {g} {s} ({b_year}) already in people.json")
        else:
            accepted_records.append(p)
            accepted_files.append(f)
            log(f"Deduplication passed for record: {p.get('person_id')}", verbose=verbose)

    return accepted_records, accepted_files


def stage_4_canonicalize_locations(
    staged_records: List[Dict[str, Any]],
    staged_files: List[Path],
    locations_entity: Dict[str, Any],
    location_index: Dict[str, Any],
    verbose: bool = False
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    redirects = location_index.get("redirects", {})
    canonical_places: Dict[str, Dict[str, Any]] = {
        loc["location"]["standardized"].lower(): loc["location"]
        for loc in locations_entity.get("locations", [])
    }

    def resolve_place(place_obj: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        if not place_obj or not isinstance(place_obj, dict):
            return True, place_obj
        raw_std = place_obj.get("standardized")
        if not raw_std:
            return True, place_obj

        key = raw_std.strip().lower()
        if key in redirects:
            target_std = redirects[key]["standardized"]
            key = target_std.lower()

        if key in canonical_places:
            matched = canonical_places[key]
            return True, {
                "standardized": matched["standardized"],
                "verbatim": place_obj.get("verbatim") or matched.get("verbatim"),
                "details": matched.get("details")
            }

        return False, None

    passed_records: List[Dict[str, Any]] = []
    passed_files: List[Path] = []

    for p, f in zip(staged_records, staged_files):
        vitals = p.get("vitals") or {}
        b_place = vitals.get("birth", {}).get("place")
        d_place = vitals.get("death", {}).get("place")

        b_ok, new_b = resolve_place(b_place)
        d_ok, new_d = resolve_place(d_place)

        if not b_ok:
            quarantine_file(f, f"Location resolution failure: Unregistered birth place '{b_place.get('standardized')}'")
            continue
        if not d_ok:
            quarantine_file(f, f"Location resolution failure: Unregistered death place '{d_place.get('standardized')}'")
            continue

        if new_b and "birth" in vitals:
            vitals["birth"]["place"] = new_b
        if new_d and "death" in vitals:
            vitals["death"]["place"] = new_d

        passed_records.append(p)
        passed_files.append(f)
        log(f"Location canonicalized for record: {p.get('person_id')}", verbose=verbose)

    log(f"Location canonicalization passed for {len(passed_records)} records.", verbose=verbose)
    return passed_records, passed_files


def stage_5_minting_and_rewrite(
    staged_records: List[Dict[str, Any]],
    existing_people: List[Dict[str, Any]],
    verbose: bool = False
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    max_num = -1
    for p in existing_people:
        match = re.match(r"^IND-(\d{5})$", p.get("person_id", ""))
        if match:
            max_num = max(max_num, int(match.group(1)))

    id_map: Dict[str, str] = {}
    current_idx = max_num + 1

    for p in staged_records:
        old_id = p["person_id"]
        new_id = f"IND-{current_idx:05d}"
        id_map[old_id] = new_id
        p["person_id"] = new_id
        log(f"Minted new master ID {new_id} for staging ID {old_id} ({p.get('display_name')})", verbose=verbose)
        current_idx += 1

    for p in staged_records:
        for rel in p.get("associated_people") or []:
            t_id = rel.get("person_id")
            if t_id and t_id in id_map:
                rel["person_id"] = id_map[t_id]

    existing_lookup: Dict[str, Dict[str, Any]] = {p["person_id"]: p for p in existing_people}
    reciprocal_map = {"FATH": "CHIL", "MOTH": "CHIL", "CHIL": "OTHER", "SPOU": "SPOU"}

    for p in staged_records:
        new_id = p["person_id"]
        for rel in p.get("associated_people") or []:
            target_id = rel.get("person_id")
            role = rel.get("role")
            if target_id in existing_lookup and role in reciprocal_map:
                recip_role = reciprocal_map[role]
                target_person = existing_lookup[target_id]
                target_rel_list = target_person.setdefault("associated_people", [])
                if not any(r.get("person_id") == new_id for r in target_rel_list):
                    target_rel_list.append({
                        "person_id": new_id,
                        "role": recip_role
                    })
                    log(f"Linked reciprocal {recip_role} from {target_id} to newly minted {new_id}", verbose=verbose)

    return staged_records, existing_people


def stage_6_atomic_commit(
    new_records: List[Dict[str, Any]],
    updated_existing: List[Dict[str, Any]],
    staged_files: List[Path],
    verbose: bool = False
) -> bool:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    if PEOPLE_FILE.exists():
        bk_target = BACKUPS_DIR / f"people.json.{TIMESTAMP}.bk"
        bk_target.write_text(PEOPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        log(f"Pre-execution backup created: {bk_target.name}")

    all_persons = updated_existing + new_records
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    registry_container = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.2",
        "created_at": "2026-08-26T20:39:12Z",
        "last_modified": now_iso,
        "total_persons": len(all_persons),
        "persons": all_persons
    }

    save_json(PEOPLE_FILE, registry_container)
    log(f"Successfully committed {len(all_persons)} persons to {PEOPLE_FILE}")

    for f in staged_files:
        try:
            f.unlink()
            log(f"Removed staging file: {f.name}", verbose=verbose)
        except Exception as e:
            log(f"Warning: Failed to unlink {f.name}: {e}", level="WARN")

    return True


def restore_quarantine() -> None:
    if not HOLD_DIR.exists():
        log("No quarantine hold directory found to restore from.", level="INFO")
        return
    
    held_files = list(HOLD_DIR.glob("pep-let-*.json"))
    if not held_files:
        log("Quarantine hold directory is empty.", level="INFO")
        return

    ENTITIES_DIR = ROOT_DIR / "data/entities"
    ENTITIES_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    for f in held_files:
        target = ENTITIES_DIR / f.name
        try:
            shutil.copy(str(f), str(target))
            f.unlink()
            log(f"Restored {f.name} from hold back to data/entities/")
            count += 1
        except Exception as e:
            log(f"Failed to restore {f.name}: {e}", level="ERROR")

    log(f"Restored {count} files from quarantine back to staging.")


def main() -> None:
    parser = argparse.ArgumentParser(description="GPI: Genealogy Person Intake Pipeline")
    parser.add_argument("--append", "-a", action="store_true", help="Execute ingestion: process person batches, merge to master people.json, backup, and clean")
    parser.add_argument("--restore", "-r", action="store_true", help="Restore all files from quarantine back to data/entities/ for re-evaluation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Output diagnostic runtime details and itemized person ingestion logs")
    args = parser.parse_args()

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log("=== Commencing Person Intake Pipeline (gpi.py) ===")

    if args.restore:
        restore_quarantine()
        return

    if not args.append:
        log("Operation mode not specified. Use --append (-a) to run ingestion or --restore (-r) to recover quarantined files.", level="WARN")
        return

    staged_files = stage_0_discovery()
    if not staged_files:
        log("No staged pep-let-*.json files discovered. Ingestion complete.")
        return
    log(f"Discovered {len(staged_files)} staged person files.")

    staged_records, valid_files = stage_1_validate_syntax(staged_files, args.verbose)
    if not staged_records:
        log("No files passed syntactic validation.", level="WARN")
        return

    if not PEOPLE_FILE.exists() or not LOCATIONS_FILE.exists() or not LOCATION_INDEX_FILE.exists():
        log("Required master entities or indexes missing.", level="ERROR")
        sys.exit(1)

    people_registry = load_json(PEOPLE_FILE)
    existing_people = people_registry.get("persons", [])
    locations_entity = load_json(LOCATIONS_FILE)
    location_index = load_json(LOCATION_INDEX_FILE)

    topo_records, topo_files = stage_2_verify_graph_topology(
        staged_records, valid_files, existing_people, args.verbose
    )
    if not topo_records:
        log("No files passed graph topology verification.", level="WARN")
        return

    dedup_records, dedup_files = stage_3_deduplication_drift(
        topo_records, topo_files, existing_people, args.verbose
    )
    if not dedup_records:
        log("All staged records resolved as duplicates.", level="WARN")
        return

    canon_records, canon_files = stage_4_canonicalize_locations(
        dedup_records, dedup_files, locations_entity, location_index, args.verbose
    )
    if not canon_records:
        log("All staged records failed location canonicalization.", level="WARN")
        return

    minted_records, updated_existing = stage_5_minting_and_rewrite(
        canon_records, existing_people, args.verbose
    )
    stage_6_atomic_commit(minted_records, updated_existing, canon_files, args.verbose)
    log("=== Person Intake Pipeline Completed Successfully ===")


if __name__ == "__main__":
    main()