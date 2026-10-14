# Name: update_golden_facts.py
# Path: tools/ops/update_golden_facts.py
# Version: 1.0.0+build.20261011.1

"""One-time migration script updating golden_facts.json with tombstone topology.

Operational Role:
    Backfills 'is_deprecated: False' and 'superseded_by: None' across the original
    100 active assertions, and appends 23 tombstone records:
    - 10 single-hop records targeting original assertions.
    - 5 two-hop records (step 1 -> step 2 -> original assertion).
    - 1 eight-hop chain (801 -> 802 -> ... -> 808 -> 0086).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

__version__ = "1.0.0+build.20261011.1"

FIXTURE_PATH = Path("tests/fixtures/facts/golden/golden_facts.json")


def build_tombstone(
    fact_id: str,
    person_id: str,
    fact_type: str,
    superseded_by: str,
    description: str,
) -> Dict[str, Any]:
    """Construct a canonical tombstone fact payload."""
    return {
        "fact_id": fact_id,
        "person_id": person_id,
        "fact_type": fact_type,
        "date": {},
        "description": description,
        "is_deprecated": True,
        "superseded_by": superseded_by,
    }


def update_golden_facts() -> None:
    """Load, backfill active records, append tombstone chains, and persist."""
    if not FIXTURE_PATH.exists():
        raise FileNotFoundError(f"Fixture file not found: {FIXTURE_PATH.as_posix()}")

    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    facts: List[Dict[str, Any]] = data.get("facts", [])

    # 1. Backfill original 100 facts
    for fact in facts:
        fact["is_deprecated"] = False
        fact["superseded_by"] = None

    tombstones: List[Dict[str, Any]] = []

    # 2. Add 10 Single-Hop Items
    single_hops = [
        ("00000000-0000-4000-8000-000000000101", "IND-00000", "Birth", "00000000-0000-4000-8000-000000000001", "Single-hop tombstone to fact 0001"),
        ("00000000-0000-4000-8000-000000000102", "IND-00000", "Marriage", "00000000-0000-4000-8000-000000000003", "Single-hop tombstone to fact 0003"),
        ("00000000-0000-4000-8000-000000000103", "IND-00000", "Marriage", "00000000-0000-4000-8000-000000000005", "Single-hop tombstone to fact 0005"),
        ("00000000-0000-4000-8000-000000000104", "IND-00029", "Birth", "00000000-0000-4000-8000-000000000009", "Single-hop tombstone to fact 0009"),
        ("00000000-0000-4000-8000-000000000105", "IND-00037", "Birth", "00000000-0000-4000-8000-000000000014", "Single-hop tombstone to fact 0014"),
        ("00000000-0000-4000-8000-000000000106", "IND-00031", "Birth", "00000000-0000-4000-8000-000000000017", "Single-hop tombstone to fact 0017"),
        ("00000000-0000-4000-8000-000000000107", "IND-00043", "Birth", "00000000-0000-4000-8000-000000000023", "Single-hop tombstone to fact 0023"),
        ("00000000-0000-4000-8000-000000000108", "IND-00019", "Birth", "00000000-0000-4000-8000-000000000032", "Single-hop tombstone to fact 0032"),
        ("00000000-0000-4000-8000-000000000109", "IND-00067", "Birth", "00000000-0000-4000-8000-000000000049", "Single-hop tombstone to fact 0049"),
        ("00000000-0000-4000-8000-000000000110", "IND-00053", "Birth", "00000000-0000-4000-8000-000000000059", "Single-hop tombstone to fact 0059"),
    ]
    for fid, pid, ftype, target, desc in single_hops:
        tombstones.append(build_tombstone(fid, pid, ftype, target, desc))

    # 3. Add 5 Two-Hop Items
    two_hops = [
        ("00000000-0000-4000-8000-000000000201", "IND-00000", "Birth", "00000000-0000-4000-8000-000000000101", "Two-hop tombstone step 1 to 0101"),
        ("00000000-0000-4000-8000-000000000202", "IND-00000", "Marriage", "00000000-0000-4000-8000-000000000102", "Two-hop tombstone step 1 to 0102"),
        ("00000000-0000-4000-8000-000000000203", "IND-00000", "Marriage", "00000000-0000-4000-8000-000000000103", "Two-hop tombstone step 1 to 0103"),
        ("00000000-0000-4000-8000-000000000204", "IND-00029", "Birth", "00000000-0000-4000-8000-000000000104", "Two-hop tombstone step 1 to 0104"),
        ("00000000-0000-4000-8000-000000000205", "IND-00037", "Birth", "00000000-0000-4000-8000-000000000105", "Two-hop tombstone step 1 to 0105"),
    ]
    for fid, pid, ftype, target, desc in two_hops:
        tombstones.append(build_tombstone(fid, pid, ftype, target, desc))

    # 4. Add 8-Hop Long Chain landing on Fact 00000000-0000-4000-8000-000000000086
    eight_hops = [
        ("00000000-0000-4000-8000-000000000801", "00000000-0000-4000-8000-000000000802", "8-hop chain step 1"),
        ("00000000-0000-4000-8000-000000000802", "00000000-0000-4000-8000-000000000803", "8-hop chain step 2"),
        ("00000000-0000-4000-8000-000000000803", "00000000-0000-4000-8000-000000000804", "8-hop chain step 3"),
        ("00000000-0000-4000-8000-000000000804", "00000000-0000-4000-8000-000000000805", "8-hop chain step 4"),
        ("00000000-0000-4000-8000-000000000805", "00000000-0000-4000-8000-000000000806", "8-hop chain step 5"),
        ("00000000-0000-4000-8000-000000000806", "00000000-0000-4000-8000-000000000807", "8-hop chain step 6"),
        ("00000000-0000-4000-8000-000000000807", "00000000-0000-4000-8000-000000000808", "8-hop chain step 7"),
        ("00000000-0000-4000-8000-000000000808", "00000000-0000-4000-8000-000000000086", "8-hop chain step 8 -> Fact 0086"),
    ]
    for fid, target, desc in eight_hops:
        tombstones.append(build_tombstone(fid, "IND-00139", "Birth", target, desc))

    all_facts = facts + tombstones
    data["schema_version"] = "1.2.0"
    data["total_facts"] = len(all_facts)
    data["facts"] = all_facts

    with open(FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {FIXTURE_PATH.as_posix()}: {len(facts)} active, {len(tombstones)} tombstones, total {len(all_facts)}.")


if __name__ == "__main__":
    update_golden_facts()