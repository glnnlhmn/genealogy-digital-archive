# Name: audit_people_registry.py
# Path: tools/audits/audit_people_registry.py

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import sys

ROOT_DIR = Path("G:/My Drive/genealogy-digital-archive")
PEOPLE_PATH = ROOT_DIR / "data/entities/people.json"
REPORTS_DIR = ROOT_DIR / "reports"
LOGS_DIR = ROOT_DIR / "gtemp"

DATE_ISO_PATTERN = re.compile(r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$")
PERSON_ID_PATTERN = re.compile(r"^IND-\d{5}$")
VALID_SEX_VALUES = {"Male", "Female", "Unknown", None}
VALID_ROLES = {
    "CHIL", "HUSB", "WIFE", "MOTH", "FATH", "SPOU", "WITN", "GODP",
    "INFORMANT", "CLERGY", "OFFICIATOR", "NEIGHBOR", "ATND", "UNDR",
    "DEC", "OTHR", "UNKNOWN"
}


class TieredFindings:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.notes = []

    def add_error(self, entity_id: str, message: str):
        self.errors.append(f"[{entity_id}] {message}")

    def add_warning(self, entity_id: str, message: str):
        self.warnings.append(f"[{entity_id}] {message}")

    def add_note(self, entity_id: str, message: str):
        self.notes.append(f"[{entity_id}] {message}")

    def extend(self, other):
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.notes.extend(other.notes)

    @property
    def total_count(self) -> int:
        return len(self.errors) + len(self.warnings) + len(self.notes)


class RegistryAuditor:
    def __init__(self, debug=False, verbose=False):
        self.debug = debug
        self.verbose = verbose
        self.log_file = None
        if self.verbose:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = LOGS_DIR / f"audit_people_registry-{ts}.log"

        self.people_data = {}
        self.persons = []
        self.person_map = {}
        self.remediation_rows = []
        self.load_data()

    def _log(self, message: str, is_error: bool = False):
        if self.debug:
            target_stream = sys.stderr if is_error else sys.stdout
            target_stream.write(f"DEBUG: {message}\n")
            target_stream.flush()
        if self.verbose and self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] {'ERROR: ' if is_error else ''}{message}\n")

    def load_data(self):
        if not PEOPLE_PATH.exists():
            err = f"Target people registry not found at: {PEOPLE_PATH}"
            self._log(err, is_error=True)
            print(f"Error: {err}")
            sys.exit(1)

        self._log(f"Reading registry data from {PEOPLE_PATH}")
        with open(PEOPLE_PATH, "r", encoding="utf-8") as f:
            self.people_data = json.load(f)

        self.persons = self.people_data.get("persons", [])
        self.person_map = {
            p.get("person_id"): p for p in self.persons if p.get("person_id")
        }
        self._log(f"Loaded {len(self.persons)} total individuals into memory.")

    def audit_schema(self) -> TieredFindings:
        findings = TieredFindings()
        self._log("Initiating Schema Requirements Audit.")

        for p in self.persons:
            pid = p.get("person_id", "UNKNOWN_ID")

            if not pid or not PERSON_ID_PATTERN.match(pid):
                findings.add_error(pid, "Invalid person_id format or missing key.")

            if "display_name" not in p or not isinstance(p["display_name"], str):
                findings.add_error(pid, "Missing or invalid required string 'display_name'.")

            cname = p.get("canonical_name")
            if not isinstance(cname, dict):
                findings.add_error(pid, "Missing or invalid required object 'canonical_name'.")
            else:
                has_raw = bool(cname.get("raw_name"))
                has_given_surname = bool(cname.get("given") and cname.get("surname"))
                if not (has_raw or has_given_surname):
                    findings.add_error(
                        pid,
                        "canonical_name requires either 'raw_name' or both 'given' and 'surname'."
                    )

            if "sex" in p and p["sex"] not in VALID_SEX_VALUES:
                findings.add_error(pid, f"Invalid 'sex' enum value: '{p['sex']}'")

            vitals = p.get("vitals", {})
            if isinstance(vitals, dict):
                for vtype in ["birth", "death"]:
                    vobj = vitals.get(vtype, {})
                    if isinstance(vobj, dict):
                        dobj = vobj.get("date", {})
                        if isinstance(dobj, dict):
                            dstart = dobj.get("date_start")
                            if dstart is not None and not DATE_ISO_PATTERN.match(str(dstart)):
                                findings.add_error(
                                    pid,
                                    f"vitals.{vtype}.date.date_start fails ISO pattern: '{dstart}'"
                                )
                            dend = dobj.get("date_end")
                            if dend is not None and not DATE_ISO_PATTERN.match(str(dend)):
                                findings.add_error(
                                    pid,
                                    f"vitals.{vtype}.date.date_end fails ISO pattern: '{dend}'"
                                )

            assoc = p.get("associated_people", [])
            if isinstance(assoc, list):
                for idx, a in enumerate(assoc):
                    role = a.get("role")
                    if role not in VALID_ROLES:
                        findings.add_error(
                            pid,
                            f"associated_people[{idx}] has invalid role enum: '{role}'"
                        )
                    if "person_id" not in a and "name" not in a:
                        findings.add_error(
                            pid,
                            f"associated_people[{idx}] requires either 'person_id' or 'name'."
                        )
            else:
                findings.add_error(pid, "'associated_people' must be an array.")

        return findings

    def audit_reciprocity(self) -> TieredFindings:
        findings = TieredFindings()
        self._log("Initiating Reciprocal Relationship Audit.")

        for pid, p in self.person_map.items():
            assoc = p.get("associated_people", [])
            for a in assoc:
                target_id = a.get("person_id")
                role = a.get("role")

                if not target_id or target_id not in self.person_map:
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
                            f"Links parent ({role}), but {target_id} does not link back as CHIL."
                        )

                elif role == "CHIL":
                    recip = any(
                        ta.get("person_id") == pid and ta.get("role") in ("FATH", "MOTH")
                        for ta in target_assoc
                    )
                    if not recip:
                        findings.add_error(
                            f"{pid} -> {target_id}",
                            f"Links child, but {target_id} does not link back as FATH or MOTH."
                        )

                elif role in ("SPOU", "HUSB", "WIFE"):
                    recip = any(
                        ta.get("person_id") == pid and ta.get("role") in ("SPOU", "HUSB", "WIFE")
                        for ta in target_assoc
                    )
                    if not recip:
                        findings.add_warning(
                            f"{pid} <-> {target_id}",
                            f"Links spouse ({role}), but {target_id} does not reciprocate spouse relationship."
                        )

        return findings

    def _extract_birth_year(self, p):
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
        findings = TieredFindings()
        self._log("Initiating Child/Parent Chronological Validation.")

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
                            "Both child and parent have unrecorded birth dates; chronological check skipped."
                        )
                        continue

                    if child_year is None:
                        findings.add_warning(
                            pid,
                            f"Child missing birth date; cannot chronologically verify against parent {parent_id} (b. {parent_year})."
                        )
                        continue

                    if parent_year is None:
                        findings.add_warning(
                            parent_id,
                            f"Parent missing birth date; cannot chronologically verify against child {pid} (b. {child_year})."
                        )
                        continue

                    diff = child_year - parent_year
                    if diff < 12:
                        findings.add_error(
                            f"{pid} vs {parent_id}",
                            f"Biological impossibility: Parent ({parent_id}, b. {parent_year}) was {diff} years old at child's birth ({pid}, b. {child_year}). Minimum threshold: 12."
                        )
                    elif diff > 85:
                        findings.add_error(
                            f"{pid} vs {parent_id}",
                            f"Biological impossibility: Parent ({parent_id}, b. {parent_year}) was {diff} years old at child's birth ({pid}, b. {child_year}). Maximum threshold: 85."
                        )

        return findings

    def _determine_presumed_truth(self, c_val, c_mod, v_val, v_mod):
        """
        Genealogical arbitration rules returning (narrative_string, proposed_action, proposed_val, reason).
        """
        if v_val and not c_val:
            val = str(v_val)[:4] if len(str(v_val)) >= 4 else str(v_val)
            return (
                f"Presume vitals is correct ({v_val}); canonical_name should be updated.",
                "UPDATE_CANONICAL_YEAR",
                val,
                "Vitals populated while canonical year is null"
            )
        if c_val and not v_val:
            return (
                f"Presume canonical is correct ({c_val}); vitals.date_start should be populated.",
                "UPDATE_VITALS_DATE",
                str(c_val),
                "Canonical populated while vitals date_start is null"
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
                        "Higher precision date in vitals overrides divergent canonical year"
                    )
                return (
                    f"Evidentiary conflict ({c_val} vs {v_val}); requires manual record disambiguation.",
                    "MANUAL_REVIEW",
                    "",
                    "Divergent 4-digit years without day-level precision"
                )
            if c_mod != v_mod:
                if v_mod == "EXACT" and len(v_val_str) >= 7:
                    return (
                        f"Presume vitals is correct ({v_val} EXACT); promote canonical_name modifier to EXACT.",
                        "UPDATE_CANONICAL_MODIFIER",
                        "EXACT",
                        "High-precision vitals date proves exact year"
                    )
                if c_mod == "UNKNOWN" and v_mod == "ABT":
                    return (
                        f"Presume vitals is correct ({v_val} ABT); change canonical_name modifier from UNKNOWN to ABT.",
                        "UPDATE_CANONICAL_MODIFIER",
                        "ABT",
                        "Estimated vitals date replaces invalid UNKNOWN year modifier"
                    )
                if len(v_val_str) == 4 and v_mod == "EXACT" and c_mod == "ABT":
                    return (
                        f"Presume vitals modifier '{v_mod}' is authoritative over canonical '{c_mod}'.",
                        "UPDATE_CANONICAL_MODIFIER",
                        "EXACT",
                        "Vitals EXACT qualifier authoritative over canonical ABT"
                    )
                return (
                    f"Presume vitals modifier '{v_mod}' is authoritative over canonical '{c_mod}'.",
                    "UPDATE_CANONICAL_MODIFIER",
                    v_mod,
                    "Vitals modifier authoritative for consistency"
                )
        return ("Requires primary document review.", "MANUAL_REVIEW", "", "Unclassified edge case")

    def audit_vital_synchronization(self) -> TieredFindings:
        findings = TieredFindings()
        self.remediation_rows = []
        self._log("Initiating Canonical vs. Vitals Cross-Synchronization Audit.")

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
                    f"Birth year conflict: canonical_name={c_byear} ({c_bmod}) vs vitals.birth={v_bstart} ({v_bmod}). -> Resolution: {narrative}"
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
                    "status": "PENDING"
                })
            elif (c_byear is None) ^ (v_byear is None):
                narrative, action, pval, reason = self._determine_presumed_truth(c_byear, c_bmod, v_bstart, v_bmod)
                findings.add_error(
                    pid,
                    f"Birth presence mismatch: canonical_name={c_byear} ({c_bmod}) vs vitals.birth={v_bstart} ({v_bmod}). -> Resolution: {narrative}"
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
                    "status": "PENDING"
                })
            elif c_bmod and v_bmod and c_bmod != v_bmod:
                narrative, action, pval, reason = self._determine_presumed_truth(c_byear, c_bmod, v_bstart, v_bmod)
                findings.add_warning(
                    pid,
                    f"Birth modifier discordance: canonical_name={c_byear} ('{c_bmod}') vs vitals.birth={v_bstart} ('{v_bmod}'). -> Resolution: {narrative}"
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
                    "status": "PENDING"
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
                pass  # Standard living placeholder
            elif c_dyear is not None and v_dyear is not None and c_dyear != v_dyear:
                narrative, action, pval, reason = self._determine_presumed_truth(c_dyear, c_dmod, v_dstart, v_dmod)
                findings.add_error(
                    pid,
                    f"Death year conflict: canonical_name={c_dyear} ({c_dmod}) vs vitals.death={v_dstart} ({v_dmod}). -> Resolution: {narrative}"
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
                    "status": "PENDING"
                })
            elif (c_dyear is None) ^ (v_dyear is None):
                narrative, action, pval, reason = self._determine_presumed_truth(c_dyear, c_dmod, v_dstart, v_dmod)
                findings.add_error(
                    pid,
                    f"Death presence mismatch: canonical_name={c_dyear} ({c_dmod}) vs vitals.death={v_dstart} ({v_dmod}). -> Resolution: {narrative}"
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
                    "status": "PENDING"
                })
            elif c_dmod and v_dmod and c_dmod != v_dmod:
                narrative, action, pval, reason = self._determine_presumed_truth(c_dyear, c_dmod, v_dstart, v_dmod)
                findings.add_warning(
                    pid,
                    f"Death modifier discordance: canonical_name={c_dyear} ('{c_dmod}') vs vitals.death={v_dstart} ('{v_dmod}'). -> Resolution: {narrative}"
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
                    "status": "PENDING"
                })

        return findings

    def audit_incomplete_dates(self) -> TieredFindings:
        findings = TieredFindings()
        self._log("Initiating Incomplete and Missing Vital Dates Audit.")

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

                # Missing date entirely
                if dstart is None:
                    if vtype == "death" and c_mod == "LIVING":
                        continue
                    findings.add_warning(
                        pid,
                        f"Missing vital date: vitals.{vtype}.date.date_start=null (modifier='{mod}', canonical_year={c_year})."
                    )
                    continue

                dstart_str = str(dstart)
                # Incomplete partial date (Year-only YYYY)
                if re.match(r"^\d{4}$", dstart_str):
                    findings.add_note(
                        pid,
                        f"Partial date [YYYY]: vitals.{vtype}.date.date_start='{dstart_str}' | mod='{mod}' | raw='{raw}' | canonical_year={c_year}."
                    )
                # Incomplete partial date (Year-Month YYYY-MM)
                elif re.match(r"^\d{4}-\d{2}$", dstart_str):
                    findings.add_note(
                        pid,
                        f"Partial date [YYYY-MM]: vitals.{vtype}.date.date_start='{dstart_str}' | mod='{mod}' | raw='{raw}' | canonical_year={c_year}."
                    )

        return findings

    def write_csv_remediation(self, rows: list, base_ts: str):
        if not rows:
            return
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        csv_file = REPORTS_DIR / f"remediation_vital_sync_{base_ts}.csv"

        fieldnames = [
            "person_id",
            "event_type",
            "target_path",
            "current_canonical",
            "current_vitals",
            "proposed_action",
            "proposed_value",
            "rule_reason",
            "status"
        ]

        self._log(f"Writing remediation CSV ledger ({len(rows)} rows) to {csv_file}")
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

        print(f"[+] Remediation CSV ledger written to: {csv_file}")

    def write_report(self, check_name: str, findings: TieredFindings):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = REPORTS_DIR / f"audit_{check_name}_{ts}.txt"

        self._log(f"Writing tiered report ({findings.total_count} total entries) to {report_file}")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"AUDIT REPORT: {check_name.upper()}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Total Entities Evaluated: {len(self.persons)}\n")
            f.write(
                f"Summary: {len(findings.errors)} Errors | {len(findings.warnings)} Warnings | {len(findings.notes)} Notes\n"
            )
            f.write("=" * 68 + "\n\n")

            # Errors Section
            f.write(f"[ERRORS] - Critical Integrity & Schema Violations ({len(findings.errors)})\n")
            f.write("-" * 68 + "\n")
            if not findings.errors:
                f.write("None detected.\n\n")
            else:
                for idx, entry in enumerate(findings.errors, 1):
                    f.write(f"{idx:03d}. {entry}\n")
                f.write("\n")

            # Warnings Section
            f.write(f"[WARNINGS] - Data Gaps, Modifier Discordances & Resolutions ({len(findings.warnings)})\n")
            f.write("-" * 68 + "\n")
            if not findings.warnings:
                f.write("None detected.\n\n")
            else:
                for idx, entry in enumerate(findings.warnings, 1):
                    f.write(f"{idx:03d}. {entry}\n")
                f.write("\n")

            # Notes Section
            f.write(f"[NOTES] - Incomplete Dates & Structural Observations ({len(findings.notes)})\n")
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


