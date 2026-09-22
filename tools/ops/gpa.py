# Name: gpa.py
# Path: tools/ops/gpa.py

"""GPA: Genealogy People Auditor Operational CLI Tool.

Audits envelope container properties, entity schema conformance, bidirectional
kinship reciprocity, biological chronology limits, vital-date synchronization,
and catalogs incomplete or missing dates. Emits diagnostic session logs to logs/
and writes structured reports and remediation ledgers to reports/.

Supports full headless execution via CLI flags as well as an interactive
console menu when invoked without operational arguments.
"""

import argparse
import csv
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path for standalone invocation
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.lib.gda_core.registry import SchemaEnums

__version__ = "1.0.1+build.20260922.2"

DATE_ISO_PATTERN = re.compile(r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$")
PERSON_ID_PATTERN = re.compile(r"^IND-\d{5}$")


class TieredFindings:
    """Aggregates and categorizes validation issues by severity level."""

    def __init__(self):
        """Initializes empty finding buckets for errors, warnings, and notes."""
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.notes: List[str] = []

    def add_error(self, entity_id: str, message: str) -> None:
        """Records a critical integrity or schema violation."""
        self.errors.append(f"[{entity_id}] {message}")

    def add_warning(self, entity_id: str, message: str) -> None:
        """Records a data gap, modifier discordance, or potential issue."""
        self.warnings.append(f"[{entity_id}] {message}")

    def add_note(self, entity_id: str, message: str) -> None:
        """Records an observational note or incomplete date pattern."""
        self.notes.append(f"[{entity_id}] {message}")

    def extend(self, other: "TieredFindings") -> None:
        """Merges all finding tiers from another TieredFindings instance."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.notes.extend(other.notes)

    @property
    def total_count(self) -> int:
        """Returns the aggregate count of all tracked findings."""
        return len(self.errors) + len(self.warnings) + len(self.notes)


class RegistryAuditor:
    """Auditor engine validating structural and evidentiary integrity in people.json."""

    def __init__(
        self,
        people_path: Optional[Path] = None,
        reports_dir: Optional[Path] = None,
        debug: bool = False,
        verbose: bool = False,
        logger: Optional[logging.Logger] = None,
    ):
        """Initializes auditor configuration, logger, and loads entities.

        Args:
            people_path (Optional[Path]): Explicit path to people.json.
            reports_dir (Optional[Path]): Target reports output directory.
            debug (bool): Flag indicating debug trace mode.
            verbose (bool): Flag indicating verbose diagnostic logging.
            logger (Optional[logging.Logger]): Dedicated operational logger.
        """
        self.people_path = people_path or CONFIG.people
        self.reports_dir = reports_dir or CONFIG.reports
        self.debug = debug
        self.verbose = verbose

        c_level = logging.DEBUG if debug else logging.INFO
        self.logger = logger or setup_logger("gpa", console_level=c_level, file_level=logging.DEBUG)

        self.people_data: Dict[str, Any] = {}
        self.persons: List[Dict[str, Any]] = []
        self.person_map: Dict[str, Dict[str, Any]] = {}
        self.remediation_rows: List[Dict[str, Any]] = []
        self.load_data()

    def load_data(self) -> None:
        """Loads and indexes entities from people.json into memory."""
        if not self.people_path.exists():
            err = f"Target people registry not found at: {self.people_path}"
            self.logger.error(err)
            print(f"Error: {err}")
            sys.exit(1)

        self.logger.debug(f"Reading registry data from {self.people_path}")
        self.people_data = GDAUtil.load_json(self.people_path)
        self.persons = self.people_data.get("persons", [])
        self.person_map = {
            p.get("person_id"): p for p in self.persons if p.get("person_id")
        }
        self.logger.info(f"Loaded {len(self.persons)} total individuals into memory.", extra={"sys_event": True})

    def audit_container(self) -> TieredFindings:
        """Validates top-level envelope properties, schema version, and entity counts."""
        findings = TieredFindings()
        self.logger.debug("Initiating Container Schema & Header Audit.")

        schema_val = self.people_data.get("$schema", "")
        if "person_registry.schema.json" not in schema_val:
            findings.add_error("CONTAINER", f"Invalid container $schema reference: '{schema_val}'")

        ver = self.people_data.get("schema_version")
        if ver != "1.0.1":
            findings.add_error("CONTAINER", f"Invalid schema_version: '{ver}' (expected '1.0.1')")

        total_persons = self.people_data.get("total_persons")
        actual_count = len(self.persons)
        if total_persons is None:
            findings.add_warning("CONTAINER", "Missing 'total_persons' field in container root.")
        elif total_persons != actual_count:
            findings.add_error(
                "CONTAINER",
                f"Count mismatch: total_persons property ({total_persons}) does not match array length ({actual_count}).",
            )

        return findings

    def audit_schema(self) -> TieredFindings:
        """Audits individual person records against schema constraints and field requirements."""
        findings = TieredFindings()
        self.logger.debug("Initiating Entity Schema Requirements Audit.")
        seen_ids = set()

        for idx, p in enumerate(self.persons):
            pid = p.get("person_id")
            entity_tag = pid if pid else f"INDEX_{idx}"

            if not pid or not PERSON_ID_PATTERN.match(pid):
                findings.add_error(entity_tag, f"Invalid or missing person_id format: '{pid}'")
            elif pid in seen_ids:
                findings.add_error(pid, "Duplicate person_id found in registry.")
            else:
                seen_ids.add(pid)

            if not p.get("display_name") or not isinstance(p["display_name"], str):
                findings.add_error(entity_tag, "Missing or invalid required string 'display_name'.")

            cname = p.get("canonical_name")
            if not isinstance(cname, dict):
                findings.add_error(entity_tag, "Missing or invalid required object 'canonical_name'.")
            else:
                has_raw = bool(cname.get("raw_name"))
                has_given_surname = bool(cname.get("given") and cname.get("surname"))
                if not (has_raw or has_given_surname):
                    findings.add_error(
                        entity_tag,
                        "canonical_name requires either 'raw_name' or both 'given' and 'surname'.",
                    )

            sex_val = p.get("sex")
            if not SchemaEnums.is_valid("enum_sex", sex_val):
                findings.add_error(entity_tag, f"Invalid 'sex' enum value: '{sex_val}'")

            vitals = p.get("vitals", {})
            if isinstance(vitals, dict):
                for vtype in ["birth", "death"]:
                    vobj = vitals.get(vtype, {})
                    if isinstance(vobj, dict):
                        dobj = vobj.get("date", {})
                        if isinstance(dobj, dict):
                            mod = dobj.get("modifier")
                            if mod and not SchemaEnums.is_valid("enum_date_modifier", mod):
                                findings.add_error(entity_tag, f"vitals.{vtype}.date has invalid modifier enum: '{mod}'")

                            dstart = dobj.get("date_start")
                            if dstart is not None and not DATE_ISO_PATTERN.match(str(dstart)):
                                findings.add_error(
                                    entity_tag,
                                    f"vitals.{vtype}.date.date_start fails ISO pattern: '{dstart}'",
                                )
                            dend = dobj.get("date_end")
                            if dend is not None and not DATE_ISO_PATTERN.match(str(dend)):
                                findings.add_error(
                                    entity_tag,
                                    f"vitals.{vtype}.date.date_end fails ISO pattern: '{dend}'",
                                )

            assoc = p.get("associated_people", [])
            if isinstance(assoc, list):
                for a_idx, a in enumerate(assoc):
                    role = a.get("role")
                    if role and not SchemaEnums.is_valid("enum_associated_role", role):
                        findings.add_error(
                            entity_tag,
                            f"associated_people[{a_idx}] has invalid role enum: '{role}'",
                        )
                    if not a.get("person_id") and not a.get("name"):
                        findings.add_error(
                            entity_tag,
                            f"associated_people[{a_idx}] requires either 'person_id' or 'name'.",
                        )
            else:
                findings.add_error(entity_tag, "'associated_people' must be an array.")

        return findings

    def audit_reciprocity(self) -> TieredFindings:
        """Verifies bidirectional kinship links across associated individuals."""
        findings = TieredFindings()
        self.logger.debug("Initiating Reciprocal Kinship Relationship Audit.")

        for pid, p in self.person_map.items():
            assoc = p.get("associated_people", [])
            for a in assoc:
                target_id = a.get("person_id")
                role = a.get("role")

                if not target_id:
                    continue

                if target_id not in self.person_map:
                    findings.add_error(
                        pid,
                        f"References non-existent person_id '{target_id}' with role '{role}'.",
                    )
                    continue

                target_p = self.person_map[target_id]
                target_assoc = target_p.get("associated_people", [])

                if role in ("FATH", "MOTH"):
                    recip = any(
                        ta.get("person_id") == pid and ta.get("role") == "CHIL"
                        for ta in target_assoc
                    )
                    if not recip:
                        findings.add_error(
                            f"{pid} -> {target_id}",
                            f"Links parent ({role}), but {target_id} does not link back as CHIL.",
                        )

                elif role == "CHIL":
                    p_sex = p.get("sex")
                    if p_sex == "Male":
                        expected_roles = ("FATH",)
                    elif p_sex == "Female":
                        expected_roles = ("MOTH",)
                    else:
                        expected_roles = ("FATH", "MOTH")

                    recip = any(
                        ta.get("person_id") == pid and ta.get("role") in expected_roles
                        for ta in target_assoc
                    )
                    if not recip:
                        findings.add_error(
                            f"{pid} -> {target_id}",
                            f"Links child, but {target_id} does not link back as {'/'.join(expected_roles)}.",
                        )

                elif role in ("SPOU", "HUSB", "WIFE"):
                    recip = any(
                        ta.get("person_id") == pid and ta.get("role") in ("SPOU", "HUSB", "WIFE")
                        for ta in target_assoc
                    )
                    if not recip:
                        findings.add_warning(
                            f"{pid} <-> {target_id}",
                            f"Links spouse ({role}), but {target_id} does not reciprocate spouse relationship.",
                        )

        return findings

    def _extract_birth_year(self, p: dict) -> Optional[int]:
        """Extracts an integer birth year from canonical_name or vitals fallback."""
        cname = p.get("canonical_name", {})
        byear_obj = cname.get("birth_year", {})
        if isinstance(byear_obj, dict) and byear_obj.get("year"):
            return byear_obj.get("year")

        vitals = p.get("vitals", {})
        if isinstance(vitals, dict):
            bdate = vitals.get("birth", {}).get("date", {})
            if isinstance(bdate, dict):
                dstart = bdate.get("date_start")
                if dstart:
                    match = re.match(r"^(\d{4})", str(dstart))
                    if match:
                        return int(match.group(1))
        return None

    def audit_chronology(self) -> TieredFindings:
        """Validates biological age limits between parents and children at birth."""
        findings = TieredFindings()
        self.logger.debug("Initiating Child/Parent Chronological Validation.")

        for pid, p in self.person_map.items():
            child_year = self._extract_birth_year(p)
            assoc = p.get("associated_people", [])

            for a in assoc:
                role = a.get("role")
                parent_id = a.get("person_id")

                if role in ("FATH", "MOTH") and parent_id in self.person_map:
                    parent_p = self.person_map[parent_id]
                    parent_year = self._extract_birth_year(parent_p)

                    if child_year is None and parent_year is None:
                        findings.add_note(
                            f"{pid} & {parent_id}",
                            "Both child and parent have unrecorded birth dates; chronological check skipped.",
                        )
                        continue

                    if child_year is None:
                        findings.add_warning(
                            pid,
                            f"Child missing birth date; cannot chronologically verify against parent {parent_id} (b. {parent_year}).",
                        )
                        continue

                    if parent_year is None:
                        findings.add_warning(
                            parent_id,
                            f"Parent missing birth date; cannot chronologically verify against child {pid} (b. {child_year}).",
                        )
                        continue

                    diff = child_year - parent_year
                    if diff < 12:
                        findings.add_error(
                            f"{pid} vs {parent_id}",
                            f"Biological impossibility: Parent ({parent_id}, b. {parent_year}) was {diff} years old at child's birth ({pid}, b. {child_year}). Minimum threshold: 12.",
                        )
                    elif diff > 85:
                        findings.add_error(
                            f"{pid} vs {parent_id}",
                            f"Biological impossibility: Parent ({parent_id}, b. {parent_year}) was {diff} years old at child's birth ({pid}, b. {child_year}). Maximum threshold: 85.",
                        )

        return findings

    def _determine_presumed_truth(
        self, c_val: Any, c_mod: Any, v_val: Any, v_mod: Any
    ) -> Tuple[str, str, str, str]:
        """Applies evidentiary arbitration rules returning proposed fixes for discordant dates."""
        if v_val and not c_val:
            val = str(v_val)[:4] if len(str(v_val)) >= 4 else str(v_val)
            return (
                f"Presume vitals is correct ({v_val}); canonical_name should be updated.",
                "UPDATE_CANONICAL_YEAR",
                val,
                "Vitals populated while canonical year is null",
            )
        if c_val and not v_val:
            return (
                f"Presume canonical is correct ({c_val}); vitals.date_start should be populated.",
                "UPDATE_VITALS_DATE",
                str(c_val),
                "Canonical populated while vitals date_start is null",
            )
        if v_val and c_val:
            v_val_str = str(v_val)
            c_val_str = str(c_val)
            if v_val_str[:4] != c_val_str[:4]:
                if len(v_val_str) > 4:
                    return (
                        f"Presume vitals is correct ({v_val}) due to higher date precision; update canonical_name to {v_val_str[:4]}.",
                        "UPDATE_CANONICAL_YEAR",
                        v_val_str[:4],
                        "Higher precision date in vitals overrides divergent canonical year",
                    )
                return (
                    f"Evidentiary conflict ({c_val} vs {v_val}); requires manual record disambiguation.",
                    "MANUAL_REVIEW",
                    "",
                    "Divergent 4-digit years without day-level precision",
                )
            if c_mod != v_mod:
                if v_mod == "EXACT" and len(v_val_str) >= 7:
                    return (
                        f"Presume vitals is correct ({v_val} EXACT); promote canonical_name modifier to EXACT.",
                        "UPDATE_CANONICAL_MODIFIER",
                        "EXACT",
                        "High-precision vitals date proves exact year",
                    )
                if c_mod == "UNKNOWN" and v_mod == "ABT":
                    return (
                        f"Presume vitals is correct ({v_val} ABT); change canonical_name modifier from UNKNOWN to ABT.",
                        "UPDATE_CANONICAL_MODIFIER",
                        "ABT",
                        "Estimated vitals date replaces invalid UNKNOWN year modifier",
                    )
                if len(v_val_str) == 4 and v_mod == "EXACT" and c_mod == "ABT":
                    return (
                        f"Presume vitals modifier '{v_mod}' is authoritative over canonical '{c_mod}'.",
                        "UPDATE_CANONICAL_MODIFIER",
                        "EXACT",
                        "Vitals EXACT qualifier authoritative over canonical ABT",
                    )
                return (
                    f"Presume vitals modifier '{v_mod}' is authoritative over canonical '{c_mod}'.",
                    "UPDATE_CANONICAL_MODIFIER",
                    str(v_mod),
                    "Vitals modifier authoritative for consistency",
                )
        return ("Requires primary document review.", "MANUAL_REVIEW", "", "Unclassified edge case")

    def audit_vital_synchronization(self) -> TieredFindings:
        """Audits consistency between canonical summary years and vitals date structures."""
        findings = TieredFindings()
        self.remediation_rows = []
        self.logger.debug("Initiating Canonical vs. Vitals Cross-Synchronization Audit.")

        for p in self.persons:
            pid = p.get("person_id", "UNKNOWN_ID")
            cname = p.get("canonical_name", {})
            vitals = p.get("vitals", {})

            # 1. Birth Evaluation
            byear_obj = cname.get("birth_year", {})
            c_byear = byear_obj.get("year")
            c_bmod = byear_obj.get("modifier")

            bdate_obj = vitals.get("birth", {}).get("date", {})
            v_bstart = bdate_obj.get("date_start")
            v_bmod = bdate_obj.get("modifier")

            v_byear = None
            if v_bstart:
                match = re.match(r"^(\d{4})", str(v_bstart))
                if match:
                    v_byear = int(match.group(1))

            if c_byear is not None and v_byear is not None and c_byear != v_byear:
                narrative, action, pval, reason = self._determine_presumed_truth(c_byear, c_bmod, v_bstart, v_bmod)
                findings.add_error(
                    pid,
                    f"Birth year conflict: canonical_name={c_byear} ({c_bmod}) vs vitals.birth={v_bstart} ({v_bmod}). -> Resolution: {narrative}",
                )
                self.remediation_rows.append({
                    "person_id": pid,
                    "event_type": "birth",
                    "target_path": "canonical_name.birth_year.year",
                    "current_canonical": f"{c_byear} ({c_bmod})",
                    "current_vitals": f"{v_bstart} ({v_bmod})",
                    "proposed_action": action,
                    "proposed_value": pval,
                    "rule_reason": reason,
                    "status": "PENDING",
                })
            elif (c_byear is None) ^ (v_byear is None):
                narrative, action, pval, reason = self._determine_presumed_truth(c_byear, c_bmod, v_bstart, v_bmod)
                findings.add_error(
                    pid,
                    f"Birth presence mismatch: canonical_name={c_byear} ({c_bmod}) vs vitals.birth={v_bstart} ({v_bmod}). -> Resolution: {narrative}",
                )
                self.remediation_rows.append({
                    "person_id": pid,
                    "event_type": "birth",
                    "target_path": "canonical_name.birth_year.year" if c_byear is None else "vitals.birth.date.date_start",
                    "current_canonical": f"{c_byear} ({c_bmod})",
                    "current_vitals": f"{v_bstart} ({v_bmod})",
                    "proposed_action": action,
                    "proposed_value": pval,
                    "rule_reason": reason,
                    "status": "PENDING",
                })
            elif c_bmod and v_bmod and c_bmod != v_bmod:
                narrative, action, pval, reason = self._determine_presumed_truth(c_byear, c_bmod, v_bstart, v_bmod)
                findings.add_warning(
                    pid,
                    f"Birth modifier discordance: canonical_name={c_byear} ('{c_bmod}') vs vitals.birth={v_bstart} ('{v_bmod}'). -> Resolution: {narrative}",
                )
                self.remediation_rows.append({
                    "person_id": pid,
                    "event_type": "birth",
                    "target_path": "canonical_name.birth_year.modifier",
                    "current_canonical": f"{c_byear} ({c_bmod})",
                    "current_vitals": f"{v_bstart} ({v_bmod})",
                    "proposed_action": action,
                    "proposed_value": pval,
                    "rule_reason": reason,
                    "status": "PENDING",
                })

            # 2. Death Evaluation
            dyear_obj = cname.get("death_year", {})
            c_dyear = dyear_obj.get("year")
            c_dmod = dyear_obj.get("modifier")

            ddate_obj = vitals.get("death", {}).get("date", {})
            v_dstart = ddate_obj.get("date_start")
            v_dmod = ddate_obj.get("modifier")

            v_dyear = None
            if v_dstart:
                match = re.match(r"^(\d{4})", str(v_dstart))
                if match:
                    v_dyear = int(match.group(1))

            if c_dmod == "LIVING" and v_dmod == "UNKNOWN" and v_dstart is None:
                pass
            elif c_dyear is not None and v_dyear is not None and c_dyear != v_dyear:
                narrative, action, pval, reason = self._determine_presumed_truth(c_dyear, c_dmod, v_dstart, v_dmod)
                findings.add_error(
                    pid,
                    f"Death year conflict: canonical_name={c_dyear} ({c_dmod}) vs vitals.death={v_dstart} ({v_dmod}). -> Resolution: {narrative}",
                )
                self.remediation_rows.append({
                    "person_id": pid,
                    "event_type": "death",
                    "target_path": "canonical_name.death_year.year",
                    "current_canonical": f"{c_dyear} ({c_dmod})",
                    "current_vitals": f"{v_dstart} ({v_dmod})",
                    "proposed_action": action,
                    "proposed_value": pval,
                    "rule_reason": reason,
                    "status": "PENDING",
                })
            elif (c_dyear is None) ^ (v_dyear is None):
                narrative, action, pval, reason = self._determine_presumed_truth(c_dyear, c_dmod, v_dstart, v_dmod)
                findings.add_error(
                    pid,
                    f"Death presence mismatch: canonical_name={c_dyear} ({c_dmod}) vs vitals.death={v_dstart} ({v_dmod}). -> Resolution: {narrative}",
                )
                self.remediation_rows.append({
                    "person_id": pid,
                    "event_type": "death",
                    "target_path": "canonical_name.death_year.year" if c_dyear is None else "vitals.death.date.date_start",
                    "current_canonical": f"{c_dyear} ({c_dmod})",
                    "current_vitals": f"{v_dstart} ({v_dmod})",
                    "proposed_action": action,
                    "proposed_value": pval,
                    "rule_reason": reason,
                    "status": "PENDING",
                })
            elif c_dmod and v_dmod and c_dmod != v_dmod:
                narrative, action, pval, reason = self._determine_presumed_truth(c_dyear, c_dmod, v_dstart, v_dmod)
                findings.add_warning(
                    pid,
                    f"Death modifier discordance: canonical_name={c_dyear} ('{c_dmod}') vs vitals.death={v_dstart} ('{v_dmod}'). -> Resolution: {narrative}",
                )
                self.remediation_rows.append({
                    "person_id": pid,
                    "event_type": "death",
                    "target_path": "canonical_name.death_year.modifier",
                    "current_canonical": f"{c_dyear} ({c_dmod})",
                    "current_vitals": f"{v_dstart} ({v_dmod})",
                    "proposed_action": action,
                    "proposed_value": pval,
                    "rule_reason": reason,
                    "status": "PENDING",
                })

        return findings

    def audit_incomplete_dates(self) -> TieredFindings:
        """Identifies missing vital dates and catalogs partial date representations."""
        findings = TieredFindings()
        self.logger.debug("Initiating Incomplete and Missing Vital Dates Audit.")

        for p in self.persons:
            pid = p.get("person_id", "UNKNOWN_ID")
            vitals = p.get("vitals", {})
            cname = p.get("canonical_name", {})

            for vtype in ["birth", "death"]:
                vobj = vitals.get(vtype, {})
                dobj = vobj.get("date", {}) if isinstance(vobj, dict) else {}
                dstart = dobj.get("date_start")
                mod = dobj.get("modifier")
                raw = dobj.get("raw_text")

                c_year_obj = cname.get(f"{vtype}_year", {})
                c_year = c_year_obj.get("year")
                c_mod = c_year_obj.get("modifier")

                if dstart is None:
                    if vtype == "death" and c_mod == "LIVING":
                        continue
                    findings.add_warning(
                        pid,
                        f"Missing vital date: vitals.{vtype}.date.date_start=null (modifier='{mod}', canonical_year={c_year}).",
                    )
                    continue

                dstart_str = str(dstart)
                if re.match(r"^\d{4}$", dstart_str):
                    findings.add_note(
                        pid,
                        f"Partial date [YYYY]: vitals.{vtype}.date.date_start='{dstart_str}' | mod='{mod}' | raw='{raw}' | canonical_year={c_year}.",
                    )
                elif re.match(r"^\d{4}-\d{2}$", dstart_str):
                    findings.add_note(
                        pid,
                        f"Partial date [YYYY-MM]: vitals.{vtype}.date.date_start='{dstart_str}' | mod='{mod}' | raw='{raw}' | canonical_year={c_year}.",
                    )

        return findings

    def run_full_audit(self) -> TieredFindings:
        """Executes all structural, container, kinship, and vital audits sequentially."""
        combined = TieredFindings()
        combined.extend(self.audit_container())
        combined.extend(self.audit_schema())
        combined.extend(self.audit_reciprocity())
        combined.extend(self.audit_chronology())
        combined.extend(self.audit_vital_synchronization())
        combined.extend(self.audit_incomplete_dates())
        return combined

    def write_csv_remediation(self, rows: list, base_ts: str) -> None:
        """Generates a CSV change ledger detailing actionable date discrepancies."""
        if not rows:
            return
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        csv_file = self.reports_dir / f"remediation_vital_sync_{base_ts}.csv"

        fieldnames = [
            "person_id",
            "event_type",
            "target_path",
            "current_canonical",
            "current_vitals",
            "proposed_action",
            "proposed_value",
            "rule_reason",
            "status",
        ]

        self.logger.debug(f"Writing remediation CSV ledger ({len(rows)} rows) to {csv_file}")
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

        print(f"[+] Remediation CSV ledger written to: {csv_file}")

    def write_report(self, check_name: str, findings: TieredFindings) -> None:
        """Writes categorized errors, warnings, and notes to a text report in reports/."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"audit_people_{check_name}_{ts}.txt"

        self.logger.info(f"Writing tiered report ({findings.total_count} total entries) to {report_file}")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"AUDIT REPORT: {check_name.upper()}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Target Database: {self.people_path}\n")
            f.write(f"Total Entities Enumerated: {len(self.persons)}\n")
            f.write(
                f"Summary: {len(findings.errors)} Errors | {len(findings.warnings)} Warnings | {len(findings.notes)} Notes\n"
            )
            f.write("=" * 68 + "\n\n")

            f.write(f"[ERRORS] - Critical Integrity & Schema Violations ({len(findings.errors)})\n")
            f.write("-" * 68 + "\n")
            if not findings.errors:
                f.write("None detected.\n\n")
            else:
                for idx, entry in enumerate(findings.errors, 1):
                    f.write(f"{idx:03d}. {entry}\n")
                f.write("\n")

            f.write(f"[WARNINGS] - Data Gaps, Modifier Discordances & Kinship Inconsistencies ({len(findings.warnings)})\n")
            f.write("-" * 68 + "\n")
            if not findings.warnings:
                f.write("None detected.\n\n")
            else:
                for idx, entry in enumerate(findings.warnings, 1):
                    f.write(f"{idx:03d}. {entry}\n")
                f.write("\n")

            f.write(f"[NOTES] - Incomplete Dates & Chronological Observations ({len(findings.notes)})\n")
            f.write("-" * 68 + "\n")
            if not findings.notes:
                f.write("None detected.\n\n")
            else:
                for idx, entry in enumerate(findings.notes, 1):
                    f.write(f"{idx:03d}. {entry}\n")
                f.write("\n")

        print(
            f"\n[+] Audit complete: {len(findings.errors)} Errors, {len(findings.warnings)} Warnings, {len(findings.notes)} Notes."
        )
        print(f"[+] Tiered report written to: {report_file}")

        if check_name in ("vital_synchronization", "full_audit") and self.remediation_rows:
            self.write_csv_remediation(self.remediation_rows, ts)
        print()


