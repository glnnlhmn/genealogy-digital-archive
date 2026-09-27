# Name: facts_merge.py
# Path: tools/ops/facts_merge.py
# Version: 1.0.0+build.20260927.10

"""Execute deterministic fact merging and provenance tracking.

Features:
- Groups 1-6 assertion consolidation.
- Batch pre-flight collision protection.
- Safe Backup Protocol & atomic commit pipeline via --run / -r.
- Automatic Markdown audit reporting to reports/ during active runs.
- Index synchronization postponed pending GIX tool development.
"""

import argparse
import copy
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid

from rapidfuzz import fuzz

__version__ = "1.0.0+build.20260927.10"

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil

__all__ = [
    "merge_fact_cluster",
    "apply_merge_clusters",
    "validate_batch_clusters",
    "generate_merge_report",
    "run_merge_job"
]


class _FactClusterMerger:
    """Internal consolidation engine. Not intended for standalone external use."""

    VERBATIM_MERGE_NOTICE = "[Consolidated assertion: original verbatim strings preserved in constituent records]"
    INDEX_INVALIDATION_NOTICE = (
        "[NOTICE] Fact consolidation complete. Existing index files referencing facts "
        "(data/indexes/) are now stale and invalid. Run index generator tools "
        "(e.g., GIX / index regenerators) to rebuild affected lookup tables."
    )

    USPS_STATE_MAP = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming"
    }

    SPELLED_ORDINAL_MAP = {
        r"\btwenty-first\b": "21st",
        r"\btwenty-second\b": "22nd",
        r"\btwenty-third\b": "23rd",
        r"\btwenty-fourth\b": "24th",
        r"\btwenty-fifth\b": "25th",
        r"\btwenty-sixth\b": "26th",
        r"\btwenty-seventh\b": "27th",
        r"\btwenty-eighth\b": "28th",
        r"\btwenty-ninth\b": "29th",
        r"\beleventh\b": "11th",
        r"\btwelfth\b": "12th",
        r"\btwentieth\b": "20th",
        r"\bthirtieth\b": "30th",
        r"\bseventh\b": "7th",
        r"\beighth\b": "8th",
        r"\bfourth\b": "4th",
        r"\bsecond\b": "2nd",
        r"\bthird\b": "3rd",
        r"\bfifth\b": "5th",
        r"\bsixth\b": "6th",
        r"\bninth\b": "9th",
        r"\btenth\b": "10th",
        r"\bfirst\b": "1st"
    }

    @staticmethod
    def _compute_soundex(name: str) -> str:
        """Calculate American Soundex code for phonetic clustering."""
        if not name or not isinstance(name, str):
            return "Z000"
        clean = re.sub(r"[^A-Za-z]", "", name).upper()
        if not clean:
            return "Z000"

        mapping = {
            "B": "1", "F": "1", "P": "1", "V": "1",
            "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
            "D": "3", "T": "3",
            "L": "4",
            "M": "5", "N": "5",
            "R": "6"
        }

        first_char = clean[0]
        codes = [first_char]
        prev_code = mapping.get(first_char, "0")

        for char in clean[1:]:
            curr_code = mapping.get(char, "0")
            if curr_code != "0":
                if curr_code != prev_code:
                    codes.append(curr_code)
                prev_code = curr_code
            else:
                prev_code = "0"
            if len(codes) == 4:
                break

        while len(codes) < 4:
            codes.append("0")
        return "".join(codes)

    @classmethod
    def _fetch_person_id(
        cls,
        name: str | None,
        people_registry: list[dict],
        threshold: float = 90.0
    ) -> tuple[str | None, str | None]:
        """Pre-intake grounding pass against master people registry."""
        if not name or not isinstance(name, str):
            return None, None

        clean_name = name.strip()
        clean_lower = clean_name.lower()
        parts = clean_name.split()
        surname = parts[-1] if parts else clean_name
        target_soundex = cls._compute_soundex(surname)

        best_match_id = None
        best_display_name = None
        highest_score = 0.0

        for person in people_registry:
            pid = person.get("person_id")
            if not pid:
                continue

            disp_name = person.get("display_name") or ""
            c_name = person.get("canonical_name") or {}
            c_given = c_name.get("given", "")
            c_mid = c_name.get("middle", "")
            c_sur = c_name.get("surname", "")
            assembled = " ".join([p for p in [c_given, c_mid, c_sur] if p]).strip()

            target_canonical = disp_name if disp_name else assembled
            candidates = [c for c in [disp_name, assembled] if c]

            for cand in candidates:
                cand_lower = cand.lower()
                if clean_lower == cand_lower:
                    return pid, target_canonical

                cand_parts = cand.split()
                cand_surname = cand_parts[-1] if cand_parts else cand
                if cls._compute_soundex(cand_surname) == target_soundex:
                    ratio = fuzz.token_set_ratio(clean_name, cand)
                    if ratio >= threshold and ratio > highest_score:
                        highest_score = ratio
                        best_match_id = pid
                        best_display_name = target_canonical

        if best_match_id and highest_score >= threshold:
            return best_match_id, best_display_name

        return None, None

    @staticmethod
    def _resolve_identity(cluster: list[dict], new_id: str) -> dict:
        """Group 1: Core Assertion & Entity Identity."""
        anchor = cluster[0]
        return {
            "fact_id": new_id,
            "person_id": anchor["person_id"],
            "fact_type": anchor["fact_type"],
            "canonical_fact_id": None,
            "absorbed_at": None
        }

    @classmethod
    def _normalize_street_address(cls, addr: str | None) -> str | None:
        """Standardize spelled-out ordinals in street addresses."""
        if not addr or not isinstance(addr, str):
            return addr
        clean = addr.strip()
        for pattern, replacement in cls.SPELLED_ORDINAL_MAP.items():
            clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)
        return clean

    @classmethod
    def _merge_spatiotemporal(cls, target: dict, cluster: list[dict]) -> list[dict]:
        """Group 2: Temporal & Spatial Spans."""
        extra_notes = []

        facts_with_dates = [f for f in cluster if f.get("date") and isinstance(f.get("date"), dict)]
        if facts_with_dates:
            def date_sort_key(item: dict):
                score = item.get("quay_score", 0)
                d = item.get("date", {})
                is_exact = 1 if d.get("modifier") == "Exact" else 0
                d_start = d.get("date_start") or ""
                return (score, is_exact, len(d_start), d_start)

            sorted_date_facts = sorted(facts_with_dates, key=date_sort_key, reverse=True)
            chosen_fact = sorted_date_facts[0]
            target["date"] = copy.deepcopy(chosen_fact["date"])
            canonical_start = target["date"].get("date_start")

            for other in sorted_date_facts[1:]:
                o_date = other.get("date", {})
                o_start = o_date.get("date_start")
                o_mod = o_date.get("modifier")
                if o_start != canonical_start or o_mod != target["date"].get("modifier"):
                    note_category = "RESEARCH" if o_start and canonical_start and not o_start.startswith(canonical_start[:4]) else "GENERAL"
                    extra_notes.append({
                        "category": note_category,
                        "title": "Alternate Date Context",
                        "text": (
                            f"Variant date '{o_start}' (Modifier: {o_mod}) from absorbed fact "
                            f"{other.get('fact_id')} (Quay {other.get('quay_score', 0)})."
                        )
                    })
        else:
            target["date"] = None

        facts_with_locs = [f for f in cluster if f.get("location") and isinstance(f.get("location"), dict)]
        if facts_with_locs:
            def loc_sort_key(item: dict):
                return (item.get("quay_score", 0), len(item.get("fact_id", "")))

            sorted_loc_facts = sorted(facts_with_locs, key=loc_sort_key, reverse=True)
            primary_fact = sorted_loc_facts[0]
            canonical_loc = copy.deepcopy(primary_fact["location"])
            canonical_std = canonical_loc.get("standardized", "")

            c_details = canonical_loc.setdefault("details", {})
            if c_details is None:
                c_details = {}
                canonical_loc["details"] = c_details

            if c_details.get("state_or_province") in cls.USPS_STATE_MAP:
                c_details["state_or_province"] = cls.USPS_STATE_MAP[c_details["state_or_province"]]
            c_details["address_line_1"] = cls._normalize_street_address(c_details.get("address_line_1"))

            for other in sorted_loc_facts[1:]:
                o_loc = other.get("location", {})
                o_std = o_loc.get("standardized", "")
                o_details = o_loc.get("details") or {}

                if o_std == canonical_std:
                    for k, v in o_details.items():
                        if k == "state_or_province" and v in cls.USPS_STATE_MAP:
                            v = cls.USPS_STATE_MAP[v]
                        if k == "address_line_1":
                            v = cls._normalize_street_address(v)

                        current_val = c_details.get(k)
                        if not current_val and v:
                            c_details[k] = copy.deepcopy(v)
                        elif k == "address_line_1" and current_val and v and current_val != v:
                            extra_notes.append({
                                "category": "GENERAL",
                                "title": "Alternate Address Context",
                                "text": (
                                    f"Variant address '{v}' from absorbed fact "
                                    f"{other.get('fact_id')} (Quay {other.get('quay_score', 0)})."
                                )
                            })
                else:
                    extra_notes.append({
                        "category": "RESEARCH",
                        "title": "Alternate Location Context",
                        "text": (
                            f"Variant location '{o_std}' from absorbed fact "
                            f"{other.get('fact_id')} (Quay {other.get('quay_score', 0)})."
                        )
                    })

            canonical_loc["verbatim"] = cls.VERBATIM_MERGE_NOTICE
            target["location"] = canonical_loc
        else:
            target["location"] = None

        return extra_notes

    @staticmethod
    def _merge_narrative(target: dict, cluster: list[dict], threshold: float = 75.0) -> list[dict]:
        """Group 3: Narrative, Confidence & Context."""
        target["quay_score"] = max(f.get("quay_score", 0) for f in cluster)

        candidates = []
        for f in cluster:
            desc = (f.get("description") or "").strip()
            if desc:
                candidates.append({
                    "fact_id": f.get("fact_id"),
                    "description": desc,
                    "quay_score": f.get("quay_score", 0),
                    "tokens": len(desc.split()),
                    "length": len(desc)
                })

        extra_notes = []
        if candidates:
            candidates.sort(
                key=lambda x: (x["quay_score"], x["tokens"], x["length"], x["fact_id"]),
                reverse=True
            )
            canonical_desc = candidates[0]["description"]
            target["description"] = canonical_desc

            for item in candidates[1:]:
                sim = fuzz.token_set_ratio(canonical_desc, item["description"])
                if sim < threshold:
                    extra_notes.append({
                        "category": "GENERAL",
                        "title": "Alternate Description Context",
                        "text": (
                            f"Variant description from absorbed fact {item['fact_id']} "
                            f"(Quay {item['quay_score']}): '{item['description']}'"
                        )
                    })
        else:
            target["description"] = cluster[0].get("description", "")

        stories = [
            f.get("life_story").strip()
            for f in cluster
            if f.get("life_story") and f.get("life_story").strip()
        ]
        target["life_story"] = " ".join(list(dict.fromkeys(stories))) if stories else None

        return extra_notes

    @classmethod
    def _merge_associated_people(
        cls,
        target: dict,
        cluster: list[dict],
        people_registry: list[dict] | None = None
    ) -> list[dict]:
        """Group 4: Associated People."""
        extra_notes = []
        registry = people_registry or []
        reg_lookup = {p["person_id"]: p for p in registry if p.get("person_id")}

        raw_entries = []
        for f in cluster:
            assoc = f.get("associated_people")
            q_score = f.get("quay_score", 0)
            f_id = f.get("fact_id")
            if isinstance(assoc, list):
                for p in assoc:
                    if isinstance(p, dict):
                        item = copy.deepcopy(p)
                        item["_parent_quay"] = q_score
                        item["_parent_fact_id"] = f_id
                        raw_entries.append(item)

        if not raw_entries:
            target["associated_people"] = None
            return extra_notes

        for entry in raw_entries:
            if not entry.get("person_id") and entry.get("name"):
                matched_id, canonical_name = cls._fetch_person_id(entry["name"], registry)
                if matched_id:
                    entry["person_id"] = matched_id
                    if canonical_name:
                        entry["name"] = canonical_name

        grounded_entries = [e for e in raw_entries if e.get("person_id")]
        unlinked_entries = [e for e in raw_entries if not e.get("person_id")]

        consolidated = []

        grounded_buckets: dict[tuple[str, str], list[dict]] = {}
        for ge in grounded_entries:
            key = (ge["person_id"], ge["role"])
            grounded_buckets.setdefault(key, []).append(ge)

        for (pid, role), bucket in grounded_buckets.items():
            bucket.sort(key=lambda x: (x.get("_parent_quay", 0), len(x.get("name") or "")), reverse=True)
            primary = copy.deepcopy(bucket[0])

            if pid in reg_lookup:
                p_obj = reg_lookup[pid]
                c_disp = p_obj.get("display_name")
                if not c_disp:
                    c_name = p_obj.get("canonical_name") or {}
                    c_disp = " ".join([v for v in [c_name.get("given"), c_name.get("middle"), c_name.get("surname")] if v]).strip()
                if c_disp:
                    primary["name"] = c_disp
            else:
                names = [b.get("name") for b in bucket if b.get("name")]
                if names:
                    names.sort(key=lambda n: (len(n.split()), len(n)), reverse=True)
                    primary["name"] = names[0]

            primary["is_primary_subject"] = any(b.get("is_primary_subject", False) for b in bucket)

            relations = [b.get("relation") for b in bucket if b.get("relation")]
            if relations:
                primary["relation"] = relations[0]
                if len(set(relations)) > 1:
                    extra_notes.append({
                        "category": "RESEARCH",
                        "title": "Alternate Relationship Context",
                        "text": f"Variant relation '{relations[1]}' for person {pid} (Role: {role}) overridden by '{relations[0]}'."
                    })
            else:
                primary["relation"] = None

            primary.pop("_parent_quay", None)
            primary.pop("_parent_fact_id", None)
            consolidated.append(primary)

        used_indices = set()
        for i, u_primary in enumerate(unlinked_entries):
            if i in used_indices:
                continue

            current_group = [u_primary]
            used_indices.add(i)

            p_name = u_primary.get("name") or ""
            p_parts = p_name.split()
            p_surname = p_parts[-1] if p_parts else p_name
            p_soundex = cls._compute_soundex(p_surname)
            p_role = u_primary.get("role")

            for j, u_other in enumerate(unlinked_entries[i + 1:], start=i + 1):
                if j in used_indices:
                    continue

                o_name = u_other.get("name") or ""
                o_role = u_other.get("role")
                if o_role != p_role:
                    continue

                o_parts = o_name.split()
                o_surname = o_parts[-1] if o_parts else o_name
                if cls._compute_soundex(o_surname) == p_soundex:
                    score = fuzz.token_set_ratio(p_name, o_name)
                    if score >= 85.0:
                        current_group.append(u_other)
                        used_indices.add(j)

            current_group.sort(
                key=lambda x: (x.get("_parent_quay", 0), len((x.get("name") or "").split()), len(x.get("name") or "")),
                reverse=True
            )
            canonical_unlinked = copy.deepcopy(current_group[0])
            canonical_unlinked["is_primary_subject"] = any(g.get("is_primary_subject", False) for g in current_group)

            u_relations = [g.get("relation") for g in current_group if g.get("relation")]
            canonical_unlinked["relation"] = u_relations[0] if u_relations else None

            canonical_unlinked.pop("_parent_quay", None)
            canonical_unlinked.pop("_parent_fact_id", None)
            consolidated.append(canonical_unlinked)

        target["associated_people"] = consolidated if consolidated else None
        return extra_notes

    @staticmethod
    def _merge_evidence(
        target: dict,
        cluster: list[dict],
        extra_notes: list[dict],
        absorbed_ids: list[str],
        current_timestamp: str
    ) -> None:
        """Group 5: Structured Evidence & Notes."""
        seen_urns = {}
        sources_no_urn = []
        for f in cluster:
            raw = f.get("source")
            items = [raw] if isinstance(raw, dict) else (raw or [])
            for s in items:
                if not isinstance(s, dict):
                    continue
                urn = s.get("record_urn")
                if urn:
                    if urn not in seen_urns:
                        seen_urns[urn] = copy.deepcopy(s)
                    else:
                        if not seen_urns[urn].get("file_name") and s.get("file_name"):
                            seen_urns[urn]["file_name"] = s.get("file_name")
                        if not seen_urns[urn].get("repository_path") and s.get("repository_path"):
                            seen_urns[urn]["repository_path"] = s.get("repository_path")
                else:
                    if s not in sources_no_urn:
                        sources_no_urn.append(copy.deepcopy(s))

        unified = list(seen_urns.values()) + sources_no_urn
        target["source"] = unified[0] if len(unified) == 1 else unified

        merged_notes = []
        seen_texts = set()
        for f in cluster:
            raw_notes = f.get("notes")
            if not raw_notes:
                continue
            items = [raw_notes] if isinstance(raw_notes, (dict, str)) else raw_notes
            for n in items:
                if isinstance(n, dict):
                    txt = n.get("text", "").strip()
                    if txt and txt not in seen_texts:
                        seen_texts.add(txt)
                        merged_notes.append(copy.deepcopy(n))
                elif isinstance(n, str) and n.strip():
                    txt = n.strip()
                    if txt not in seen_texts:
                        seen_texts.add(txt)
                        merged_notes.append({
                            "note_id": None,
                            "category": "GENERAL",
                            "title": None,
                            "text": txt
                        })

        for en in extra_notes:
            if en["text"] not in seen_texts:
                seen_texts.add(en["text"])
                merged_notes.append({
                    "note_id": None,
                    "category": en["category"],
                    "title": en["title"],
                    "text": en["text"]
                })

        audit_entry = f"Consolidated {len(cluster)} assertions: {', '.join(absorbed_ids)} on {current_timestamp}."
        merged_notes.append({
            "note_id": None,
            "category": "GENERAL",
            "title": "Consolidation Provenance",
            "text": audit_entry
        })

        for idx, n in enumerate(merged_notes, 1):
            n["note_id"] = f"NOT-{idx:05d}"
        target["notes"] = merged_notes

        ext = {}
        for f in cluster:
            if isinstance(f.get("external_identifiers"), dict):
                ext.update(f["external_identifiers"])
        target["external_identifiers"] = ext if ext else None

    @staticmethod
    def _resolve_provenance(target: dict, cluster: list[dict], current_timestamp: str) -> None:
        """Group 6: Audit & Lifecycle Provenance."""
        valid_created = [f["created_at"] for f in cluster if f.get("created_at")]
        target["created_at"] = min(valid_created) if valid_created else current_timestamp
        target["updated_at"] = current_timestamp

    @staticmethod
    def _rebuild_indexes() -> None:
        """Postponed hook: Index rebuilding delegated to GIX once operational."""
        raise NotImplementedError(
            "Automated index rebuilding is postponed pending GIX implementation. "
            "Index synchronization must be triggered via external index tools."
        )


