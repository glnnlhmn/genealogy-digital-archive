# Name: gpa.py
# Path: tools/ops/gpa.py
# Version: 1.1.0+build.20261006.7

"""GPA: Genealogy People Auditor Operational CLI Tool.

Audits envelope container properties, entity schema conformance, bidirectional
kinship reciprocity, biological chronology limits, vital-date synchronization,
union symmetry, topological island isolation, and location structure. Emits
diagnostic session logs to logs/ and writes structured reports to reports/.

Supports full headless execution via CLI flags as well as an interactive
console menu when invoked without operational arguments.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Union

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from gdacore.config import CONFIG, GDAConfig
from gdacore.logger import get_logger, setup_logger
from gdacore.reference_manager import GDAReferenceManager
from gdacore.util import GDAUtil
from gdadomain.kinship import KinshipEngine
from gdadomain.people import GDAPeople

__version__ = "1.1.0+build.20261006.7"


class TieredFindings:
    """Diagnostic findings container segregated into critical, warning, and info tiers."""

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
    """Domain auditor evaluating people registry data against genealogical invariants."""

    def __init__(
        self,
        people_data: Union[Dict[str, Any], GDAPeople],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or get_logger(__name__)
        self.findings = TieredFindings()

        if isinstance(people_data, GDAPeople):
            self.people_manager: Optional[GDAPeople] = people_data
            self.persons: List[Dict[str, Any]] = [dict(p) for p in people_data]
            self.data: Dict[str, Any] = {
                "total_persons": len(self.persons),
                "persons": self.persons,
            }
        elif isinstance(people_data, dict):
            self.people_manager = None
            self.data = people_data
            self.persons = self.data.get("persons", self.data.get("people", []))
        else:
            raise TypeError("people_data must be a dictionary or a GDAPeople instance.")

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
    def _parse_year(date_val: Optional[Any]) -> Optional[int]:
        if not date_val:
            return None
        if isinstance(date_val, dict):
            if "year" in date_val and isinstance(date_val["year"], int):
                return date_val["year"]
            date_val = date_val.get("date_start") or date_val.get("date")
        m = re.match(r"^(\d{4})", str(date_val).strip())
        return int(m.group(1)) if m else None

    def audit_envelope(self) -> None:
        """Audits container envelope metadata and total count synchronization."""
        req = ["$schema", "schema_version", "created_at", "last_modified", "total_persons", "persons"]
        for f in req:
            if f not in self.data:
                self.findings.add("CRITICAL", "ENV", "ENV_REQ", f"Missing top-level envelope property: {f}")
        total = self.data.get("total_persons")
        actual = len(self.persons)
        if total != actual:
            self.findings.add("CRITICAL", "ENV", "COUNT_MISMATCH", f"total_persons={total} does not match count={actual}")

    def audit_deduplication(self) -> None:
        """Audits identifier uniqueness and name/birth year fingerprint collisions."""
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

            canon_birth_year = (cname.get("birth_year") or {}).get("year")
            vital_birth_date = ((vitals.get("birth") or {}).get("date") or {})
            if isinstance(vital_birth_date, dict):
                vital_birth_start = vital_birth_date.get("date_start") or vital_birth_date.get("date")
            else:
                vital_birth_start = str(vital_birth_date)
            parsed_birth_year = self._parse_year(vital_birth_start)

            if canon_birth_year is not None and parsed_birth_year is not None:
                if canon_birth_year != parsed_birth_year:
                    self.findings.add(
                        "CRITICAL",
                        pid,
                        "VITAL_SYNC_BIRTH_YEAR",
                        f"Canonical birth_year ({canon_birth_year}) does not match vitals.birth ({vital_birth_start})"
                    )

            canon_death_year = (cname.get("death_year") or {}).get("year")
            vital_death_date = ((vitals.get("death") or {}).get("date") or {})
            if isinstance(vital_death_date, dict):
                vital_death_start = vital_death_date.get("date_start") or vital_death_date.get("date")
            else:
                vital_death_start = str(vital_death_date)
            parsed_death_year = self._parse_year(vital_death_start)

            if canon_death_year is not None and parsed_death_year is not None:
                if canon_death_year != parsed_death_year:
                    self.findings.add(
                        "CRITICAL",
                        pid,
                        "VITAL_SYNC_DEATH_YEAR",
                        f"Canonical death_year ({canon_death_year}) does not match vitals.death ({vital_death_start})"
                    )

    def audit_biological_chronology(self) -> None:
        """Audits biological timeline plausibility and parent-child generational gaps."""
        for p in self.persons:
            pid = p.get("person_id", "UNKNOWN")
            vitals = p.get("vitals") or {}
            birth_dt = ((vitals.get("birth") or {}).get("date") or {})
            death_dt = ((vitals.get("death") or {}).get("date") or {})

            b_year = self._parse_year(birth_dt)
            d_year = self._parse_year(death_dt)

            if b_year and d_year and d_year < b_year:
                self.findings.add("CRITICAL", pid, "CHRONO_DEATH_BEFORE_BIRTH", f"Death year ({d_year}) precedes birth year ({b_year})")

            if b_year and d_year and (d_year - b_year) > 115:
                has_longevity_note = any("longevity" in (n.get("text", "").lower() + n.get("title", "").lower()) for n in p.get("notes", []))
                if not has_longevity_note:
                    self.findings.add("WARNING", pid, "CHRONO_IMPLAUSIBLE_LIFESPAN", f"Lifespan of {d_year - b_year} years exceeds standard biological threshold")

            for assoc in p.get("associated_people", []):
                role = assoc.get("role")
                parent_id = assoc.get("person_id")
                if role in ("FATH", "MOTH", "PARENT") and parent_id and parent_id in self.person_map:
                    parent_p = self.person_map[parent_id]
                    p_birth_dt = (((parent_p.get("vitals") or {}).get("birth") or {}).get("date") or {})
                    p_death_dt = (((parent_p.get("vitals") or {}).get("death") or {}).get("date") or {})
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

        visited: Set[str] = set()
        components: List[Set[str]] = []
        for pid in adj:
            if pid not in visited:
                comp: Set[str] = set()
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
        """Audits reciprocal kinship pointers against KinshipEngine mappings."""
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

                expected = KinshipEngine.get_reciprocal_role(role, subject_sex=p.get("sex"))
                if expected is None:
                    continue

                audit_result = KinshipEngine.audit_kinship_symmetry(p, target_p)
                if not audit_result.is_symmetric:
                    self.findings.add(
                        "WARNING",
                        pid,
                        "ASYM_ASSOC",
                        f"Missing or mismatched reciprocal linkage on {aid} for {role} -> {expected}",
                    )

    def audit_unions(self) -> None:
        """Audits union status validity, reciprocal presence, and marriage date synchronization."""
        valid_union_statuses = GDAReferenceManager.get_union_statuses()
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

                if status not in valid_union_statuses:
                    self.findings.add("CRITICAL", pid, "UNION_INVALID_STATUS", f"Invalid union status: {status}")

                if sid not in spou_assoc_ids:
                    self.findings.add("WARNING", pid, "UNION_ASSOC_DESYNC", f"Spouse {sid} in unions not found in associated_people (role: SPOU)")

                target_p = self.person_map[sid]
                target_unions = target_p.get("unions", [])
                reciprocal_union = next((tu for tu in target_unions if tu.get("spouse_id") == pid), None)

                if not reciprocal_union:
                    self.findings.add("WARNING", pid, "UNION_ASYM_RECIPROCAL", f"Spouse {sid} does not have reciprocal union entry pointing to {pid}")
                    continue

                m_date_a = (u.get("marriage_date") or {}).get("date_start") if isinstance(u.get("marriage_date"), dict) else u.get("marriage_date")
                m_date_b = (reciprocal_union.get("marriage_date") or {}).get("date_start") if isinstance(reciprocal_union.get("marriage_date"), dict) else reciprocal_union.get("marriage_date")
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
        """Executes full diagnostic suite across all audit disciplines."""
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
    """CLI execution entrypoint for GPA."""
    parser = argparse.ArgumentParser(description="Genealogy People Auditor (GPA)")
    parser.add_argument("--file", "-f", type=Path, default=None, help="Custom people.json file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose log emission")
    args = parser.parse_args()

    logger = setup_logger("gpa", ephemeral=True, console_level=logging.DEBUG if args.verbose else logging.INFO)
    logger.info("GPA version %s initializing", __version__)

    target_path = args.file or CONFIG.people

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