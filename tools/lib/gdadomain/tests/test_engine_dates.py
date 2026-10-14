# Name: test_engine_dates.py
# Path: tools/lib/gdadomain/tests/test_engine_dates.py
# Version: 1.0.0+build.r1

"""Unit test harness verifying DateEngine historical date normalization.

Operational Role:
    Validates ISO-8601 date parsing, natural text interpretation, age parsing,
    vital year extraction, GEDCOM modifier harmonization, schema exportation,
    schema disk serialization, biological plausibility, date reconciliation
    (corroboration, intersection, union), and discrepancy note generation.

Test Structure & Protocol:
    - Atomized tests: Strictly 1:1 assertion mapping per test function.
    - Fully decorated: Strictly marked with @pytest.mark.unit; sanity checks
      tagged with @pytest.mark.smoke; boundary cases with @pytest.mark.regression.
    - Dependencies: Isolated tmp_path sandboxes; GDAConfig singleton mocking.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch
import pytest

from gdacore.config import GDAConfig
from gdadomain.dates import (
    AgeRecord,
    DateEngine,
    InterpretedDate,
    ParsedDate,
    VitalYear,
)


# ==============================================================================
# GROUP 1: IntrospectableMixin & Reflection Verification
# Note: Verifies terminal directory generation, signatures, and invalid query handling
# ==============================================================================


@pytest.mark.unit
def test_help_directory_generation(capsys: Any) -> None:
    """Verify DateEngine.help() outputs all public classmethods without private attributes."""
    DateEngine.help()

    captured = capsys.readouterr().out
    assert "parse" in captured
    assert "interpret" in captured
    assert "reconcile_dates" in captured
    assert "export_schema" in captured

    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    member_lines = [l for l in lines if l.startswith("-") or l.startswith("*")]
    for ml in member_lines:
        assert not ml.lstrip("- *").strip().startswith("_")


@pytest.mark.smoke
@pytest.mark.unit
def test_help_member_signature(capsys: Any) -> None:
    """Verify DateEngine.help('parse') prints call signature, parameter types, and docstring."""
    DateEngine.help("parse")

    captured = capsys.readouterr().out
    assert "parse(" in captured
    assert "date_str" in captured
    assert "Parse an ISO date string" in captured


@pytest.mark.unit
def test_help_invalid_member(capsys: Any) -> None:
    """Verify DateEngine.help() gracefully handles unknown member names without exceptions."""
    DateEngine.help("non_existent_method")

    captured = capsys.readouterr().out
    assert "not found" in captured or "No public member" in captured or "non_existent_method" in captured


# ==============================================================================
# GROUP 2: GEDCOM Modifier Precedence & Ranking
# Note: Verifies modifier parsing, precision ranks, and comparator branches
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_get_modifier_rank_exact_returns_six() -> None:
    """Verify EXACT modifier ranks at level 6."""
    assert DateEngine.get_modifier_rank("EXACT") == 6


@pytest.mark.unit
@pytest.mark.smoke
def test_get_modifier_rank_abt_returns_five() -> None:
    """Verify ABT modifier ranks at level 5."""
    assert DateEngine.get_modifier_rank("ABT") == 5


@pytest.mark.unit
@pytest.mark.smoke
def test_get_modifier_rank_bet_returns_four() -> None:
    """Verify BET modifier ranks at level 4."""
    assert DateEngine.get_modifier_rank("BET") == 4


@pytest.mark.unit
@pytest.mark.smoke
def test_get_modifier_rank_bef_returns_three() -> None:
    """Verify BEF modifier ranks at level 3."""
    assert DateEngine.get_modifier_rank("BEF") == 3


@pytest.mark.unit
@pytest.mark.smoke
def test_get_modifier_rank_aft_returns_three() -> None:
    """Verify AFT modifier ranks at level 3."""
    assert DateEngine.get_modifier_rank("AFT") == 3


@pytest.mark.unit
@pytest.mark.smoke
def test_get_modifier_rank_from_to_returns_two() -> None:
    """Verify FROM_TO modifier ranks at level 2."""
    assert DateEngine.get_modifier_rank("FROM_TO") == 2


@pytest.mark.unit
@pytest.mark.smoke
def test_get_modifier_rank_unknown_returns_one() -> None:
    """Verify UNKNOWN modifier ranks at level 1."""
    assert DateEngine.get_modifier_rank("UNKNOWN") == 1


@pytest.mark.unit
@pytest.mark.regression
def test_get_modifier_rank_none_returns_one() -> None:
    """Verify None modifier normalizes to UNKNOWN and ranks at level 1."""
    assert DateEngine.get_modifier_rank(None) == 1


@pytest.mark.unit
@pytest.mark.smoke
def test_normalize_modifier_colloquial_about_to_abt() -> None:
    """Verify colloquial 'About' normalizes to standard GEDCOM 'ABT'."""
    assert DateEngine.normalize_modifier("About") == "ABT"


@pytest.mark.unit
@pytest.mark.smoke
def test_normalize_modifier_colloquial_between_to_bet() -> None:
    """Verify colloquial 'Between' normalizes to standard GEDCOM 'BET'."""
    assert DateEngine.normalize_modifier("Between") == "BET"


@pytest.mark.unit
@pytest.mark.smoke
def test_compare_modifiers_returns_one_when_first_is_higher() -> None:
    """Verify compare_modifiers returns 1 when first rank exceeds second."""
    assert DateEngine.compare_modifiers("EXACT", "ABT") == 1


@pytest.mark.unit
@pytest.mark.smoke
def test_compare_modifiers_returns_minus_one_when_second_is_higher() -> None:
    """Verify compare_modifiers returns -1 when second rank exceeds first."""
    assert DateEngine.compare_modifiers("BET", "EXACT") == -1


@pytest.mark.unit
@pytest.mark.regression
def test_compare_modifiers_returns_zero_when_ranks_equal() -> None:
    """Verify compare_modifiers returns 0 when ranks are identical."""
    assert DateEngine.compare_modifiers("ABT", "ABOUT") == 0


# ==============================================================================
# GROUP 3: ISO Date Parsing & Extraction
# Note: Verifies ISO-8601 tokenization, calendar bounds, and fallback extractors
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_parse_full_iso_date_success() -> None:
    """Verify parsing full YYYY-MM-DD date sets all components."""
    parsed = DateEngine.parse("1850-06-15")
    assert parsed == ParsedDate(year=1850, month=6, day=15, modifier="EXACT", raw="1850-06-15")


@pytest.mark.unit
@pytest.mark.smoke
def test_parse_year_month_iso_date() -> None:
    """Verify parsing YYYY-MM date sets month and leaves day None."""
    parsed = DateEngine.parse("1900-11")
    assert parsed == ParsedDate(year=1900, month=11, day=None, modifier="EXACT", raw="1900-11")


@pytest.mark.unit
@pytest.mark.smoke
def test_parse_year_only_iso_date() -> None:
    """Verify parsing YYYY date leaves month and day None."""
    parsed = DateEngine.parse("1880")
    assert parsed == ParsedDate(year=1880, month=None, day=None, modifier="EXACT", raw="1880")


@pytest.mark.unit
@pytest.mark.regression
def test_parse_empty_string_returns_none() -> None:
    """Verify parsing an empty string returns None."""
    assert DateEngine.parse("") is None


@pytest.mark.unit
@pytest.mark.regression
def test_parse_non_string_returns_none() -> None:
    """Verify parsing non-string types returns None."""
    assert DateEngine.parse(None) is None  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.regression
def test_parse_invalid_month_returns_none() -> None:
    """Verify month > 12 fails calendar validation and returns None."""
    assert DateEngine.parse("1850-13-01") is None


@pytest.mark.unit
@pytest.mark.regression
def test_parse_invalid_month_zero_returns_none() -> None:
    """Verify month 00 fails calendar validation and returns None."""
    assert DateEngine.parse("1850-00-01") is None


@pytest.mark.unit
@pytest.mark.regression
def test_parse_invalid_day_returns_none() -> None:
    """Verify invalid calendar date (Feb 30) returns None."""
    assert DateEngine.parse("1850-02-30") is None


@pytest.mark.unit
@pytest.mark.regression
def test_parse_embedded_year_string_fallback() -> None:
    """Verify arbitrary string containing a 4-digit year falls back to year parse with ABT modifier."""
    parsed = DateEngine.parse("Born circa 1795 in Lancaster")
    assert parsed == ParsedDate(year=1795, month=None, day=None, modifier="ABT", raw="Born circa 1795 in Lancaster")


@pytest.mark.unit
@pytest.mark.regression
def test_parse_unparseable_string_returns_none() -> None:
    """Verify arbitrary string lacking any 4-digit year returns None."""
    assert DateEngine.parse("Date completely unknown") is None


@pytest.mark.unit
@pytest.mark.smoke
def test_parsed_date_is_complete_true_for_full_date() -> None:
    """Verify is_complete returns True when year, month, and day are present."""
    parsed = DateEngine.parse("1920-04-12")
    assert parsed is not None and parsed.is_complete is True


@pytest.mark.unit
@pytest.mark.regression
def test_parsed_date_is_complete_false_for_partial_date() -> None:
    """Verify is_complete returns False when day is missing."""
    parsed = DateEngine.parse("1920-04")
    assert parsed is not None and parsed.is_complete is False


@pytest.mark.unit
@pytest.mark.smoke
def test_parsed_date_to_iso_full_date() -> None:
    """Verify to_iso formats complete date into YYYY-MM-DD."""
    parsed = DateEngine.parse("1865-04-09")
    assert parsed is not None and parsed.to_iso() == "1865-04-09"


@pytest.mark.unit
@pytest.mark.smoke
def test_parsed_date_to_iso_month_only() -> None:
    """Verify to_iso formats partial date into YYYY-MM."""
    parsed = DateEngine.parse("1865-04")
    assert parsed is not None and parsed.to_iso() == "1865-04"


@pytest.mark.unit
@pytest.mark.smoke
def test_parsed_date_to_iso_year_only() -> None:
    """Verify to_iso formats year-only date into YYYY."""
    parsed = DateEngine.parse("1865")
    assert parsed is not None and parsed.to_iso() == "1865"


@pytest.mark.unit
@pytest.mark.smoke
def test_extract_year_valid_date() -> None:
    """Verify extract_year returns integer year from valid date string."""
    assert DateEngine.extract_year("1875-10-31") == 1875


@pytest.mark.unit
@pytest.mark.regression
def test_extract_year_invalid_date_returns_none() -> None:
    """Verify extract_year returns None when given invalid date."""
    assert DateEngine.extract_year("NotADate") is None


# ==============================================================================
# GROUP 4: Natural Text Interpretation & Vital Conversions
# Note: Verifies unstructured phrase interpretation, ranges, age and vital objects
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_interpret_between_range() -> None:
    """Verify interpret resolves BETWEEN date ranges with GEDCOM 'BET' modifier."""
    res = DateEngine.interpret("Between 1845 and 1848")
    assert res == InterpretedDate(
        modifier="BET",
        date_start="1845",
        date_end="1848",
        raw_text="Between 1845 and 1848",
    )


@pytest.mark.unit
@pytest.mark.smoke
def test_interpret_before_qualifier() -> None:
    """Verify interpret resolves BEFORE date with GEDCOM 'BEF' modifier."""
    res = DateEngine.interpret("Before 1880-05-01")
    assert res == InterpretedDate(
        modifier="BEF",
        date_start="1880-05-01",
        date_end=None,
        raw_text="Before 1880-05-01",
    )


@pytest.mark.unit
@pytest.mark.smoke
def test_interpret_after_qualifier() -> None:
    """Verify interpret resolves AFTER date with GEDCOM 'AFT' modifier."""
    res = DateEngine.interpret("After 1910")
    assert res == InterpretedDate(
        modifier="AFT",
        date_start="1910",
        date_end=None,
        raw_text="After 1910",
    )


@pytest.mark.unit
@pytest.mark.smoke
def test_interpret_circa_qualifier() -> None:
    """Verify interpret maps circa / about prefix to standard GEDCOM 'ABT' modifier."""
    res = DateEngine.interpret("circa 1832")
    assert res == InterpretedDate(
        modifier="ABT",
        date_start="1832",
        date_end=None,
        raw_text="circa 1832",
    )


@pytest.mark.unit
@pytest.mark.smoke
def test_interpret_direct_iso_string_populates_date_start() -> None:
    """Verify interpret directly parses valid ISO date string without range/prefix."""
    res = DateEngine.interpret("1850-06-15")
    assert res == InterpretedDate(
        modifier="EXACT",
        date_start="1850-06-15",
        date_end=None,
        raw_text="1850-06-15",
    )


@pytest.mark.unit
@pytest.mark.regression
def test_interpret_none_returns_none() -> None:
    """Verify interpret returns None when given None."""
    assert DateEngine.interpret(None) is None


@pytest.mark.unit
@pytest.mark.regression
def test_interpret_unparseable_returns_none() -> None:
    """Verify interpret returns None when text lacks parseable dates."""
    assert DateEngine.interpret("Unknown date") is None


@pytest.mark.unit
@pytest.mark.smoke
def test_interpreted_date_to_dict_matches_schema() -> None:
    """Verify InterpretedDate.to_dict emits schema-compliant keys."""
    interp = InterpretedDate(modifier="EXACT", date_start="1850-01-01", date_end=None, raw_text="1850-01-01")
    assert interp.to_dict() == {
        "modifier": "EXACT",
        "date_start": "1850-01-01",
        "date_end": None,
        "raw_text": "1850-01-01",
    }


@pytest.mark.unit
@pytest.mark.smoke
def test_to_vital_year_from_string() -> None:
    """Verify to_vital_year extracts year and maps modifier to GEDCOM 'ABT'."""
    vital = DateEngine.to_vital_year("About 1872")
    assert vital == VitalYear(year=1872, modifier="ABT")


@pytest.mark.unit
@pytest.mark.smoke
def test_to_vital_year_from_interpreted_date() -> None:
    """Verify to_vital_year maps from InterpretedDate object."""
    interp = InterpretedDate(modifier="EXACT", date_start="1905-08-12", date_end=None, raw_text=None)
    vital = DateEngine.to_vital_year(interp)
    assert vital == VitalYear(year=1905, modifier="EXACT")


@pytest.mark.unit
@pytest.mark.smoke
def test_to_vital_year_from_parsed_date() -> None:
    """Verify to_vital_year maps from ParsedDate object with normalized modifier."""
    p = ParsedDate(year=1840, modifier="ESTIMATED")
    vital = DateEngine.to_vital_year(p)
    assert vital == VitalYear(year=1840, modifier="ABT")


@pytest.mark.unit
@pytest.mark.regression
def test_to_vital_year_none_input_returns_none() -> None:
    """Verify to_vital_year returns None when input is None."""
    assert DateEngine.to_vital_year(None) is None


@pytest.mark.unit
@pytest.mark.regression
def test_to_vital_year_invalid_string_returns_none() -> None:
    """Verify to_vital_year returns None when given invalid text."""
    assert DateEngine.to_vital_year("Invalid") is None


@pytest.mark.unit
@pytest.mark.regression
def test_to_vital_year_interpreted_without_start_returns_none() -> None:
    """Verify to_vital_year returns None when InterpretedDate lacks date_start."""
    interp = InterpretedDate(modifier="EXACT", date_start=None)
    assert DateEngine.to_vital_year(interp) is None


@pytest.mark.unit
@pytest.mark.regression
def test_to_vital_year_unsupported_type_returns_none() -> None:
    """Verify to_vital_year returns None when given an unsupported data type."""
    assert DateEngine.to_vital_year(12345) is None


@pytest.mark.unit
@pytest.mark.smoke
def test_vital_year_to_dict() -> None:
    """Verify VitalYear.to_dict emits dictionary matching vital_year schema."""
    vital = VitalYear(year=1890, modifier="ABT")
    assert vital.to_dict() == {"year": 1890, "modifier": "ABT"}


@pytest.mark.unit
@pytest.mark.smoke
def test_parse_age_full_breakdown() -> None:
    """Verify parse_age extracts years, months, and days."""
    age = DateEngine.parse_age("72 years, 4 months, 12 days")
    assert age == AgeRecord(years=72, months=4, days=12, raw_text="72 years, 4 months, 12 days")


@pytest.mark.unit
@pytest.mark.smoke
def test_parse_age_years_only() -> None:
    """Verify parse_age extracts standalone years."""
    age = DateEngine.parse_age("45y")
    assert age == AgeRecord(years=45, months=None, days=None, raw_text="45y")


@pytest.mark.unit
@pytest.mark.regression
def test_parse_age_none_input_returns_none() -> None:
    """Verify parse_age returns None on None input."""
    assert DateEngine.parse_age(None) is None


@pytest.mark.unit
@pytest.mark.regression
def test_parse_age_invalid_input_returns_none() -> None:
    """Verify parse_age returns None on invalid string."""
    assert DateEngine.parse_age("Infant") is None


@pytest.mark.unit
@pytest.mark.smoke
def test_age_record_to_dict() -> None:
    """Verify AgeRecord.to_dict emits dictionary matching age_record schema."""
    age = AgeRecord(years=80, months=2, days=None, raw_text="80y 2m")
    assert age.to_dict() == {"years": 80, "months": 2, "days": None, "raw_text": "80y 2m"}


# ==============================================================================
# GROUP 5: Interval Arithmetic & Biological Plausibility
# Note: Verifies decimal year spans, chronological ordering, and kinship rules 2-5
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_calculate_span_years_complete_dates() -> None:
    """Verify calculate_span_years accurately calculates span for complete dates."""
    span = DateEngine.calculate_span_years("1850-01-01", "1860-01-01")
    assert span == 10.0


@pytest.mark.unit
@pytest.mark.smoke
def test_calculate_span_years_year_only() -> None:
    """Verify calculate_span_years falls back to integer difference for partial dates."""
    span = DateEngine.calculate_span_years("1850", "1875")
    assert span == 25.0


@pytest.mark.unit
@pytest.mark.regression
def test_calculate_span_years_first_date_invalid_returns_none() -> None:
    """Verify calculate_span_years returns None when first date is invalid."""
    assert DateEngine.calculate_span_years("InvalidDate", "1860-01-01") is None


@pytest.mark.unit
@pytest.mark.regression
def test_calculate_span_years_second_date_invalid_returns_none() -> None:
    """Verify calculate_span_years returns None when second date is invalid."""
    assert DateEngine.calculate_span_years("1850-01-01", "InvalidDate") is None


@pytest.mark.unit
@pytest.mark.smoke
def test_is_chronologically_valid_strictly_earlier_year() -> None:
    """Verify validation passes when earlier year is strictly less than later year."""
    assert DateEngine.is_chronologically_valid("1840", "1850") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_chronologically_valid_reversed_year() -> None:
    """Verify validation fails when earlier year is greater than later year."""
    assert DateEngine.is_chronologically_valid("1860", "1850") is False


@pytest.mark.unit
@pytest.mark.smoke
def test_is_chronologically_valid_same_year_earlier_month() -> None:
    """Verify validation passes for same year when earlier month precedes later month."""
    assert DateEngine.is_chronologically_valid("1850-03", "1850-08") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_chronologically_valid_same_year_reversed_month() -> None:
    """Verify validation fails for same year when earlier month succeeds later month."""
    assert DateEngine.is_chronologically_valid("1850-09", "1850-04") is False


@pytest.mark.unit
@pytest.mark.smoke
def test_is_chronologically_valid_same_month_earlier_day() -> None:
    """Verify validation passes for same month when earlier day precedes later day."""
    assert DateEngine.is_chronologically_valid("1850-05-10", "1850-05-20") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_chronologically_valid_same_month_reversed_day() -> None:
    """Verify validation fails for same month when earlier day succeeds later day."""
    assert DateEngine.is_chronologically_valid("1850-05-25", "1850-05-15") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_chronologically_valid_identical_dates_with_allow_equal_true() -> None:
    """Verify validation passes for identical dates when allow_equal is True."""
    assert DateEngine.is_chronologically_valid("1850-05-15", "1850-05-15", allow_equal=True) is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_chronologically_valid_identical_dates_with_allow_equal_false() -> None:
    """Verify validation fails for identical dates when allow_equal is False."""
    assert DateEngine.is_chronologically_valid("1850-05-15", "1850-05-15", allow_equal=False) is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_chronologically_valid_same_month_no_day_allow_equal_false() -> None:
    """Verify validation returns allow_equal value when months match but days are missing."""
    assert DateEngine.is_chronologically_valid("1850-05", "1850-05", allow_equal=False) is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_chronologically_valid_same_month_one_missing_day_returns_allow_equal() -> None:
    """Verify validation returns allow_equal when one date has a day and the other does not."""
    assert DateEngine.is_chronologically_valid("1850-05-15", "1850-05", allow_equal=True) is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_chronologically_valid_same_year_missing_one_month_returns_allow_equal() -> None:
    """Verify validation returns allow_equal when same year but one month is missing."""
    assert DateEngine.is_chronologically_valid("1850-05", "1850", allow_equal=True) is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_chronologically_valid_invalid_dates_return_false() -> None:
    """Verify validation returns False when either date is unparseable."""
    assert DateEngine.is_chronologically_valid("BrokenDate", "1850-01-01") is False


@pytest.mark.unit
@pytest.mark.smoke
def test_is_age_biologically_plausible_valid_lifespan() -> None:
    """Verify plausibility passes for an 80-year lifespan (Rule 5)."""
    assert DateEngine.is_age_biologically_plausible("1820-01-01", "1900-01-01") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_age_biologically_plausible_fails_on_excessive_lifespan() -> None:
    """Verify plausibility fails when lifespan exceeds 115 years (Rule 5)."""
    assert DateEngine.is_age_biologically_plausible("1800-01-01", "1925-01-01") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_age_biologically_plausible_fails_on_negative_span() -> None:
    """Verify plausibility fails when event precedes birth."""
    assert DateEngine.is_age_biologically_plausible("1850-01-01", "1840-01-01") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_age_biologically_plausible_returns_false_when_span_calculation_fails() -> None:
    """Verify plausibility returns False when date parsing fails during span calculation."""
    assert DateEngine.is_age_biologically_plausible("1850-01-01", "InvalidDate") is False


@pytest.mark.unit
@pytest.mark.smoke
def test_is_parenting_biologically_plausible_valid_ages() -> None:
    """Verify plausibility passes for parent aged 25 at child birth."""
    assert DateEngine.is_parenting_biologically_plausible("1825-01-01", "1850-01-01") is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_parenting_biologically_plausible_parent_too_young() -> None:
    """Verify plausibility fails when parent is under 12 years old (Rule 2)."""
    assert DateEngine.is_parenting_biologically_plausible("1840-01-01", "1850-01-01") is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_parenting_biologically_plausible_mother_too_old() -> None:
    """Verify plausibility fails when mother is over 55 years old (Rule 3)."""
    assert DateEngine.is_parenting_biologically_plausible(
        parent_birth="1800-01-01",
        child_birth="1860-01-01",
        parent_sex="Female",
    ) is False


@pytest.mark.unit
@pytest.mark.smoke
def test_is_parenting_biologically_plausible_child_born_before_mother_death() -> None:
    """Verify plausibility passes when mother dies after child is born."""
    assert DateEngine.is_parenting_biologically_plausible(
        parent_birth="1820-01-01",
        child_birth="1850-01-01",
        parent_death="1855-01-01",
        parent_sex="Female",
    ) is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_parenting_biologically_plausible_child_born_after_mother_death() -> None:
    """Verify plausibility fails when child is born after mother's death (Rule 4)."""
    assert DateEngine.is_parenting_biologically_plausible(
        parent_birth="1820-01-01",
        child_birth="1855-01-01",
        parent_death="1854-01-01",
        parent_sex="Female",
    ) is False


