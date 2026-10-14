# Name: test_util.py
# Path: tools/lib/gdacore/tests/test_util.py
# Version: 1.0.0+build.rc1

"""Unit test suite verifying GDAUtil, GDANote, and GDANoteCollection primitives.

Operational Role:
    Validates atomic JSON I/O, Safe Backup Protocol, numeric high-water mark
    sequence extraction, recursive tombstone graveyard resolution, fuzzy matching,
    string normalization slugs, timestamp parsing, size formatting, hash calculation,
    note collection lifecycle operations, and runtime reflection introspection.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly marked with @pytest.mark.unit; basic sanity
      checks tagged with @pytest.mark.smoke; boundary cases with @pytest.mark.regression.
    - Dependencies: Isolated hermetic tmp_path sandboxes without production disk I/O.
"""

from __future__ import annotations

__version__ = "1.0.0+build.rc1"

from collections.abc import Sequence
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from gdacore import config
from gdacore.config import GDAConfig
from gdacore.util import GDANote, GDANoteCollection, GDAUtil


# ==============================================================================
# GROUP 1: Numeric High-Water Mark Sequence Extraction
# Note: Verification of find_max_numeric_id parsing and boundary safety
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_find_max_numeric_id_extracts_highest() -> None:
    """Verify find_max_numeric_id extracts highest integer from ID list."""
    ids = ["IND-00001", "IND-00042", "IND-00010"]
    assert GDAUtil.find_max_numeric_id(ids) == 42


@pytest.mark.unit
@pytest.mark.smoke
def test_find_max_numeric_id_unhyphenated_trailing_digits() -> None:
    """Verify find_max_numeric_id extracts trailing digits without hyphen."""
    ids = ["TAG00012", "TAG00088", "TAG00005"]
    assert GDAUtil.find_max_numeric_id(ids) == 88


@pytest.mark.unit
@pytest.mark.regression
def test_find_max_numeric_id_empty_list_returns_zero() -> None:
    """Verify find_max_numeric_id returns 0 when given an empty list."""
    assert GDAUtil.find_max_numeric_id([]) == 0


@pytest.mark.unit
@pytest.mark.regression
def test_find_max_numeric_id_non_sequence_type_returns_zero() -> None:
    """Verify find_max_numeric_id returns 0 when input is not a sequence."""
    assert GDAUtil.find_max_numeric_id("IND-00042") == 0  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.regression
def test_find_max_numeric_id_none_input_returns_zero() -> None:
    """Verify find_max_numeric_id returns 0 safely when passed None."""
    assert GDAUtil.find_max_numeric_id(None) == 0  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.regression
def test_find_max_numeric_id_no_digits_returns_zero() -> None:
    """Verify find_max_numeric_id returns 0 when items lack any numeric digits."""
    assert GDAUtil.find_max_numeric_id(["NO_DIGITS_HERE", "NONE"]) == 0


@pytest.mark.unit
@pytest.mark.regression
def test_find_max_numeric_id_ignores_non_digit_suffix() -> None:
    """Verify find_max_numeric_id ignores items whose hyphen suffix is not numeric."""
    assert GDAUtil.find_max_numeric_id(["IND-TEMP", "IND-00004"]) == 4


@pytest.mark.unit
@pytest.mark.regression
def test_find_max_numeric_id_ignores_non_string_items() -> None:
    """Verify find_max_numeric_id safely skips non-string elements in list."""
    assert GDAUtil.find_max_numeric_id([123, None, "IND-00005"]) == 5  # type: ignore[list-item]


@pytest.mark.unit
@pytest.mark.regression
def test_find_max_numeric_id_handles_extended_sequences_over_99999() -> None:
    """Verify find_max_numeric_id parses numeric sequences exceeding 5 digits."""
    ids = ["IND-00001", "IND-100050", "IND-00042"]
    assert GDAUtil.find_max_numeric_id(ids) == 100050


@pytest.mark.unit
@pytest.mark.regression
def test_find_max_numeric_id_trailing_hyphen_empty_suffix_returns_zero() -> None:
    """Verify find_max_numeric_id safely handles items with trailing hyphens and empty suffixes."""
    assert GDAUtil.find_max_numeric_id(["IND-"]) == 0


@pytest.mark.unit
@pytest.mark.regression
def test_find_max_numeric_id_short_unpadded_digit_suffix() -> None:
    """Verify find_max_numeric_id correctly converts single-digit unpadded suffixes."""
    assert GDAUtil.find_max_numeric_id(["IND-1", "IND-00002"]) == 2


@pytest.mark.unit
@pytest.mark.regression
def test_find_max_numeric_id_continues_loop_after_skipped_item() -> None:
    """Verify find_max_numeric_id continues loop iteration when invalid token is mid-list."""
    ids = ["IND-00001", "NO_DIGITS", 999, "IND-00055"]
    assert GDAUtil.find_max_numeric_id(ids) == 55  # type: ignore[list-item]


# ==============================================================================
# GROUP 2: GDANote Dataclass Primitive
# Note: Verification of 4-key canonical dictionary contract and attribute access
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_gda_note_to_dict_contract() -> None:
    """Verify GDANote.to_dict produces exact 4-key canonical dictionary."""
    note = GDANote(
        note_id="NOT-00001",
        note_type="RESEARCH",
        note_text="Primary research note.",
        modified_date="2026-10-10T12:00:00Z",
    )
    expected = {
        "note_id": "NOT-00001",
        "note_type": "RESEARCH",
        "note_text": "Primary research note.",
        "modified_date": "2026-10-10T12:00:00Z",
    }
    assert note.to_dict() == expected


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_note_attribute_access() -> None:
    """Verify GDANote allows direct typed attribute access."""
    note = GDANote(
        note_id="NOT-00001",
        note_type="DISCREPANCY",
        note_text="Age mismatch in 1860 census.",
        modified_date="2026-10-10T12:00:00Z",
    )
    assert note.note_id == "NOT-00001"
    assert note.note_type == "DISCREPANCY"


