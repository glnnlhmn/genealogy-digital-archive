# Name: test_facts_md.py
# Path: tests/unit/test_facts_md.py
# Version: 1.0.0+build.20260928.6

"""Unit test suite for the facts_md remediation engine.

Operational Role:
    Validates atomic First-Aid remediation functions for data/entities/facts.json:
    - _remedy_fact_type: casing normalization, synonym remapping, and fallback provenance.
    - _remedy_notes_structure: string promotion, blank pruning, category validation,
      title retention, sequential ID renumbering, and mutation ordering invariance.
    - _remedy_date_modifier: alias mapping and end date pruning for discrete modifiers.
    - _remedy_reciprocal_union: symmetrical marriage/divorce generation and note provenance.

Test Structure & Protocol:
    - Atomized tests: 1:1 assertion mapping isolating single behaviors and boundaries.
    - Strict schema verification: Schema files must exist; zero fallbacks permitted.
    - Fully decorated: Explicitly marked with @pytest.mark.unit and @pytest.mark.regression.
    - Dependencies: tmp_path hermetic sandbox, GDAConfig, GDAFacts.
"""

from typing import Any
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAFacts import GDAFacts
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops.facts_md import (
    _get_allowed_enums,
    _remedy_date_modifier,
    _remedy_fact_type,
    _remedy_notes_structure,
    _remedy_reciprocal_union,
    remedy_facts,
)


@pytest.fixture(autouse=True)
def setup_test_sandbox(tmp_path, monkeypatch):
    """Sets up an isolated filesystem environment with schema and data stores."""
    entities_dir = tmp_path / "data" / "entities"
    backups_dir = tmp_path / "backups"
    reports_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"
    schema_defs_dir = tmp_path / "schemas" / "defs"

    for d in (entities_dir, backups_dir, reports_dir, logs_dir, schema_defs_dir):
        d.mkdir(parents=True, exist_ok=True)

    sandbox_config = GDAConfig(root=tmp_path, manifest={})
    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", sandbox_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", sandbox_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAFacts.CONFIG", sandbox_config)
    monkeypatch.setattr("tools.ops.facts_md.CONFIG", sandbox_config)

    # Establish canonical _enums.schema.json
    enums_content = {
        "$defs": {
            "enum_fact_type": {
                "type": "string",
                "enum": [
                    "Association", "Award", "Baptism", "Birth", "Burial", "Census",
                    "Civic", "Death", "Divorce", "Education", "Incident", "Legal",
                    "Marriage", "Military", "Occupation", "Parentage", "Probate",
                    "Property", "Residence", "Other"
                ]
            },
            "enum_note_category": {
                "type": "string",
                "enum": [
                    "GENERAL", "RESEARCH_TODO", "ANOMALY", "RESEARCH",
                    "DISCREPANCY", "TRANSCRIPTION", "CORRECTION", "PROVENANCE"
                ]
            },
            "enum_date_modifier": {
                "type": "string",
                "enum": ["EXACT", "ABT", "BEF", "AFT", "BET", "EST", "FROM", "TO"]
            }
        }
    }
    GDAUtil.save_json(schema_defs_dir / "_enums.schema.json", enums_content)

    facts_file = sandbox_config.facts
    GDAUtil.save_json(facts_file, {"facts": []})

    return {
        "root": tmp_path,
        "config": sandbox_config,
        "facts_file": facts_file,
    }


# -----------------------------------------------------------------------------
# Strict Schema Resolution Tests
# -----------------------------------------------------------------------------

@pytest.mark.unit
def test_get_allowed_enums_missing_schema_raises_error(tmp_path, monkeypatch):
    """Verifies that attempting to read enums without a schema file raises FileNotFoundError."""
    empty_root = tmp_path / "empty_env"
    empty_root.mkdir()
    empty_config = GDAConfig(root=empty_root, manifest={})
    monkeypatch.setattr("tools.ops.facts_md.CONFIG", empty_config)

    with pytest.raises(FileNotFoundError):
        _get_allowed_enums("enum_fact_type")