@pytest.mark.unit
@pytest.mark.smoke
def test_is_parenting_biologically_plausible_child_born_within_nine_months_of_father_death() -> None:
    """Verify plausibility passes when child is born within 9 months of father's death (Rule 4)."""
    assert DateEngine.is_parenting_biologically_plausible(
        parent_birth="1820-01-01",
        child_birth="1850-06-01",
        parent_death="1850-01-01",
        parent_sex="Male",
    ) is True


@pytest.mark.unit
@pytest.mark.regression
def test_is_parenting_biologically_plausible_child_born_nine_months_after_father_death() -> None:
    """Verify plausibility fails when child is born > 9 months after father's death (Rule 4)."""
    assert DateEngine.is_parenting_biologically_plausible(
        parent_birth="1820-01-01",
        child_birth="1855-01-01",
        parent_death="1853-01-01",
        parent_sex="Male",
    ) is False


@pytest.mark.unit
@pytest.mark.regression
def test_is_parenting_biologically_plausible_unspecified_sex_with_death_passes() -> None:
    """Verify plausibility passes when parent_death is provided but parent_sex is None."""
    assert DateEngine.is_parenting_biologically_plausible(
        parent_birth="1820-01-01",
        child_birth="1850-01-01",
        parent_death="1860-01-01",
        parent_sex=None,
    ) is True


