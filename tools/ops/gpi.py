# Name: gpi.py
# Path: tools/ops/gpi.py

"""Genealogy Person Intake Pipeline (GPI).

Automated 7-stage state machine and pipeline for discovering, validating,
canonicalizing, and committing individual person entities (pep-lets) to the
master person registry (people.json) within the digital archive.
"""

import argparse
import glob
import json
import logging
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure repository root is on sys.path for standalone invocation
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import jsonschema

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil

__version__ = "1.0.4+build.20260922.2"

STAGING_GLOB_PATTERN = "data/entities/pep-let-*.json"


def quarantine_file(
    file_path: Path,
    reason: str,
    logger: Optional[logging.Logger] = None,
    quarantine_dir: Optional[Path] = None,
) -> None:
    """Safely relocates an unverified or invalid entity file to quarantine.

    Args:
        file_path (Path): Path to the target entity JSON file.
        reason (str): Diagnostic rationale for quarantining the file.
        logger (Optional[logging.Logger]): Operational logger instance.
        quarantine_dir (Optional[Path]): Override quarantine target directory.
    """
    log = logger or logging.getLogger("gpi")
    dest_dir = quarantine_dir or CONFIG.quarantine
    log.warning(f"Quarantining {file_path.name} to {dest_dir}: {reason}")
    try:
        GDAUtil.quarantine_file(file_path, quarantine_dir=dest_dir)
    except Exception as e:
        log.error(f"Failed to quarantine file {file_path.name}: {e}")


# ----------------------------------------------------------------------
# PIPELINE STAGES
# ----------------------------------------------------------------------

def stage_0_discovery(root_dir: Optional[Path] = None) -> List[Path]:
    """Discovers staged pep-let JSON files in the entity intake workspace.

    Args:
        root_dir (Optional[Path]): Archive root directory anchor.

    Returns:
        List[Path]: Sorted list of discovered pep-let file paths.
    """
    anchor = root_dir or CONFIG.root
    pattern = str(anchor / STAGING_GLOB_PATTERN)
    files = [Path(p) for p in glob.glob(pattern)]
    return sorted(files)


