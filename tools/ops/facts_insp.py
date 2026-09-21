# Name: facts_insp.py
# Path: tools/ops/facts_insp.py

"""
Fact Registry Inspector (facts_insp)
Version: 1.0.3 Build 5

Description:
    Read-only audit tool for evaluating data/entities/facts.json against structural,
    referential, biological, and deduplication standards. Cross-references
    data/entities/people.json to detect referential anomalies, chronological drift,
    and reciprocal link opportunities. Emits human-readable logs, Markdown reports,
    and remediation CSVs.

Usage:
    python tools/ops/facts_insp.py [--help] [--verbose] [--debug]
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROGRAM_NAME = "facts_insp"
PROGRAM_VERSION = "1.0.3"
PROGRAM_BUILD = "5"

ROOT_DIR = Path("G:/My Drive/genealogy-digital-archive")
FACTS_FILE = ROOT_DIR / "data/entities/facts.json"
PEOPLE_FILE = ROOT_DIR / "data/entities/people.json"
REPORTS_DIR = ROOT_DIR / "reports"
LOGS_DIR = ROOT_DIR / "logs"

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOGS_DIR / f"facts_insp-{TIMESTAMP}.log"

UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
ISO_DATE_REGEX = re.compile(r"^(\d{4})(-\d{2})?(-\d{2})?$")

VALID_FACT_TYPES = {
    "Birth", "Death", "Burial", "Marriage", "Divorce", "Census", "Residence",
    "Occupation", "Education", "Military", "Probate", "Immigration", "Emigration",
    "Naturalization", "Religion", "Baptism", "Confirmation", "Adoption",
    "Parentage", "Award", "Civic", "Incident", "Property", "Association", "Other"
}

VALID_MODIFIERS = {"EXACT", "ABT", "BEF", "AFT", "BET", "FROM_TO", "UNKNOWN"}
SPAN_MODIFIERS = {"BET", "FROM_TO"}
SPOUSE_ROLES = {"HUSB", "WIFE", "SPOU"}


def log_line(msg: str, level: str = "INFO", verbose: bool = False, debug: bool = False) -> None:
    entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}\n"
    if debug or (level in ["INFO", "ERROR", "WARN"] and verbose):
        print(entry.strip())
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


def load_json(filepath: Path) -> Any:
    return json.loads(filepath.read_text(encoding="utf-8-sig"))


def parse_year(date_str: Optional[str]) -> Optional[int]:
    if not date_str:
        return None
    match = re.match(r"^(\d{4})", str(date_str).strip())
    return int(match.group(1)) if match else None


def normalize_str(val: Optional[str]) -> str:
    return str(val or "").strip().lower()


def get_fact_date_dict(fact: Dict[str, Any]) -> Dict[str, Any]:
    d = fact.get("date")
    return d if isinstance(d, dict) else {}


def get_fact_loc_dict(fact: Dict[str, Any]) -> Dict[str, Any]:
    loc = fact.get("location")
    return loc if isinstance(loc, dict) else {}


def get_person_display(person_map: Dict[str, Dict[str, Any]], person_id: Optional[str]) -> str:
    if not person_id:
        return "Unassigned"
    p = person_map.get(person_id)
    if not p:
        return f"{person_id} (Unknown)"
    d_name = p.get("display_name")
    return f"{person_id} ({d_name})" if d_name else person_id


def format_fid_short(fact_id: str) -> str:
    cleaned = fact_id.replace("factoid-", "")
    return cleaned[:8] if len(cleaned) >= 8 else cleaned


def audit_facts(verbose: bool = False, debug: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not FACTS_FILE.exists():
        log_line(f"Facts file missing: {FACTS_FILE}", level="ERROR", verbose=True)
        sys.exit(1)
    if not PEOPLE_FILE.exists():
        log_line(f"People registry missing: {PEOPLE_FILE}", level="ERROR", verbose=True)
        sys.exit(1)

    facts_container = load_json(FACTS_FILE)
    people_container = load_json(PEOPLE_FILE)

    facts: List[Dict[str, Any]] = facts_container.get("facts", [])
    people: List[Dict[str, Any]] = people_container.get("persons", [])
    people_map: Dict[str, Dict[str, Any]] = {p["person_id"]: p for p in people if "person_id" in p}

    findings: List[Dict[str, Any]] = []
    merge_proposals: List[Dict[str, Any]] = []

    def record_issue(level: str, tag: str, fact_id: str, person_id: Optional[str], message: str) -> None:
        findings.append({
            "level": level,
            "category": tag,
            "fact_id": fact_id,
            "person_id": person_id or "N/A",
            "message": message
        })
        p_desc = get_person_display(people_map, person_id)
        fid_disp = format_fid_short(fact_id)
        log_line(f"[{tag}] FCT {fid_disp} ({p_desc}): {message}", level=level, verbose=verbose, debug=debug)

    seen_fact_ids: Set[str] = set()
    person_facts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    # ==================================================================
    # STAGE 1: Schema, Typology, Temporal & Spatial Integrity
    # ==================================================================
    log_line("[Stage-1] --- Record Validation ---", level="INFO", verbose=verbose, debug=debug)

    # 1.1 Structural Identifiers & Referential Links
    log_line("[Stage-1.1] Verifying Identifier Formats & Registry References...", level="INFO", verbose=verbose, debug=debug)
    s1_1_start = len(findings)
    for f in facts:
        fid = f.get("fact_id", "")
        pid = f.get("person_id")

        if not fid:
            record_issue("ERROR", "Schema", "MISSING_ID", pid, "Fact record is missing required 'fact_id'.")
            continue

        if fid in seen_fact_ids:
            record_issue("ERROR", "Schema", fid, pid, f"Duplicate fact_id collision detected: {fid}.")
        seen_fact_ids.add(fid)

        if not UUID_REGEX.match(fid):
            record_issue("ERROR", "Schema", fid, pid, f"Identifier does not conform to standard GUID/UUID format: '{fid}'.")

        if not pid:
            record_issue("ERROR", "Referential", fid, None, "Fact is missing required 'person_id'.")
        elif pid not in people_map:
            record_issue("ERROR", "Referential", fid, pid, f"Broken reference: Person ID '{pid}' does not exist in people.json.")
        else:
            person_facts[pid].append(f)

    s1_1_diff = len(findings) - s1_1_start
    if s1_1_diff == 0:
        log_line("[Stage-1.1] Status: PASS (0 issues)", level="INFO", verbose=verbose, debug=debug)
    else:
        log_line(f"[Stage-1.1] Completed: {s1_1_diff} issues detected", level="INFO", verbose=verbose, debug=debug)

    # 1.2 Controlled Typology Validation
    log_line("[Stage-1.2] Validating Controlled Fact Typology...", level="INFO", verbose=verbose, debug=debug)
    s1_2_start = len(findings)
    for f in facts:
        fid = f.get("fact_id", "")
        pid = f.get("person_id")
        ftype = f.get("fact_type", "")
        if ftype not in VALID_FACT_TYPES:
            record_issue("ERROR", "Typology", fid, pid, f"Invalid fact_type '{ftype}' not in controlled vocabulary.")

    s1_2_diff = len(findings) - s1_2_start
    if s1_2_diff == 0:
        log_line("[Stage-1.2] Status: PASS (0 issues)", level="INFO", verbose=verbose, debug=debug)
    else:
        log_line(f"[Stage-1.2] Completed: {s1_2_diff} issues detected", level="INFO", verbose=verbose, debug=debug)

    # 1.3 Temporal Bounds & Modifier Consistency
    log_line("[Stage-1.3] Inspecting Temporal Bounds, Syntax & Modifiers...", level="INFO", verbose=verbose, debug=debug)
    s1_3_start = len(findings)
    for f in facts:
        fid = f.get("fact_id", "")
        pid = f.get("person_id")
        date_obj = get_fact_date_dict(f)

        d_start = date_obj.get("date_start")
        d_end = date_obj.get("date_end")
        modifier = date_obj.get("modifier", "EXACT")

        if f.get("date") is not None and modifier not in VALID_MODIFIERS:
            record_issue("ERROR", "Temporal", fid, pid, f"Unrecognized date modifier '{modifier}'.")

        if d_start and not ISO_DATE_REGEX.match(str(d_start)):
            record_issue("ERROR", "Temporal", fid, pid, f"date_start '{d_start}' is not valid ISO 8601 (YYYY, YYYY-MM, or YYYY-MM-DD).")

        if d_end and not ISO_DATE_REGEX.match(str(d_end)):
            record_issue("ERROR", "Temporal", fid, pid, f"date_end '{d_end}' is not valid ISO 8601.")

        y_start = parse_year(d_start)
        y_end = parse_year(d_end)

        if y_start and y_end and y_end < y_start:
            record_issue("ERROR", "Temporal", fid, pid, f"Inverted date range: date_end ({d_end}) precedes date_start ({d_start}).")

        if d_end and modifier not in SPAN_MODIFIERS:
            record_issue("WARN", "Temporal", fid, pid, f"date_end is populated ({d_end}), but modifier is '{modifier}' instead of span (BET, FROM_TO).")

        if not d_start and d_end:
            record_issue("ERROR", "Temporal", fid, pid, f"Orphan date_end ({d_end}) present without date_start.")

    s1_3_diff = len(findings) - s1_3_start
    if s1_3_diff == 0:
        log_line("[Stage-1.3] Status: PASS (0 issues)", level="INFO", verbose=verbose, debug=debug)
    else:
        log_line(f"[Stage-1.3] Completed: {s1_3_diff} issues detected", level="INFO", verbose=verbose, debug=debug)

    # 1.4 Spatial Structure & Canonical Normalization
    log_line("[Stage-1.4] Checking Spatial Structures & Canonical Locations...", level="INFO", verbose=verbose, debug=debug)
    s1_4_start = len(findings)
    for f in facts:
        fid = f.get("fact_id", "")
        pid = f.get("person_id")
        loc_obj = get_fact_loc_dict(f)
        std_loc = loc_obj.get("standardized")
        verb_loc = loc_obj.get("verbatim")

        if verb_loc and not std_loc:
            record_issue("WARN", "Spatial", fid, pid, f"Verbatim location present ('{verb_loc}') without canonical standardized string.")

    s1_4_diff = len(findings) - s1_4_start
    if s1_4_diff == 0:
        log_line("[Stage-1.4] Status: PASS (0 issues)", level="INFO", verbose=verbose, debug=debug)
    else:
        log_line(f"[Stage-1.4] Completed: {s1_4_diff} issues detected", level="INFO", verbose=verbose, debug=debug)

    # ==================================================================
    # STAGE 2: Biological & Chronological Contradictions
    # ==================================================================
    log_line("[Stage-2] --- Biological & Chronological Verification ---", level="INFO", verbose=verbose, debug=debug)
    stage2_start = len(findings)

    for pid, f_list in person_facts.items():
        person = people_map[pid]
        p_vitals = person.get("vitals") or {}
        b_date_raw = p_vitals.get("birth", {}).get("date", {}).get("date_start") if isinstance(p_vitals.get("birth"), dict) else None
        d_date_raw = p_vitals.get("death", {}).get("date", {}).get("date_start") if isinstance(p_vitals.get("death"), dict) else None

        b_year = parse_year(b_date_raw)
        d_year = parse_year(d_date_raw)

        birth_facts = [f for f in f_list if f.get("fact_type") == "Birth"]
        death_facts = [f for f in f_list if f.get("fact_type") == "Death"]

        if len(birth_facts) > 1:
            dates = {get_fact_date_dict(f).get("date_start") for f in birth_facts}
            places = {normalize_str(get_fact_loc_dict(f).get("standardized")) for f in birth_facts}
            if len(dates) > 1 or len(places) > 1:
                fids = ", ".join(format_fid_short(f.get("fact_id", "")) for f in birth_facts)
                record_issue("ERROR", "Biological", birth_facts[0]["fact_id"], pid, f"Multiple conflicting Birth facts detected: {fids}.")

        if len(death_facts) > 1:
            dates = {get_fact_date_dict(f).get("date_start") for f in death_facts}
            places = {normalize_str(get_fact_loc_dict(f).get("standardized")) for f in death_facts}
            if len(dates) > 1 or len(places) > 1:
                fids = ", ".join(format_fid_short(f.get("fact_id", "")) for f in death_facts)
                record_issue("ERROR", "Biological", death_facts[0]["fact_id"], pid, f"Multiple conflicting Death facts detected: {fids}.")

        for f in f_list:
            fid = f["fact_id"]
            ftype = f.get("fact_type", "")
            f_year = parse_year(get_fact_date_dict(f).get("date_start"))

            if f_year and b_year and f_year < b_year:
                if ftype not in ["Parentage", "Probate"]:
                    record_issue("ERROR", "Biological", fid, pid, f"Pre-natal event: '{ftype}' in {f_year} occurs before subject birth ({b_year}).")

            if f_year and d_year and f_year > d_year:
                if ftype not in ["Death", "Burial", "Probate", "Association", "Other"]:
                    record_issue("ERROR", "Biological", fid, pid, f"Post-mortem event: '{ftype}' in {f_year} occurs after subject death ({d_year}).")

            if ftype in ["Marriage"] and f_year and b_year:
                age_at_event = f_year - b_year
                if age_at_event < 13:
                    record_issue("WARN", "Biological", fid, pid, f"Plausibility conflict: Marriage at implausible age ({age_at_event} years old).")

    stage2_diff = len(findings) - stage2_start
    if stage2_diff == 0:
        log_line("[Stage-2] Status: PASS (0 issues)", level="INFO", verbose=verbose, debug=debug)
    else:
        log_line(f"[Stage-2] Completed: {stage2_diff} issues detected", level="INFO", verbose=verbose, debug=debug)

    # ==================================================================
    # STAGE 3: Deduplication & Consolidation Proposals
    # ==================================================================
    log_line("[Stage-3] --- Duplicate Discovery & Merge Proposals ---", level="INFO", verbose=verbose, debug=debug)
    stage3_start = len(findings)

    # Source-Level Collision Scan (Dedup-Source)
    source_collision_groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for f in facts:
        pid = f.get("person_id")
        ftype = f.get("fact_type")
        urn = f.get("source_urn")
        if pid and ftype and urn:
            urn_key = json.dumps(sorted(urn)) if isinstance(urn, list) else str(urn).strip()
            source_collision_groups[(pid, ftype, urn_key)].append(f)

    for (pid, ftype, _), group in source_collision_groups.items():
        if len(group) > 1:
            group.sort(key=lambda x: len(x.get("notes") or x.get("description") or ""), reverse=True)
            primary = group[0]
            redundant = group[1:]
            red_ids = [r["fact_id"] for r in redundant]
            record_issue("WARN", "Dedup-Source", primary["fact_id"], pid, f"{len(group)} redundant extractions for '{ftype}' from identical source URN.")
            merge_proposals.append({
                "primary_fact_id": primary["fact_id"],
                "absorbed_fact_ids": red_ids,
                "person_id": pid,
                "fact_type": ftype,
                "reason": "Duplicate extraction from identical source URN",
                "action": "MERGE"
            })

    # Event-Level Corroboration Scan (Dedup-Event)
    semantic_groups: Dict[Tuple[str, str, Optional[str], str], List[Dict[str, Any]]] = defaultdict(list)
    for f in facts:
        pid = f.get("person_id")
        ftype = f.get("fact_type")
        d_start = get_fact_date_dict(f).get("date_start")
        loc_std = normalize_str(get_fact_loc_dict(f).get("standardized"))
        if pid and ftype and d_start:
            semantic_groups[(pid, ftype, d_start, loc_std)].append(f)

    for (pid, ftype, d_start, _), group in semantic_groups.items():
        if len(group) > 1:
            already_proposed = {m["primary_fact_id"] for m in merge_proposals} | {
                sub for m in merge_proposals for sub in m["absorbed_fact_ids"]
            }
            sub_group = [item for item in group if item["fact_id"] not in already_proposed]
            if len(sub_group) > 1:
                sub_group.sort(key=lambda x: len(x.get("notes") or x.get("description") or ""), reverse=True)
                primary = sub_group[0]
                redundant = sub_group[1:]
                red_ids = [r["fact_id"] for r in redundant]
                record_issue("WARN", "Dedup-Event", primary["fact_id"], pid, f"{len(sub_group)} multi-source records match '{ftype}' ({d_start}) representing same real-world event.")
                merge_proposals.append({
                    "primary_fact_id": primary["fact_id"],
                    "absorbed_fact_ids": red_ids,
                    "person_id": pid,
                    "fact_type": ftype,
                    "reason": "Multi-source corroboration of identical event",
                    "action": "MERGE"
                })

    stage3_diff = len(findings) - stage3_start
    if stage3_diff == 0:
        log_line("[Stage-3] Status: PASS (0 duplicate clusters found)", level="INFO", verbose=verbose, debug=debug)
    else:
        log_line(f"[Stage-3] Completed: {stage3_diff} merge candidates proposed", level="INFO", verbose=verbose, debug=debug)

    # ==================================================================
    # STAGE 4: Relational Consistency & Bilateral Pairing
    # ==================================================================
    log_line("[Stage-4] --- Relational Consistency & Reciprocal Pairing ---", level="INFO", verbose=verbose, debug=debug)
    stage4_start = len(findings)

    for f in facts:
        ftype = f.get("fact_type")
        fid = f.get("fact_id")
        pid = f.get("person_id")

        if ftype in ["Marriage", "Divorce"] and pid in people_map:
            associated = f.get("associated_people") or []
            if not isinstance(associated, list):
                continue

            # Identify if subject has an attendant/non-principal role in the text or list
            subj_entry = next((a for a in associated if isinstance(a, dict) and a.get("person_id") == pid), None)
            subj_role = subj_entry.get("role") if subj_entry else None

            # If subject is explicitly marked as an attendant, skip spouse reciprocity
            if subj_role and subj_role not in SPOUSE_ROLES:
                continue

            # Check if notes indicate subject is an attendant
            notes_str = normalize_str(f.get("notes") or f.get("description"))
            if any(term in notes_str for term in ["matron of honor", "maid of honor", "best man", "bridesmaid", "groomsman", "officiant"]):
                continue

            # Identify candidate spouse partners
            spouses = [a.get("person_id") for a in associated if isinstance(a, dict) and a.get("role") in SPOUSE_ROLES]

            if not spouses:
                registered_spouses = {
                    rel.get("person_id") for rel in people_map[pid].get("associated_people", [])
                    if isinstance(rel, dict) and rel.get("role") == "SPOU"
                }
                spouses = [
                    a.get("person_id") for a in associated
                    if isinstance(a, dict) and a.get("person_id") in registered_spouses
                ]

            for sp_id in spouses:
                if sp_id and sp_id in people_map:
                    partner_facts = person_facts.get(sp_id, [])
                    has_recip = any(
                        pf.get("fact_type") == ftype and any(
                            isinstance(rel, dict) and rel.get("person_id") == pid for rel in (pf.get("associated_people") or [])
                        )
                        for pf in partner_facts
                    )
                    if not has_recip:
                        sp_desc = get_person_display(people_map, sp_id)
                        record_issue("INFO", "Relational", fid, pid, f"Partner {sp_desc} has no reciprocal '{ftype}' fact asserted.")

    stage4_diff = len(findings) - stage4_start
    if stage4_diff == 0:
        log_line("[Stage-4] Status: PASS (0 bilateral discrepancies found)", level="INFO", verbose=verbose, debug=debug)
    else:
        log_line(f"[Stage-4] Completed: {stage4_diff} unreciprocated partner assertions", level="INFO", verbose=verbose, debug=debug)

    return findings, merge_proposals


def generate_reports(findings: List[Dict[str, Any]], merge_proposals: List[Dict[str, Any]]) -> Tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_md_path = REPORTS_DIR / f"fact_audit_report_{TIMESTAMP}.md"
    remediation_csv_path = REPORTS_DIR / f"fact_merge_candidates_{TIMESTAMP}.csv"

    with open(remediation_csv_path, "w", encoding="utf-8", newline="") as cf:
        writer = csv.writer(cf)
        writer.writerow(["primary_fact_id", "absorbed_fact_ids", "person_id", "fact_type", "reason", "action"])
        for m in merge_proposals:
            writer.writerow([
                m["primary_fact_id"],
                ";".join(m["absorbed_fact_ids"]),
                m["person_id"],
                m["fact_type"],
                m["reason"],
                m["action"]
            ])

    error_count = sum(1 for x in findings if x["level"] == "ERROR")
    warn_count = sum(1 for x in findings if x["level"] == "WARN")
    info_count = sum(1 for x in findings if x["level"] == "INFO")
    total_issues = len(findings)

    category_counts: Dict[str, int] = defaultdict(int)
    for x in findings:
        category_counts[x["category"]] += 1

    md_lines = [
        f"# Fact Registry Audit Report ({TIMESTAMP})",
        "",
        "## Executive Summary",
        f"* **Tool:** {PROGRAM_NAME} v{PROGRAM_VERSION} (Build {PROGRAM_BUILD})",
        f"* **Total Facts Audited:** {len(load_json(FACTS_FILE).get('facts', []))}",
        f"* **Total Audit Findings:** {total_issues}",
        f"* **Errors (Blockers):** {error_count}",
        f"* **Warnings (Deduplication / Normalization):** {warn_count}",
        f"* **Informational (Relational Suggestions):** {info_count}",
        f"* **Proposed Fact Merges:** {len(merge_proposals)}",
        "",
        "## Distribution by Category",
        "| Category | Count | Percentage |",
        "| :--- | :--- | :--- |"
    ]

    for cat, count in sorted(category_counts.items(), key=lambda item: item[1], reverse=True):
        pct = (count / total_issues * 100) if total_issues > 0 else 0
        md_lines.append(f"| {cat} | {count} | {pct:.1f}% |")

    md_lines.extend([
        "",
        "## Consolidation & Remediation Candidates",
        f"A total of **{len(merge_proposals)}** merge proposals were exported to `{remediation_csv_path.name}`.",
        "",
        "| Primary Fact ID | Absorbed IDs | Subject | Fact Type | Rationale |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ])

    for m in merge_proposals:
        absorbed_str = "<br>".join(m["absorbed_fact_ids"])
        md_lines.append(f"| `{m['primary_fact_id']}` | `{absorbed_str}` | {m['person_id']} | {m['fact_type']} | {m['reason']} |")

    md_lines.extend([
        "",
        "## Itemized Issue Findings",
        "| Level | Category | Fact ID | Person ID | Diagnostic Message |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ])

    for x in findings:
        md_lines.append(f"| {x['level']} | {x['category']} | `{x['fact_id']}` | {x['person_id']} | {x['message']} |")

    md_lines.append("")
    report_md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return report_md_path, remediation_csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{PROGRAM_NAME}: Fact Registry Diagnostic & Audit Tool (v{PROGRAM_VERSION} Build {PROGRAM_BUILD})")
    parser.add_argument("--verbose", "-v", action="store_true", help="Display diagnostic log output during execution")
    parser.add_argument("--debug", action="store_true", help="Display low-level trace messages directly to console")
    args = parser.parse_args()

    log_line(f"=== Commencing Fact Registry Inspection ({PROGRAM_NAME}.py v{PROGRAM_VERSION} Build {PROGRAM_BUILD}) ===", verbose=args.verbose)
    findings, proposals = audit_facts(verbose=args.verbose, debug=args.debug)
    report_md, report_csv = generate_reports(findings, proposals)

    errs = sum(1 for x in findings if x["level"] == "ERROR")
    warns = sum(1 for x in findings if x["level"] == "WARN")
    infos = sum(1 for x in findings if x["level"] == "INFO")

    log_line("--- SUMMARY ---", level="INFO", verbose=args.verbose)
    log_line(f"Total Findings: {len(findings)} | Errors: {errs} | Warnings: {warns} | Proposals: {len(proposals)} | Reciprocal: {infos}", level="INFO", verbose=args.verbose)
    log_line(f"Audit completed. Report: {report_md.name}", level="INFO", verbose=True)
    log_line(f"Remediation candidates: {report_csv.name}", level="INFO", verbose=True)
    log_line(f"=== Fact Registry Inspection Complete ({PROGRAM_NAME}.py v{PROGRAM_VERSION} Build {PROGRAM_BUILD}) ===", level="INFO", verbose=args.verbose)


if __name__ == "__main__":
    main()