# =============================================================================
# PUBLIC INTERFACE & PRE-FLIGHT VALIDATION
# =============================================================================

def validate_batch_clusters(
    clusters: list[list[str]],
    facts_registry: list[dict]
) -> None:
    """Pre-flight batch validation for collisions and pre-absorbed assertions."""
    if not clusters:
        return

    seen_ids: set[str] = set()
    fact_map = {f.get("fact_id"): f for f in facts_registry if f.get("fact_id")}

    for cluster_idx, id_list in enumerate(clusters, start=1):
        if len(id_list) < 2:
            raise ValueError(
                f"Cluster {cluster_idx} is malformed: requires at least 2 distinct fact IDs, received {len(id_list)}."
            )

        if len(id_list) != len(set(id_list)):
            raise ValueError(f"Cluster {cluster_idx} contains duplicate IDs: {id_list}")

        for fid in id_list:
            if fid in seen_ids:
                raise ValueError(
                    f"Batch collision detected: fact_id '{fid}' is referenced in multiple clusters."
                )
            seen_ids.add(fid)

            if fid in fact_map:
                existing_fact = fact_map[fid]
                if existing_fact.get("absorbed_at") is not None:
                    raise ValueError(
                        f"Fact '{fid}' in cluster {cluster_idx} is already absorbed into canonical "
                        f"fact '{existing_fact.get('canonical_fact_id')}' on {existing_fact.get('absorbed_at')}."
                    )