# ==============================================================================
# GROUP 3: GDANoteCollection Management & Sequence Protocols
# Note: Verification of note ingestion, sequence slicing, containment, and CRUD
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_init_empty() -> None:
    """Verify GDANoteCollection initializes empty when passed None."""
    notes = GDANoteCollection()
    assert len(notes) == 0


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_init_empty_list_bypasses_load_loop() -> None:
    """Verify GDANoteCollection initializes empty when passed an explicit empty list."""
    notes = GDANoteCollection([])
    assert len(notes) == 0


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_init_from_entity_dict() -> None:
    """Verify GDANoteCollection extracts notes list from entity dictionary."""
    entity = {
        "person_id": "IND-00001",
        "notes": [
            {
                "note_id": "NOT-00001",
                "note_type": "RESEARCH",
                "note_text": "Sample note",
                "modified_date": "2026-10-10T08:00:00Z",
            }
        ],
    }
    notes = GDANoteCollection(entity)
    assert len(notes) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_init_ignores_non_dict_elements() -> None:
    """Verify GDANoteCollection skips non-dict candidates during initialization."""
    raw = [None, "invalid_string", 123, {"note_text": "Valid note"}]
    notes = GDANoteCollection(raw)  # type: ignore[arg-type]
    assert len(notes) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_init_memory_isolation() -> None:
    """Verify GDANoteCollection enforces memory isolation on input dictionaries."""
    raw = [
        {
            "note_id": "NOT-00001",
            "note_type": "RESEARCH",
            "note_text": "Original text",
            "modified_date": "2026-10-10T08:00:00Z",
        }
    ]
    notes = GDANoteCollection(raw)
    raw[0]["note_text"] = "Mutated Externally"
    assert notes[0].note_text == "Original text"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_sequence_slicing() -> None:
    """Verify GDANoteCollection supports slice indexing returning list of notes."""
    notes = GDANoteCollection()
    notes.add("Note 1")
    notes.add("Note 2")
    notes.add("Note 3")
    sliced = notes[0:2]
    assert isinstance(sliced, list)
    assert len(sliced) == 2
    assert sliced[0].note_text == "Note 1"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_contains_protocol() -> None:
    """Verify GDANoteCollection supports in operator for string IDs and GDANote instances."""
    notes = GDANoteCollection()
    n1 = notes.add("Note 1")
    assert "NOT-00001" in notes
    assert n1 in notes
    assert "NOT-99999" not in notes
    assert 42 not in notes  # type: ignore[operator]


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_iteration() -> None:
    """Verify GDANoteCollection supports iteration yielding GDANote copies."""
    notes = GDANoteCollection()
    notes.add("Note 1")
    notes.add("Note 2")
    collected = [n.note_text for n in notes]
    assert collected == ["Note 1", "Note 2"]


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_mint_initial_id() -> None:
    """Verify mint_next_id allocates NOT-00001 when collection is empty."""
    notes = GDANoteCollection()
    assert notes.mint_next_id() == "NOT-00001"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_mint_next_id_when_populated() -> None:
    """Verify mint_next_id allocates sequential ID when collection is populated."""
    notes = GDANoteCollection()
    notes.add("Note 1")
    assert notes.mint_next_id() == "NOT-00002"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_add_returns_gda_note() -> None:
    """Verify add method returns GDANote instance with minted ID and timestamps."""
    notes = GDANoteCollection()
    created = notes.add("First note entry")
    assert isinstance(created, GDANote)
    assert created.note_id == "NOT-00001"
    assert created.note_text == "First note entry"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_add_sequential_increment() -> None:
    """Verify consecutive add calls increment sequential note identifiers."""
    notes = GDANoteCollection()
    notes.add("Note 1")
    n2 = notes.add("Note 2")
    assert n2.note_id == "NOT-00002"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_add_many_batch() -> None:
    """Verify add_many appends multiple notes and returns minted IDs."""
    notes = GDANoteCollection()
    batch = [
        {"note_text": "Batch note 1", "note_type": "RESEARCH"},
        {"note_text": "Batch note 2", "note_type": "TRANSCRIPTION"},
    ]
    minted_ids = notes.add_many(batch)
    assert minted_ids == ["NOT-00001", "NOT-00002"]
    assert len(notes) == 2


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_add_many_skips_non_dict_items() -> None:
    """Verify add_many skips elements that are not mappings."""
    notes = GDANoteCollection()
    batch = [None, "invalid", {"note_text": "Valid note"}]
    minted_ids = notes.add_many(batch)  # type: ignore[arg-type]
    assert minted_ids == ["NOT-00001"]
    assert len(notes) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_add_empty_text_raises_value_error() -> None:
    """Verify add raises ValueError when note_text is empty or whitespace."""
    notes = GDANoteCollection()
    with pytest.raises(ValueError, match="cannot be empty"):
        notes.add("   ")


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_controlled_vocabulary_enforcement_on_add() -> None:
    """Verify add raises ValueError when note_type violates controlled vocabulary."""
    notes = GDANoteCollection(valid_types={"RESEARCH", "DISCREPANCY"})
    with pytest.raises(ValueError, match="Invalid note_type 'INVALID'"):
        notes.add("Text", note_type="INVALID")


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_controlled_vocabulary_enforcement_on_init() -> None:
    """Verify initialization raises ValueError if loaded note has an invalid note_type."""
    raw = [
        {
            "note_id": "NOT-00001",
            "note_type": "FORBIDDEN",
            "note_text": "Bad",
            "modified_date": "2026-10-10T00:00:00Z",
        }
    ]
    with pytest.raises(ValueError, match="Invalid note_type 'FORBIDDEN'"):
        GDANoteCollection(raw, valid_types={"RESEARCH"})


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_get_existing() -> None:
    """Verify get returns a deep copy of the requested note."""
    notes = GDANoteCollection()
    n = notes.add("Test note text")
    entry = notes.get(n.note_id)
    assert entry is not None and entry.note_text == "Test note text"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_get_second_note() -> None:
    """Verify get traverses multiple notes and retrieves subsequent match."""
    notes = GDANoteCollection()
    notes.add("First")
    notes.add("Second")
    entry = notes.get("NOT-00002")
    assert entry is not None and entry.note_text == "Second"


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_get_missing_returns_none() -> None:
    """Verify get returns None when note_id does not exist."""
    notes = GDANoteCollection()
    assert notes.get("NOT-99999") is None


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_update_success() -> None:
    """Verify update mutates note text and updates modified_date in-place."""
    notes = GDANoteCollection()
    n = notes.add("Initial text")
    success = notes.update(n.note_id, note_text="Revised text")
    assert success is True
    assert notes.get(n.note_id).note_text == "Revised text"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_update_advances_timestamp_beyond_original() -> None:
    """Verify update automatically advances modified_date past original creation timestamp."""
    notes = GDANoteCollection()
    created = notes.add("Initial note text", modified_date="2020-01-01T00:00:00Z")
    success = notes.update(created.note_id, note_text="Updated note text")
    assert success is True
    assert notes.get(created.note_id).modified_date > "2020-01-01T00:00:00Z"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_update_type_only_preserves_text() -> None:
    """Verify update mutates note_type without touching note_text when note_text is None."""
    notes = GDANoteCollection()
    created = notes.add("Original text", note_type="RESEARCH")
    success = notes.update(created.note_id, note_type="DISCREPANCY")
    assert success is True
    assert notes[0].note_type == "DISCREPANCY"
    assert notes[0].note_text == "Original text"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_update_text_only_preserves_type() -> None:
    """Verify update mutates note_text without touching note_type when note_type is None."""
    notes = GDANoteCollection()
    created = notes.add("Original text", note_type="RESEARCH")
    success = notes.update(created.note_id, note_text="Altered text")
    assert success is True
    assert notes[0].note_text == "Altered text"
    assert notes[0].note_type == "RESEARCH"


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_update_missing_returns_false() -> None:
    """Verify update returns False when note_id is absent from an empty collection."""
    notes = GDANoteCollection()
    assert notes.update("NOT-99999", note_text="New") is False


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_update_missing_in_populated_collection_returns_false() -> None:
    """Verify update iterates through notes and returns False when note_id is absent."""
    notes = GDANoteCollection()
    notes.add("Existing note 1")
    notes.add("Existing note 2")
    assert notes.update("NOT-99999", note_text="Nonexistent") is False


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_update_empty_text_raises_value_error() -> None:
    """Verify update raises ValueError when replacement text is empty or whitespace."""
    notes = GDANoteCollection()
    n = notes.add("Initial text")
    with pytest.raises(ValueError, match="cannot be empty"):
        notes.update(n.note_id, note_text="   ")


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_update_invalid_type_raises_value_error() -> None:
    """Verify update raises ValueError when new note_type violates vocabulary."""
    notes = GDANoteCollection(valid_types={"RESEARCH", "DISCREPANCY"})
    n = notes.add("Valid", note_type="RESEARCH")
    with pytest.raises(ValueError, match="Invalid note_type"):
        notes.update(n.note_id, note_type="INVALID")


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_remove_renumbers_and_preserves_timestamp() -> None:
    """Verify remove excises target note, renumbers remaining sequentially, and preserves timestamps."""
    notes = GDANoteCollection()
    notes.add("Note 1", modified_date="2026-10-01T10:00:00Z")
    notes.add("Note 2", modified_date="2026-10-02T10:00:00Z")
    notes.add("Note 3", modified_date="2026-10-03T10:00:00Z")

    removed = notes.remove("NOT-00002")
    assert removed is True
    assert len(notes) == 2

    exported = notes.to_list()
    assert exported[0]["note_id"] == "NOT-00001"
    assert exported[0]["note_text"] == "Note 1"
    assert exported[0]["modified_date"] == "2026-10-01T10:00:00Z"

    assert exported[1]["note_id"] == "NOT-00002"
    assert exported[1]["note_text"] == "Note 3"
    assert exported[1]["modified_date"] == "2026-10-03T10:00:00Z"


