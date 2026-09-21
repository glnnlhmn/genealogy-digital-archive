# Name: facts_insp.py
# Path: tools/ops/facts_insp.py

"""
Read-only operational inspection tool to audit facts.json integrity:
- Schema conformance (UUID/GUID pattern checks classified as WARN)
- Typology and controlled vocabulary via SchemaEnums (classified as ERROR)
- Temporal and modifier validity via SchemaEnums (classified as ERROR)
- Biological & chronological plausibility against people.json (classified as ERROR)
  * Deep resolution of vitals.birth, vitals.death, and canonical_name years
  * Exempts post-mortem 'Parentage' (parent documented on child vital records post-mortem)
- Duplicate extractions (Dedup-Source and Dedup-Event classified as WARN)
- Relational reciprocal consistency (strictly classified as INFO)
- Enriched log formatting: FCT <short_id> (<person_id> (<full_name>))
- Multi-variant name resolution across canonical_name, name, names, and root strings
- System execution traces prefixed with [SYS]
- Robust extraction of singular/array record_urn from fact['source']
- Conditional CSV export (only when merge proposals exist)
- Audit summary emitted to JSON in reports/

Version: 1.0.0 Build 20
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path("G:/My Drive/genealogy-digital-archive")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.lib.gda_core.registry import SchemaEnums

__version__ = "1.0.0"
__build__ = 20

FACTS_PATH = ROOT_DIR / "data/entities/facts.json"
PEOPLE_PATH = ROOT_DIR / "data/entities/people.json"
LOGS_DIR = ROOT_DIR / "logs"
REPORTS_DIR = ROOT_DIR / "reports"

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

SPOUSE_ROLES = {"spouse", "husband", "wife", "partner", "fiancé", "fiancee", "groom", "bride"}
POST_MORTEM_ALLOWED_TYPES = {"Burial", "Death", "Probate", "Association", "Parentage"}


def setup_logger(timestamp: str):
    """Initializes execution logging to logs/."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"facts_insp-{timestamp}.log"

    def log(message: str, level: str = "SYS", to_stderr: bool = False):
        formatted = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}"
        if to_stderr:
            sys.stderr.write(formatted + "\n")
        else:
            print(formatted)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")

    return log


def extract_year(date_val) -> int | None:
    """Extracts a 4-digit calendar year from date field variants."""
    if not date_val:
        return None
    if isinstance(date_val, int):
        return date_val if 1000 <= date_val <= 2100 else None
    if isinstance(date_val, dict):
        if "year" in date_val and isinstance(date_val["year"], int):
            return date_val["year"]
        date_val = (
            date_val.get("date")
            or date_val.get("date_start")
            or date_val.get("raw_text")
            or date_val.get("raw")
            or ""
        )
    match = re.search(r"\b(1[6-9]\d{2}|20\d{2})\b", str(date_val))
    return int(match.group(1)) if match else None


def normalize_date_str(date_val) -> str:
    """Normalizes date structure into comparable string representation."""
    if not date_val:
        return ""
    if isinstance(date_val, dict):
        return str(
            date_val.get("date")
            or date_val.get("date_start")
            or date_val.get("raw_text")
            or date_val.get("raw")
            or ""
        ).strip()
    return str(date_val).strip()


def extract_source_keys(fact: dict) -> list[str]:
    """
    Extracts a deduplicated list of source/record URN strings from a fact.
    Handles scalar strings, lists of strings, and nested dictionaries across:
      - fact['source']['record_urn']
      - fact['source']['source_urn']
      - fact['sources'][*]['record_urn']
      - fact['record_urn'], fact['source_urn'], fact['source_reference']
    """
    keys = set()

    def _collect(val):
        if not val:
            return
        if isinstance(val, str):
            cleaned = val.strip()
            if cleaned:
                keys.add(cleaned)
        elif isinstance(val, list):
            for item in val:
                _collect(item)
        elif isinstance(val, dict):
            for attr in ("record_urn", "source_urn", "urn", "source_id", "source_reference"):
                if attr in val:
                    _collect(val[attr])

    if "source" in fact:
        _collect(fact["source"])
    if "sources" in fact:
        _collect(fact["sources"])
    for top_attr in ("record_urn", "source_urn", "source_reference", "source_id"):
        if top_attr in fact:
            _collect(fact[top_attr])

    return sorted(keys)