@pytest.mark.unit
def test_get_allowed_enums_missing_key_raises_error():
    """Verifies that requesting an unregistered enum key raises KeyError."""
    with pytest.raises(KeyError):
        _get_allowed_enums("non_existent_key")


# -----------------------------------------------------------------------------
# Correction 1: _remedy_fact_type
# -----------------------------------------------------------------------------

@pytest.mark.unit
def test_remedy_fact_type_casing():
    """Verifies lowercase fact_type is normalized to canonical TitleCase."""
    fact = {"fact_type": "birth"}
    assert _remedy_fact_type(fact) is True
    assert fact["fact_type"] == "Birth"


@pytest.mark.unit
def test_remedy_fact_type_synonym():
    """Verifies known historical synonym is remapped to standard enum."""
    fact = {"fact_type": "Christening"}
    assert _remedy_fact_type(fact) is True
    assert fact["fact_type"] == "Baptism"


@pytest.mark.unit
def test_remedy_fact_type_already_valid():
    """Verifies that an already valid fact_type is untouched and returns False."""
    fact = {"fact_type": "Death"}
    assert _remedy_fact_type(fact) is False
    assert fact["fact_type"] == "Death"


@pytest.mark.unit
def test_remedy_fact_type_fallback_to_other():
    """Verifies unrecognized fact_type falls back to Other with provenance note."""
    fact = {"fact_type": "UnknownCustomEvent", "notes": []}
    assert _remedy_fact_type(fact, allow_fallback=True) is True
    assert fact["fact_type"] == "Other"
    assert len(fact["notes"]) == 1
    assert fact["notes"][0]["category"] == "PROVENANCE"
    assert fact["notes"][0]["title"] == "Recorded by facts_md.remedy_facts"
    assert "UnknownCustomEvent" in fact["notes"][0]["text"]


@pytest.mark.unit
def test_remedy_fact_type_queue_for_triage():
    """Verifies unrecognized fact_type is added to queue without immediate fallback."""
    queue = []
    fact = {"fact_type": "UnknownCustomEvent"}
    assert _remedy_fact_type(fact, unresolved_queue=queue) is False
    assert len(queue) == 1
    assert queue[0] is fact
    assert fact["fact_type"] == "UnknownCustomEvent"


# -----------------------------------------------------------------------------
# Correction 2: _remedy_notes_structure
# -----------------------------------------------------------------------------

@pytest.mark.unit
def test_remedy_notes_raw_string():
    """Verifies flat string note is promoted to structured dictionary."""
    fact = {"notes": "Buried in lot 4."}
    assert _remedy_notes_structure(fact) is True
    assert fact["notes"] == [
        {
            "note_id": "NOT-00001",
            "category": "GENERAL",
            "title": None,
            "text": "Buried in lot 4.",
        }
    ]


@pytest.mark.unit
def test_remedy_notes_prune_blanks_and_renumber():
    """Verifies blank notes are pruned and identifiers are sequentially renumbered."""
    fact = {
        "notes": [
            {"note_id": "NOT-00099", "category": "GENERAL", "text": "Valid note 1"},
            {"note_id": "NOT-00002", "category": "GENERAL", "text": "   "},
            {"note_id": "NOT-00003", "category": "GENERAL", "text": ""},
            {"note_id": "NOT-00004", "category": "GENERAL", "text": "Valid note 2"},
        ]
    }
    assert _remedy_notes_structure(fact) is True
    assert len(fact["notes"]) == 2
    assert fact["notes"][0]["note_id"] == "NOT-00001"
    assert fact["notes"][0]["text"] == "Valid note 1"
    assert fact["notes"][1]["note_id"] == "NOT-00002"
    facts_notes = fact["notes"]
    assert facts_notes[1]["text"] == "Valid note 2"