# ==============================================================================
# GROUP 6: Date Reconciliation & Multi-Criteria Tiebreaking
# Note: Verifies Quay confidence precedence, range intersection/union, and notes
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_select_authoritative_date_quay_score_priority() -> None:
    """Verify higher Quay score candidate wins regardless of modifier precision."""
    cand_a = ("1850-06-01", "ABT", 3)
    cand_b = ("1850-06-01", "EXACT", 1)
    assert DateEngine.select_authoritative_date(cand_a, cand_b) == cand_a


@pytest.mark.unit
@pytest.mark.smoke
def test_select_authoritative_date_modifier_tiebreaker() -> None:
    """Verify GEDCOM modifier precision breaks ties when Quay scores match."""
    cand_a = ("1850-06-01", "ABT", 2)
    cand_b = ("1850-06-01", "EXACT", 2)
    assert DateEngine.select_authoritative_date(cand_a, cand_b) == cand_b


@pytest.mark.unit
@pytest.mark.smoke
def test_select_authoritative_date_string_length_tiebreaker() -> None:
    """Verify longer ISO date representation breaks ties when Quay and modifier match."""
    cand_a = ("1850-06-01", "EXACT", 2)
    cand_b = ("1850-06", "EXACT", 2)
    assert DateEngine.select_authoritative_date(cand_a, cand_b) == cand_a