def extract_person_name(person: dict, default_id: str) -> str:
    """Extracts formatted display name across all person schema variations."""
    if not isinstance(person, dict):
        return default_id

    # 1. Direct display_name string
    if isinstance(person.get("display_name"), str) and person["display_name"].strip():
        return person["display_name"].strip()

    # 2. Canonical name
    canonical = person.get("canonical_name")
    if isinstance(canonical, dict):
        name = canonical.get("full") or canonical.get("display") or canonical.get("name")
        if name:
            return str(name).strip()
        given = canonical.get("given") or ""
        middle = canonical.get("middle") or ""
        surname = canonical.get("surname") or ""
        parts = [p for p in (given, middle, surname) if p]
        if parts:
            return " ".join(parts).strip()
    elif isinstance(canonical, str) and canonical.strip():
        return canonical.strip()

    # 3. Name object or string
    name_obj = person.get("name")
    if isinstance(name_obj, dict):
        name = name_obj.get("display_name") or name_obj.get("full") or name_obj.get("display")
        if name:
            return str(name).strip()
    elif isinstance(name_obj, str) and name_obj.strip():
        return name_obj.strip()

    # 4. Names array
    names = person.get("names")
    if isinstance(names, list) and names:
        first = names[0]
        if isinstance(first, dict):
            name = first.get("full") or first.get("display") or first.get("display_name")
            if name:
                return str(name).strip()
        elif isinstance(first, str) and first.strip():
            return first.strip()

    return default_id


def extract_person_lifespan(person: dict) -> tuple[int | None, int | None]:
    """
    Extracts birth and death calendar years across all schema representations:
      - person['vitals']['birth']['date']
      - person['vitals']['death']['date']
      - person['canonical_name']['birth_year']['year']
      - person['canonical_name']['death_year']['year']
      - person['events'] / person['vitals'] arrays
      - person['birth'] / person['death'] root objects
    """
    if not isinstance(person, dict):
        return None, None

    b_year = None
    d_year = None

    def _resolve_year(val) -> int | None:
        if not val:
            return None
        if isinstance(val, int):
            return val if 1000 <= val <= 2100 else None
        if isinstance(val, dict):
            if "year" in val and isinstance(val["year"], int):
                return val["year"]
            sub_date = val.get("date")
            if sub_date:
                res = _resolve_year(sub_date)
                if res:
                    return res
            for field in ("date_start", "date_end", "raw_text", "raw", "year"):
                if field in val:
                    res = extract_year(val[field])
                    if res:
                        return res
        return extract_year(val)

    # 1. Structured vitals wrapper
    vitals = person.get("vitals")
    if isinstance(vitals, dict):
        if "birth" in vitals:
            b_year = _resolve_year(vitals["birth"])
        if "death" in vitals:
            d_year = _resolve_year(vitals["death"])

    # 2. Canonical name year integers
    canonical = person.get("canonical_name")
    if isinstance(canonical, dict):
        if not b_year and "birth_year" in canonical:
            b_year = _resolve_year(canonical["birth_year"])
        if not d_year and "death_year" in canonical:
            d_year = _resolve_year(canonical["death_year"])

    # 3. Direct root attributes
    if not b_year and "birth" in person:
        b_year = _resolve_year(person["birth"])
    if not b_year and "birth_date" in person:
        b_year = _resolve_year(person["birth_date"])
    if not b_year and "birth_year" in person:
        b_year = _resolve_year(person["birth_year"])

    if not d_year and "death" in person:
        d_year = _resolve_year(person["death"])
    if not d_year and "death_date" in person:
        d_year = _resolve_year(person["death_date"])
    if not d_year and "death_year" in person:
        d_year = _resolve_year(person["death_year"])

    # 4. Events or vitals array traversal
    events = person.get("events")
    if isinstance(events, list):
        for ev in events:
            if isinstance(ev, dict):
                ev_type = str(ev.get("type") or ev.get("event_type") or "").lower()
                if "birth" in ev_type and not b_year:
                    b_year = _resolve_year(ev.get("date") or ev)
                elif "death" in ev_type and not d_year:
                    d_year = _resolve_year(ev.get("date") or ev)

    return b_year, d_year


