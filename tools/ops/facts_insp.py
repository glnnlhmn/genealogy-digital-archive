# Name: facts_insp.py
# Path: tools/ops/facts_insp.py

"""Fact Registry Inspection Engine.

Audits facts.json against schema specifications, controlled vocabularies,
biological chronology plausibility, deduplication criteria, and relational
consistency against people.json unions.
"""

import argparse
import csv
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

__version__ = "1.0.2+build.20260925.2"

UUID_REGEX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
DATE_ISO_REGEX = re.compile(
    r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$"
)

POST_MORTEM_EXEMPT_FACT_TYPES: Set[str] = {
    "Parentage",
    "Death",
    "Burial",
    "Probate",
    "Association",
}

DEFAULT_FACT_TYPES: Set[str] = {
    "Birth",
    "Death",
    "Burial",
    "Marriage",
    "Divorce",
    "Parentage",
    "Residence",
    "Census",
    "Occupation",
    "Probate",
    "Association",
    "Immigration",
    "Military",
    "Education",
    "Other",
}

DEFAULT_DATE_MODIFIERS: Set[str] = {
    "EXACT",
    "ABT",
    "BEF",
    "AFT",
    "BET",
    "EST",
    "CAL",
    "LIVING",
    "UNKNOWN",
}


def load_vocabularies(config: GDAConfig) -> Tuple[Set[str], Set[str]]:
    """Loads controlled vocabularies from schemas/defs/_enums.schema.json."""
    enums_path = (
        getattr(config, "schemas_dir", ROOT_DIR / "schemas")
        / "defs"
        / "_enums.schema.json"
    )
    if not enums_path.is_file():
        enums_path = ROOT_DIR / "schemas" / "defs" / "_enums.schema.json"

    fact_types = set(DEFAULT_FACT_TYPES)
    date_modifiers = set(DEFAULT_DATE_MODIFIERS)

    if enums_path.is_file():
        try:
            schema_data = GDAUtil.load_json(enums_path)
            defs = schema_data.get("$defs", {})
            if "enum_fact_type" in defs and "enum" in defs["enum_fact_type"]:
                fact_types = set(defs["enum_fact_type"]["enum"])
            if "enum_date_modifier" in defs and "enum" in defs["enum_date_modifier"]:
                date_modifiers = set(defs["enum_date_modifier"]["enum"])
        except Exception:
            pass

    return fact_types, date_modifiers