@pytest.mark.unit
@pytest.mark.regression
def test_note_collection_remove_missing_returns_false() -> None:
    """Verify remove returns False when note_id is absent."""
    notes = GDANoteCollection()
    assert notes.remove("NOT-99999") is False


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_to_list_isolation() -> None:
    """Verify to_list returns deep copies isolated from internal state mutations."""
    notes = GDANoteCollection()
    notes.add("Original entry")
    exported = notes.to_list()
    exported[0]["note_text"] = "Mutated Export"
    assert notes[0].note_text == "Original entry"


@pytest.mark.unit
@pytest.mark.smoke
def test_note_collection_to_list_empty() -> None:
    """Verify to_list returns an empty list when collection contains zero notes."""
    notes = GDANoteCollection()
    assert notes.to_list() == []


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_create_note_collection_factory() -> None:
    """Verify GDAUtil.create_note_collection constructs a functional GDANoteCollection."""
    raw = [{"note_id": "NOT-00001", "note_text": "Factory", "note_type": "RESEARCH"}]
    collection = GDAUtil.create_note_collection(raw)
    assert isinstance(collection, GDANoteCollection)
    assert len(collection) == 1


# ==============================================================================
# GROUP 4: Graveyard Resolution & Multi-Field Fuzzy Match
# Note: Verification of recursive tombstone redirect traversal and text comparison
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_resolve_superseded_id_returns_same_for_active_id() -> None:
    """Verify resolve_superseded_id returns input unchanged if not in graveyard."""
    graveyard: dict[str, dict[str, str]] = {}
    assert GDAUtil.resolve_superseded_id("IND-00001", graveyard) == "IND-00001"