@pytest.mark.unit
@pytest.mark.smoke
def test_select_authoritative_date_modifier_b_wins_tiebreaker() -> None:
    """Verify candidate B wins when Quay matches and modifier B has higher rank."""
    cand_a = ("1850", "BET", 2)
    cand_b = ("1850", "EXACT", 2)
    assert DateEngine.select_authoritative_date(cand_a, cand_b) == cand_b


@pytest.mark.unit
@pytest.mark.smoke
def test_select_authoritative_date_string_length_b_wins() -> None:
    """Verify candidate B wins when Quay and modifier match but B has longer ISO representation."""
    cand_a = ("1850", "EXACT", 2)
    cand_b = ("1850-06-15", "EXACT", 2)
    assert DateEngine.select_authoritative_date(cand_a, cand_b) == cand_b


@pytest.mark.unit
@pytest.mark.smoke
def test_select_authoritative_date_quay_b_wins() -> None:
    """Verify candidate B wins when Quay B is strictly greater than Quay A."""
    cand_a = ("1850-06-15", "EXACT", 1)
    cand_b = ("1850", "ABT", 2)
    assert DateEngine.select_authoritative_date(cand_a, cand_b) == cand_b


@pytest.mark.unit
@pytest.mark.smoke
def test_reconcile_dates_corroborates_point_inside_range_candidate_a() -> None:
    """Verify point estimate inside range is adopted when candidate A is point."""
    point = InterpretedDate(modifier="EXACT", date_start="1862-06-15", raw_text="15 Jun 1862")
    rng = InterpretedDate(modifier="BET", date_start="1860", date_end="1865", raw_text="Between 1860 and 1865")
    res = DateEngine.reconcile_dates(point, rng)
    assert res.reconciled is True
    assert res.strategy_used == "CORROBORATION"
    assert res.date.date_start == "1862-06-15"
    assert res.has_note is False