def display_menu(auditor: RegistryAuditor) -> None:
    """Renders the interactive command console for targeted verification routines."""
    while True:
        print("=" * 56)
        print(f"        GPA: GENEALOGY PEOPLE AUDITOR ({__version__})")
        print("=" * 56)
        print("1. Validate Container Schema & Version")
        print("2. Validate Entity Schema Requirements")
        print("3. Validate Bidirectional Kinship Reciprocity")
        print("4. Validate Child/Parent Birth Chronology")
        print("5. Validate Birth & Death Cross-Synchronization (TXT + CSV)")
        print("6. Audit Incomplete & Partial Vital Dates")
        print("7. Run Complete Audit (All Checks + CSV)")
        print("Q. Quit")
        print("=" * 56)
        choice = input("Select an option [1-7, Q]: ").strip().upper()

        if choice == "1":
            print("\nExecuting: Container Schema Audit...")
            findings = auditor.audit_container()
            auditor.write_report("container_schema", findings)
        elif choice == "2":
            print("\nExecuting: Entity Schema Requirements Audit...")
            findings = auditor.audit_schema()
            auditor.write_report("schema_requirements", findings)
        elif choice == "3":
            print("\nExecuting: Bidirectional Kinship Reciprocity Audit...")
            findings = auditor.audit_reciprocity()
            auditor.write_report("relationship_reciprocity", findings)
        elif choice == "4":
            print("\nExecuting: Child/Parent Chronological Audit...")
            findings = auditor.audit_chronology()
            auditor.write_report("birth_chronology", findings)
        elif choice == "5":
            print("\nExecuting: Birth & Death Synchronization Audit...")
            findings = auditor.audit_vital_synchronization()
            auditor.write_report("vital_synchronization", findings)
        elif choice == "6":
            print("\nExecuting: Incomplete & Partial Dates Audit...")
            findings = auditor.audit_incomplete_dates()
            auditor.write_report("incomplete_dates", findings)
        elif choice == "7":
            print("\nExecuting: Complete Master Registry Audit...")
            findings = auditor.run_full_audit()
            auditor.write_report("full_audit", findings)
        elif choice == "Q":
            print("\nExiting GPA utility.")
            break
        else:
            print("\n[!] Invalid selection. Please choose 1-7 or Q.")