def merge_fact_cluster(
    cluster: list[dict],
    people_registry: list[dict] | None = None
) -> tuple[dict, list[dict]]:
    """Execute complete 6-group merge on a single cluster.

    Returns:
        Tuple of (canonical_fact, archived_constituents).
    """
    if len(cluster) < 2:
        raise ValueError(f"Merging requires >= 2 facts, received {len(cluster)}.")

    fact_types = {f.get("fact_type") for f in cluster}
    if len(fact_types) > 1:
        raise ValueError(f"Cannot merge heterogeneous fact types across cluster: {fact_types}")

    person_ids = {f.get("person_id") for f in cluster}
    if len(person_ids) > 1:
        raise ValueError(f"Cannot merge facts across multiple people: {person_ids}")

    for f in cluster:
        if f.get("absorbed_at") is not None:
            raise ValueError(
                f"Fact {f.get('fact_id')} is already absorbed into {f.get('canonical_fact_id')}."
            )

    current_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_id = str(uuid.uuid4())
    absorbed_ids = [f["fact_id"] for f in cluster]

    merger = _FactClusterMerger
    canonical = merger._resolve_identity(cluster, new_id)
    g2_notes = merger._merge_spatiotemporal(canonical, cluster)
    g3_notes = merger._merge_narrative(canonical, cluster)
    g4_notes = merger._merge_associated_people(canonical, cluster, people_registry)
    all_extra_notes = g2_notes + g3_notes + g4_notes
    merger._merge_evidence(canonical, cluster, all_extra_notes, absorbed_ids, current_timestamp)
    merger._resolve_provenance(canonical, cluster, current_timestamp)

    archived = []
    for f in cluster:
        arc = copy.deepcopy(f)
        arc["canonical_fact_id"] = new_id
        arc["absorbed_at"] = current_timestamp
        arc["updated_at"] = current_timestamp
        archived.append(arc)

    return canonical, archived