@pytest.mark.unit
@pytest.mark.smoke
def test_reconcile_dates_corroborates_point_inside_range_candidate_b() -> None:
    """Verify point estimate inside range is adopted when candidate B is point."""
    rng = InterpretedDate(modifier="BET", date_start="1860", date_end="1865", raw_text="Between 1860 and 1865")
    point = InterpretedDate(modifier="ABT", date_start="1863", raw_text=None)
    res = DateEngine.reconcile_dates(rng, point)
    assert res.reconciled is True
    assert res.strategy_used == "CORROBORATION"
    assert res.date.date_start == "1863"
    assert res.has_note is False


@pytest.mark.unit
@pytest.mark.regression
def test_reconcile_dates_point_outside_range_triggers_fallback() -> None:
    """Verify point estimate outside range fails corroboration and triggers fallback."""
    point = InterpretedDate(modifier="EXACT", date_start="1870", raw_text="1870")
    rng = InterpretedDate(modifier="BET", date_start="1860", date_end="1865", raw_text="Between 1860 and 1865")
    res = DateEngine.reconcile_dates(point, rng, quay_a=2, quay_b=1)
    assert res.reconciled is False
    assert res.strategy_used == "QUAY_FALLBACK"
    assert res.date == point
    assert res.has_note is True


@pytest.mark.unit
@pytest.mark.regression
def test_reconcile_dates_point_range_unparseable_point_triggers_fallback() -> None:
    """Verify unextractable year in point triggers fallback."""
    point = InterpretedDate(modifier="EXACT", date_start="UnparseablePoint")
    rng = InterpretedDate(modifier="BET", date_start="1850", date_end="1860")
    res = DateEngine.reconcile_dates(point, rng)
    assert res.reconciled is False
    assert res.strategy_used == "QUAY_FALLBACK"