@pytest.mark.unit
@pytest.mark.smoke
def test_resolve_superseded_id_single_hop() -> None:
    """Verify resolve_superseded_id traces a single tombstone redirect."""
    graveyard = {"IND-00001": {"superseded_by": "IND-00002"}}
    assert GDAUtil.resolve_superseded_id("IND-00001", graveyard) == "IND-00002"


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_superseded_id_multi_hop_chain() -> None:
    """Verify resolve_superseded_id traces chained multi-hop redirects."""
    graveyard = {
        "IND-00001": {"superseded_by": "IND-00002"},
        "IND-00002": {"superseded_by": "IND-00003"},
    }
    assert GDAUtil.resolve_superseded_id("IND-00001", graveyard) == "IND-00003"


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_superseded_id_detects_circular_loop() -> None:
    """Verify resolve_superseded_id raises RecursionError on direct circular reference."""
    graveyard = {
        "IND-00001": {"superseded_by": "IND-00002"},
        "IND-00002": {"superseded_by": "IND-00001"},
    }
    with pytest.raises(RecursionError, match="Circular graveyard reference"):
        GDAUtil.resolve_superseded_id("IND-00001", graveyard)


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_superseded_id_stops_on_missing_target_key() -> None:
    """Verify resolve_superseded_id returns current node if superseded_by is None or missing."""
    graveyard = {"IND-00001": {"is_deprecated": True, "superseded_by": None}}
    assert GDAUtil.resolve_superseded_id("IND-00001", graveyard) == "IND-00001"


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_superseded_id_stops_on_empty_string_target() -> None:
    """Verify resolve_superseded_id returns current node when superseded_by is an empty string."""
    graveyard = {"IND-00001": {"is_deprecated": True, "superseded_by": ""}}
    assert GDAUtil.resolve_superseded_id("IND-00001", graveyard) == "IND-00001"


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_superseded_id_stops_on_non_dict_metadata() -> None:
    """Verify resolve_superseded_id returns current node if graveyard value is not a mapping."""
    graveyard = {"IND-00001": "corrupt_meta_string"}  # type: ignore[dict-item]
    assert GDAUtil.resolve_superseded_id("IND-00001", graveyard) == "IND-00001"


@pytest.mark.unit
@pytest.mark.regression
def test_resolve_superseded_id_exceeds_max_hops_raises_recursion_error() -> None:
    """Verify resolve_superseded_id raises RecursionError when redirect hops reach max_hops threshold."""
    graveyard = {
        "IND-00001": {"superseded_by": "IND-00002"},
        "IND-00002": {"superseded_by": "IND-00003"},
        "IND-00003": {"superseded_by": "IND-00004"},
    }
    with pytest.raises(RecursionError, match="Graveyard redirect loop exceeded max_hops=2"):
        GDAUtil.resolve_superseded_id("IND-00001", graveyard, max_hops=2)


@pytest.mark.unit
@pytest.mark.smoke
def test_match_text_exact_substring() -> None:
    """Verify match_text returns True for direct case-insensitive substring match."""
    assert GDAUtil.match_text("Strafford", "Strafford County") is True


@pytest.mark.unit
@pytest.mark.smoke
def test_match_text_fuzzy_similarity() -> None:
    """Verify match_text returns True for high similarity typographical variance."""
    assert GDAUtil.match_text("Somersworth", "Summersworth", min_ratio=0.8) is True


@pytest.mark.unit
@pytest.mark.regression
def test_match_text_below_threshold_returns_false() -> None:
    """Verify match_text returns False when ratio falls below min_ratio."""
    assert GDAUtil.match_text("Dover", "Concord", min_ratio=0.8) is False


@pytest.mark.unit
@pytest.mark.regression
def test_match_text_empty_strings_return_false() -> None:
    """Verify match_text returns False if either string argument is empty."""
    assert GDAUtil.match_text("", "Dover") is False


