# Name: gpa.py
# Path: tools/ops/gpa.py

"""GPA: Genealogy People Auditor Operational CLI Tool.

Audits envelope container properties, entity schema conformance, bidirectional
kinship reciprocity, biological chronology limits, vital-date synchronization,
union symmetry, topological island isolation, and location structure. Emits
diagnostic session logs to logs/ and writes structured reports to reports/.

Supports full headless execution via CLI flags as well as an interactive
console menu when invoked without operational arguments.
"""

import argparse
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

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil

__version__ = "1.0.2+build.20260926.2"

VALID_UNION_STATUSES = {
    "MARRIED",
    "DIVORCED",
    "ANNULLED",
    "SEPARATED",
    "WIDOWED",
    "PARTNER",
    "UNKNOWN",
}


class TieredFindings:
    def __init__(self) -> None:
        self.critical: List[Dict[str, Any]] = []
        self.warning: List[Dict[str, Any]] = []
        self.info: List[Dict[str, Any]] = []

    def add(self, level: str, person_id: str, rule: str, message: str) -> None:
        entry = {"person_id": person_id, "rule": rule, "message": message}
        lvl = level.upper()
        if lvl == "CRITICAL":
            self.critical.append(entry)
        elif lvl == "WARNING":
            self.warning.append(entry)
        else:
            self.info.append(entry)

    @property
    def total(self) -> int:
        return len(self.critical) + len(self.warning) + len(self.info)

    def find_rules(self, rule_prefix: str) -> List[Dict[str, Any]]:
        all_items = self.critical + self.warning + self.info
        return [i for i in all_items if i["rule"].startswith(rule_prefix)]