@pytest.mark.unit
@pytest.mark.regression
def test_reconcile_dates_point_range_unparseable_range_boundary_triggers_fallback() -> None:
    """Verify unextractable year in range start or end triggers fallback."""
    point = InterpretedDate(modifier="EXACT", date_start="1855")
    rng = InterpretedDate(modifier="BET", date_start="UnparseableStart", date_end="1860")
    res = DateEngine.reconcile_dates(point, rng)
    assert res.reconciled is False
    assert res.strategy_used == "QUAY_FALLBACK"


@pytest.mark.unit
@pytest.mark.smoke
def test_reconcile_dates_intersects_overlapping_ranges() -> None:
    """Verify overlapping ranges narrow to their intersection."""
    rng1 = InterpretedDate(modifier="BET", date_start="1840", date_end="1855", raw_text="Between 1840 and 1855")
    rng2 = InterpretedDate(modifier="BET", date_start="1850", date_end="1860", raw_text="Between 1850 and 1860")
    res = DateEngine.reconcile_dates(rng1, rng2, range_strategy="INTERSECTION")
    assert res.reconciled is True
    assert res.strategy_used == "INTERSECTION"
    assert res.date.modifier == "BET"
    assert res.date.date_start == "1850"
    assert res.date.date_end == "1855"
    assert res.has_note is False