# ==============================================================================
# GROUP 5: JSON I/O and Safe Backup Protocol
# Note: Verification of atomic writes, pre-write snapshots, and rollback
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_save_json_returns_target_path(tmp_path: Path) -> None:
    """Verify save_json returns the resolved target file path."""
    target_file = tmp_path / "sample.json"
    result_path = GDAUtil.save_json(target_file, {"count": 42})
    assert result_path == target_file


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_save_json_persists_payload(tmp_path: Path) -> None:
    """Verify save_json persists accurate data loadable by load_json."""
    target_file = tmp_path / "sample.json"
    data = {"status": "active", "count": 42}
    GDAUtil.save_json(target_file, data)
    assert GDAUtil.load_json(target_file) == data


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_read_json_returns_payload_when_exists(tmp_path: Path) -> None:
    """Verify read_json reads valid JSON payload when file exists."""
    target_file = tmp_path / "config.json"
    GDAUtil.save_json(target_file, {"loaded": True})
    assert GDAUtil.read_json(target_file) == {"loaded": True}


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_read_json_returns_default_when_missing(tmp_path: Path) -> None:
    """Verify read_json returns specified default when file does not exist."""
    missing_file = tmp_path / "missing.json"
    assert GDAUtil.read_json(missing_file, default={}) == {}


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_load_json_missing_raises_filenotfound(tmp_path: Path) -> None:
    """Verify load_json raises FileNotFoundError when target path is missing."""
    missing_file = tmp_path / "ghost.json"
    with pytest.raises(FileNotFoundError, match="JSON file not found"):
        GDAUtil.load_json(missing_file)


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_load_json_malformed_raises_value_error(tmp_path: Path) -> None:
    """Verify load_json wraps JSONDecodeError into informative ValueError."""
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{bad_json:", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed JSON in"):
        GDAUtil.load_json(corrupt_file)


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_save_json_cleans_tmp_on_serialization_failure(tmp_path: Path) -> None:
    """Verify save_json removes dangling .tmp file if JSON serialization fails."""
    target_file = tmp_path / "fail.json"
    with pytest.raises(TypeError):
        GDAUtil.save_json(target_file, {"bad": object()})
    assert not (tmp_path / "fail.json.tmp").exists()


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_save_json_target_file_not_created_on_failure(tmp_path: Path) -> None:
    """Verify target file is not left behind if serialization fails."""
    target_file = tmp_path / "fail.json"
    with pytest.raises(TypeError):
        GDAUtil.save_json(target_file, {"bad": object()})
    assert not target_file.exists()


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_save_json_handles_failure_before_tmp_creation(tmp_path: Path) -> None:
    """Verify save_json handles I/O exceptions when write operation cannot open file."""
    target_file = tmp_path / "fail_io.json"
    with patch("builtins.open", side_effect=OSError("Disk write prohibited")):
        with pytest.raises(OSError, match="Disk write prohibited"):
            GDAUtil.save_json(target_file, {"valid": "payload"})
    assert not target_file.exists()


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_save_json_retries_transient_permission_error(tmp_path: Path) -> None:
    """Verify save_json retries atomic replace upon encountering transient locking."""
    target_file = tmp_path / "retry.json"
    attempts = [0]
    orig_replace = Path.replace

    def mock_replace(self, target):
        if str(self).endswith(".tmp") and attempts[0] == 0:
            attempts[0] += 1
            raise PermissionError("Locked by antivirus")
        return orig_replace(self, target)

    with patch.object(Path, "replace", autospec=True, side_effect=mock_replace):
        result = GDAUtil.save_json(target_file, {"status": "ok"})
        assert result.exists()
        assert attempts[0] == 1


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_save_json_replace_exhausts_retries_raises(tmp_path: Path) -> None:
    """Verify save_json raises after exhausting three replace attempts."""
    target_file = tmp_path / "exhaust_retries.json"
    with patch.object(Path, "replace", side_effect=PermissionError("Locked continuously")):
        with pytest.raises(PermissionError, match="Locked continuously"):
            GDAUtil.save_json(target_file, {"data": "persist"})


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_save_json_cleanup_unlink_oserror_suppressed(tmp_path: Path) -> None:
    """Verify save_json suppresses OSError if temp_dest unlink fails during cleanup."""
    target_file = tmp_path / "fail_cleanup.json"
    orig_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if str(self).endswith(".tmp"):
            raise OSError("Temp file locked by virus scan")
        return orig_unlink(self, *args, **kwargs)

    with patch.object(Path, "unlink", autospec=True, side_effect=mock_unlink):
        with pytest.raises(TypeError):
            GDAUtil.save_json(target_file, {"unserializable": object()})


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_save_json_skip_backup_when_not_requested(tmp_path: Path) -> None:
    """Verify save_json does not create a backup when create_backup is False."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "entity.json"
    GDAUtil.save_json(target_file, {"version": 1})
    GDAUtil.save_json(target_file, {"version": 2}, create_backup=False, backup_dir=backup_dir)
    assert not backup_dir.exists()


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_save_json_skip_backup_for_new_file(tmp_path: Path) -> None:
    """Verify save_json skips backup creation if target file does not yet exist on disk."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "brand_new.json"
    GDAUtil.save_json(target_file, {"initial": True}, create_backup=True, backup_dir=backup_dir)
    assert len(GDAUtil.list_backups(target_file, backup_dir=backup_dir)) == 0


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_save_json_creates_backup_when_file_exists(tmp_path: Path) -> None:
    """Verify save_json creates a safe backup snapshot when overwriting existing file."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "sites.json"
    GDAUtil.save_json(target_file, {"state": "original"}, create_backup=False)
    GDAUtil.save_json(target_file, {"state": "mutated"}, create_backup=True, backup_dir=backup_dir)
    assert len(GDAUtil.list_backups(target_file, backup_dir=backup_dir)) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_save_json_backup_preserves_original_content(tmp_path: Path) -> None:
    """Verify backup snapshot retains previous file state prior to overwrite."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "sites.json"
    GDAUtil.save_json(target_file, {"state": "original"}, create_backup=False)
    GDAUtil.save_json(target_file, {"state": "mutated"}, create_backup=True, backup_dir=backup_dir)
    backup_file = GDAUtil.list_backups(target_file, backup_dir=backup_dir)[0]
    assert GDAUtil.load_json(backup_file) == {"state": "original"}


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_create_safe_backup_missing_file_raises(tmp_path: Path) -> None:
    """Verify create_safe_backup raises FileNotFoundError when target does not exist."""
    missing_file = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError, match="Cannot backup non-existent file"):
        GDAUtil.create_safe_backup(missing_file)


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_create_safe_backup_with_label(tmp_path: Path) -> None:
    """Verify create_safe_backup embeds custom label token in backup filename."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "registry.json"
    GDAUtil.save_json(target_file, {"data": True})
    backup_path = GDAUtil.create_safe_backup(target_file, label="pre_ingest", backup_dir=backup_dir)
    assert backup_path.name == "registry.json.pre_ingest.bk"


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_create_safe_backup_default_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify create_safe_backup falls back to config.CONFIG.backups when backup_dir is None."""
    sandbox_config = GDAConfig(root=tmp_path.resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)
    target_file = tmp_path / "default_target.json"
    GDAUtil.save_json(target_file, {"default": True})
    backup_path = GDAUtil.create_safe_backup(target_file, label="snap_default")
    assert backup_path.parent == sandbox_config.backups


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_list_backups_sorted_chronological(tmp_path: Path) -> None:
    """Verify list_backups orders snapshots newest to oldest by modification time."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "test.json"
    GDAUtil.save_json(target_file, {"v": 0})
    b1 = GDAUtil.create_safe_backup(target_file, label="snap_1", backup_dir=backup_dir)
    b2 = GDAUtil.create_safe_backup(target_file, label="snap_2", backup_dir=backup_dir)

    now = datetime.now(timezone.utc).timestamp()
    os.utime(b1, (now - 300, now - 300))
    os.utime(b2, (now - 100, now - 100))

    backups = GDAUtil.list_backups(target_file, backup_dir=backup_dir)
    assert backups[0].name == b2.name


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_list_backups_empty_when_directory_missing(tmp_path: Path) -> None:
    """Verify list_backups returns an empty list if backup_dir does not exist."""
    missing_dir = tmp_path / "nonexistent_backups"
    assert GDAUtil.list_backups(tmp_path / "foo.json", backup_dir=missing_dir) == []


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_restore_backup_most_recent(tmp_path: Path) -> None:
    """Verify restore_backup restores the latest backup when label is omitted."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "config.json"
    GDAUtil.save_json(target_file, {"step": 1})
    b1 = GDAUtil.create_safe_backup(target_file, label="first", backup_dir=backup_dir)
    GDAUtil.save_json(target_file, {"step": 2})
    b2 = GDAUtil.create_safe_backup(target_file, label="second", backup_dir=backup_dir)

    now = datetime.now(timezone.utc).timestamp()
    os.utime(b1, (now - 300, now - 300))
    os.utime(b2, (now - 100, now - 100))

    GDAUtil.save_json(target_file, {"step": "corrupted"})
    GDAUtil.restore_backup(target_file, backup_dir=backup_dir)
    assert GDAUtil.load_json(target_file) == {"step": 2}


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_restore_backup_specific_label(tmp_path: Path) -> None:
    """Verify restore_backup restores targeted snapshot matching label token."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "locations.json"
    GDAUtil.save_json(target_file, {"version": "golden"})
    GDAUtil.create_safe_backup(target_file, label="golden_tag", backup_dir=backup_dir)
    GDAUtil.save_json(target_file, {"version": "dirty"})
    GDAUtil.restore_backup(target_file, label_or_timestamp="golden_tag", backup_dir=backup_dir)
    assert GDAUtil.load_json(target_file) == {"version": "golden"}


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_restore_backup_missing_label_raises(tmp_path: Path) -> None:
    """Verify restore_backup raises FileNotFoundError when specified label is absent."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "missing_label.json"
    GDAUtil.save_json(target_file, {"seed": 1})
    with pytest.raises(FileNotFoundError, match="Requested backup does not exist"):
        GDAUtil.restore_backup(target_file, label_or_timestamp="ghost_label", backup_dir=backup_dir)


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_restore_backup_no_backups_found_raises(tmp_path: Path) -> None:
    """Verify restore_backup raises FileNotFoundError when no backups exist for file."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "no_backups.json"
    GDAUtil.save_json(target_file, {"seed": 1})
    with pytest.raises(FileNotFoundError, match="No backups found"):
        GDAUtil.restore_backup(target_file, backup_dir=backup_dir)


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_prune_backups_enforces_retention_limit(tmp_path: Path) -> None:
    """Verify prune_backups leaves only the specified number of snapshots intact."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "archive.json"
    GDAUtil.save_json(target_file, {"seed": True})
    now = datetime.now(timezone.utc).timestamp()
    for idx in range(5):
        b = GDAUtil.create_safe_backup(target_file, label=f"snap_{idx}", backup_dir=backup_dir)
        ts = now - (500 - idx * 100)
        os.utime(b, (ts, ts))
    GDAUtil.prune_backups(target_file, keep=2, backup_dir=backup_dir)
    assert len(GDAUtil.list_backups(target_file, backup_dir=backup_dir)) == 2


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_prune_backups_returns_unlinked_paths(tmp_path: Path) -> None:
    """Verify prune_backups returns exact list of unlinked snapshot paths."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "archive.json"
    GDAUtil.save_json(target_file, {"seed": True})
    now = datetime.now(timezone.utc).timestamp()
    for idx in range(5):
        b = GDAUtil.create_safe_backup(target_file, label=f"snap_{idx}", backup_dir=backup_dir)
        ts = now - (500 - idx * 100)
        os.utime(b, (ts, ts))
    pruned = GDAUtil.prune_backups(target_file, keep=2, backup_dir=backup_dir)
    assert len(pruned) == 3


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_prune_backups_no_op_when_within_limit(tmp_path: Path) -> None:
    """Verify prune_backups returns empty list when backup count <= keep."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "small_archive.json"
    GDAUtil.save_json(target_file, {"seed": True})
    GDAUtil.create_safe_backup(target_file, label="snap_0", backup_dir=backup_dir)
    assert GDAUtil.prune_backups(target_file, keep=5, backup_dir=backup_dir) == []


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_prune_backups_invalid_keep_raises(tmp_path: Path) -> None:
    """Verify prune_backups raises ValueError when keep parameter < 1."""
    with pytest.raises(ValueError, match="keep parameter must be at least 1"):
        GDAUtil.prune_backups(tmp_path / "file.json", keep=0)


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_prune_backups_handles_unlink_oserror(tmp_path: Path) -> None:
    """Verify prune_backups catches and suppresses OSError during unlinking."""
    backup_dir = tmp_path / "backups"
    target_file = tmp_path / "file.json"
    GDAUtil.save_json(target_file, {"seed": True})
    for idx in range(3):
        GDAUtil.create_safe_backup(target_file, label=f"snap_{idx}", backup_dir=backup_dir)

    with patch.object(Path, "unlink", side_effect=OSError("File locked")):
        pruned = GDAUtil.prune_backups(target_file, keep=1, backup_dir=backup_dir)
    assert pruned == []