@pytest.mark.unit
def test_remedy_notes_empty_text_with_title():
    """Verifies that an empty text note with a valid title copies title into text."""
    fact = {
        "notes": [
            {"note_id": "NOT-00001", "category": "GENERAL", "title": "Orphan Title", "text": ""}
        ]
    }
    assert _remedy_notes_structure(fact) is True
    assert fact["notes"][0]["text"] == "Orphan Title"
    assert fact["notes"][0]["title"] == "Orphan Title"


@pytest.mark.unit
def test_remedy_notes_all_pruned_leaves_empty_list():
    """Verifies that a list with only whitespace entries results in an empty list."""
    fact = {"notes": ["   ", ""]}
    assert _remedy_notes_structure(fact) is True
    assert fact["notes"] == []


@pytest.mark.unit
def test_notes_mutation_order_add_then_renumber():
    """Verifies appending a note to malformed notes followed by renumbering yields contiguous IDs."""
    fact = {
        "fact_type": "UnknownCustomEvent",
        "notes": [
            "Legacy flat note.",
            {"note_id": "NOT-00099", "category": "GENERAL", "title": None, "text": "Old note 2"}
        ]
    }

    # Step 1: Add note via fallback
    added = _remedy_fact_type(fact, allow_fallback=True)
    assert added is True
    assert len(fact["notes"]) == 3

    # Step 2: Renumber and clean
    renumbered = _remedy_notes_structure(fact)
    assert renumbered is True
    assert len(fact["notes"]) == 3

    # Verify contiguous numbering and schema compliance
    note_ids = [n["note_id"] for n in fact["notes"]]
    assert note_ids == ["NOT-00001", "NOT-00002", "NOT-00003"]
    assert fact["notes"][2]["category"] == "PROVENANCE"
    assert fact["notes"][2]["title"] == "Recorded by facts_md.remedy_facts"


@pytest.mark.unit
def test_notes_mutation_order_renumber_then_add():
    """Verifies renumbering notes first followed by appending maintains contiguous sequence."""
    fact = {
        "fact_type": "UnknownCustomEvent",
        "notes": [
            {"note_id": "NOT-00008", "category": "GENERAL", "title": None, "text": "First"},
            {"note_id": "NOT-00022", "category": "GENERAL", "title": None, "text": "Second"}
        ]
    }

    # Step 1: Renumber first
    renumbered = _remedy_notes_structure(fact)
    assert renumbered is True
    assert [n["note_id"] for n in fact["notes"]] == ["NOT-00001", "NOT-00002"]

    # Step 2: Add note via fallback
    added = _remedy_fact_type(fact, allow_fallback=True)
    assert added is True
    assert len(fact["notes"]) == 3

    # Verify contiguous numbering and provenance note properties
    note_ids = [n["note_id"] for n in fact["notes"]]
    assert note_ids == ["NOT-00001", "NOT-00002", "NOT-00003"]
    assert fact["notes"][2]["note_id"] == "NOT-00003"
    assert fact["notes"][2]["category"] == "PROVENANCE"


# -----------------------------------------------------------------------------
# Correction 4: _remedy_date_modifier
# -----------------------------------------------------------------------------

@pytest.mark.unit
def test_remedy_date_modifier_normalization():
    """Verifies date modifier is capitalized and mapped from synonym."""
    fact = {
        "date_interpreted": {
            "modifier": "abt.",
            "date_start": "1845",
            "date_end": None,
        }
    }
    assert _remedy_date_modifier(fact) is True
    assert fact["date_interpreted"]["modifier"] == "ABT"


@pytest.mark.unit
def test_remedy_date_modifier_prunes_discrete_end_date():
    """Verifies non-range modifier forces date_end to null."""
    fact = {
        "date_interpreted": {
            "modifier": "EXACT",
            "date_start": "1845-05-12",
            "date_end": "1845-05-13",
        }
    }
    assert _remedy_date_modifier(fact) is True
    assert fact["date_interpreted"]["date_end"] is None


@pytest.mark.unit
def test_remedy_date_modifier_preserves_range_end_date():
    """Verifies range modifier retains its valid date_end."""
    fact = {
        "date_interpreted": {
            "modifier": "BET",
            "date_start": "1845",
            "date_end": "1848",
        }
    }
    assert _remedy_date_modifier(fact) is False
    assert fact["date_interpreted"]["date_end"] == "1848"