def main() -> None:
    """Parses command-line arguments and dispatches auditor routines."""
    parser = argparse.ArgumentParser(
        description=f"GPA: Genealogy People Auditor ({__version__}) - Person Registry Verification Tool"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Route runtime traces directly to console/stderr",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log detailed execution diagnostics to logs/",
    )

    group = parser.add_argument_group("Audit Operations")
    group.add_argument(
        "--container",
        action="store_true",
        help="Run container schema and header verification",
    )
    group.add_argument(
        "--schema",
        action="store_true",
        help="Run entity schema requirements verification",
    )
    group.add_argument(
        "--reciprocity",
        action="store_true",
        help="Run bidirectional kinship reciprocity verification",
    )
    group.add_argument(
        "--chronology",
        action="store_true",
        help="Run child/parent birth chronology verification",
    )
    group.add_argument(
        "--vital-sync",
        action="store_true",
        help="Run birth and death cross-synchronization check (TXT + CSV)",
    )
    group.add_argument(
        "--incomplete-dates",
        action="store_true",
        help="Run incomplete and partial vital dates audit",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Execute all audit checks and generate complete report + CSV",
    )

    args = parser.parse_args()
    auditor = RegistryAuditor(debug=args.debug, verbose=args.verbose)

    has_op = any([
        args.container,
        args.schema,
        args.reciprocity,
        args.chronology,
        args.vital_sync,
        args.incomplete_dates,
        args.all,
    ])

    if not has_op:
        display_menu(auditor)
        return

    if args.container:
        findings = auditor.audit_container()
        auditor.write_report("container_schema", findings)

    if args.schema:
        findings = auditor.audit_schema()
        auditor.write_report("schema_requirements", findings)

    if args.reciprocity:
        findings = auditor.audit_reciprocity()
        auditor.write_report("relationship_reciprocity", findings)

    if args.chronology:
        findings = auditor.audit_chronology()
        auditor.write_report("birth_chronology", findings)

    if args.vital_sync:
        findings = auditor.audit_vital_synchronization()
        auditor.write_report("vital_synchronization", findings)

    if args.incomplete_dates:
        findings = auditor.audit_incomplete_dates()
        auditor.write_report("incomplete_dates", findings)

    if args.all:
        findings = auditor.run_full_audit()
        auditor.write_report("full_audit", findings)


if __name__ == "__main__":
    main()