# ==============================================================================
# GROUP 6: Workspace Hygiene and Quarantine Routing
# Note: Verification of gtemp scratch clearance and isolation routing
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_clear_gtemp_deletes_scratch_items(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify clear_gtemp unlinks scratch files from temp directory."""
    sandbox_config = GDAConfig(root=tmp_path.resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)

    temp_dir = sandbox_config.temp
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "scratch.tmp").write_text("transient", encoding="utf-8")
    GDAUtil.clear_gtemp()
    assert not (temp_dir / "scratch.tmp").exists()


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_clear_gtemp_deletes_subdirectories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify clear_gtemp removes nested scratch subdirectories."""
    sandbox_config = GDAConfig(root=tmp_path.resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)

    temp_dir = sandbox_config.temp
    temp_dir.mkdir(parents=True, exist_ok=True)
    nested = temp_dir / "sub_scratch"
    nested.mkdir()
    (nested / "nested_file.tmp").write_text("sub-transient", encoding="utf-8")

    deleted = GDAUtil.clear_gtemp()
    assert deleted == 1
    assert not nested.exists()


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_clear_gtemp_preserves_gitkeep(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify clear_gtemp preserves tracking files (.gitkeep)."""
    sandbox_config = GDAConfig(root=tmp_path.resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)

    temp_dir = sandbox_config.temp
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / ".gitkeep").write_text("", encoding="utf-8")
    GDAUtil.clear_gtemp()
    assert (temp_dir / ".gitkeep").exists()


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_clear_gtemp_missing_dir_returns_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify clear_gtemp returns 0 if temp directory does not exist on disk."""
    sandbox_config = GDAConfig(root=(tmp_path / "nonexistent_root").resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)
    assert GDAUtil.clear_gtemp() == 0


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_clear_gtemp_handles_oserror(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify clear_gtemp suppresses OSError when item cannot be unlinked."""
    sandbox_config = GDAConfig(root=tmp_path.resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)

    temp_dir = sandbox_config.temp
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "locked.tmp").write_text("locked", encoding="utf-8")

    with patch.object(Path, "unlink", side_effect=OSError("Locked")):
        count = GDAUtil.clear_gtemp()
    assert count == 0


@pytest.mark.unit
@pytest.mark.regression
def test_clear_gtemp_custom_preserve_patterns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify clear_gtemp honors custom preserve_patterns parameter."""
    sandbox_config = GDAConfig(root=tmp_path.resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)

    temp_dir = sandbox_config.temp
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "keep_me.txt").write_text("safe", encoding="utf-8")
    (temp_dir / "delete_me.txt").write_text("gone", encoding="utf-8")

    deleted = GDAUtil.clear_gtemp(preserve_patterns=["keep_me.txt"])
    assert deleted == 1
    assert (temp_dir / "keep_me.txt").exists()


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_quarantine_file_relocates_file(tmp_path: Path) -> None:
    """Verify quarantine_file moves target file into designated quarantine store."""
    source_file = tmp_path / "corrupt_record.json"
    source_file.write_text("{}", encoding="utf-8")
    quarantine_dir = tmp_path / "quarantine"
    GDAUtil.quarantine_file(source_file, quarantine_dir=quarantine_dir)
    assert not source_file.exists()


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_quarantine_file_dest_exists(tmp_path: Path) -> None:
    """Verify quarantined file exists in target quarantine directory."""
    source_file = tmp_path / "corrupt_record.json"
    source_file.write_text("{}", encoding="utf-8")
    quarantine_dir = tmp_path / "quarantine"
    target = GDAUtil.quarantine_file(source_file, quarantine_dir=quarantine_dir)
    assert target.exists()


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_quarantine_file_missing_source_raises(tmp_path: Path) -> None:
    """Verify quarantine_file raises FileNotFoundError if source is missing."""
    missing = tmp_path / "ghost.json"
    with pytest.raises(FileNotFoundError, match="Cannot quarantine non-existent file"):
        GDAUtil.quarantine_file(missing)


# ==============================================================================
# GROUP 7: String, Timestamp, Cryptographic Hashing, and Introspection
# Note: Verification of normalization, slugification, ISO timestamps, and SHA-256
# ==============================================================================
@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_normalize_slug_basic() -> None:
    """Verify normalize_slug standardizes punctuation and casing into slug string."""
    assert GDAUtil.normalize_slug("John O'Connor & Sons - 1880") == "john_o_connor_sons_1880"


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_normalize_slug_custom_delimiter() -> None:
    """Verify normalize_slug respects custom separator token."""
    assert GDAUtil.normalize_slug("Strafford County", delimiter="-") == "strafford-county"


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_normalize_slug_empty_returns_empty() -> None:
    """Verify normalize_slug returns empty string when input is empty or whitespace."""
    assert GDAUtil.normalize_slug("") == ""


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_parse_iso_timestamp_utc_z() -> None:
    """Verify parse_iso_timestamp accurately parses trailing Z UTC timestamp."""
    dt = GDAUtil.parse_iso_timestamp("2026-10-10T12:00:00Z")
    assert dt.year == 2026
    assert dt.tzinfo == timezone.utc


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_parse_iso_timestamp_offset() -> None:
    """Verify parse_iso_timestamp normalizes nonzero timezone offset to UTC."""
    dt = GDAUtil.parse_iso_timestamp("2026-10-10T08:00:00-04:00")
    assert dt.hour == 12
    assert dt.tzinfo == timezone.utc


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_parse_iso_timestamp_naive_assumes_utc() -> None:
    """Verify parse_iso_timestamp pins naive timestamp strings to UTC."""
    dt = GDAUtil.parse_iso_timestamp("2026-10-10T12:00:00")
    assert dt.tzinfo == timezone.utc


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_parse_iso_timestamp_invalid_raises_value_error() -> None:
    """Verify parse_iso_timestamp raises ValueError on non-ISO candidate string."""
    with pytest.raises(ValueError, match="Invalid timestamp candidate"):
        GDAUtil.parse_iso_timestamp("invalid-date")


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_parse_iso_timestamp_empty_or_non_string_raises() -> None:
    """Verify parse_iso_timestamp raises ValueError when input is empty or non-string."""
    with pytest.raises(ValueError, match="Invalid timestamp candidate"):
        GDAUtil.parse_iso_timestamp("")
    with pytest.raises(ValueError, match="Invalid timestamp candidate"):
        GDAUtil.parse_iso_timestamp(12345)  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_format_file_size_bytes() -> None:
    """Verify format_file_size renders byte counts under 1024 as integer B."""
    assert GDAUtil.format_file_size(512) == "512 B"


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_format_file_size_kilobytes() -> None:
    """Verify format_file_size formats kilobyte values with decimal places."""
    assert GDAUtil.format_file_size(2048) == "2.00 KB"


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_format_file_size_megabytes() -> None:
    """Verify format_file_size formats megabyte values with decimal places."""
    assert GDAUtil.format_file_size(1048576 * 5) == "5.00 MB"


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_format_file_size_petabytes_cap() -> None:
    """Verify format_file_size caps at PB for exceptionally large byte counts."""
    large_size = 1024**5 * 3
    assert GDAUtil.format_file_size(large_size) == "3.00 PB"


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_format_file_size_exabytes_fallthrough() -> None:
    """Verify format_file_size handles byte counts exceeding PB loop limit."""
    exabyte_size = 1024**6 * 2
    assert GDAUtil.format_file_size(exabyte_size).endswith("PB")


@pytest.mark.unit
@pytest.mark.regression
def test_gda_util_format_file_size_negative_raises_value_error() -> None:
    """Verify format_file_size raises ValueError for negative byte counts."""
    with pytest.raises(ValueError, match="File size cannot be negative"):
        GDAUtil.format_file_size(-1)


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_compute_text_hash() -> None:
    """Verify compute_text_hash calculates accurate SHA-256 digest on string."""
    expected = "cf38f6bcbce5a530e1dc71e8bed91337cf80fdffc0a7dcc74c208c0bec058519"
    assert GDAUtil.compute_text_hash("Genealogy Digital Archive") == expected


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_iso_now_format() -> None:
    """Verify iso_now produces valid UTC ISO-8601 string ending with Z."""
    assert GDAUtil.iso_now().endswith("Z")


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_compute_sha256(tmp_path: Path) -> None:
    """Verify compute_sha256 calculates accurate SHA-256 digest across raw bytes."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"Genealogy Digital Archive")
    expected_hash = "cf38f6bcbce5a530e1dc71e8bed91337cf80fdffc0a7dcc74c208c0bec058519"
    assert GDAUtil.compute_sha256(test_file) == expected_hash


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_compute_sha256_multiblock_loop(tmp_path: Path) -> None:
    """Verify compute_sha256 iterates through multiple 64 KB chunk blocks."""
    test_file = tmp_path / "large_block.dat"
    test_file.write_bytes(b"A" * 81920)
    assert len(GDAUtil.compute_sha256(test_file)) == 64


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_util_introspectable_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify GDAUtil inherits IntrospectableMixin and renders directory help."""
    GDAUtil.help()
    captured = capsys.readouterr().out
    assert "=== GDAUtil Public Directory ===" in captured