# -----------------------------------------------------------------------------
# Correction 5: _remedy_reciprocal_union
# -----------------------------------------------------------------------------

@pytest.mark.unit
def test_remedy_reciprocal_union_success():
    """Verifies creation of reciprocal marriage fact for unlinked spouse."""
    source_fact = {
        "fact_id": "00000000-0000-4000-8000-000000000001",
        "person_id": "IND-00001",
        "fact_type": "Marriage",
        "associated_people": [
            {"person_id": "IND-00002", "role": "Spouse"},
            {"person_id": "IND-00099", "role": "Witness"},
        ],
        "notes": [],
    }

    facts_mgr = GDAFacts()
    facts_mgr.add(source_fact)

    assert _remedy_reciprocal_union(facts_mgr, source_fact) is True
    assert len(facts_mgr) == 2

    spouse_facts = facts_mgr.get_by_person("IND-00002")
    assert len(spouse_facts) == 1
    reciprocal = spouse_facts[0]

    assert reciprocal["fact_type"] == "Marriage"
    assert reciprocal["person_id"] == "IND-00002"

    roles = {p["person_id"]: p["role"] for p in reciprocal["associated_people"]}
    assert roles["IND-00001"] == "Spouse"
    assert roles["IND-00099"] == "Witness"

    assert len(reciprocal["notes"]) == 1
    assert reciprocal["notes"][0]["category"] == "PROVENANCE"
    assert reciprocal["notes"][0]["title"] == "Recorded by facts_md.remedy_facts"


@pytest.mark.unit
def test_remedy_reciprocal_union_skipped_if_already_exists():
    """Verifies reciprocal generation skips when reciprocal fact is already present."""
    fact_a = {
        "fact_id": "00000000-0000-4000-8000-000000000001",
        "person_id": "IND-00001",
        "fact_type": "Marriage",
        "associated_people": [{"person_id": "IND-00002", "role": "Spouse"}],
    }
    fact_b = {
        "fact_id": "00000000-0000-4000-8000-000000000002",
        "person_id": "IND-00002",
        "fact_type": "Marriage",
        "associated_people": [{"person_id": "IND-00001", "role": "Spouse"}],
    }

    facts_mgr = GDAFacts()
    facts_mgr.add(fact_a)
    facts_mgr.add(fact_b)

    assert _remedy_reciprocal_union(facts_mgr, fact_a) is False
    assert len(facts_mgr) == 2


# -----------------------------------------------------------------------------
# Integrated Pipeline
# -----------------------------------------------------------------------------

@pytest.mark.unit
def test_remedy_facts_pipeline():
    """Verifies that remedy_facts runs all active remedies across targets."""
    fact = {
        "fact_id": "00000000-0000-4000-8000-000000000010",
        "person_id": "IND-00010",
        "fact_type": "marriage",
        "date_interpreted": {
            "modifier": "abt.",
            "date_start": "1880",
            "date_end": "1882",
        },
        "associated_people": [{"person_id": "IND-00011", "role": "Spouse"}],
        "notes": "Wedding celebrated in church.",
    }

    facts_mgr = GDAFacts()
    facts_mgr.add(fact)

    stats = remedy_facts(facts_mgr, target_ids={"00000000-0000-4000-8000-000000000010"})

    assert stats["fact_type_fixed"] == 1
    assert stats["notes_fixed"] == 1
    assert stats["dates_fixed"] == 1
    assert stats["reciprocals_added"] == 1

    cleaned = facts_mgr.get("00000000-0000-4000-8000-000000000010")
    assert cleaned["fact_type"] == "Marriage"
    assert cleaned["date_interpreted"]["modifier"] == "ABT"
    assert cleaned["date_interpreted"]["date_end"] is None
    assert isinstance(cleaned["notes"], list)
    assert cleaned["notes"][0]["note_id"] == "NOT-00001"