def stage_1_validate_syntax(
    files: List[Path],
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
    person_schema_path: Optional[Path] = None,
    quarantine_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """Validates staged individual person entities against person.schema.json.

    Args:
        files (List[Path]): Staged files under evaluation.
        verbose (bool): Whether to emit detailed diagnostics.
        logger (Optional[logging.Logger]): Operational logger.
        person_schema_path (Optional[Path]): Explicit person schema path.
        quarantine_dir (Optional[Path]): Explicit quarantine directory.

    Returns:
        Tuple[List[Dict[str, Any]], List[Path]]: Valid records and corresponding paths.
    """
    log = logger or logging.getLogger("gpi")
    valid_records: List[Dict[str, Any]] = []
    valid_files: List[Path] = []

    schema_file = person_schema_path or CONFIG.person_schema
    if not schema_file.exists():
        log.error(f"Person entity schema not found: {schema_file}")
        return [], []

    shared_schema_file = schema_file.parent.parent / "defs" / "_shared_defs.schema.json"
    schema_data = GDAUtil.load_json(schema_file)

    store = {}
    if shared_schema_file.exists():
        shared_data = GDAUtil.load_json(shared_schema_file)
        store = {
            shared_data.get("$id", "https://genealogy.archive/schemas/defs/_shared_defs.schema.json"): shared_data,
            shared_schema_file.as_uri(): shared_data,
            "../defs/_shared_defs.schema.json": shared_data,
        }

    resolver = jsonschema.RefResolver(
        base_uri=f"{schema_file.parent.as_uri()}/",
        referrer=schema_data,
        store=store,
    )
    validator = jsonschema.Draft202012Validator(schema_data, resolver=resolver)

    for file_path in files:
        try:
            record = GDAUtil.load_json(file_path)
            validator.validate(instance=record)
            valid_records.append(record)
            valid_files.append(file_path)
            if verbose:
                log.info(f"Syntax valid: {file_path.name}")
        except jsonschema.ValidationError as ve:
            quarantine_file(file_path, f"Schema validation error: {ve.message}", logger=log, quarantine_dir=quarantine_dir)
        except Exception as e:
            quarantine_file(file_path, f"Reference/Parse error: {e}", logger=log, quarantine_dir=quarantine_dir)

    return valid_records, valid_files


def stage_2_verify_graph_topology(
    staged_records: List[Dict[str, Any]],
    staged_files: List[Path],
    existing_people: List[Dict[str, Any]],
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
    quarantine_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """Ensures each staged entity has a contiguous path to root individual IND-00000.

    Args:
        staged_records (List[Dict[str, Any]]): Validated entity records.
        staged_files (List[Path]): File paths corresponding to staged_records.
        existing_people (List[Dict[str, Any]]): Current master people records.
        verbose (bool): Whether to log detailed item traces.
        logger (Optional[logging.Logger]): Operational logger.
        quarantine_dir (Optional[Path]): Explicit quarantine directory.

    Returns:
        Tuple[List[Dict[str, Any]], List[Path]]: Topology-verified records and paths.
    """
    log = logger or logging.getLogger("gpi")
    existing_ids: Set[str] = {p["person_id"] for p in existing_people if isinstance(p, dict) and "person_id" in p}
    staged_ids: Set[str] = {p["person_id"] for p in staged_records if isinstance(p, dict) and "person_id" in p}

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
            if verbose:
                log.info(f"Graph topology verified for item: {pid}")
        else:
            quarantine_file(
                f,
                f"Graph topology error: Person {pid} has no path to root IND-00000",
                logger=log,
                quarantine_dir=quarantine_dir,
            )

    log.info(f"Graph topology passed for {len(verified_records)}/{len(staged_records)} entities.")
    return verified_records, verified_files


def stage_3_deduplication_drift(
    staged_records: List[Dict[str, Any]],
    staged_files: List[Path],
    existing_people: List[Dict[str, Any]],
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
    quarantine_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """Filters duplicate entities matching an existing identity fingerprint.

    Args:
        staged_records (List[Dict[str, Any]]): Staged person entities.
        staged_files (List[Path]): File paths corresponding to staged_records.
        existing_people (List[Dict[str, Any]]): Current master individuals.
        verbose (bool): Whether to log detailed diagnostic traces.
        logger (Optional[logging.Logger]): Operational logger.
        quarantine_dir (Optional[Path]): Explicit quarantine directory.

    Returns:
        Tuple[List[Dict[str, Any]], List[Path]]: Non-duplicate records and paths.
    """
    log = logger or logging.getLogger("gpi")
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
            quarantine_file(
                f,
                f"Collision: Candidate duplicate matching {g} {s} ({b_year}) already in people.json",
                logger=log,
                quarantine_dir=quarantine_dir,
            )
        else:
            accepted_records.append(p)
            accepted_files.append(f)
            if verbose:
                log.info(f"Deduplication passed for record: {p.get('person_id')}")

    return accepted_records, accepted_files


def stage_4_canonicalize_locations(
    staged_records: List[Dict[str, Any]],
    staged_files: List[Path],
    locations_entity: Dict[str, Any],
    location_index: Dict[str, Any],
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
    quarantine_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """Standardizes birth and death location objects against canonical locations.

    Args:
        staged_records (List[Dict[str, Any]]): Staged entities.
        staged_files (List[Path]): File paths corresponding to staged_records.
        locations_entity (Dict[str, Any]): Canonical locations registry payload.
        location_index (Dict[str, Any]): Master location redirects index.
        verbose (bool): Whether to log detailed diagnostic messages.
        logger (Optional[logging.Logger]): Operational logger.
        quarantine_dir (Optional[Path]): Explicit quarantine directory.

    Returns:
        Tuple[List[Dict[str, Any]], List[Path]]: Canonicalized records and paths.
    """
    log = logger or logging.getLogger("gpi")
    redirects = location_index.get("redirects", {})
    canonical_places: Dict[str, Dict[str, Any]] = {
        loc["location"]["standardized"].lower(): loc["location"]
        for loc in locations_entity.get("locations", [])
        if "location" in loc and "standardized" in loc["location"]
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
                "details": matched.get("details"),
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
            quarantine_file(
                f,
                f"Location resolution failure: Unregistered birth place '{b_place.get('standardized')}'",
                logger=log,
                quarantine_dir=quarantine_dir,
            )
            continue
        if not d_ok:
            quarantine_file(
                f,
                f"Location resolution failure: Unregistered death place '{d_place.get('standardized')}'",
                logger=log,
                quarantine_dir=quarantine_dir,
            )
            continue

        if new_b and "birth" in vitals:
            vitals["birth"]["place"] = new_b
        if new_d and "death" in vitals:
            vitals["death"]["place"] = new_d

        passed_records.append(p)
        passed_files.append(f)
        if verbose:
            log.info(f"Location canonicalized for record: {p.get('person_id')}")

    log.info(f"Location canonicalization passed for {len(passed_records)} records.")
    return passed_records, passed_files


def stage_5_minting_and_rewrite(
    staged_records: List[Dict[str, Any]],
    existing_people: List[Dict[str, Any]],
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Mints sequential IND-XXXXX identifiers and rewrites internal reciprocal links.

    Args:
        staged_records (List[Dict[str, Any]]): Validated staged person entities.
        existing_people (List[Dict[str, Any]]): Current master individuals.
        verbose (bool): Whether to log ID minting actions.
        logger (Optional[logging.Logger]): Operational logger.

    Returns:
        Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: Minted staged entities and updated master records.
    """
    log = logger or logging.getLogger("gpi")
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
        if verbose:
            log.info(f"Minted new master ID {new_id} for staging ID {old_id} ({p.get('display_name')})")
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
                        "role": recip_role,
                    })
                    if verbose:
                        log.info(f"Linked reciprocal {recip_role} from {target_id} to newly minted {new_id}")

    return staged_records, existing_people


def stage_6_atomic_commit(
    new_records: List[Dict[str, Any]],
    updated_existing: List[Dict[str, Any]],
    staged_files: List[Path],
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
    people_path: Optional[Path] = None,
) -> bool:
    """Executes safe backup, writes updated master people.json, and cleans staged files.

    Args:
        new_records (List[Dict[str, Any]]): Minted new individuals.
        updated_existing (List[Dict[str, Any]]): Existing records with updated reciprocal edges.
        staged_files (List[Path]): Successfully ingested staging files.
        verbose (bool): Whether to log file unlink events.
        logger (Optional[logging.Logger]): Operational logger.
        people_path (Optional[Path]): Explicit path to people.json.

    Returns:
        bool: True upon successful commit and unlinking.
    """
    log = logger or logging.getLogger("gpi")
    target_people = people_path or CONFIG.people

    if target_people.exists():
        backup_path = GDAUtil.create_safe_backup(target_people)
        log.info(f"Pre-execution backup created: {backup_path.name}")

    all_persons = updated_existing + new_records
    now_iso = GDAUtil.iso_now()

    registry_container = {
        "$schema": "schemas/entities/person_registry.schema.json",
        "schema_version": "1.0.2",
        "created_at": "2026-08-26T20:39:12Z",
        "last_modified": now_iso,
        "total_persons": len(all_persons),
        "persons": all_persons,
    }

    GDAUtil.save_json(target_people, registry_container)
    log.info(f"Successfully committed {len(all_persons)} persons to {target_people}")

    for f in staged_files:
        try:
            f.unlink()
            if verbose:
                log.info(f"Removed staging file: {f.name}")
        except Exception as e:
            log.warning(f"Failed to unlink {f.name}: {e}")

    return True


def restore_quarantine(
    logger: Optional[logging.Logger] = None,
    quarantine_dir: Optional[Path] = None,
    entities_dir: Optional[Path] = None,
) -> None:
    """Restores all quarantined pep-let files back to data/entities/ for re-evaluation.

    Args:
        logger (Optional[logging.Logger]): Operational logger.
        quarantine_dir (Optional[Path]): Explicit quarantine directory.
        entities_dir (Optional[Path]): Explicit target entities directory.
    """
    log = logger or logging.getLogger("gpi")
    q_dir = quarantine_dir or CONFIG.quarantine
    ent_dir = entities_dir or CONFIG.entities

    if not q_dir.exists():
        log.info("No quarantine directory found to restore from.")
        return

    held_files = list(q_dir.glob("pep-let-*.json"))
    if not held_files:
        log.info("Quarantine directory is empty.")
        return

    ent_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in held_files:
        target = ent_dir / f.name
        try:
            shutil.copy(str(f), str(target))
            f.unlink()
            log.info(f"Restored {f.name} from quarantine back to {ent_dir.name}")
            count += 1
        except Exception as e:
            log.error(f"Failed to restore {f.name}: {e}")

    log.info(f"Restored {count} files from quarantine back to staging.")


def main() -> None:
    """CLI parameter parsing and stage dispatch for the Person Intake Pipeline."""
    parser = argparse.ArgumentParser(description="GPI: Genealogy Person Intake Pipeline")
    parser.add_argument(
        "--append", "-a", action="store_true",
        help="Execute ingestion: process person batches, merge to master people.json, backup, and clean",
    )
    parser.add_argument(
        "--restore", "-r", action="store_true",
        help="Restore all files from quarantine back to data/entities/ for re-evaluation",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Output diagnostic runtime details and itemized person ingestion logs",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Route runtime traces to standard error",
    )
    args = parser.parse_args()

    c_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logger("gpi", console_level=c_level, file_level=logging.DEBUG)
    logger.info("=== Commencing Person Intake Pipeline (gpi.py) ===", extra={"sys_event": True})

    if args.restore:
        restore_quarantine(logger=logger)
        return

    if not args.append:
        logger.warning("Operation mode not specified. Use --append (-a) to run ingestion or --restore (-r) to recover quarantined files.")
        return

    staged_files = stage_0_discovery()
    if not staged_files:
        logger.info("No staged pep-let-*.json files discovered. Ingestion complete.", extra={"sys_event": True})
        return
    logger.info(f"Discovered {len(staged_files)} staged person files.")

    staged_records, valid_files = stage_1_validate_syntax(staged_files, verbose=args.verbose, logger=logger)
    if not staged_records:
        logger.warning("No files passed syntactic validation.")
        return

    if not CONFIG.people.exists() or not CONFIG.locations.exists() or not CONFIG.locations_index.exists():
        logger.error("Required master entities or indexes missing.")
        sys.exit(1)

    people_registry = GDAUtil.load_json(CONFIG.people)
    existing_people = people_registry.get("persons", [])
    locations_entity = GDAUtil.load_json(CONFIG.locations)
    location_index = GDAUtil.load_json(CONFIG.locations_index)

    topo_records, topo_files = stage_2_verify_graph_topology(
        staged_records, valid_files, existing_people, verbose=args.verbose, logger=logger
    )
    if not topo_records:
        logger.warning("No files passed graph topology verification.")
        return

    dedup_records, dedup_files = stage_3_deduplication_drift(
        topo_records, topo_files, existing_people, verbose=args.verbose, logger=logger
    )
    if not dedup_records:
        logger.warning("All staged records resolved as duplicates.")
        return

    canon_records, canon_files = stage_4_canonicalize_locations(
        dedup_records, dedup_files, locations_entity, location_index, verbose=args.verbose, logger=logger
    )
    if not canon_records:
        logger.warning("All staged records failed location canonicalization.")
        return

    minted_records, updated_existing = stage_5_minting_and_rewrite(
        canon_records, existing_people, verbose=args.verbose, logger=logger
    )
    stage_6_atomic_commit(minted_records, updated_existing, canon_files, verbose=args.verbose, logger=logger)
    logger.info("=== Person Intake Pipeline Completed Successfully ===", extra={"sys_event": True})


if __name__ == "__main__":
    main()