def apply_merge_clusters(
    facts: list[dict],
    clusters: list[list[str]],
    people_registry: list[dict] | None = None,
    logger=None
) -> tuple[list[dict], list[dict], list[dict]]:
    """Execute merges across cluster batches after validation.

    Returns:
        Tuple of (updated_master_facts, new_canonical_facts, all_archived_facts).
    """
    validate_batch_clusters(clusters, facts)

    fact_map = {f.get("fact_id"): f for f in facts if f.get("fact_id")}
    new_facts = []
    all_archived = []

    for id_list in clusters:
        cluster_records = [fact_map[fid] for fid in id_list if fid in fact_map]
        if len(cluster_records) < 2:
            if logger:
                logger.warning(f"Skipping cluster: fewer than 2 valid facts found for {id_list}")
            continue

        canonical, archived = merge_fact_cluster(cluster_records, people_registry=people_registry)
        new_facts.append(canonical)
        all_archived.extend(archived)

        for arc in archived:
            fact_map[arc["fact_id"]] = arc

    updated_master = list(fact_map.values()) + new_facts
    return updated_master, new_facts, all_archived


def parse_csv_clusters(csv_path: Path) -> list[list[str]]:
    """Parse clusters from CSV where each row is a comma-delimited list of fact_ids."""
    clusters = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            ids = [cell.strip() for cell in row if cell.strip()]
            if len(ids) >= 2:
                clusters.append(ids)
    return clusters