def load_people() -> dict[str, dict]:
    """Loads people registry mapping person_id across all registry structures."""
    if not PEOPLE_PATH.exists():
        return {}
    try:
        data = json.loads(PEOPLE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    people_map = {}
    if isinstance(data, list):
        for p in data:
            if isinstance(p, dict) and p.get("person_id"):
                people_map[p["person_id"]] = p
    elif isinstance(data, dict):
        candidates = data.get("people") or data.get("persons") or data.get("records")
        if isinstance(candidates, list):
            for p in candidates:
                if isinstance(p, dict) and p.get("person_id"):
                    people_map[p["person_id"]] = p
        elif isinstance(candidates, dict):
            for k, v in candidates.items():
                if isinstance(v, dict):
                    pid = v.get("person_id") or k
                    people_map[pid] = v
        else:
            for k, v in data.items():
                if isinstance(v, dict):
                    pid = v.get("person_id") or k
                    people_map[pid] = v
    return people_map


def format_subject_label(person_id: str | None, people_map: dict[str, dict]) -> str:
    """Formats person reference as 'IND-XXXXX (Full Name)'."""
    if not person_id:
        return "N/A"
    person = people_map.get(person_id, {})
    name = extract_person_name(person, person_id)
    return f"{person_id} ({name})"


def short_fact_id(fact_id: str) -> str:
    """Extracts short 8-char identifier for log formatting."""
    cleaned = fact_id.replace("factoid-", "")
    return cleaned[:8]


def write_audit_deliverables(
    timestamp: str,
    total_facts: int,
    findings: list[dict],
    merge_candidates: list[dict],
) -> tuple[Path, Path | None]:
    """Generates JSON audit summary and exports CSV only if merge proposals exist."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_json_path = REPORTS_DIR / f"facts_audit_summary_{timestamp}.json"
    csv_file: Path | None = None

    if merge_candidates:
        csv_file = REPORTS_DIR / f"fact_merge_candidates_{timestamp}.csv"
        csv_headers = ["Primary Fact ID", "Absorbed IDs", "Subject", "Fact Type", "Rationale"]
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(csv_headers)
            for row in merge_candidates:
                writer.writerow([
                    row["primary_id"],
                    row["absorbed_ids"].replace("<br>", "; "),
                    row["subject"],
                    row["fact_type"],
                    row["rationale"],
                ])

    error_count = sum(1 for item in findings if item["level"] == "ERROR")
    warn_count = sum(1 for item in findings if item["level"] == "WARN")
    info_count = sum(1 for item in findings if item["level"] == "INFO")

    category_counts: dict[str, int] = {}
    for item in findings:
        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    summary_data = {
        "timestamp": timestamp,
        "engine": f"facts_insp v{__version__} (Build {__build__})",
        "total_facts_audited": total_facts,
        "total_findings": len(findings),
        "counts": {
            "errors": error_count,
            "warnings": warn_count,
            "info": info_count,
            "proposals": len(merge_candidates),
        },
        "distribution_by_category": category_counts,
        "merge_candidates_exported": str(csv_file.name) if csv_file else None,
        "findings": findings,
    }

    report_json_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return report_json_path, csv_file


def inspect_facts(verbose: bool = False, debug: bool = False) -> int:
    """Performs full archival integrity inspection on facts.json."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = setup_logger(timestamp)
    log(f"=== Commencing Fact Registry Inspection (facts_insp.py v{__version__} Build {__build__}) ===")

    if not FACTS_PATH.exists():
        log(f"Target facts file missing at: {FACTS_PATH}", level="ERROR", to_stderr=True)
        return 1

    try:
        facts_data = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"Failed to parse {FACTS_PATH}: {e}", level="ERROR", to_stderr=True)
        return 1

    records = facts_data if isinstance(facts_data, list) else facts_data.get("facts", [])
    log(f"Loaded {len(records)} fact records for evaluation")

    people_map = load_people()
    log(f"Loaded {len(people_map)} reference entities from people.json")

    findings = []
    merge_candidates = []

    source_urn_tracker: dict[tuple, list[str]] = {}
    event_tracker: dict[tuple, list[str]] = {}
    marriages_by_person: dict[str, set[tuple[str, str]]] = {}

    log("[Stage-1] --- Record Validation ---")
    log("[Stage-1.1] Verifying Identifier Formats & Registry References...")
    s1_issues = 0

    for idx, fact in enumerate(records):
        fact_id = fact.get("fact_id", f"INDEX_{idx}")
        person_id = fact.get("person_id")
        ftype = fact.get("fact_type")
        fact_year = extract_year(fact.get("date"))
        date_str = normalize_date_str(fact.get("date"))
        subj_label = format_subject_label(person_id, people_map)
        fct_short = short_fact_id(fact_id)

        # 1. Schema Validation (WARN)
        if not UUID_PATTERN.match(str(fact_id)):
            msg = f"Identifier does not conform to standard GUID/UUID format: '{fact_id}'."
            findings.append({
                "level": "WARN",
                "category": "Schema",
                "fact_id": fact_id,
                "person_id": person_id,
                "message": msg,
            })
            log(f"[Schema] FCT {fct_short} ({subj_label}): {msg}", level="WARN", to_stderr=debug)
            s1_issues += 1

        # 2. Typology (ERROR)
        if not SchemaEnums.is_valid("enum_fact_type", ftype):
            msg = f"Invalid fact_type '{ftype}' not in controlled vocabulary."
            findings.append({
                "level": "ERROR",
                "category": "Typology",
                "fact_id": fact_id,
                "person_id": person_id,
                "message": msg,
            })
            log(f"[Typology] FCT {fct_short} ({subj_label}): {msg}", level="ERROR", to_stderr=debug)

        # 3. Temporal (ERROR)
        date_obj = fact.get("date")
        if isinstance(date_obj, dict):
            modifier = date_obj.get("modifier")
            if modifier is not None and not SchemaEnums.is_valid("enum_date_modifier", modifier):
                msg = f"Unrecognized date modifier '{modifier}'."
                findings.append({
                    "level": "ERROR",
                    "category": "Temporal",
                    "fact_id": fact_id,
                    "person_id": person_id,
                    "message": msg,
                })
                log(f"[Temporal] FCT {fct_short} ({subj_label}): {msg}", level="ERROR", to_stderr=debug)

        # 4. Biological & Chronological Plausibility (ERROR)
        if person_id and person_id in people_map and fact_year:
            person = people_map[person_id]
            b_year, d_year = extract_person_lifespan(person)

            if b_year and fact_year < b_year:
                msg = f"Pre-natal event: '{ftype}' in {fact_year} occurs before subject birth ({b_year})."
                findings.append({
                    "level": "ERROR",
                    "category": "Biological",
                    "fact_id": fact_id,
                    "person_id": person_id,
                    "message": msg,
                })
                log(f"[Biological] FCT {fct_short} ({subj_label}): {msg}", level="ERROR", to_stderr=debug)

            if d_year and fact_year > (d_year + 1) and ftype not in POST_MORTEM_ALLOWED_TYPES:
                msg = f"Post-mortem event: '{ftype}' in {fact_year} occurs after subject death ({d_year})."
                findings.append({
                    "level": "ERROR",
                    "category": "Biological",
                    "fact_id": fact_id,
                    "person_id": person_id,
                    "message": msg,
                })
                log(f"[Biological] FCT {fct_short} ({subj_label}): {msg}", level="ERROR", to_stderr=debug)

        # 5. Deduplication Indexing
        source_keys = extract_source_keys(fact)
        if person_id and ftype and source_keys:
            for skey in source_keys:
                src_sig = (person_id, ftype, skey)
                source_urn_tracker.setdefault(src_sig, []).append(fact_id)

        if person_id and ftype and date_str:
            event_sig = (person_id, ftype, date_str)
            event_tracker.setdefault(event_sig, []).append(fact_id)

        # 6. Relational Reciprocal Indexing
        if ftype == "Marriage" and person_id:
            for assoc in fact.get("associated_people", []):
                if isinstance(assoc, dict):
                    rel = (assoc.get("relationship") or assoc.get("role") or "").lower().strip()
                    target_id = assoc.get("person_id")
                    if target_id and rel in SPOUSE_ROLES:
                        marriages_by_person.setdefault(person_id, set()).add((target_id, fact_id))

    log(f"[Stage-1.1] Completed: {s1_issues} issues detected")

    # Stage 3: Duplicate Discovery & Merges
    log("[Stage-3] --- Duplicate Discovery & Merge Proposals ---")
    merged_fact_ids: set[str] = set()

    for (pid, ftype, urn), fids in source_urn_tracker.items():
        unique_fids = list(dict.fromkeys(fids))
        if len(unique_fids) > 1:
            primary = unique_fids[0]
            absorbed = unique_fids[1:]
            merged_fact_ids.update(unique_fids)
            msg = f"{len(unique_fids)} redundant extractions for '{ftype}' from identical source URN."
            findings.append({
                "level": "WARN",
                "category": "Dedup-Source",
                "fact_id": primary,
                "person_id": pid,
                "message": msg,
            })
            fct_short = short_fact_id(primary)
            subj_label = format_subject_label(pid, people_map)
            log(f"[Dedup-Source] FCT {fct_short} ({subj_label}): {msg}", level="WARN", to_stderr=debug)
            merge_candidates.append({
                "primary_id": primary,
                "absorbed_ids": "<br>".join(absorbed),
                "subject": pid,
                "fact_type": ftype,
                "rationale": "Duplicate extraction from identical source URN",
            })

    for (pid, ftype, d_str), fids in event_tracker.items():
        unique_fids = list(dict.fromkeys(fids))
        if len(unique_fids) > 1:
            unmerged = [fid for fid in unique_fids if fid not in merged_fact_ids]
            if len(unmerged) > 1:
                primary = unmerged[0]
                absorbed = unmerged[1:]
                msg = f"{len(unmerged)} multi-source records match '{ftype}' ({d_str}) representing same real-world event."
                findings.append({
                    "level": "WARN",
                    "category": "Dedup-Event",
                    "fact_id": primary,
                    "person_id": pid,
                    "message": msg,
                })
                fct_short = short_fact_id(primary)
                subj_label = format_subject_label(pid, people_map)
                log(f"[Dedup-Event] FCT {fct_short} ({subj_label}): {msg}", level="WARN", to_stderr=debug)
                merge_candidates.append({
                    "primary_id": primary,
                    "absorbed_ids": "<br>".join(absorbed),
                    "subject": pid,
                    "fact_type": ftype,
                    "rationale": "Multi-source corroboration of identical event",
                })

    log(f"[Stage-3] Completed: {len(merge_candidates)} merge candidates proposed")

    # Stage 4: Relational Consistency
    log("[Stage-4] --- Relational Consistency & Reciprocal Pairing ---")
    rel_count = 0
    for p1_id, partner_facts in marriages_by_person.items():
        for p2_id, fact_id in partner_facts:
            p2_partners = {t[0] for t in marriages_by_person.get(p2_id, set())}
            if p1_id not in p2_partners:
                p2_name = extract_person_name(people_map.get(p2_id, {}), p2_id)
                msg = f"Partner {p2_id} ({p2_name}) has no reciprocal 'Marriage' fact asserted."
                findings.append({
                    "level": "INFO",
                    "category": "Relational",
                    "fact_id": fact_id,
                    "person_id": p1_id,
                    "message": msg,
                })
                fct_short = short_fact_id(fact_id)
                subj_label = format_subject_label(p1_id, people_map)
                log(f"[Relational] FCT {fct_short} ({subj_label}): {msg}", level="INFO", to_stderr=debug)
                rel_count += 1

    log(f"[Stage-4] Completed: {rel_count} unreciprocated partner assertions")

    report_json, csv_file = write_audit_deliverables(
        timestamp,
        len(records),
        findings,
        merge_candidates,
    )

    errors = sum(1 for item in findings if item["level"] == "ERROR")
    warnings = sum(1 for item in findings if item["level"] == "WARN")
    infos = sum(1 for item in findings if item["level"] == "INFO")

    log("--- SUMMARY ---")
    log(
        f"Total Findings: {len(findings)} | Errors: {errors} | Warnings: {warnings} | "
        f"Proposals: {len(merge_candidates)} | Reciprocal: {infos}"
    )
    log(f"Audit completed. Summary JSON: {report_json.name}")
    if csv_file:
        log(f"Remediation candidates: {csv_file.name}")
    else:
        log("No merge candidates identified; CSV output skipped.")

    log(f"=== Fact Registry Inspection Complete (facts_insp.py v{__version__} Build {__build__}) ===")

    return 0 if errors == 0 else 2


def main():
    parser = argparse.ArgumentParser(
        description="Full audit inspection engine for facts.json across schema, typology, temporal, and relational rules."
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Emit diagnostic logs to session log."
    )
    parser.add_argument(
        "--debug", action="store_true", help="Route runtime traces directly to sys.stderr."
    )
    args = parser.parse_args()

    exit_code = inspect_facts(verbose=args.verbose, debug=args.debug)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()