class RegistryAuditor:
    def __init__(self, people_data: Dict[str, Any], logger: logging.Logger) -> None:
        self.data = people_data
        self.persons: List[Dict[str, Any]] = self.data.get("persons", [])
        self.logger = logger
        self.findings = TieredFindings()

        self.person_map: Dict[str, Dict[str, Any]] = {}
        self.duplicate_ids: List[str] = []
        for p in self.persons:
            pid = p.get("person_id")
            if not pid:
                continue
            if pid in self.person_map:
                self.duplicate_ids.append(pid)
            else:
                self.person_map[pid] = p

    @staticmethod
    def _parse_year(date_str: Optional[str]) -> Optional[int]:
        if not date_str:
            return None
        m = re.match(r"^(\d{4})", str(date_str).strip())
        return int(m.group(1)) if m else None

    def audit_envelope(self) -> None:
        req = ["$schema", "schema_version", "created_at", "last_modified", "total_persons", "persons"]
        for f in req:
            if f not in self.data:
                self.findings.add("CRITICAL", "ENV", "ENV_REQ", f"Missing top-level envelope property: {f}")
        total = self.data.get("total_persons")
        actual = len(self.persons)
        if total != actual:
            self.findings.add("CRITICAL", "ENV", "COUNT_MISMATCH", f"total_persons={total} does not match count={actual}")

    def audit_deduplication(self) -> None:
        for pid in self.duplicate_ids:
            self.findings.add("CRITICAL", pid, "DUPLICATE_PERSON_ID", f"Duplicate person_id detected: {pid}")

        seen_fingerprints: Dict[str, str] = {}
        for p in self.persons:
            pid = p.get("person_id", "UNKNOWN")
            cname = p.get("canonical_name") or {}
            given = (cname.get("given") or "").strip().lower()
            surname = (cname.get("surname") or "").strip().lower()
            byear = (cname.get("birth_year") or {}).get("year") or ""

            if given and surname:
                fingerprint = f"{given}|{surname}|{byear}"
                if fingerprint in seen_fingerprints:
                    orig_id = seen_fingerprints[fingerprint]
                    if orig_id != pid:
                        self.findings.add(
                            "WARNING",
                            pid,
                            "DEDUP_COLLISION",
                            f"Identity fingerprint collision with {orig_id}: '{fingerprint}'",
                        )
                else:
                    seen_fingerprints[fingerprint] = pid

    def audit_vital_synchronization(self) -> None:
        """Audits that canonical birth/death years match the dates recorded in vitals."""
        for p in self.persons:
            pid = p.get("person_id", "UNKNOWN")
            cname = p.get("canonical_name") or {}
            vitals = p.get("vitals") or {}

            # Birth year sync
            canon_birth_year = (cname.get("birth_year") or {}).get("year")
            vital_birth_date = ((vitals.get("birth") or {}).get("date") or {}).get("date_start")
            parsed_birth_year = self._parse_year(vital_birth_date)

            if canon_birth_year is not None and parsed_birth_year is not None:
                if canon_birth_year != parsed_birth_year:
                    self.findings.add(
                        "CRITICAL",
                        pid,
                        "VITAL_SYNC_BIRTH_YEAR",
                        f"Canonical birth_year ({canon_birth_year}) does not match vitals.birth ({vital_birth_date})"
                    )

            # Death year sync
            canon_death_year = (cname.get("death_year") or {}).get("year")
            vital_death_date = ((vitals.get("death") or {}).get("date") or {}).get("date_start")
            parsed_death_year = self._parse_year(vital_death_date)

            if canon_death_year is not None and parsed_death_year is not None:
                if canon_death_year != parsed_death_year:
                    self.findings.add(
                        "CRITICAL",
                        pid,
                        "VITAL_SYNC_DEATH_YEAR",
                        f"Canonical death_year ({canon_death_year}) does not match vitals.death ({vital_death_date})"
                    )

    def audit_biological_chronology(self) -> None:
        """Audits biological timeline plausibility and parent-child generational gaps."""
        for p in self.persons:
            pid = p.get("person_id", "UNKNOWN")
            vitals = p.get("vitals") or {}
            birth_dt = ((vitals.get("birth") or {}).get("date") or {}).get("date_start")
            death_dt = ((vitals.get("death") or {}).get("date") or {}).get("date_start")

            b_year = self._parse_year(birth_dt)
            d_year = self._parse_year(death_dt)

            # 1. Death before birth
            if b_year and d_year and d_year < b_year:
                self.findings.add("CRITICAL", pid, "CHRONO_DEATH_BEFORE_BIRTH", f"Death year ({d_year}) precedes birth year ({b_year})")

            # 2. Maximum plausible lifespan (> 115 years without verified note)
            if b_year and d_year and (d_year - b_year) > 115:
                has_longevity_note = any("longevity" in (n.get("text", "").lower() + n.get("title", "").lower()) for n in p.get("notes", []))
                if not has_longevity_note:
                    self.findings.add("WARNING", pid, "CHRONO_IMPLAUSIBLE_LIFESPAN", f"Lifespan of {d_year - b_year} years exceeds standard biological threshold")

            # 3. Generational gap checks against associated parents
            for assoc in p.get("associated_people", []):
                role = assoc.get("role")
                parent_id = assoc.get("person_id")
                if role in ("FATH", "MOTH", "PARENT") and parent_id and parent_id in self.person_map:
                    parent_p = self.person_map[parent_id]
                    p_birth_dt = (((parent_p.get("vitals") or {}).get("birth") or {}).get("date") or {}).get("date_start")
                    p_death_dt = (((parent_p.get("vitals") or {}).get("death") or {}).get("date") or {}).get("date_start")
                    p_b_year = self._parse_year(p_birth_dt)
                    p_d_year = self._parse_year(p_death_dt)

                    if b_year and p_b_year:
                        age_at_child_birth = b_year - p_b_year
                        if age_at_child_birth < 12:
                            self.findings.add("CRITICAL", pid, "CHRONO_PARENT_TOO_YOUNG", f"Parent {parent_id} was {age_at_child_birth} years old when child was born")
                        elif role == "MOTH" and age_at_child_birth > 55:
                            has_late_note = any("late" in (n.get("text", "").lower() + n.get("title", "").lower()) for n in p.get("notes", []))
                            if not has_late_note:
                                self.findings.add("WARNING", pid, "CHRONO_MOTHER_TOO_OLD", f"Mother {parent_id} was {age_at_child_birth} years old at child birth")

                    # Child born after parent death
                    if b_year and p_d_year:
                        if b_year > p_d_year + 1:
                            self.findings.add("CRITICAL", pid, "CHRONO_BORN_AFTER_PARENT_DEATH", f"Child born in {b_year}, after parent {parent_id} died in {p_d_year}")

    def audit_topology(self) -> None:
        """Audits graph connectivity and flags disconnected orphan islands."""
        if len(self.persons) <= 1:
            return

        adj: Dict[str, Set[str]] = {p["person_id"]: set() for p in self.persons if "person_id" in p}
        for p in self.persons:
            pid = p.get("person_id")
            if not pid or pid not in adj:
                continue
            for assoc in p.get("associated_people", []):
                aid = assoc.get("person_id")
                if aid and aid in adj:
                    adj[pid].add(aid)
                    adj[aid].add(pid)
            for u in p.get("unions", []):
                sid = u.get("spouse_id")
                if sid and sid in adj:
                    adj[pid].add(sid)
                    adj[sid].add(pid)

        # BFS connected components
        visited: Set[str] = set()
        components: List[Set[str]] = []
        for pid in adj:
            if pid not in visited:
                comp = set()
                queue = [pid]
                visited.add(pid)
                while queue:
                    curr = queue.pop(0)
                    comp.add(curr)
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                components.append(comp)

        if len(components) > 1:
            components.sort(key=len, reverse=True)
            main_tree = components[0]
            for island in components[1:]:
                for island_pid in island:
                    self.findings.add("CRITICAL", island_pid, "TOPOLOGY_ISLAND", f"Person is in an isolated disconnected component ({len(island)} nodes)")

    def audit_locations(self) -> None:
        """Audits structural integrity of vital location objects."""
        for p in self.persons:
            pid = p.get("person_id", "UNKNOWN")
            vitals = p.get("vitals") or {}
            for vital_type in ("birth", "death"):
                vital_obj = vitals.get(vital_type)
                if not vital_obj:
                    continue
                place = vital_obj.get("place")
                if place is not None:
                    if not isinstance(place, dict):
                        self.findings.add("CRITICAL", pid, "LOCATION_MALFORMED", f"Place under {vital_type} must be an object")
                        continue
                    if "standardized" not in place and "verbatim" not in place:
                        self.findings.add("WARNING", pid, "LOCATION_MISSING_STANDARD", f"Place under {vital_type} missing standardized and verbatim keys")

    def audit_associated_people_reciprocity(self) -> None:
        reciprocal_map = {
            "FATH": "CHIL",
            "MOTH": "CHIL",
            "PARENT": "CHIL",
            "CHIL": ["FATH", "MOTH", "PARENT"],
            "SPOU": "SPOU",
            "HUSB": "WIFE",
            "WIFE": "HUSB",
        }
        for p in self.persons:
            pid = p.get("person_id", "UNKNOWN")
            for assoc in p.get("associated_people", []):
                aid = assoc.get("person_id")
                role = assoc.get("role")
                if not aid:
                    continue
                if aid not in self.person_map:
                    self.findings.add("CRITICAL", pid, "DANGLING_ASSOC", f"Associated person {aid} not found in registry")
                    continue
                target_p = self.person_map[aid]
                expected = reciprocal_map.get(role)
                if not expected:
                    continue
                has_recip = False
                for t_assoc in target_p.get("associated_people", []):
                    if t_assoc.get("person_id") == pid:
                        t_role = t_assoc.get("role")
                        if isinstance(expected, list):
                            if t_role in expected:
                                has_recip = True
                                break
                        elif t_role == expected:
                            has_recip = True
                            break
                if not has_recip:
                    self.findings.add("WARNING", pid, "ASYM_ASSOC", f"Missing reciprocal linkage on {aid} for {role} -> {expected}")

    def audit_unions(self) -> None:
        for p in self.persons:
            pid = p.get("person_id", "UNKNOWN")
            unions = p.get("unions", [])
            spou_assoc_ids = {
                a.get("person_id")
                for a in p.get("associated_people", [])
                if isinstance(a, dict) and a.get("role") in ("SPOU", "HUSB", "WIFE")
            }

            for u in unions:
                sid = u.get("spouse_id")
                status = u.get("status")

                if not sid:
                    self.findings.add("CRITICAL", pid, "UNION_NO_SPOUSE", "Union entry missing spouse_id")
                    continue
                if sid not in self.person_map:
                    self.findings.add("CRITICAL", pid, "UNION_DANGLING_SPOUSE", f"Union spouse_id {sid} does not exist in registry")
                    continue

                if status not in VALID_UNION_STATUSES:
                    self.findings.add("CRITICAL", pid, "UNION_INVALID_STATUS", f"Invalid union status: {status}")

                if sid not in spou_assoc_ids:
                    self.findings.add("WARNING", pid, "UNION_ASSOC_DESYNC", f"Spouse {sid} in unions not found in associated_people (role: SPOU)")

                target_p = self.person_map[sid]
                target_unions = target_p.get("unions", [])
                reciprocal_union = next((tu for tu in target_unions if tu.get("spouse_id") == pid), None)

                if not reciprocal_union:
                    self.findings.add("WARNING", pid, "UNION_ASYM_RECIPROCAL", f"Spouse {sid} does not have reciprocal union entry pointing to {pid}")
                    continue

                m_date_a = (u.get("marriage_date") or {}).get("date_start")
                m_date_b = (reciprocal_union.get("marriage_date") or {}).get("date_start")
                if m_date_a != m_date_b:
                    self.findings.add("WARNING", pid, "UNION_DATE_MISMATCH", f"Marriage date mismatch with {sid}: '{m_date_a}' != '{m_date_b}'")

                t_status = reciprocal_union.get("status")
                compatible_status = False
                if status == t_status:
                    compatible_status = True
                elif {status, t_status} == {"MARRIED", "WIDOWED"}:
                    compatible_status = True

                if not compatible_status:
                    self.findings.add("WARNING", pid, "UNION_STATUS_MISMATCH", f"Union status mismatch with {sid}: {status} vs {t_status}")

    def run_all(self) -> TieredFindings:
        self.audit_envelope()
        self.audit_deduplication()
        self.audit_vital_synchronization()
        self.audit_biological_chronology()
        self.audit_topology()
        self.audit_locations()
        self.audit_associated_people_reciprocity()
        self.audit_unions()
        return self.findings


