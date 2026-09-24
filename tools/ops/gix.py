# Name: Genealogy Indexing Executor
# Path: tools/ops/gix.py

"""
Genealogy Indexing Executor (gix.py)
Automates compilation, synchronization, and atomic storage of digital archive indices.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

__version__ = "1.2.0+build.20260923.01"

SCRIPT_PATH = Path(__file__).resolve()
ROOT_DIR = SCRIPT_PATH.parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.lib.gda_core.GDAConfig import CONFIG, GDAConfig
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil


def sanitize_surname_key(surname: str) -> str:
    """Normalizes a surname into a clean dictionary key."""
    clean = surname.strip()
    clean = re.sub(r"\s+(?:Jr\.?|Sr\.?|II|III|IV)$", "", clean, flags=re.IGNORECASE).strip().lower()
    sanitized = re.sub(r"[^a-z0-9\s\-]", "", clean)
    return "".join(sanitized.split())


def resolve_canonical_display(target_key: str, raw_surname: str, is_aliased: bool) -> str:
    """Determines canonical surname display capitalization."""
    clean_raw = raw_surname.replace(".", "").strip()
    if is_aliased:
        return target_key.replace("-", " ").title()
    return clean_raw


def extract_child_birth_year(child_entry: Dict[str, Any]) -> int:
    """Extracts integer birth year for chronological child sorting."""
    cname = child_entry.get("canonical_name") or {}
    byear_obj = cname.get("birth_year") or {}
    year = byear_obj.get("year")
    if isinstance(year, int):
        return year
    return 9999


# ---------------------------------------------------------------------------
# Index Generation Functions
# ---------------------------------------------------------------------------

def build_surname_index(config: GDAConfig, logger: logging.Logger) -> bool:
    """Compile surname_index.json from data/entities/people.json and surname_aliases.json."""
    logger.info("[SYS] Initiating build: Surname Index")
    people_file = config.people
    if not people_file.exists():
        logger.error("[SYS] Source file missing: %s", people_file)
        raise FileNotFoundError(f"Source entity file not found: {people_file}")

    target_file = config.indexes / "surname_index.json"
    if target_file.exists():
        backup_path = GDAUtil.create_safe_backup(target_file)
        logger.info("[SYS] Created pre-execution safe backup: %s", backup_path.name)

    alias_file = config.indexes / "surname_aliases.json"
    alias_map: Dict[str, str] = {}
    if alias_file.exists():
        try:
            alias_payload = GDAUtil.load_json(alias_file)
            alias_map = dict(alias_payload.get("aliases", {}))
            logger.info("[SYS] Loaded %d curated surname alias redirects from %s", len(alias_map), alias_file.name)
        except Exception as err:
            logger.warning("[SYS] Failed loading alias map: %s", err)

    logger.info("[SYS] Reading canonical entities from: %s", people_file)
    people_payload = GDAUtil.load_json(people_file)
    people_list: List[Dict[str, Any]] = people_payload.get("persons") or people_payload.get("people", [])
    logger.info("[SYS] Total entities loaded for index compilation: %d", len(people_list))

    harvested_aliases = 0
    for person in people_list:
        cname = person.get("canonical_name")
        if not cname or not isinstance(cname, dict):
            continue
        primary_surname = cname.get("surname")
        if not primary_surname or not str(primary_surname).strip():
            continue

        target_root = sanitize_surname_key(str(primary_surname))
        alias_names = cname.get("aliases") or cname.get("alternate_surnames") or []
        if isinstance(alias_names, str):
            alias_names = [alias_names]

        for alt in alias_names:
            if not alt or not str(alt).strip():
                continue
            alt_key = sanitize_surname_key(str(alt))
            if alt_key and alt_key != target_root and alt_key not in alias_map:
                alias_map[alt_key] = target_root
                harvested_aliases += 1

    if harvested_aliases > 0:
        logger.info("[SYS] Ingested %d dynamic alias redirects from entity records", harvested_aliases)

    surnames_map: Dict[str, Dict[str, Any]] = {}
    skipped_no_name = 0
    skipped_no_surname = 0
    total_persons_indexed = 0

    for idx, person in enumerate(people_list, start=1):
        person_id = person.get("person_id")
        canonical_name = person.get("canonical_name")

        if not person_id or not canonical_name:
            logger.debug("[SKIP] [%d/%d] Entity missing identifier or canonical_name: %s", idx, len(people_list), person_id or "UNKNOWN")
            skipped_no_name += 1
            continue

        raw_surname = canonical_name.get("surname")
        if not raw_surname or not str(raw_surname).strip():
            logger.debug("[SKIP] [%d/%d] %s: canonical_name missing surname", idx, len(people_list), person_id)
            skipped_no_surname += 1
            continue

        clean_surname = str(raw_surname).replace(".", "").strip()
        sanitized_key = sanitize_surname_key(clean_surname)

        target_key = alias_map.get(sanitized_key, sanitized_key)
        is_aliased = (target_key != sanitized_key)
        if is_aliased:
            logger.debug("[ALIAS] [%d/%d] %s (%s) redirected '%s' -> '%s'", idx, len(people_list), person_id, clean_surname, sanitized_key, target_key)

        display_name = GDAUtil.build_display_name(canonical_name)
        if display_name == "UNKNOWN" and person.get("display_name"):
            display_name = person["display_name"].replace(".", "").strip()

        if target_key not in surnames_map:
            canonical_display = resolve_canonical_display(target_key, clean_surname, is_aliased)
            logger.debug("[NEW] [%d/%d] Minting surname bucket '%s' (Canonical: '%s')", idx, len(people_list), target_key, canonical_display)
            surnames_map[target_key] = {
                "canonical_surname": canonical_display,
                "spelling_variants": [],
                "total_persons": 0,
                "persons": []
            }

        bucket = surnames_map[target_key]
        if clean_surname.lower() != bucket["canonical_surname"].lower() and clean_surname not in bucket["spelling_variants"]:
            bucket["spelling_variants"].append(clean_surname)

        person_entry = {
            "person_id": person_id,
            "display_name": display_name
        }
        bucket["persons"].append(person_entry)
        total_persons_indexed += 1
        logger.debug("[ADD] [%d/%d] %s (%s) -> '%s'", idx, len(people_list), person_id, display_name, target_key)

    logger.info("[SYS] Sorting %d surname buckets deterministically", len(surnames_map))
    sorted_surnames: Dict[str, Dict[str, Any]] = {}
    for key in sorted(surnames_map.keys()):
        bucket = surnames_map[key]
        bucket["persons"].sort(key=lambda p: (p["display_name"], p["person_id"]))
        bucket["spelling_variants"].sort()
        bucket["total_persons"] = len(bucket["persons"])
        sorted_surnames[key] = bucket

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    index_payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": "1.0.0",
        "last_modified": now_iso,
        "total_surnames": len(sorted_surnames),
        "aliases": dict(sorted(alias_map.items())),
        "surnames": sorted_surnames
    }

    config.indexes.mkdir(parents=True, exist_ok=True)
    GDAUtil.save_json(target_file, index_payload, indent=2)

    logger.info("[SYS] Build Complete: %s", target_file)
    logger.info("[SYS]   - Surnames Indexed: %d", len(sorted_surnames))
    logger.info("[SYS]   - Active Aliases Ingested: %d", len(alias_map))
    logger.info("[SYS]   - Persons Assigned: %d", total_persons_indexed)
    logger.info("[SYS]   - Skipped (No Name): %d", skipped_no_name)
    logger.info("[SYS]   - Skipped (No Surname): %d", skipped_no_surname)
    return True


def build_family_group_index(config: GDAConfig, logger: logging.Logger) -> bool:
    """Compile family_group_index.json from data/entities/people.json."""
    logger.info("[SYS] Initiating build: Family Group Index")
    people_file = config.people
    if not people_file.exists():
        logger.error("[SYS] Source file missing: %s", people_file)
        raise FileNotFoundError(f"Source entity file not found: {people_file}")

    target_file = config.indexes / "family_group_index.json"
    if target_file.exists():
        backup_path = GDAUtil.create_safe_backup(target_file)
        logger.info("[SYS] Created pre-execution safe backup: %s", backup_path.name)

    logger.info("[SYS] Reading canonical entities from: %s", people_file)
    people_payload = GDAUtil.load_json(people_file)
    people_list: List[Dict[str, Any]] = people_payload.get("persons") or people_payload.get("people", [])
    logger.info("[SYS] Total entities loaded: %d", len(people_list))

    people_by_id: Dict[str, Dict[str, Any]] = {
        p["person_id"]: p for p in people_list if p.get("person_id")
    }

    assocs_by_person: Dict[str, List[Dict[str, Any]]] = {}
    for p in people_list:
        pid = p.get("person_id")
        if not pid:
            continue
        cleaned_assocs = []
        for a in p.get("associated_people", []):
            target_id = a.get("person_id")
            raw_role = (a.get("role") or "").strip().upper()
            role = "SPOU" if raw_role in ("HUSB", "WIFE", "SPOU") else raw_role
            rel = a.get("relationship") or a.get("notes") or ""
            cleaned_assocs.append({
                "person_id": target_id,
                "role": role,
                "relationship": str(rel).strip()
            })
        assocs_by_person[pid] = cleaned_assocs

    spouses_by_person: Dict[str, set] = {}
    couples: set = set()
    single_parents: set = set()

    for pid, assocs in assocs_by_person.items():
        sps = {a["person_id"] for a in assocs if a["role"] == "SPOU" and a["person_id"] in people_by_id}
        if sps:
            spouses_by_person[pid] = sps
            for sp in sps:
                couples.add(tuple(sorted([pid, sp])))

    child_parent_map: Dict[str, Dict[str, Optional[str]]] = {}
    for pid, assocs in assocs_by_person.items():
        fath = next((a["person_id"] for a in assocs if a["role"] == "FATH" and a["person_id"] in people_by_id), None)
        moth = next((a["person_id"] for a in assocs if a["role"] == "MOTH" and a["person_id"] in people_by_id), None)
        if fath or moth:
            child_parent_map[pid] = {"FATH": fath, "MOTH": moth}

        if fath and moth:
            couples.add(tuple(sorted([fath, moth])))
            spouses_by_person.setdefault(fath, set()).add(moth)
            spouses_by_person.setdefault(moth, set()).add(fath)
        elif fath:
            if not any(fath in c for c in couples):
                single_parents.add((fath, None))
        elif moth:
            if not any(moth in c for c in couples):
                single_parents.add((moth, None))

    all_unions = list(couples) + list(single_parents)

    raw_families: List[Dict[str, Any]] = []
    for pair in all_unions:
        p1_id, p2_id = pair
        ent1 = people_by_id.get(p1_id)
        ent2 = people_by_id.get(p2_id) if p2_id else None

        px, py = None, None
        if ent1 and ent2:
            sex1 = ent1.get("sex", "Unknown")
            sex2 = ent2.get("sex", "Unknown")
            if sex1 == "Male" and sex2 == "Female":
                px, py = ent1, ent2
            elif sex1 == "Female" and sex2 == "Male":
                px, py = ent2, ent1
            else:
                px, py = (ent1, ent2) if ent1["person_id"] <= ent2["person_id"] else (ent2, ent1)
        else:
            px = ent1 or ent2
            py = None

        raw_families.append({
            "parent_x": px,
            "parent_y": py,
            "pair_key": (px["person_id"], py["person_id"] if py else None),
            "children": []
        })

    reported_source_errors: set = set()

    for fam in raw_families:
        px = fam["parent_x"]
        py = fam["parent_y"]
        px_id = px["person_id"] if px else None
        py_id = py["person_id"] if py else None

        candidate_children_ids = set()

        if px:
            for a in assocs_by_person.get(px_id, []):
                if a["role"] == "CHIL" and a["person_id"] in people_by_id:
                    candidate_children_ids.add(a["person_id"])
        if py:
            for a in assocs_by_person.get(py_id, []):
                if a["role"] == "CHIL" and a["person_id"] in people_by_id:
                    candidate_children_ids.add(a["person_id"])

        for cid, p_links in child_parent_map.items():
            cf = p_links.get("FATH")
            cm = p_links.get("MOTH")
            if px_id and py_id:
                if (cf == px_id and cm == py_id) or (cf == py_id and cm == px_id):
                    candidate_children_ids.add(cid)
            elif px_id and not py_id:
                if cf == px_id or cm == px_id:
                    candidate_children_ids.add(cid)

        assigned_children_ids = set()
        for cid in candidate_children_ids:
            cf = child_parent_map.get(cid, {}).get("FATH")
            cm = child_parent_map.get(cid, {}).get("MOTH")

            if px_id and py_id:
                if (cf == px_id and cm == py_id) or (cf == py_id and cm == px_id):
                    assigned_children_ids.add(cid)
                    continue

                px_has_multiple = len(spouses_by_person.get(px_id, set())) > 1
                py_has_multiple = len(spouses_by_person.get(py_id, set())) > 1

                py_acknowledges = any(a["person_id"] == cid and a["role"] == "CHIL" for a in assocs_by_person.get(py_id, []))
                px_acknowledges = any(a["person_id"] == cid and a["role"] == "CHIL" for a in assocs_by_person.get(px_id, []))

                if cf == px_id and cm is None and px_has_multiple:
                    if not py_acknowledges:
                        err_key = (cid, px_id)
                        if err_key not in reported_source_errors:
                            err_msg = (
                                f"[ERROR] Source Data Defect: Child {cid} lists father {px_id} who has multiple spouses, "
                                f"but {cid} lacks a MOTH association and spouse {py_id} does not acknowledge child. Cannot assign."
                            )
                            logger.error(err_msg)
                            print(f"\n{err_msg}\n", file=sys.stderr)
                            reported_source_errors.add(err_key)
                        continue
                    else:
                        assigned_children_ids.add(cid)
                elif cm == py_id and cf is None and py_has_multiple:
                    if not px_acknowledges:
                        err_key = (cid, py_id)
                        if err_key not in reported_source_errors:
                            err_msg = (
                                f"[ERROR] Source Data Defect: Child {cid} lists mother {py_id} who has multiple spouses, "
                                f"but {cid} lacks a FATH association and spouse {px_id} does not acknowledge child. Cannot assign."
                            )
                            logger.error(err_msg)
                            print(f"\n{err_msg}\n", file=sys.stderr)
                            reported_source_errors.add(err_key)
                        continue
                    else:
                        assigned_children_ids.add(cid)
                elif cf == px_id and cm is None and not px_has_multiple:
                    assigned_children_ids.add(cid)
                elif cm == py_id and cf is None and not py_has_multiple:
                    assigned_children_ids.add(cid)

            elif px_id and not py_id:
                if cf == px_id and cm is None:
                    assigned_children_ids.add(cid)
                elif cm == px_id and cf is None:
                    assigned_children_ids.add(cid)

        for cid in assigned_children_ids:
            cent = people_by_id[cid]
            c_display = GDAUtil.build_display_name(cent.get("canonical_name"))
            px_display = GDAUtil.build_display_name(px.get("canonical_name")) if px else "Father"
            py_display = GDAUtil.build_display_name(py.get("canonical_name")) if py else "Mother"

            child_assocs = assocs_by_person.get(cid, [])
            x_assoc = next((a for a in child_assocs if a["person_id"] == px_id), None)
            y_assoc = next((a for a in child_assocs if a["person_id"] == py_id), None)

            x_rel = (x_assoc.get("relationship") or "").lower() if x_assoc else ""
            y_rel = (y_assoc.get("relationship") or "").lower() if y_assoc else ""

            if px and not x_rel:
                px_to_c = next((a for a in assocs_by_person.get(px_id, []) if a["person_id"] == cid), None)
                x_rel = (px_to_c.get("relationship") or "").lower() if px_to_c else ""
            if py and not y_rel:
                py_to_c = next((a for a in assocs_by_person.get(py_id, []) if a["person_id"] == cid), None)
                y_rel = (py_to_c.get("relationship") or "").lower() if py_to_c else ""

            rel_note = None
            if "adopt" in x_rel and "adopt" in y_rel:
                rel_note = f"Adopted by {px_display} and {py_display}"
            elif "adopt" in x_rel:
                rel_note = f"Adopted by {px_display}"
            elif "adopt" in y_rel:
                rel_note = f"Adopted by {py_display}"
            elif "step" in x_rel:
                rel_note = f"Stepchild of {px_display}"
            elif "step" in y_rel:
                rel_note = f"Stepchild of {py_display}"

            child_entry = {
                "person_id": cid,
                "display_name": c_display,
                "canonical_name": cent.get("canonical_name"),
                "relationship_note": rel_note
            }
            fam["children"].append(child_entry)

        fam["children"].sort(key=lambda c: (extract_child_birth_year(c), c["person_id"]))

    populated_families = [f for f in raw_families if f["parent_y"] is not None or len(f["children"]) > 0]

    families_by_px: Dict[str, List[Dict[str, Any]]] = {}
    for fam in populated_families:
        px_id = fam["parent_x"]["person_id"]
        families_by_px.setdefault(px_id, []).append(fam)

    minted_families: Dict[str, Dict[str, Any]] = {}

    for px_id, px_fam_list in families_by_px.items():
        def union_sort_key(f):
            children = f["children"]
            earliest_byear = min([extract_child_birth_year(c) for c in children], default=9999)
            py_id = f["parent_y"]["person_id"] if f["parent_y"] else "ZZZZZ"
            return (earliest_byear, py_id)

        px_fam_list.sort(key=union_sort_key)

        digits_match = re.search(r"\d+", px_id)
        base_num = int(digits_match.group()) if digits_match else 0
        for idx, f in enumerate(px_fam_list):
            suffix_char = chr(ord('A') + idx)
            fam_id = f"FAM-{base_num:05d}-{suffix_char}"

            def format_parent(ent):
                if not ent:
                    return None
                return {
                    "person_id": ent["person_id"],
                    "display_name": GDAUtil.build_display_name(ent.get("canonical_name")),
                    "canonical_name": ent.get("canonical_name")
                }

            minted_families[fam_id] = {
                "family_id": fam_id,
                "parent_x": format_parent(f["parent_x"]),
                "parent_y": format_parent(f["parent_y"]),
                "total_children": len(f["children"]),
                "children": f["children"]
            }
            logger.debug("[ADD] Minted %s: %s & %s (%d children)",
                         fam_id,
                         f["parent_x"]["person_id"] if f["parent_x"] else "None",
                         f["parent_y"]["person_id"] if f["parent_y"] else "None",
                         len(f["children"]))

    sorted_families = {k: minted_families[k] for k in sorted(minted_families.keys())}

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    index_payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": "1.1.0",
        "last_modified": now_iso,
        "total_families": len(sorted_families),
        "families": sorted_families
    }

    config.indexes.mkdir(parents=True, exist_ok=True)
    GDAUtil.save_json(target_file, index_payload, indent=2)

    logger.info("[SYS] Build Complete: %s", target_file)
    logger.info("[SYS]   - Total Nuclear Families Indexed: %d", len(sorted_families))
    return True


def build_ahnentafel_index(config: GDAConfig, logger: logging.Logger) -> bool:
    """Compile ahnentafel_index.json from data/entities/people.json."""
    logger.info("[SYS] Initiating build: Ahnentafel Index")
    raise NotImplementedError("Generator function not yet developed: build_ahnentafel_index")


def build_newspaper_obituary_index(config: GDAConfig, logger: logging.Logger) -> bool:
    """Compile newspaper_obituary_index.json from newspaper registry and vitals."""
    logger.info("[SYS] Initiating build: Newspaper Obituary Index")
    raise NotImplementedError("Generator function not yet developed: build_newspaper_obituary_index")


def build_place_index(config: GDAConfig, logger: logging.Logger) -> bool:
    """Compile place_index.json by hierarchical jurisdiction from vital places."""
    logger.info("[SYS] Initiating build: Place / Geographic Index")
    raise NotImplementedError("Generator function not yet developed: build_place_index")


def build_timeline_index(config: GDAConfig, logger: logging.Logger) -> bool:
    """Compile timeline_index.json grouping assertions chronologically by era and year."""
    logger.info("[SYS] Initiating build: Chronological Timeline Index")
    raise NotImplementedError("Generator function not yet developed: build_timeline_index")


def build_source_index(config: GDAConfig, logger: logging.Logger) -> bool:
    """Compile source_index.json resolving citation frequencies and repositories."""
    logger.info("[SYS] Initiating build: Source Citation Index")
    raise NotImplementedError("Generator function not yet developed: build_source_index")


def build_all_indices(config: GDAConfig, logger: logging.Logger) -> bool:
    """Execute compilation sequentially across all archive indices."""
    logger.info("[SYS] Initiating build: ALL INDICES")
    build_surname_index(config, logger)
    build_family_group_index(config, logger)
    build_ahnentafel_index(config, logger)
    build_newspaper_obituary_index(config, logger)
    build_place_index(config, logger)
    build_timeline_index(config, logger)
    build_source_index(config, logger)
    return True


# ---------------------------------------------------------------------------
# Interactive Menu
# ---------------------------------------------------------------------------

def render_interactive_menu(config: GDAConfig, logger: logging.Logger) -> None:
    """Render interactive CLI menu when no action parameters are supplied."""
    while True:
        print("\n=======================================================")
        print("     Genealogy Indexing Executor (GIX) - Main Menu     ")
        print("=======================================================")
        print("  [1] Surname Index (surname_index.json)")
        print("  [2] Family Group Index (family_group_index.json)")
        print("  [3] Ahnentafel Index (ahnentafel_index.json)")
        print("  [4] Newspaper Obituary Index (newspaper_obituary_index.json)")
        print("  [5] Place / Geographic Index (place_index.json)")
        print("  [6] Timeline / Chronological Index (timeline_index.json)")
        print("  [7] Source Citation Index (source_index.json)")
        print("  [A] Build All Indices")
        print("  [Q] Quit (Default)")
        print("-------------------------------------------------------")

        choice = input("Select an option [Q]: ").strip().upper()
        if not choice or choice == "Q":
            print("Exiting GIX.")
            break
        elif choice == "1":
            try:
                build_surname_index(config, logger)
            except Exception as e:
                print(f"[STATUS] {e}")
        elif choice == "2":
            try:
                build_family_group_index(config, logger)
            except Exception as e:
                print(f"[STATUS] {e}")
        elif choice == "3":
            try:
                build_ahnentafel_index(config, logger)
            except NotImplementedError as e:
                print(f"[STATUS] {e}")
        elif choice == "4":
            try:
                build_newspaper_obituary_index(config, logger)
            except NotImplementedError as e:
                print(f"[STATUS] {e}")
        elif choice == "5":
            try:
                build_place_index(config, logger)
            except NotImplementedError as e:
                print(f"[STATUS] {e}")
        elif choice == "6":
            try:
                build_timeline_index(config, logger)
            except NotImplementedError as e:
                print(f"[STATUS] {e}")
        elif choice == "7":
            try:
                build_source_index(config, logger)
            except NotImplementedError as e:
                print(f"[STATUS] {e}")
        elif choice == "A":
            try:
                build_all_indices(config, logger)
            except NotImplementedError as e:
                print(f"[STATUS] {e}")
        else:
            print(f"Invalid option: {choice}. Please select 1-7, A, or Q.")


# ---------------------------------------------------------------------------
# Entry Point & CLI Argument Parsing
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gix.py",
        description="Genealogy Indexing Executor: Compiles and synchronizes archive lookup indices."
    )
    parser.add_argument("--surname", action="store_true", help="Build surname lookup index")
    parser.add_argument("--family", action="store_true", help="Build nuclear family group index")
    parser.add_argument("--ahnentafel", action="store_true", help="Build Ahnentafel pedigree index")
    parser.add_argument("--obituary", action="store_true", help="Build newspaper obituary index")
    parser.add_argument("--place", action="store_true", help="Build place/geographic lookup index")
    parser.add_argument("--timeline", action="store_true", help="Build chronological timeline index")
    parser.add_argument("--source", action="store_true", help="Build source citation cross-reference index")
    parser.add_argument("-a", "--all", action="store_true", help="Build all indices sequentially")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose log emission")
    parser.add_argument("--debug", action="store_true", help="Output debugging traces to stderr")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    console_level = logging.DEBUG if (args.debug or args.verbose) else logging.INFO
    logger = setup_logger(tool_name="gix", console_level=console_level, file_level=logging.DEBUG)

    action_flags = [args.surname, args.family, args.ahnentafel, args.obituary, args.place, args.timeline, args.source, args.all]

    if not any(action_flags):
        render_interactive_menu(CONFIG, logger)
        return 0

    try:
        if args.all:
            build_all_indices(CONFIG, logger)
        else:
            if args.surname:
                build_surname_index(CONFIG, logger)
            if args.family:
                build_family_group_index(CONFIG, logger)
            if args.ahnentafel:
                build_ahnentafel_index(CONFIG, logger)
            if args.obituary:
                build_newspaper_obituary_index(CONFIG, logger)
            if args.place:
                build_place_index(CONFIG, logger)
            if args.timeline:
                build_timeline_index(CONFIG, logger)
            if args.source:
                build_source_index(CONFIG, logger)
    except NotImplementedError as err:
        logger.error("[SYS] Execution halted: %s", err)
        print(f"Error: {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())