@pytest.mark.unit
@pytest.mark.smoke
def test_reconcile_dates_intersection_collapses_to_single_year() -> None:
    """Verify ranges intersecting on a single year collapse to modifier ABT."""
    rng1 = InterpretedDate(modifier="BET", date_start="1840", date_end="1850")
    rng2 = InterpretedDate(modifier="BET", date_start="1850", date_end="1860")
    res = DateEngine.reconcile_dates(rng1, rng2, range_strategy="INTERSECTION")
    assert res.reconciled is True
    assert res.strategy_used == "INTERSECTION"
    assert res.date.modifier == "ABT"
    assert res.date.date_start == "1850"
    assert res.date.date_end is None


@pytest.mark.unit
@pytest.mark.smoke
def test_reconcile_dates_union_strategy_expands_boundaries() -> None:
    """Verify range_strategy='UNION' expands to the broadest bounding interval."""
    rng1 = InterpretedDate(modifier="BET", date_start="1840", date_end="1855")
    rng2 = InterpretedDate(modifier="BET", date_start="1850", date_end="1865")
    res = DateEngine.reconcile_dates(rng1, rng2, range_strategy="UNION")
    assert res.reconciled is True
    assert res.strategy_used == "UNION"
    assert res.date.date_start == "1840"
    assert res.date.date_end == "1865"