def run_cli() -> int:
    parser = argparse.ArgumentParser(description="Genealogy People Auditor (GPA)")
    parser.add_argument("--file", "-f", type=Path, default=None, help="Custom people.json file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose log emission")
    args = parser.parse_args()

    logger = setup_logger("gpa", ephemeral=True, console_level=logging.DEBUG if args.verbose else logging.INFO)
    logger.info("GPA version %s initializing", __version__)

    config = GDAConfig(ROOT_DIR)
    default_people_path = getattr(config, "entities_dir", ROOT_DIR / "data" / "entities") / "people.json"
    target_path = args.file or default_people_path

    if not target_path.is_file():
        logger.error("Target file does not exist: %s", target_path)
        return 1

    data = GDAUtil.load_json(target_path)
    auditor = RegistryAuditor(data, logger)
    findings = auditor.run_all()

    logger.info("==========================================")
    logger.info("GPA AUDIT FINDINGS SUMMARY")
    logger.info("==========================================")
    logger.info("CRITICAL findings: %d", len(findings.critical))
    logger.info("WARNING findings:  %d", len(findings.warning))
    logger.info("INFO findings:     %d", len(findings.info))
    logger.info("Total findings:    %d", findings.total)
    logger.info("==========================================")

    for c in findings.critical:
        logger.error("[%s] (%s): %s", c["person_id"], c["rule"], c["message"])
    for w in findings.warning[:15]:
        logger.warning("[%s] (%s): %s", w["person_id"], w["rule"], w["message"])

    return 0 if len(findings.critical) == 0 else 1


if __name__ == "__main__":
    sys.exit(run_cli())