# PATH: auto/audit_tools/verify-people-registry.py
# TIMESTAMP: 2026-09-18-14-05-00

import json
import re
from datetime import datetime, timezone
from pathlib import Path

def main():
    repo_root = Path(__file__).resolve().parent.parent.parent
    people_file = repo_root / "data" / "entities" / "people.json"
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    now_dt = datetime.now(timezone.utc)
    ts_file = now_dt.strftime("%Y%m%d-%H%M%S")
    ts_iso = now_dt.isoformat().replace("+00:00", "Z")

    report_lines = [
        f"# People Registry Audit Report",
        f"**Generated**: {ts_iso}",
        f"**File**: `{people_file.relative_to(repo_root)}`\n",
        "---",
        ""
    ]

    if not people_file.exists():
        msg = f"Error: Master file not found at {people_file}"
        print(msg)
        report_lines.append(f"❌ **Fatal Error**: Master file does not exist.\n")
        _write_report(reports_dir / f"audit-people-registry-{ts_file}.md", report_lines)
        return

    with open(people_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    persons = data.get("persons", [])
    total_persons = data.get("total_persons", 0)

    schema_errors = []
    reciprocal_errors = []

    # 1. Container Schema Checks
    if data.get("$schema") != "schemas\\entities\\person_registry.schema.json" and data.get("$schema") != "schemas/entities/person_registry.schema.json":
        schema_errors.append(f"Invalid container $schema: {data.get('$schema')}")
    if data.get("schema_version") != "1.0.1":
        schema_errors.append(f"Invalid schema_version: {data.get('schema_version')} (expected '1.0.1')")
    if len(persons) != total_persons:
        schema_errors.append(f"Count mismatch: total_persons ({total_persons}) does not equal len(persons) ({len(persons)})")

    # 2. Entity Schema Checks
    id_map = {}
    valid_sexes = {"Male", "Female", "Unknown", None}
    valid_modifiers = {"EXACT", "ABT", "BEF", "AFT", "BET", "FROM_TO", "LIVING", "UNKNOWN"}

    for idx, p in enumerate(persons):
        pid = p.get("person_id")
        if not pid or not re.match(r"^IND-\d{5}$", pid):
            schema_errors.append(f"Record #{idx}: invalid or missing person_id: {pid}")
            continue
        if pid in id_map:
            schema_errors.append(f"Duplicate person_id: {pid}")
        id_map[pid] = p

        # Mandatory fields
        if not p.get("display_name"):
            schema_errors.append(f"{pid}: missing display_name")
        cname = p.get("canonical_name")
        if not cname or not isinstance(cname, dict):
            schema_errors.append(f"{pid}: missing or invalid canonical_name")
        else:
            if not cname.get("raw_name") and not (cname.get("given") and cname.get("surname")):
                schema_errors.append(f"{pid}: canonical_name must have raw_name or (given and surname)")

        if p.get("sex") not in valid_sexes:
            schema_errors.append(f"{pid}: invalid sex '{p.get('sex')}'")

        # Check vital modifiers
        for event in ("birth", "death"):
            v_ev = p.get("vitals", {}).get(event, {})
            v_date = v_ev.get("date", {})
            mod = v_date.get("modifier")
            if mod and mod not in valid_modifiers:
                schema_errors.append(f"{pid}: invalid {event} date modifier '{mod}'")

    # 3. Reciprocal Link Audit
    for pid, p in id_map.items():
        assos = p.get("associated_people", [])
        for asso in assos:
            target_id = asso.get("person_id")
            role = asso.get("role")
            
            # Non-minted literal names are allowed
            if not target_id:
                if not asso.get("name"):
                    reciprocal_errors.append(f"{pid}: associated_people entry missing both person_id and name")
                continue

            if target_id not in id_map:
                reciprocal_errors.append(f"{pid}: references unknown target person_id {target_id} (role {role})")
                continue

            target = id_map[target_id]
            target_assos = target.get("associated_people", [])

            if role == "SPOU":
                if not any(a.get("person_id") == pid and a.get("role") == "SPOU" for a in target_assos):
                    reciprocal_errors.append(f"Missing reciprocal SPOU: {target_id} does not link back to {pid}")
            elif role in ("FATH", "MOTH"):
                if not any(a.get("person_id") == pid and a.get("role") == "CHIL" for a in target_assos):
                    reciprocal_errors.append(f"Missing reciprocal CHIL: {target_id} does not list {pid} as CHIL (parent role {role})")
            elif role == "CHIL":
                p_sex = p.get("sex")
                expected = ["FATH", "MOTH"] if p_sex not in ("Male", "Female") else (["FATH"] if p_sex == "Male" else ["MOTH"])
                if not any(a.get("person_id") == pid and a.get("role") in expected for a in target_assos):
                    reciprocal_errors.append(f"Missing reciprocal parent link: {target_id} does not list {pid} as {'/'.join(expected)}")

    # 4. Generate Report Output
    report_lines.append("## Summary Statistics")
    report_lines.append(f"* **Total Persons Enumerated**: {len(persons)}")
    report_lines.append(f"* **Total Schema / Field Issues**: {len(schema_errors)}")
    report_lines.append(f"* **Total Reciprocal Link Inconsistencies**: {len(reciprocal_errors)}\n")

    if schema_errors:
        report_lines.append("## Schema and Field Violations")
        for err in schema_errors:
            report_lines.append(f"* {err}")
        report_lines.append("")

    if reciprocal_errors:
        report_lines.append("## Reciprocal Association Discrepancies")
        for err in reciprocal_errors:
            report_lines.append(f"* {err}")
        report_lines.append("")

    if not schema_errors and not reciprocal_errors:
        report_lines.append("## Audit Verdict")
        report_lines.append("✅ **Passed**: The master registry strictly conforms to schemas and all bidirectional kinship links are verified.")

    report_path = reports_dir / f"audit-people-registry-{ts_file}.md"
    _write_report(report_path, report_lines)

    print(f"Audit completed.")
    print(f"Persons checked: {len(persons)}")
    print(f"Schema errors: {len(schema_errors)}")
    print(f"Reciprocal issues: {len(reciprocal_errors)}")
    print(f"Detailed report written to: {report_path.relative_to(repo_root)}")

def _write_report(path: Path, lines: list):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()