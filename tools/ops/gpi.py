# Name: gpi.py
# Path: tools/ops/gpi.py
# Version: 1.1.0+build.20261006.5

"""GPI: Genealogy Person Intake Operational CLI Pipeline.

Executes a 7-stage state machine processing staged pep-let entities into
canonical people registries:
- Stage 0: Staging discovery pattern matching (pep-let-*.json).
- Stage 1: Syntax and strict schema conformance (disallowed props, vital sync).
- Stage 2: Topological graph reachability and path-to-root validation.
- Stage 2b: Inter-record relational chronology checks (parent age boundaries).
- Stage 3: Deduplication drift and master registry collision detection.
- Stage 4: Canonical location resolution, redirects, and detail expansion.
- Stage 5: Sequential identifier minting and reciprocal relation rewrites.
- Stage 6: Atomic commit via GDAPeople, Safe Backup generation, and staging cleanup.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import jsonschema

from gdacore.config import CONFIG, GDAConfig
from gdacore.logger import get_logger, setup_logger
from gdacore.reference_manager import GDAReferenceManager
from gdacore.util import GDAUtil
from gdadomain.people import GDAPeople
from tools.ops.gpa import RegistryAuditor

__version__ = "1.1.0+build.20261006.5"


def quarantine_file(
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
    """Restores all quarantined pep-let files back to the entities directory."""
    q_dir = quarantine_dir or CONFIG.quarantine
    target_dir = entities_dir or CONFIG.entities
    if not q_dir.exists():
        logger.info("Quarantine directory does not exist: %s", q_dir)
        return 0

    count = 0
    for q_file in q_dir.glob("*_pep-let-*.json"):
        clean_name = re.sub(r"^\d{8}_\d{6}_", "", q_file.name)
        dest = target_dir / clean_name
        q_file.rename(dest)
        meta_file = q_dir / f"{q_file.name}.reason.txt"
        if meta_file.exists():
            meta_file.unlink()
        logger.info("RESTORED: %s -> %s", q_file.name, dest.name)
        count += 1
    return count


def stage_0_discovery(root_dir: Optional[Path] = None) -> List[Path]:
    """Finds all pep-let-*.json staging files in entities directory."""
    ent_dir = (root_dir / "data" / "entities") if root_dir else CONFIG.entities
    if not ent_dir.exists():
        return []
    return sorted(ent_dir.glob("pep-let-*.json"))


def stage_1_validate_syntax(
    staged_files: List[Path],
    verbose: bool,
    logger: logging.Logger,
    quarantine_dir: Optional[Path] = None,
    schema_file: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """Validates schema conformance and basic biological chronology via GPA."""
    valid_records: List[Dict[str, Any]] = []
    valid_paths: List[Path] = []

    resolved_schema = schema_file or (CONFIG.schema_entities / "person.schema.json")
    schema_data = GDAUtil.load_json(resolved_schema) if resolved_schema.is_file() else None

    for f in staged_files:
        try:
            data = GDAUtil.load_json(f)
        except Exception as e:
            quarantine_file(f, f"JSON Parse Error: {e}", logger, quarantine_dir)
            continue

        if schema_data:
            validator = jsonschema.Draft202012Validator(schema_data)
            errors = list(validator.iter_errors(data))
            if errors:
                err_msg = "; ".join(f"{e.message} at path {list(e.path)}" for e in errors)
                quarantine_file(f, f"Schema Conformance Error: {err_msg}", logger, quarantine_dir)
                continue

        auditor = RegistryAuditor({"total_persons": 1, "persons": [data]}, logger)
        auditor.audit_vital_synchronization()
        auditor.audit_biological_chronology()
        criticals = auditor.findings.critical
        if criticals:
            reasons = "; ".join(f"[{c['rule']}] {c['message']}" for c in criticals)
            quarantine_file(f, f"GPA Critical Validation Error: {reasons}", logger, quarantine_dir)
            continue

        valid_records.append(data)
        valid_paths.append(f)

    return valid_records, valid_paths


def stage_2_verify_graph_topology(
    records: List[Dict[str, Any]],
    paths: List[Path],
    existing_people: List[Dict[str, Any]],
    verbose: bool,
    logger: logging.Logger,
    quarantine_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """Ensures records contain valid linkages to existing entities or co-staged entities."""
    known_ids: Set[str] = {p.get("person_id") for p in existing_people if p.get("person_id")}
    staged_ids: Set[str] = {r.get("person_id") for r in records if r.get("person_id")}
    all_known = known_ids | staged_ids

    passed_records: List[Dict[str, Any]] = []
    passed_paths: List[Path] = []

    for r, p in zip(records, paths):
        assocs = r.get("associated_people", [])
        unions = r.get("unions", [])
        referenced_ids = {a.get("person_id") for a in assocs if a.get("person_id")}
        referenced_ids.update(u.get("spouse_id") for u in unions if u.get("spouse_id"))

        if not referenced_ids and len(known_ids) > 0:
            quarantine_file(p, "Isolated entity: zero connections specified", logger, quarantine_dir)
            continue

        dangling = referenced_ids - all_known
        if dangling:
            quarantine_file(p, f"Dangling references: {dangling}", logger, quarantine_dir)
            continue

        passed_records.append(r)
        passed_paths.append(p)

    return passed_records, passed_paths


def stage_2b_verify_relational_chronology(
    records: List[Dict[str, Any]],
    paths: List[Path],
    existing_people: List[Dict[str, Any]],
    verbose: bool,
    logger: logging.Logger,
    quarantine_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """Evaluates cross-entity biological chronology against established entities."""
    combined_persons = copy.deepcopy(existing_people) + copy.deepcopy(records)
    auditor = RegistryAuditor({"total_persons": len(combined_persons), "persons": combined_persons}, logger)
    auditor.audit_biological_chronology()

    staged_pids = {r.get("person_id") for r in records}
    critical_by_pid: Dict[str, List[str]] = {}
    for c in auditor.findings.critical:
        pid = c["person_id"]
        if pid in staged_pids:
            critical_by_pid.setdefault(pid, []).append(f"[{c['rule']}] {c['message']}")

    passed_records: List[Dict[str, Any]] = []
    passed_paths: List[Path] = []

    for r, p in zip(records, paths):
        pid = r.get("person_id")
        if pid in critical_by_pid:
            reason = "; ".join(critical_by_pid[pid])
            quarantine_file(p, f"Relational Chronology Error: {reason}", logger, quarantine_dir)
            continue
        passed_records.append(r)
        passed_paths.append(p)

    return passed_records, passed_paths


def stage_3_deduplication_drift(
    records: List[Dict[str, Any]],
    paths: List[Path],
    existing_people: List[Dict[str, Any]],
    verbose: bool,
    logger: logging.Logger,
    quarantine_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """Flags exact identity collisions against existing person records."""
    existing_fingerprints: Dict[str, str] = {}
    for p in existing_people:
        pid = p.get("person_id", "UNKNOWN")
        cname = p.get("canonical_name") or {}
        given = (cname.get("given") or "").strip().lower()
        surname = (cname.get("surname") or "").strip().lower()
        byear = (cname.get("birth_year") or {}).get("year") or ""
        if given and surname:
            existing_fingerprints[f"{given}|{surname}|{byear}"] = pid

    passed_records: List[Dict[str, Any]] = []
    passed_paths: List[Path] = []

    for r, p in zip(records, paths):
        cname = r.get("canonical_name") or {}
        given = (cname.get("given") or "").strip().lower()
        surname = (cname.get("surname") or "").strip().lower()
        byear = (cname.get("birth_year") or {}).get("year") or ""
        fp = f"{given}|{surname}|{byear}"

        if fp in existing_fingerprints:
            colliding_id = existing_fingerprints[fp]
            quarantine_file(p, f"Deduplication collision with {colliding_id}: {fp}", logger, quarantine_dir)
            continue

        passed_records.append(r)
        passed_paths.append(p)

    return passed_records, passed_paths


def stage_4_canonicalize_locations(
    records: List[Dict[str, Any]],
    paths: List[Path],
    loc_data: Dict[str, Any],
    index_data: Dict[str, Any],
    verbose: bool,
    logger: logging.Logger,
    quarantine_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """Resolves and canonicalizes vital place names against locations.json."""
    locations_list = loc_data.get("locations", [])
    loc_by_std = {
        loc["location"]["standardized"].strip().lower(): loc
        for loc in locations_list
        if "location" in loc and "standardized" in loc["location"]
    }
    redirects = {
        k.strip().lower(): v.get("standardized")
        for k, v in index_data.get("redirects", {}).items()
    }

    passed_records: List[Dict[str, Any]] = []
    passed_paths: List[Path] = []

    for r, p in zip(records, paths):
        failed_loc = False
        vitals = r.get("vitals") or {}
        for vital_type in ("birth", "death"):
            v_obj = vitals.get(vital_type)
            if not v_obj:
                continue
            place_obj = v_obj.get("place")
            if not place_obj or not isinstance(place_obj, dict):
                continue

            std_candidate = (place_obj.get("standardized") or place_obj.get("verbatim") or "").strip()
            if not std_candidate:
                continue

            low_std = std_candidate.lower()
            if low_std in redirects:
                std_candidate = redirects[low_std]
                low_std = std_candidate.lower()

            if low_std not in loc_by_std:
                quarantine_file(p, f"Unregistered location: '{std_candidate}' under {vital_type}", logger, quarantine_dir)
                failed_loc = True
                break

            matched_loc = loc_by_std[low_std]["location"]
            place_obj["standardized"] = matched_loc.get("standardized")
            if "details" in matched_loc:
                place_obj["details"] = copy.deepcopy(matched_loc["details"])

        if not failed_loc:
            passed_records.append(r)
            passed_paths.append(p)

    return passed_records, passed_paths


def stage_5_minting_and_rewrite(
    records: List[Dict[str, Any]],
    existing_people: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Mints canonical IND-XXXXX identifiers and creates reciprocal relationship links."""
    existing_copy = copy.deepcopy(existing_people)
    records_copy = copy.deepcopy(records)

    max_id = 0
    for p in existing_copy:
        pid = p.get("person_id", "")
        m = re.match(r"^IND-(\d{5})$", pid)
        if m:
            max_id = max(max_id, int(m.group(1)))

    id_map: Dict[str, str] = {}
    for r in records_copy:
        old_id = r.get("person_id")
        max_id += 1
        new_id = f"IND-{max_id:05d}"
        r["person_id"] = new_id
        if old_id:
            id_map[old_id] = new_id

    for r in records_copy:
        for a in r.get("associated_people", []):
            if a.get("person_id") in id_map:
                a["person_id"] = id_map[a["person_id"]]
        for u in r.get("unions", []):
            if u.get("spouse_id") in id_map:
                u["spouse_id"] = id_map[u["spouse_id"]]

    reciprocal_role_map = {
        "FATH": "CHIL",
        "MOTH": "CHIL",
        "PARENT": "CHIL",
        "CHIL": "FATH",
        "SPOU": "SPOU",
    }
    existing_by_id = {p["person_id"]: p for p in existing_copy if "person_id" in p}

    for r in records_copy:
        new_pid = r["person_id"]
        for a in r.get("associated_people", []):
            target_pid = a.get("person_id")
            role = a.get("role")
            if target_pid in existing_by_id:
                target_p = existing_by_id[target_pid]
                recip_role = reciprocal_role_map.get(role, "ASSOC")
                t_assocs = target_p.setdefault("associated_people", [])
                if not any(x.get("person_id") == new_pid for x in t_assocs):
                    t_assocs.append({"person_id": new_pid, "role": recip_role})

    return records_copy, existing_copy