def generate_merge_report(
    report_path: Path,
    mode: str,
    new_canonicals: list[dict],
    archived_constituents: list[dict],
    backup_file: Path | None = None
) -> None:
    """Generate structured Markdown consolidation audit report."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    lines = [
        "# Fact Consolidation Audit Report",
        "",
        f"- **Execution Timestamp:** {timestamp}",
        f"- **Mode:** {mode}",
        f"- **Canonical Facts Minted:** {len(new_canonicals)}",
        f"- **Constituent Assertions Absorbed:** {len(archived_constituents)}",
        f"- **Safe Backup Snapshot:** `{backup_file.name if backup_file else 'None'}`",
        "",
        "---",
        "",
        "## Consolidated Clusters",
        ""
    ]

    cluster_groups: dict[str, list[dict]] = {}
    for arc in archived_constituents:
        cid = arc.get("canonical_fact_id", "UNKNOWN")
        cluster_groups.setdefault(cid, []).append(arc)

    for c_fact in new_canonicals:
        cid = c_fact["fact_id"]
        pid = c_fact.get("person_id")
        ftype = c_fact.get("fact_type")
        qscore = c_fact.get("quay_score", 0)
        absorbed = cluster_groups.get(cid, [])
        absorbed_ids = [a["fact_id"] for a in absorbed]

        lines.append(f"### Canonical Fact: `{cid}`")
        lines.append(f"- **Person ID:** `{pid}`")
        lines.append(f"- **Fact Type:** `{ftype}`")
        lines.append(f"- **Consolidated Quay Score:** `{qscore}`")
        lines.append(f"- **Absorbed Constituent Assertions ({len(absorbed)}):**")
        for afid in absorbed_ids:
            lines.append(f"  - `{afid}`")

        notes = c_fact.get("notes") or []
        offloaded = [n for n in notes if n.get("category") in {"RESEARCH", "GENERAL"} and n.get("title") != "Consolidation Provenance"]
        if offloaded:
            lines.append("- **Generated Context Notes:**")
            for n in offloaded:
                title = n.get("title") or "Note"
                cat = n.get("category")
                txt = n.get("text")
                lines.append(f"  - **[{cat}] {title}:** {txt}")
        lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def run_merge_job(
    clusters: list[list[str]],
    run_commit: bool = False,
    apply: bool = False,
    verbose: bool = False,
    debug: bool = False,
    **kwargs
) -> int:
    """Execute merge job with pre-flight checks, atomic safe backups, and report generation."""
    should_commit = run_commit or apply or kwargs.get("run", False)
    config = GDAConfig(root=ROOT_DIR)
    logger = setup_logger("facts_merge", log_dir=config.logs)
    mode_str = "RUN (Commit Enabled)" if should_commit else "DRY-RUN (Safe)"
    logger.info(f"Initializing facts_merge ({mode_str}).")

    if not clusters:
        logger.warning("No clusters to process.")
        return 0

    facts_path = config.entities / "facts.json"
    if not facts_path.is_file():
        logger.error(f"Facts registry not found: {facts_path}")
        return 1

    registry_container = json.loads(facts_path.read_text(encoding="utf-8-sig"))
    initial_facts = registry_container.get("facts", [])

    people_registry = []
    if config.people.is_file():
        try:
            people_data = json.loads(config.people.read_text(encoding="utf-8-sig"))
            people_registry = people_data.get("persons", [])
        except Exception as e:
            logger.warning(f"Failed to load people registry: {e}")

    try:
        updated_facts, new_canonicals, archived_constituents = apply_merge_clusters(
            initial_facts, clusters, people_registry=people_registry, logger=logger
        )
    except ValueError as ve:
        logger.error(f"Pre-flight cluster validation failed: {ve}")
        print(f"Error: {ve}", file=sys.stderr)
        return 1

    logger.info(
        f"Merge calculations complete: {len(clusters)} cluster(s) evaluated. "
        f"Minted {len(new_canonicals)} canonical fact(s), absorbed {len(archived_constituents)} constituent assertion(s)."
    )

    if not should_commit:
        logger.info("DRY-RUN COMPLETE: No files or reports were written. Pass --run / -r to execute.")
        return 0

    # -------------------------------------------------------------------------
    # ACTIVE COMMIT & AUTOMATIC REPORTING
    # -------------------------------------------------------------------------
    logger.info("Executing atomic commit to data/entities/facts.json...")
    try:
        backup_path = GDAUtil.create_safe_backup(facts_path, backup_dir=config.backups)
        logger.info(f"Safe Backup established: {backup_path.name}")
    except Exception as e:
        logger.error(f"Failed to generate pre-execution safe backup: {e}")
        return 1

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry_container["facts"] = updated_facts
    registry_container["total_facts"] = len(updated_facts)
    registry_container["last_modified"] = now_iso

    try:
        GDAUtil.save_json(facts_path, registry_container)
        logger.info(f"Successfully committed {len(updated_facts)} assertions to {facts_path}")
    except Exception as e:
        logger.error(f"Atomic write failed: {e}")
        return 1

    logger.warning(_FactClusterMerger.INDEX_INVALIDATION_NOTICE)
    print(_FactClusterMerger.INDEX_INVALIDATION_NOTICE, file=sys.stderr)

    report_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_file = config.reports / f"facts_merge_report_{report_timestamp}.md"
    generate_merge_report(
        report_path=report_file,
        mode=mode_str,
        new_canonicals=new_canonicals,
        archived_constituents=archived_constituents,
        backup_file=backup_path
    )
    logger.info(f"Audit report generated: {report_file}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge duplicate fact clusters into newly minted canonical assertions."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-f", "--facts",
        nargs="+",
        metavar="FACT_ID",
        help="Space-delimited list of fact IDs to merge as a single cluster (minimum 2)."
    )
    group.add_argument(
        "--csv",
        type=Path,
        metavar="CSV_FILE",
        help="Path to CSV file where each row contains comma-separated fact IDs for one cluster."
    )
    parser.add_argument(
        "-r", "--run", "--apply",
        dest="run_commit",
        action="store_true",
        help="Commit merges to disk with atomic Safe Backup and report generation. Default is dry-run mode."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Emit diagnostic logs to logs/."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Route traces directly to stdout."
    )

    args = parser.parse_args()

    clusters = []
    if args.facts:
        if len(args.facts) < 2:
            print("Error: -f/--facts requires at least 2 fact IDs for a single cluster.", file=sys.stderr)
            return 1
        clusters.append(args.facts)

    if args.csv:
        if not args.csv.is_file():
            print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
            return 1
        clusters = parse_csv_clusters(args.csv)

    return run_merge_job(clusters, run_commit=args.run_commit, verbose=args.verbose, debug=args.debug)


if __name__ == "__main__":
    sys.exit(main())