class FactInspector:
    """Core auditing engine for facts.json validation and plausibility."""

    def __init__(
        self,
        facts_payload: Dict[str, Any],
        people_payload: Dict[str, Any],
        logger: logging.Logger,
        valid_fact_types: Optional[Set[str]] = None,
        valid_date_modifiers: Optional[Set[str]] = None,
    ) -> None:
        self.facts_data = facts_payload
        self.people_data = people_payload
        self.logger = logger
        self.valid_fact_types = valid_fact_types or DEFAULT_FACT_TYPES
        self.valid_date_modifiers = valid_date_modifiers or DEFAULT_DATE_MODIFIERS

        self.facts: List[Dict[str, Any]] = self.facts_data.get("facts", [])
        self.persons: List[Dict[str, Any]] = self.people_data.get("persons", [])
        self.person_map: Dict[str, Dict[str, Any]] = {
            p["person_id"]: p for p in self.persons if "person_id" in p
        }

        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.info: List[Dict[str, Any]] = []
        self.merge_proposals: List[Dict[str, Any]] = []

    def _format_fct_label(self, fact: Dict[str, Any]) -> str:
        fid = str(fact.get("fact_id", "UNKNOWN"))
        short_id = fid[:8] if len(fid) >= 8 else fid
        pid = str(fact.get("person_id", "UNKNOWN"))
        person = self.person_map.get(pid, {})
        name = person.get("display_name")
        if not name:
            cname = person.get("canonical_name", {})
            given = cname.get("given", "")
            surname = cname.get("surname", "")
            name = f"{given} {surname}".strip() or "Unknown Name"
        return f"FCT {short_id} ({pid} ({name}))"

    def _resolve_year(self, date_dict: Optional[Dict[str, Any]]) -> Optional[int]:
        if not isinstance(date_dict, dict):
            return None
        ds = date_dict.get("date_start")
        if ds and isinstance(ds, str) and len(ds) >= 4 and ds[:4].isdigit():
            return int(ds[:4])
        return None

    def _resolve_person_lifespan(
        self, person: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[int]]:
        birth_yr = None
        v_birth = person.get("vitals", {}).get("birth", {}).get("date")
        birth_yr = self._resolve_year(v_birth)
        if birth_yr is None:
            c_birth = person.get("canonical_name", {}).get("birth_year", {})
            if isinstance(c_birth, dict):
                birth_yr = c_birth.get("year")

        death_yr = None
        v_death = person.get("vitals", {}).get("death", {}).get("date")
        death_yr = self._resolve_year(v_death)
        if death_yr is None:
            c_death = person.get("canonical_name", {}).get("death_year", {})
            if isinstance(c_death, dict):
                death_yr = c_death.get("year")

        return birth_yr, death_yr

    def audit_schema_conformance(self) -> None:
        """Audits envelope, UUID formatting, and required fact fields."""
        req_env = ["$schema", "schema_version", "created_at", "last_modified", "facts"]
        for key in req_env:
            if key not in self.facts_data:
                self.warnings.append({
                    "rule": "ENV_PROPERTY_MISSING",
                    "message": f"Envelope missing key: {key}",
                })

        for fact in self.facts:
            label = self._format_fct_label(fact)
            fid = fact.get("fact_id")
            if not fid:
                self.errors.append({
                    "rule": "FACT_ID_MISSING",
                    "label": label,
                    "message": "Fact record is missing fact_id",
                })
            elif not UUID_REGEX.match(str(fid)):
                self.warnings.append({
                    "rule": "UUID_PATTERN_INVALID",
                    "label": label,
                    "message": f"Fact ID '{fid}' does not adhere to standard UUID v4 regex",
                })

            pid = fact.get("person_id")
            if not pid:
                self.errors.append({
                    "rule": "PERSON_ID_MISSING",
                    "label": label,
                    "message": "Fact record is missing person_id",
                })
            elif pid not in self.person_map:
                self.errors.append({
                    "rule": "ORPHANED_PERSON_ID",
                    "label": label,
                    "message": f"Target person_id '{pid}' does not exist in people.json",
                })

    def audit_controlled_vocabularies(self) -> None:
        """Audits fact_type and date modifiers against controlled schemas."""
        for fact in self.facts:
            label = self._format_fct_label(fact)
            ftype = fact.get("fact_type")
            if not ftype:
                self.errors.append({
                    "rule": "FACT_TYPE_MISSING",
                    "label": label,
                    "message": "Fact record missing fact_type",
                })
            elif ftype not in self.valid_fact_types:
                self.errors.append({
                    "rule": "FACT_TYPE_INVALID",
                    "label": label,
                    "message": f"Fact type '{ftype}' not defined in controlled schema",
                })

            date_obj = fact.get("date")
            if isinstance(date_obj, dict):
                d_start = date_obj.get("date_start")
                if d_start and not DATE_ISO_REGEX.match(str(d_start)):
                    self.errors.append({
                        "rule": "DATE_START_FORMAT_INVALID",
                        "label": label,
                        "message": f"date_start '{d_start}' does not match ISO 8601 pattern",
                    })

                mod = date_obj.get("modifier")
                if mod and mod not in self.valid_date_modifiers:
                    self.errors.append({
                        "rule": "DATE_MODIFIER_INVALID",
                        "label": label,
                        "message": f"date modifier '{mod}' not defined in controlled schema",
                    })

    def audit_biological_plausibility(self) -> None:
        """Validates chronology against lifespan, exempting post-mortem types."""
        for fact in self.facts:
            label = self._format_fct_label(fact)
            pid = fact.get("person_id")
            if not pid or pid not in self.person_map:
                continue

            person = self.person_map[pid]
            birth_yr, death_yr = self._resolve_person_lifespan(person)
            fact_yr = self._resolve_year(fact.get("date"))

            if fact_yr is None:
                continue

            ftype = fact.get("fact_type", "")

            if birth_yr is not None and fact_yr < birth_yr:
                if ftype != "Birth":
                    self.errors.append({
                        "rule": "ANACHRONISTIC_PRE_BIRTH",
                        "label": label,
                        "message": f"Fact year ({fact_yr}) predates individual birth year ({birth_yr})",
                    })

            if death_yr is not None and fact_yr > death_yr:
                if ftype in POST_MORTEM_EXEMPT_FACT_TYPES:
                    self.info.append({
                        "rule": "POST_MORTEM_EXEMPTION_APPLIED",
                        "label": label,
                        "message": f"Post-mortem assertion ({ftype} in {fact_yr}) permitted after death ({death_yr})",
                    })
                else:
                    self.errors.append({
                        "rule": "ANACHRONISTIC_POST_DEATH",
                        "label": label,
                        "message": f"Event fact '{ftype}' in {fact_yr} occurs after death year ({death_yr})",
                    })

    def audit_unions_cross_validation(self) -> None:
        """Cross-validates Marriage and Divorce facts against person unions."""
        for fact in self.facts:
            ftype = fact.get("fact_type")
            if ftype not in ("Marriage", "Divorce"):
                continue

            label = self._format_fct_label(fact)
            pid = fact.get("person_id")
            if not pid or pid not in self.person_map:
                continue

            person = self.person_map[pid]
            unions = person.get("unions", [])

            spouse_ids: Set[str] = set()
            for assoc in fact.get("associated_people", []):
                if isinstance(assoc, dict) and assoc.get("person_id"):
                    spouse_ids.add(assoc["person_id"])

            if not spouse_ids:
                continue

            for sid in spouse_ids:
                matched_union = next(
                    (u for u in unions if u.get("spouse_id") == sid), None
                )
                if not matched_union:
                    self.warnings.append({
                        "rule": "UNION_FACT_NOT_IN_PERSON",
                        "label": label,
                        "message": f"Fact {ftype} with {sid} has no corresponding union record in people.json",
                    })
                    continue

                if ftype == "Divorce" and matched_union.get("status") != "DIVORCED":
                    self.warnings.append({
                        "rule": "UNION_STATUS_DIVORCE_MISMATCH",
                        "label": label,
                        "message": f"Person union status is '{matched_union.get('status')}', expected 'DIVORCED'",
                    })

                f_date = (fact.get("date") or {}).get("date_start")
                u_mdate = (matched_union.get("marriage_date") or {}).get("date_start")
                if ftype == "Marriage" and f_date and u_mdate and f_date != u_mdate:
                    self.warnings.append({
                        "rule": "UNION_MARRIAGE_DATE_MISMATCH",
                        "label": label,
                        "message": f"Marriage fact date '{f_date}' differs from union date '{u_mdate}'",
                    })

    def audit_deduplication(self) -> None:
        """Identifies duplicate source citations and redundant event assertions."""
        seen_events: Dict[Tuple[str, str, Optional[str]], str] = {}

        for fact in self.facts:
            fid = str(fact.get("fact_id", ""))
            pid = str(fact.get("person_id", ""))
            ftype = str(fact.get("fact_type", ""))
            d_start = (fact.get("date") or {}).get("date_start")

            key = (pid, ftype, d_start)
            if key in seen_events:
                prior_fid = seen_events[key]
                self.warnings.append({
                    "rule": "DEDUP_EVENT_COLLISION",
                    "label": self._format_fct_label(fact),
                    "message": f"Redundant event signature matches earlier fact {prior_fid[:8]}",
                })
                self.merge_proposals.append({
                    "primary_fact_id": prior_fid,
                    "duplicate_fact_id": fid,
                    "person_id": pid,
                    "fact_type": ftype,
                    "date": d_start,
                })
            else:
                seen_events[key] = fid

    def run_all(self) -> Dict[str, Any]:
        self.audit_schema_conformance()
        self.audit_controlled_vocabularies()
        self.audit_biological_plausibility()
        self.audit_unions_cross_validation()
        self.audit_deduplication()

        return {
            "timestamp": datetime.now().isoformat(),
            "facts_total": len(self.facts),
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "info_count": len(self.info),
            "merge_proposals_count": len(self.merge_proposals),
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "merge_proposals": self.merge_proposals,
        }


