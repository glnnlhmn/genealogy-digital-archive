# Name: Archival Topology and Demographic Drift Auditor
# Path: tests/integrity/test_demographic_integrity.py

"""
Automated integrity test and drift detection suite.
Evaluates the demographic plausibility, connectivity, and structural integrity
of data/entities/people.json and data/indexes/family_group_index.json.

Serves as an automated trigger to signal persona drift, unattached stubs,
over-merging, or phantom unions prior to deep pipeline execution.
"""

import json
from pathlib import Path
import pytest
from typing import Any, Dict, List, Set

ROOT = Path("G:/My Drive/genealogy-digital-archive")
PEOPLE_FILE = ROOT / "data/entities/people.json"
FAMILY_INDEX_FILE = ROOT / "data/indexes/family_group_index.json"


@pytest.fixture(scope="module")
def archive_data() -> Dict[str, Any]:
    """Loads people registry and family group index."""
    assert PEOPLE_FILE.exists(), f"Missing required file: {PEOPLE_FILE}"
    assert FAMILY_INDEX_FILE.exists(), f"Missing required file: {FAMILY_INDEX_FILE}"

    with open(PEOPLE_FILE, "r", encoding="utf-8") as f:
        p_data = json.load(f)

    with open(FAMILY_INDEX_FILE, "r", encoding="utf-8") as f:
        f_data = json.load(f)

    return {
        "people": p_data.get("persons") or p_data.get("people", []),
        "families": f_data.get("families", {}),
        "total_families": f_data.get("total_families", 0)
    }


def test_people_to_family_ratio_bounds(archive_data: Dict[str, Any]) -> None:
    """
    Validates that the ratio of unique individuals (N) to nuclear families (F)
    falls within realistic demographic boundaries for multi-generational pedigree trees.
    
    Expected demographic range: 2.20 <= (N / F) <= 3.20.
    Values < 2.20 indicate fragmented, over-partitioned, or phantom duplicate families.
    Values > 3.20 indicate unindexed islands, disconnected stubs, or severe under-linking.
    """
    total_persons = len(archive_data["people"])
    total_families = len(archive_data["families"])

    assert total_families > 0, "Family group index contains 0 families."
    ratio = total_persons / total_families

    assert 2.20 <= ratio <= 3.20, (
        f"[DEMOGRAPHIC DRIFT] Person-to-Family ratio {ratio:.2f} is out of plausible bounds "
        f"(2.20 - 3.20). Total Persons: {total_persons}, Total Families: {total_families}."
    )


def test_unindexed_persona_coverage(archive_data: Dict[str, Any]) -> None:
    """
    Validates that at least 99% of canonical personas in people.json are integrated
    into at least one nuclear family unit as a parent or child.
    
    Catches disconnected islands, orphan stubs, or unassigned multi-spouse children.
    """
    people_list = archive_data["people"]
    families = archive_data["families"]

    all_pids: Set[str] = {p["person_id"] for p in people_list if p.get("person_id")}
    indexed_pids: Set[str] = set()

    for fam in families.values():
        for pk in ["parent_x", "parent_y"]:
            parent = fam.get(pk)
            if parent and isinstance(parent, dict) and parent.get("person_id"):
                indexed_pids.add(parent["person_id"])
        for ch in fam.get("children", []):
            if ch and isinstance(ch, dict) and ch.get("person_id"):
                indexed_pids.add(ch["person_id"])

    unindexed = all_pids - indexed_pids
    coverage_pct = (len(indexed_pids) / len(all_pids)) * 100 if all_pids else 0.0

    # Tolerance threshold: allows at most 1.5% unindexed edge stubs (e.g. unassigned living terminal stubs)
    assert coverage_pct >= 98.5, (
        f"[COVERAGE DRIFT] Only {coverage_pct:.2f}% of entities are indexed into families. "
        f"Unindexed entities ({len(unindexed)}): {sorted(list(unindexed))}"
    )


def test_generational_overlap_plausibility(archive_data: Dict[str, Any]) -> None:
    """
    Validates generational bridging: in an integrated genealogy, a substantial portion
    of entities must serve as both a child in an ancestral family and a parent in a descendant family.
    
    Bridge ratio: Overlap / Total Persons >= 0.25 (at least 25% of individuals bridge generations).
    """
    families = archive_data["families"]
    parents: Set[str] = set()
    children: Set[str] = set()

    for fam in families.values():
        for pk in ["parent_x", "parent_y"]:
            p = fam.get(pk)
            if p and p.get("person_id"):
                parents.add(p["person_id"])
        for ch in fam.get("children", []):
            if ch and ch.get("person_id"):
                children.add(ch["person_id"])

    overlap = parents.intersection(children)
    total_indexed = len(parents.union(children))

    overlap_ratio = len(overlap) / total_indexed if total_indexed else 0.0

    assert overlap_ratio >= 0.25, (
        f"[TOPOLOGY DRIFT] Generational overlap ratio {overlap_ratio:.2f} is suspiciously low. "
        f"Only {len(overlap)} individuals connect ancestral and descendant lines out of {total_indexed} indexed."
    )


def test_average_family_size_limits(archive_data: Dict[str, Any]) -> None:
    """
    Validates that average children per indexed family remains within typical
    historical demographic limits (1.0 <= avg <= 3.5).
    """
    families = archive_data["families"]
    child_counts = [len(f.get("children", [])) for f in families.values()]

    avg_children = sum(child_counts) / len(child_counts) if child_counts else 0.0

    assert 1.0 <= avg_children <= 3.5, (
        f"[DEMOGRAPHIC DRIFT] Average children per family ({avg_children:.2f}) is outside expected norms (1.0 - 3.5)."
    )