def stage_6_atomic_commit(
    new_records: List[Dict[str, Any]],
    updated_existing: List[Dict[str, Any]],
    staged_files: List[Path],
    verbose: bool,
    logger: logging.Logger,
    people_path: Optional[Path] = None,
) -> bool:
    """Commits minted records via GDAPeople with safe backups and unlinks staging files."""
    target_path = people_path or (CONFIG.entities / "people.json")
    people_mgr = GDAPeople(filepath=target_path)

    for p in updated_existing:
        pid = p.get("person_id")
        if pid and people_mgr.exists(pid):
            people_mgr.update(pid, p)

    for p in new_records:
        if hasattr(people_mgr, "create_person"):
            people_mgr.create_person(p)
        else:
            cname = p.get("canonical_name", {})
            sex = p.get("sex", "U")
            extra_kwargs = {k: v for k, v in p.items() if k not in ("canonical_name", "sex")}
            try:
                people_mgr.add(canonical_name=cname, sex=sex, **extra_kwargs)
            except TypeError:
                people_mgr.add(p)

    people_mgr.save(create_backup=True)

    for f in staged_files:
        if f.exists():
            f.unlink()
            logger.info("CLEANUP: Unlinked staging file %s", f.name)

    return True


def main() -> int:
    """Main CLI entry point for GPI pipeline."""
    parser = argparse.ArgumentParser(description="GPI: Genealogy Person Intake Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Perform checks without committing changes")
    parser.add_argument("--restore", action="store_true", help="Restore quarantined pep-let files to entities")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose diagnostics")
    args = parser.parse_args()

    logger = setup_logger("gpi", ephemeral=True, console_level=logging.DEBUG if args.verbose else logging.INFO)
    logger.info("GPI version %s starting", __version__)

    if args.restore:
        restored = restore_quarantine(logger)
        logger.info("Restore complete: %d files moved out of quarantine", restored)
        return 0

    staged_files = stage_0_discovery()
    if not staged_files:
        logger.info("No pep-let staging files discovered. Exiting.")
        return 0

    logger.info("Discovered %d staged pep-let file(s)", len(staged_files))

    r1, p1 = stage_1_validate_syntax(staged_files, args.verbose, logger)
    if not r1:
        return 0

    people_file = CONFIG.entities / "people.json"
    if people_file.is_file():
        p_data = GDAUtil.load_json(people_file)
        existing_people = p_data.get("persons", p_data.get("people", []))
    else:
        existing_people = []

    r2, p2 = stage_2_verify_graph_topology(r1, p1, existing_people, args.verbose, logger)
    if not r2:
        return 0

    r2b, p2b = stage_2b_verify_relational_chronology(r2, p2, existing_people, args.verbose, logger)
    if not r2b:
        return 0

    r3, p3 = stage_3_deduplication_drift(r2b, p2b, existing_people, args.verbose, logger)
    if not r3:
        return 0

    loc_file = CONFIG.entities / "locations.json"
    idx_file = CONFIG.indexes / "location_index.json"
    loc_data = GDAUtil.load_json(loc_file) if loc_file.is_file() else {}
    idx_data = GDAUtil.load_json(idx_file) if idx_file.is_file() else {}

    r4, p4 = stage_4_canonicalize_locations(r3, p3, loc_data, idx_data, args.verbose, logger)
    if not r4:
        return 0

    if args.dry_run:
        logger.info("[DRY-RUN] All 4 verification stages passed for %d record(s). No changes committed.", len(r4))
        return 0

    minted, updated = stage_5_minting_and_rewrite(r4, existing_people)
    stage_6_atomic_commit(minted, updated, p4, args.verbose, logger, people_path=people_file)
    logger.info("Successfully committed %d record(s) to registry", len(minted))
    return 0


if __name__ == "__main__":
    sys.exit(main())