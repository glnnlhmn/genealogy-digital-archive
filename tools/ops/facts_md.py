# Name: facts_md.py
# Path: tools/ops/facts_md.py

"""
Operational tool for fact registry inspection, remediation, and markdown export.

Operational Role:
    Serves as the Stage 1 & Stage 4 First-Aid Remediation Engine for data/entities/facts.json.
    Integrates with GDAFacts transactional registry container to repair malformed fact types,
    non-conforming note structures, invalid date modifiers, and unilateral marriage unions.

Invariants:
    - fact_id UUIDv4 values are strictly immutable and never altered.
    - All automated provenance notes follow the title format 'Recorded by <prog>.<outer_method>'.
    - Multi-assertion duplicate consolidation is deferred to facts_merge.py.
    - Schema resolution is strict: no hardcoded enum fallbacks are permitted.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from typing import Any

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDAFacts import GDAFacts

__version__ = "1.0.0+build.20260928.4"

# Exact-match synonyms mapping to canonical schema-defined fact types
FACT_TYPE_SYNONYM_MAP: dict[str, str] = {
    "christening": "Baptism",
    "infant baptism": "Baptism",
    "adult baptism": "Baptism",
    "immersion": "Baptism",
    "dedication": "Baptism",
    "born": "Birth",
    "nativity": "Birth",
    "buried": "Burial",
    "interment": "Burial",
    "cremation": "Burial",
    "entombment": "Burial",
    "funeral": "Burial",
    "deceased": "Death",
    "died": "Death",
    "demise": "Death",
    "passing": "Death",
    "annulment": "Divorce",
    "dissolution of marriage": "Divorce",
    "legal separation": "Divorce",
    "divorce filing": "Divorce",
    "matrimony": "Marriage",
    "nuptials": "Marriage",
    "wedding": "Marriage",
    "marriage banns": "Marriage",
    "marriage bond": "Marriage",
    "marriage license": "Marriage",
    "address": "Residence",
    "lived at": "Residence",
    "domicile": "Residence",
    "abode": "Residence",
    "enumeration": "Census",
    "population schedule": "Census",
    "tax list": "Census",
    "electoral roll": "Census",
}

# Date modifier synonyms mapping to canonical schema enums
DATE_MODIFIER_MAP: dict[str, str] = {
    "ABOUT": "ABT",
    "ABT": "ABT",
    "CIRCA": "ABT",
    "C": "ABT",
    "CA": "ABT",
    "APP": "ABT",
    "BEFORE": "BEF",
    "BEF": "BEF",
    "BY": "BEF",
    "AFTER": "AFT",
    "AFT": "AFT",
    "ESTIMATED": "EST",
    "EST": "EST",
    "APPROX": "EST",
    "BETWEEN": "BET",
    "BET": "BET",
    "EXACT": "EXACT",
}


def _get_allowed_enums(enum_key: str) -> list[str]:
    """Retrieves allowed enum values strictly from _enums.schema.json.

    Raises:
        FileNotFoundError: If _enums.schema.json does not exist.
        KeyError: If enum_key is not defined in $defs.
        ValueError: If the enum definition is empty or invalid.
    """
    schema_path = CONFIG.schema_defs / "_enums.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Canonical schema definitions not found at '{schema_path}'")

    data = json.loads(schema_path.read_text(encoding="utf-8"))
    defs = data.get("$defs", {})
    if enum_key not in defs:
        raise KeyError(f"Enum key '{enum_key}' not defined in '{schema_path}'")

    enum_vals = defs[enum_key].get("enum")
    if not isinstance(enum_vals, list) or not enum_vals:
        raise ValueError(f"Enum key '{enum_key}' contains no valid enum choices in '{schema_path}'")

    return enum_vals


def _remedy_fact_type(
    fact: dict[str, Any],
    unresolved_queue: list[dict[str, Any]] | None = None,
    allow_fallback: bool = True,
    outer_method: str = "facts_md.remedy_facts",
) -> bool:
    """Remediates non-conforming, lowercase, or synonym fact_type attributes."""
    current_type = fact.get("fact_type")
    if not current_type or not isinstance(current_type, str):
        return False

    allowed_types = _get_allowed_enums("enum_fact_type")
    if current_type in allowed_types:
        return False

    # 1. Casing normalization
    for allowed in allowed_types:
        if current_type.strip().lower() == allowed.lower():
            fact["fact_type"] = allowed
            return True

    # 2. Known synonym matching
    lookup_key = current_type.strip().lower()
    if lookup_key in FACT_TYPE_SYNONYM_MAP:
        mapped_type = FACT_TYPE_SYNONYM_MAP[lookup_key]
        if mapped_type in allowed_types:
            fact["fact_type"] = mapped_type
            return True

    # 3. Queue for interactive resolution or fallback to Other
    if unresolved_queue is not None:
        unresolved_queue.append(fact)
        return False

    if allow_fallback:
        original = fact["fact_type"]
        fact["fact_type"] = "Other"

        notes = fact.setdefault("notes", [])
        if not isinstance(notes, list):
            notes = []
            fact["notes"] = notes

        note_id = f"NOT-{len(notes) + 1:05d}"
        notes.append(
            {
                "note_id": note_id,
                "category": "PROVENANCE",
                "title": f"Recorded by {outer_method}",
                "text": f"Remediated non-conforming fact_type '{original}' to 'Other'.",
            }
        )
        return True

    return False


def _remedy_notes_structure(
    fact: dict[str, Any],
    outer_method: str = "facts_md.remedy_facts",
) -> bool:
    """Normalizes notes into sequentially numbered dictionaries conforming to note_entry."""
    raw_notes = fact.get("notes")
    if raw_notes is None:
        return False

    allowed_categories = _get_allowed_enums("enum_note_category")
    clean_notes: list[dict[str, Any]] = []

    # Handle raw string note
    if isinstance(raw_notes, str):
        text = raw_notes.strip()
        if text:
            clean_notes.append(
                {
                    "note_id": "NOT-00001",
                    "category": "GENERAL",
                    "title": None,
                    "text": text,
                }
            )
        fact["notes"] = clean_notes
        return True

    if not isinstance(raw_notes, list):
        fact["notes"] = []
        return True

    for entry in raw_notes:
        if isinstance(entry, str):
            text = entry.strip()
            if text:
                clean_notes.append(
                    {
                        "note_id": "",
                        "category": "GENERAL",
                        "title": None,
                        "text": text,
                    }
                )
        elif isinstance(entry, dict):
            text = entry.get("text")
            title = entry.get("title")

            if (not text or not str(text).strip()) and title and str(title).strip():
                text = str(title).strip()

            if not text or not str(text).strip():
                continue

            clean_text = str(text).strip()
            clean_title = str(title).strip() if title and str(title).strip() else None

            category = entry.get("category")
            if not category or category not in allowed_categories:
                category = "GENERAL"

            clean_notes.append(
                {
                    "note_id": "",
                    "category": category,
                    "title": clean_title,
                    "text": clean_text,
                }
            )

    # Renumber sequentially
    for idx, note in enumerate(clean_notes, start=1):
        note["note_id"] = f"NOT-{idx:05d}"

    if clean_notes == raw_notes:
        return False

    fact["notes"] = clean_notes
    return True


def _remedy_date_modifier(fact: dict[str, Any]) -> bool:
    """Standardizes date modifiers and clears date_end for non-range modifiers."""
    date_obj = fact.get("date_interpreted")
    if not isinstance(date_obj, dict):
        return False

    allowed_modifiers = _get_allowed_enums("enum_date_modifier")
    modified = False
    raw_mod = date_obj.get("modifier")

    if isinstance(raw_mod, str):
        cleaned_mod = raw_mod.strip().upper().rstrip(".")
        if cleaned_mod in DATE_MODIFIER_MAP:
            target_mod = DATE_MODIFIER_MAP[cleaned_mod]
            if target_mod in allowed_modifiers and raw_mod != target_mod:
                date_obj["modifier"] = target_mod
                modified = True

    current_mod = date_obj.get("modifier")
    # If modifier does not represent a date range, end date must be null
    if current_mod not in {"BET", "FROM", "TO"}:
        if date_obj.get("date_end") is not None:
            date_obj["date_end"] = None
            modified = True

    return modified


def _remedy_reciprocal_union(
    facts_mgr: GDAFacts,
    fact: dict[str, Any],
    outer_method: str = "facts_md.remedy_facts",
) -> bool:
    """Synthesizes reciprocal marriage/divorce assertions for unlinked spouses."""
    fact_type = fact.get("fact_type")
    if fact_type not in {"Marriage", "Divorce"}:
        return False

    person_id = fact.get("person_id")
    if not person_id:
        return False

    associated = fact.get("associated_people", [])
    if not isinstance(associated, list):
        return False

    # Discover spouse
    spouse_id: str | None = None
    for person in associated:
        if isinstance(person, dict) and person.get("role") in {"Spouse", "Husband", "Wife"}:
            candidate_pid = person.get("person_id")
            if candidate_pid and isinstance(candidate_pid, str):
                spouse_id = candidate_pid
                break

    if not spouse_id:
        return False

    # Check if reciprocal assertion already exists for spouse
    spouse_facts = facts_mgr.get_by_person(spouse_id)
    for s_fact in spouse_facts:
        if s_fact.get("fact_type") == fact_type:
            s_assoc = s_fact.get("associated_people", [])
            if any(isinstance(p, dict) and p.get("person_id") == person_id for p in s_assoc):
                return False

    # Invert associated people
    reciprocal_assoc: list[dict[str, Any]] = [
        {
            "person_id": person_id,
            "role": "Spouse",
        }
    ]

    for p in associated:
        if isinstance(p, dict):
            pid = p.get("person_id")
            role = p.get("role")
            if pid != spouse_id and role not in {"Spouse", "Husband", "Wife"}:
                reciprocal_assoc.append(dict(p))

    # Clone and prepare notes
    source_notes = fact.get("notes", [])
    reciprocal_notes = [dict(n) for n in source_notes if isinstance(n, dict)]
    next_idx = len(reciprocal_notes) + 1
    reciprocal_notes.append(
        {
            "note_id": f"NOT-{next_idx:05d}",
            "category": "PROVENANCE",
            "title": f"Recorded by {outer_method}",
            "text": f"Automatically generated reciprocal {fact_type} fact derived from canonical assertion {fact.get('fact_id')}.",
        }
    )

    new_fact: dict[str, Any] = {
        "fact_id": str(uuid.uuid4()),
        "person_id": spouse_id,
        "fact_type": fact_type,
        "associated_people": reciprocal_assoc,
        "notes": reciprocal_notes,
    }

    if "date_interpreted" in fact:
        new_fact["date_interpreted"] = fact["date_interpreted"]
    if "location" in fact:
        new_fact["location"] = fact["location"]
    if "citations" in fact:
        new_fact["citations"] = fact["citations"]
    if "record_urn" in fact:
        new_fact["record_urn"] = fact["record_urn"]

    return facts_mgr.add(new_fact)


def remedy_facts(
    facts_mgr: GDAFacts,
    target_ids: set[str] | None = None,
    interactive: bool = False,
) -> dict[str, int]:
    """Coordinates and executes the multi-remedy First-Aid remediation pipeline."""
    stats = {
        "fact_type_fixed": 0,
        "notes_fixed": 0,
        "dates_fixed": 0,
        "reciprocals_added": 0,
        "unresolved_manual": 0,
    }

    unresolved_types: list[dict[str, Any]] = []
    scope_facts = [
        f for f in facts_mgr if target_ids is None or f.get("fact_id") in target_ids
    ]

    for fact in scope_facts:
        fid = fact.get("fact_id")
        if not fid:
            continue

        mutated = False

        if _remedy_fact_type(fact, unresolved_queue=unresolved_types if interactive else None):
            stats["fact_type_fixed"] += 1
            mutated = True

        if _remedy_notes_structure(fact):
            stats["notes_fixed"] += 1
            mutated = True

        if _remedy_date_modifier(fact):
            stats["dates_fixed"] += 1
            mutated = True

        if mutated:
            facts_mgr.mark_dirty(fid)

    # Reciprocal assertions pass
    for fact in list(scope_facts):
        if _remedy_reciprocal_union(facts_mgr, fact):
            stats["reciprocals_added"] += 1

    # Interactive manual triage
    if interactive and unresolved_types:
        print(f"\nFound {len(unresolved_types)} fact(s) with unrecognized fact_type.")
        choice = input("Would you like to review these manually? [Y/n]: ").strip().lower()
        if choice in {"y", "yes", ""}:
            allowed = sorted(list(_get_allowed_enums("enum_fact_type")))
            for fact in unresolved_types:
                fid = fact.get("fact_id")
                curr = fact.get("fact_type")
                print(f"\nFact ID: {fid} | Current Type: '{curr}'")
                print(f"Allowed types: {', '.join(allowed)}")
                val = input("Enter replacement fact_type (or press Enter for 'Other'): ").strip()
                if val in allowed:
                    fact["fact_type"] = val
                    stats["fact_type_fixed"] += 1
                else:
                    fact["fact_type"] = "Other"
                    stats["fact_type_fixed"] += 1
                if fid:
                    facts_mgr.mark_dirty(fid)
        else:
            for fact in unresolved_types:
                _remedy_fact_type(fact, allow_fallback=True)
                stats["fact_type_fixed"] += 1
                fid = fact.get("fact_id")
                if fid:
                    facts_mgr.mark_dirty(fid)

    return stats


def main() -> None:
    """CLI execution entrypoint."""
    parser = argparse.ArgumentParser(
        description="First-Aid Remediation Engine & Fact Synchronizer"
    )
    parser.add_argument("-r", "--run", "--apply", action="store_true", help="Commit remediations to disk")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive prompt for unresolved records")
    parser.add_argument("--facts", nargs="+", help="Specific fact UUIDs to remediate")
    args = parser.parse_args()

    logger = logging.getLogger("facts_md")
    targets = set(args.facts) if args.facts else None

    with GDAFacts(auto_commit=args.run, logger=logger) as facts_mgr:
        stats = remedy_facts(facts_mgr, target_ids=targets, interactive=args.interactive)
        print(f"Remediation summary: {stats}")

    if not args.run:
        print("\nDry-run completed. Run with -r/--apply to commit changes to disk.")


if __name__ == "__main__":
    main()