def display_menu(auditor: RegistryAuditor):
    while True:
        print("=" * 56)
        print("    ARCHIVAL REGISTRY AUDIT MENU (MIP v1.0.1)")
        print("=" * 56)
        print("1. Validate Schema Requirements")
        print("2. Validate Relationship Reciprocity")
        print("3. Validate Child/Parent Birth Chronology")
        print("4. Validate Birth & Death Cross-Synchronization (TXT + CSV)")
        print("5. Audit Incomplete & Partial Vital Dates")
        print("6. Run Complete Audit (All Checks + CSV)")
        print("Q. Quit")
        print("=" * 56)
        choice = input("Select an option [1-6, Q]: ").strip().upper()

        if choice == "1":
            print("\nExecuting: Schema Requirements Audit...")
            findings = auditor.audit_schema()
            auditor.write_report("schema_requirements", findings)
        elif choice == "2":
            print("\nExecuting: Relationship Reciprocity Audit...")
            findings = auditor.audit_reciprocity()
            auditor.write_report("relationship_reciprocity", findings)
        elif choice == "3":
            print("\nExecuting: Child/Parent Chronological Audit...")
            findings = auditor.audit_chronology()
            auditor.write_report("birth_chronology", findings)
        elif choice == "4":
            print("\nExecuting: Birth & Death Synchronization Audit...")
            findings = auditor.audit_vital_synchronization()
            auditor.write_report("vital_synchronization", findings)
        elif choice == "5":
            print("\nExecuting: Incomplete & Partial Dates Audit...")
            findings = auditor.audit_incomplete_dates()
            auditor.write_report("incomplete_dates", findings)
        elif choice == "6":
            print("\nExecuting: Complete Registry Audit...")
            findings = TieredFindings()
            findings.extend(auditor.audit_schema())
            findings.extend(auditor.audit_reciprocity())
            findings.extend(auditor.audit_chronology())
            findings.extend(auditor.audit_vital_synchronization())
            findings.extend(auditor.audit_incomplete_dates())
            auditor.write_report("full_audit", findings)
        elif choice == "Q":
            print("\nExiting audit utility.")
            break
        else:
            print("\n[!] Invalid selection. Please choose 1-6 or Q.")


def main():
    parser = argparse.ArgumentParser(
        description="MIP Master Person Registry Validation & Audit Tool"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Route runtime traces directly to sys.stderr"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log execution details to gtemp/[script name]-timestamp.log"
    )
    args = parser.parse_args()

    auditor = RegistryAuditor(debug=args.debug, verbose=args.verbose)
    display_menu(auditor)


if __name__ == "__main__":
    main()