def run_cli() -> int:
    parser = argparse.ArgumentParser(description="Fact Registry Inspection Engine (FactsInsp)")
    parser.add_argument("--facts", "-f", type=Path, default=None, help="Custom facts.json path")
    parser.add_argument("--people", "-p", type=Path, default=None, help="Custom people.json path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Emit verbose logging traces")
    parser.add_argument("--export-csv", action="store_true", help="Force export merge proposals to CSV")
    args = parser.parse_args()

    logger = setup_logger("facts_insp", ephemeral=True, console_level=logging.DEBUG if args.verbose else logging.INFO)
    logger.info("FactsInsp version %s initializing", __version__)

    config = GDAConfig(ROOT_DIR)
    facts_path = args.facts or getattr(config, "entities_dir", ROOT_DIR / "data" / "entities") / "facts.json"
    people_path = args.people or getattr(config, "entities_dir", ROOT_DIR / "data" / "entities") / "people.json"

    if not facts_path.is_file():
        logger.error("Facts registry file missing: %s", facts_path)
        return 1
    if not people_path.is_file():
        logger.error("People registry file missing: %s", people_path)
        return 1

    facts_payload = GDAUtil.load_json(facts_path)
    people_payload = GDAUtil.load_json(people_path)

    fact_types, date_modifiers = load_vocabularies(config)

    inspector = FactInspector(
        facts_payload,
        people_payload,
        logger,
        valid_fact_types=fact_types,
        valid_date_modifiers=date_modifiers,
    )
    results = inspector.run_all()

    logger.info("==========================================")
    logger.info("FACTS INSPECTION AUDIT REPORT")
    logger.info("==========================================")
    logger.info("Total Facts Audited:      %d", results["facts_total"])
    logger.info("Errors Encountered:       %d", results["errors_count"])
    logger.info("Warnings Flagged:         %d", results["warnings_count"])
    logger.info("Informational Notes:      %d", results["info_count"])
    logger.info("Merge Proposals Pending:  %d", results["merge_proposals_count"])
    logger.info("==========================================")

    for err in results["errors"][:15]:
        logger.error("[%s] %s: %s", err.get("rule"), err.get("label", ""), err.get("message"))
    for warn in results["warnings"][:15]:
        logger.warning("[%s] %s: %s", warn.get("rule"), warn.get("label", ""), warn.get("message"))

    reports_dir = getattr(config, "reports_dir", ROOT_DIR / "reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / f"facts_insp_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    GDAUtil.save_json(report_file, results)
    logger.info("Audit report emitted to: %s", report_file.name)

    if (results["merge_proposals"] or args.export_csv) and results["merge_proposals_count"] > 0:
        csv_file = reports_dir / f"merge_proposals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(csv_file, "w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=["primary_fact_id", "duplicate_fact_id", "person_id", "fact_type", "date"],
            )
            writer.writeheader()
            writer.writerows(results["merge_proposals"])
        logger.info("Merge proposals CSV emitted: %s", csv_file.name)

    return 0 if results["errors_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(run_cli())