@pytest.mark.unit
@pytest.mark.regression
def test_reconcile_dates_disjoint_ranges_trigger_fallback() -> None:
    """Verify completely disjoint ranges fail intersection and trigger fallback."""
    rng1 = InterpretedDate(modifier="BET", date_start="1820", date_end="1825", raw_text="1820-1825")
    rng2 = InterpretedDate(modifier="BET", date_start="1840", date_end="1845", raw_text="1840-1845")
    res = DateEngine.reconcile_dates(rng1, rng2, quay_a=2, quay_b=1)
    assert res.reconciled is False
    assert res.strategy_used == "QUAY_FALLBACK"
    assert res.date == rng1
    assert res.has_note is True


@pytest.mark.unit
@pytest.mark.regression
def test_reconcile_dates_range_unparseable_boundary_triggers_fallback() -> None:
    """Verify unextractable year in range candidates triggers fallback."""
    rng1 = InterpretedDate(modifier="BET", date_start="InvalidStart", date_end="1850")
    rng2 = InterpretedDate(modifier="BET", date_start="1840", date_end="1860")
    res = DateEngine.reconcile_dates(rng1, rng2)
    assert res.reconciled is False
    assert res.strategy_used == "QUAY_FALLBACK"


@pytest.mark.unit
@pytest.mark.smoke
def test_reconcile_dates_discrepancy_generates_note_property() -> None:
    """Verify conflicting point outside range falls back to higher Quay and populates generated_note."""
    point = InterpretedDate(modifier="EXACT", date_start="1875-01-01", raw_text="1875-01-01")
    rng = InterpretedDate(modifier="BET", date_start="1840", date_end="1850", raw_text="Between 1840 and 1850")
    res = DateEngine.reconcile_dates(point, rng, quay_a=1, quay_b=3)
    assert res.reconciled is False
    assert res.strategy_used == "QUAY_FALLBACK"
    assert res.date == rng
    assert res.has_note is True
    assert res.generated_note is not None
    assert res.generated_note["category"] == "DISCREPANCY"


# ==============================================================================
# GROUP 7: Code-First Schema Exportation & File Serialization
# Note: Verifies Draft 2020-12 schema generation and Safe Backup disk writes
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_export_schema_defines_expected_types() -> None:
    """Verify export_schema outputs Draft 2020-12 schema containing date definitions."""
    schema = DateEngine.export_schema()
    defs = schema.get("$defs", {})
    assert "enum_date_modifier" in defs
    assert "enum_vital_modifier" in defs
    assert "date_iso" in defs
    assert "date_interpreted" in defs
    assert "vital_year" in defs
    assert "age_record" in defs


@pytest.mark.unit
@pytest.mark.smoke
def test_write_schema_emits_valid_json_file_with_explicit_path(tmp_path: Path) -> None:
    """Verify write_schema writes formatted JSON file matching export_schema to explicit path."""
    out_file = tmp_path / "schemas" / "defs" / "_shared_dates.schema.json"
    written_path = DateEngine.write_schema(out_file)
    assert written_path.exists()
    loaded = json.loads(written_path.read_text(encoding="utf-8"))
    assert loaded["$id"] == "https://genealogy.archive/schemas/defs/_shared_dates.schema.json"


@pytest.mark.unit
@pytest.mark.smoke
def test_write_schema_uses_config_default_when_no_path_provided(tmp_path: Path) -> None:
    """Verify write_schema defaults to CONFIG.schema_defs when output_path is None."""
    mock_config = GDAConfig(root=tmp_path)
    with patch("gdadomain.dates.CONFIG", mock_config):
        written_path = DateEngine.write_schema()
        assert written_path == mock_config.schema_defs / "_shared_dates.schema.json"
        assert written_path.exists()