# Name: dates.py
# Path: tools/lib/gdadomain/src/gdadomain/dates.py
# Version: 1.0.0+build.r1

"""Date parsing, interval evaluation, and precision harmonization engine.

Operational Role:
    Code-first canonical authority for historical date interpretation,
    GEDCOM modifier precedence, interval calculation, demographic plausibility,
    interval reconciliation (intersection/union), and schema emission.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union

from gdacore.config import CONFIG
from gdacore.introspectable import IntrospectableMixin
from gdacore.logger import GDALogger

__version__ =  "1.0.0+build.r1"

LOGGER = GDALogger.get_logger("gda_dates")


@dataclass(frozen=True)
class ParsedDate:
    """Structured representation of a parsed historical date."""

    year: int
    month: Optional[int] = None
    day: Optional[int] = None
    modifier: str = "EXACT"
    raw: str = ""

    @property
    def is_complete(self) -> bool:
        """Return True if year, month, and day are fully populated."""
        return self.month is not None and self.day is not None

    def to_iso(self) -> str:
        """Render normalized ISO string representation (YYYY, YYYY-MM, or YYYY-MM-DD)."""
        if self.month is not None and self.day is not None:
            return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"
        if self.month is not None:
            return f"{self.year:04d}-{self.month:02d}"
        return f"{self.year:04d}"


@dataclass(frozen=True)
class InterpretedDate:
    """Structured interpreted date matching date_interpreted schema."""

    modifier: str
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    raw_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Serialize directly to schema-compliant dictionary."""
        return {
            "modifier": self.modifier,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "raw_text": self.raw_text,
        }


@dataclass(frozen=True)
class VitalYear:
    """Structured vital year matching vital_year schema."""

    year: Optional[int]
    modifier: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize directly to schema-compliant dictionary."""
        return {
            "year": self.year,
            "modifier": self.modifier,
        }


@dataclass(frozen=True)
class AgeRecord:
    """Structured age duration matching age_record schema."""

    years: Optional[int] = None
    months: Optional[int] = None
    days: Optional[int] = None
    raw_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize directly to schema-compliant dictionary."""
        return {
            "years": self.years,
            "months": self.months,
            "days": self.days,
            "raw_text": self.raw_text,
        }


@dataclass(frozen=True)
class DateMergeResult:
    """Outcome of reconciling two competing date assertions."""

    date: InterpretedDate
    reconciled: bool
    strategy_used: str
    generated_note: Optional[Dict[str, str]] = None

    @property
    def has_note(self) -> bool:
        """Convenience property for calling programs to test note availability."""
        return self.generated_note is not None


class DateEngine(IntrospectableMixin):
    """Code-first historical date authority, parser, and schema generator."""

    ENUM_DATE_MODIFIERS: ClassVar[List[str]] = [
        "EXACT",
        "ABT",
        "BEF",
        "AFT",
        "BET",
        "FROM_TO",
        "UNKNOWN",
    ]

    ENUM_VITAL_MODIFIERS: ClassVar[List[str]] = [
        "EXACT",
        "ABT",
        "BEF",
        "AFT",
        "BET",
        "FROM_TO",
        "LIVING",
        "UNKNOWN",
    ]

    MODIFIER_PRECEDENCE: ClassVar[Dict[str, int]] = {
        "EXACT": 6,
        "ABT": 5,
        "BET": 4,
        "BEF": 3,
        "AFT": 3,
        "FROM_TO": 2,
        "UNKNOWN": 1,
    }

    NORMALIZATION_MAP: ClassVar[Dict[str, str]] = {
        "EXACT": "EXACT",
        "ABOUT": "ABT",
        "ABT": "ABT",
        "CIRCA": "ABT",
        "C": "ABT",
        "ESTIMATED": "ABT",
        "CALCULATED": "ABT",
        "APPROX": "ABT",
        "BEFORE": "BEF",
        "BEF": "BEF",
        "AFTER": "AFT",
        "AFT": "AFT",
        "BETWEEN": "BET",
        "BET": "BET",
        "FROM_TO": "FROM_TO",
        "LIVING": "LIVING",
        "UNKNOWN": "UNKNOWN",
    }

    ISO_DATE_REGEX: ClassVar[re.Pattern] = re.compile(
        r"^(?P<year>\d{4})(?:-(?P<month>\d{2})(?:-(?P<day>\d{2}))?)?$"
    )
    YEAR_EXTRACT_REGEX: ClassVar[re.Pattern] = re.compile(r"\b(\d{4})\b")

    BETWEEN_REGEX: ClassVar[re.Pattern] = re.compile(
        r"^(?:BETWEEN|BET\.?)\s+(.+?)\s+(?:AND|&)\s+(.+)$", re.IGNORECASE
    )
    BEFORE_REGEX: ClassVar[re.Pattern] = re.compile(r"^(?:BEFORE|BEF\.?)\s+(.+)$", re.IGNORECASE)
    AFTER_REGEX: ClassVar[re.Pattern] = re.compile(r"^(?:AFTER|AFT\.?)\s+(.+)$", re.IGNORECASE)
    ABOUT_REGEX: ClassVar[re.Pattern] = re.compile(
        r"^(?:ABOUT|ABT\.?|CIRCA|C\.?|EST\.?|ESTIMATED)\s+(.+)$", re.IGNORECASE
    )

    AGE_REGEX: ClassVar[re.Pattern] = re.compile(
        r"(?:(\d+)\s*(?:years?|yrs?|y))?\s*,?\s*(?:(\d+)\s*(?:months?|mos?|m))?\s*,?\s*(?:(\d+)\s*(?:days?|dys?|d))?",
        re.IGNORECASE,
    )

    @classmethod
    def normalize_modifier(cls, modifier: Optional[str]) -> str:
        """Map raw modifier string to canonical GEDCOM standard token.

        Args:
            modifier: Raw modifier string (e.g. 'About', 'circa', 'BETWEEN').

        Returns:
            Standardized GEDCOM uppercase token.
        """
        if not modifier or not isinstance(modifier, str):
            return "UNKNOWN"
        token = modifier.strip().upper().replace(".", "")
        return cls.NORMALIZATION_MAP.get(token, "UNKNOWN")

    @classmethod
    def get_modifier_rank(cls, modifier: Optional[str]) -> int:
        """Return the integer rank for a GEDCOM modifier. Higher is more precise.

        Args:
            modifier: Raw or canonical modifier token.

        Returns:
            Integer rank between 1 and 6.
        """
        canon = cls.normalize_modifier(modifier)
        return cls.MODIFIER_PRECEDENCE.get(canon, 0)

    @classmethod
    def compare_modifiers(cls, mod_a: Optional[str], mod_b: Optional[str]) -> int:
        """Compare two modifiers by GEDCOM precision precedence.

        Args:
            mod_a: First modifier candidate.
            mod_b: Second modifier candidate.

        Returns:
            1 if mod_a > mod_b, -1 if mod_a < mod_b, 0 if equal.
        """
        rank_a = cls.get_modifier_rank(mod_a)
        rank_b = cls.get_modifier_rank(mod_b)
        if rank_a > rank_b:
            return 1
        if rank_a < rank_b:
            return -1
        return 0

    @classmethod
    def parse(cls, date_str: Optional[str], default_modifier: str = "EXACT") -> Optional[ParsedDate]:
        """Parse an ISO date string or year-only string into a ParsedDate.

        Args:
            date_str: Date string (e.g. '1850-06-15', '1900-11', '1880').
            default_modifier: Fallback modifier if none detected.

        Returns:
            ParsedDate instance if parseable, None otherwise.
        """
        if not date_str or not isinstance(date_str, str):
            return None

        clean_str = date_str.strip()
        norm_mod = cls.normalize_modifier(default_modifier)
        match = cls.ISO_DATE_REGEX.match(clean_str)
        if match:
            year = int(match.group("year"))
            month = int(match.group("month")) if match.group("month") else None
            day = int(match.group("day")) if match.group("day") else None

            if month is not None and (month < 1 or month > 12):
                return None
            if month is not None and day is not None:
                try:
                    _ = date(year, month, day)
                except ValueError:
                    return None

            return ParsedDate(
                year=year,
                month=month,
                day=day,
                modifier=norm_mod,
                raw=clean_str,
            )

        year_match = cls.YEAR_EXTRACT_REGEX.search(clean_str)
        if year_match:
            year = int(year_match.group(1))
            return ParsedDate(
                year=year,
                month=None,
                day=None,
                modifier="ABT" if norm_mod == "EXACT" else norm_mod,
                raw=clean_str,
            )

        return None

    @classmethod
    def interpret(cls, text: Optional[str], default_modifier: str = "EXACT") -> Optional[InterpretedDate]:
        """Interpret natural historical text into a structured InterpretedDate.

        Args:
            text: Unstructured date string (e.g. 'Between 1845 and 1848', 'Before 1880').
            default_modifier: Fallback modifier if none parsed.

        Returns:
            InterpretedDate instance, or None if unparseable.
        """
        if not text or not isinstance(text, str):
            return None

        raw = text.strip()

        # 1. Range: Between X and Y (GEDCOM 'BET')
        m_between = cls.BETWEEN_REGEX.match(raw)
        if m_between:
            start_p = cls.parse(m_between.group(1))
            end_p = cls.parse(m_between.group(2))
            return InterpretedDate(
                modifier="BET",
                date_start=start_p.to_iso() if start_p else None,
                date_end=end_p.to_iso() if end_p else None,
                raw_text=raw,
            )

        # 2. Before X (GEDCOM 'BEF')
        m_before = cls.BEFORE_REGEX.match(raw)
        if m_before:
            start_p = cls.parse(m_before.group(1))
            return InterpretedDate(
                modifier="BEF",
                date_start=start_p.to_iso() if start_p else None,
                date_end=None,
                raw_text=raw,
            )

        # 3. After X (GEDCOM 'AFT')
        m_after = cls.AFTER_REGEX.match(raw)
        if m_after:
            start_p = cls.parse(m_after.group(1))
            return InterpretedDate(
                modifier="AFT",
                date_start=start_p.to_iso() if start_p else None,
                date_end=None,
                raw_text=raw,
            )

        # 4. About / Circa X (GEDCOM 'ABT')
        m_about = cls.ABOUT_REGEX.match(raw)
        if m_about:
            start_p = cls.parse(m_about.group(1), default_modifier="ABT")
            return InterpretedDate(
                modifier="ABT",
                date_start=start_p.to_iso() if start_p else None,
                date_end=None,
                raw_text=raw,
            )

        # 5. Direct ISO or Year
        direct_p = cls.parse(raw, default_modifier=default_modifier)
        if direct_p:
            return InterpretedDate(
                modifier=direct_p.modifier,
                date_start=direct_p.to_iso(),
                date_end=None,
                raw_text=raw,
            )

        return None

    @classmethod
    def to_vital_year(cls, value: Union[str, InterpretedDate, ParsedDate, Any]) -> Optional[VitalYear]:
        """Convert a date representation to schema-compliant VitalYear.

        Args:
            value: Date string, InterpretedDate, or ParsedDate.

        Returns:
            VitalYear instance if year can be resolved, None otherwise.
        """
        if value is None:
            return None

        if isinstance(value, str):
            interp = cls.interpret(value)
            if not interp or not interp.date_start:
                return None
            year = cls.extract_year(interp.date_start)
            mod = cls.normalize_modifier(interp.modifier)
            return VitalYear(year=year, modifier=mod)

        if isinstance(value, InterpretedDate):
            if not value.date_start:
                return None
            year = cls.extract_year(value.date_start)
            mod = cls.normalize_modifier(value.modifier)
            return VitalYear(year=year, modifier=mod)

        if isinstance(value, ParsedDate):
            mod = cls.normalize_modifier(value.modifier)
            return VitalYear(year=value.year, modifier=mod)

        return None

    @classmethod
    def parse_age(cls, age_text: Optional[str]) -> Optional[AgeRecord]:
        """Parse age strings (e.g., '72y 4m 12d') into AgeRecord.

        Args:
            age_text: Natural age string from tombstone or census.

        Returns:
            AgeRecord instance, or None if unparseable.
        """
        if not age_text or not isinstance(age_text, str):
            return None

        clean = age_text.strip()
        match = cls.AGE_REGEX.search(clean)
        if not match or not any(match.groups()):
            return None

        y_str, m_str, d_str = match.groups()
        years = int(y_str) if y_str else None
        months = int(m_str) if m_str else None
        days = int(d_str) if d_str else None

        return AgeRecord(years=years, months=months, days=days, raw_text=clean)

    @classmethod
    def extract_year(cls, date_str: Optional[str]) -> Optional[int]:
        """Extract the numeric year component from a date string.

        Args:
            date_str: Date string.

        Returns:
            Four-digit integer year, or None if invalid.
        """
        parsed = cls.parse(date_str)
        return parsed.year if parsed else None

    @classmethod
    def calculate_span_years(
        cls,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Optional[float]:
        """Calculate elapsed decimal years between two historical dates.

        Args:
            start_date: Starting date string.
            end_date: Ending date string.

        Returns:
            Elapsed decimal years, or None if either date is invalid.
        """
        start = cls.parse(start_date)
        end = cls.parse(end_date)
        if not start or not end:
            return None

        if start.is_complete and end.is_complete:
            d_start = date(start.year, start.month, start.day)
            d_end = date(end.year, end.month, end.day)
            days = (d_end - d_start).days
            return round(days / 365.25, 2)

        return float(end.year - start.year)

    @classmethod
    def is_chronologically_valid(
        cls,
        earlier_date: Optional[str],
        later_date: Optional[str],
        allow_equal: bool = True,
    ) -> bool:
        """Validate whether earlier_date chronologically precedes later_date.

        Args:
            earlier_date: Baseline earlier date string.
            later_date: Comparison later date string.
            allow_equal: Whether identical dates are considered valid.

        Returns:
            True if earlier_date <= later_date (or < if allow_equal=False).
        """
        start = cls.parse(earlier_date)
        end = cls.parse(later_date)
        if not start or not end:
            return False

        if start.year < end.year:
            return True
        if start.year > end.year:
            return False

        if start.month is not None and end.month is not None:
            if start.month < end.month:
                return True
            if start.month > end.month:
                return False

            if start.day is not None and end.day is not None:
                if start.day < end.day:
                    return True
                if start.day > end.day:
                    return False
                return allow_equal

            return allow_equal

        return allow_equal

    @classmethod
    def is_age_biologically_plausible(
        cls,
        birth_date: Optional[str],
        event_date: Optional[str],
        max_age: int = 115,
    ) -> bool:
        """Verify event occurs post-birth and within max human lifespan (Rule 5).

        Args:
            birth_date: Person birth date string.
            event_date: Event date string.
            max_age: Upper bound on human lifespan in years.

        Returns:
            True if 0 <= elapsed_years <= max_age.
        """
        if not cls.is_chronologically_valid(birth_date, event_date, allow_equal=True):
            return False
        span = cls.calculate_span_years(birth_date, event_date)
        return span <= float(max_age)

    @classmethod
    def is_parenting_biologically_plausible(
        cls,
        parent_birth: Optional[str],
        child_birth: Optional[str],
        parent_death: Optional[str] = None,
        parent_sex: Optional[str] = None,
    ) -> bool:
        """Verify biological parenting plausibility per MIP-Topic-People-Domain Rules 2-4.

        Args:
            parent_birth: Parent birth date string.
            child_birth: Child birth date string.
            parent_death: Optional parent death date string.
            parent_sex: 'Male', 'Female', or None.

        Returns:
            True if all parenting age boundaries are satisfied.
        """
        span = cls.calculate_span_years(parent_birth, child_birth)
        if span is None or span < 12.0:
            return False

        if parent_sex == "Female" and span > 55.0:
            return False

        if parent_death:
            if parent_sex == "Female":
                if not cls.is_chronologically_valid(child_birth, parent_death, allow_equal=True):
                    return False
            elif parent_sex == "Male":
                post_mortem_span = cls.calculate_span_years(parent_death, child_birth)
                if post_mortem_span is not None and post_mortem_span > 0.75:
                    return False

        return True

    @classmethod
    def select_authoritative_date(
        cls,
        candidate_a: Tuple[str, str, int],
        candidate_b: Tuple[str, str, int],
    ) -> Tuple[str, str, int]:
        """Harmonize and choose more authoritative date per Group 2 rules.

        Args:
            candidate_a: Tuple of (date_string, modifier, quay_score).
            candidate_b: Tuple of (date_string, modifier, quay_score).

        Returns:
            The winning candidate tuple.
        """
        date_a, mod_a, quay_a = candidate_a
        date_b, mod_b, quay_b = candidate_b

        if quay_a > quay_b:
            return candidate_a
        if quay_b > quay_a:
            return candidate_b

        mod_cmp = cls.compare_modifiers(mod_a, mod_b)
        if mod_cmp > 0:
            return candidate_a
        if mod_cmp < 0:
            return candidate_b

        if len(date_a) >= len(date_b):
            return candidate_a
        return candidate_b

    @classmethod
    def reconcile_dates(
        cls,
        cand_a: InterpretedDate,
        cand_b: InterpretedDate,
        quay_a: int = 0,
        quay_b: int = 0,
        batch_mode: bool = True,
        range_strategy: str = "INTERSECTION",
    ) -> DateMergeResult:
        """Reconcile and merge two interpreted dates into the most precise valid date.

        Args:
            cand_a: First candidate interpreted date.
            cand_b: Second candidate interpreted date.
            quay_a: Quay confidence score for candidate A (0-3).
            quay_b: Quay confidence score for candidate B (0-3).
            batch_mode: If True, falls back to highest authority on contradiction.
            range_strategy: Policy for overlapping intervals ('INTERSECTION' or 'UNION').

        Returns:
            DateMergeResult containing the resulting date and optional note property.
        """
        # 1. Point vs Range Reconciliation (Point inside Interval)
        point, rng = None, None
        if cand_a.modifier in ("EXACT", "ABT") and cand_b.modifier == "BET":
            point, rng = cand_a, cand_b
        elif cand_b.modifier in ("EXACT", "ABT") and cand_a.modifier == "BET":
            point, rng = cand_b, cand_a

        if point and rng and point.date_start and rng.date_start and rng.date_end:
            p_yr = cls.extract_year(point.date_start)
            s_yr = cls.extract_year(rng.date_start)
            e_yr = cls.extract_year(rng.date_end)

            if p_yr is not None and s_yr is not None and e_yr is not None:
                if s_yr <= p_yr <= e_yr:
                    merged = InterpretedDate(
                        modifier=point.modifier,
                        date_start=point.date_start,
                        date_end=None,
                        raw_text=point.raw_text or point.date_start,
                    )
                    return DateMergeResult(
                        date=merged,
                        reconciled=True,
                        strategy_used="CORROBORATION",
                        generated_note=None,
                    )

        # 2. Interval vs Interval Reconciliation (Two Ranges)
        if (
            cand_a.modifier == "BET"
            and cand_b.modifier == "BET"
            and cand_a.date_start
            and cand_a.date_end
            and cand_b.date_start
            and cand_b.date_end
        ):
            s1 = cls.extract_year(cand_a.date_start)
            e1 = cls.extract_year(cand_a.date_end)
            s2 = cls.extract_year(cand_b.date_start)
            e2 = cls.extract_year(cand_b.date_end)

            if s1 is not None and e1 is not None and s2 is not None and e2 is not None:
                s_int = max(s1, s2)
                e_int = min(e1, e2)

                if s_int <= e_int:
                    if range_strategy.upper() == "UNION":
                        s_u = min(s1, s2)
                        e_u = max(e1, e2)
                        merged = InterpretedDate(
                            modifier="BET",
                            date_start=f"{s_u:04d}",
                            date_end=f"{e_u:04d}",
                            raw_text=f"Between {s_u} and {e_u}",
                        )
                        return DateMergeResult(
                            date=merged,
                            reconciled=True,
                            strategy_used="UNION",
                            generated_note=None,
                        )

                    if s_int == e_int:
                        merged = InterpretedDate(
                            modifier="ABT",
                            date_start=f"{s_int:04d}",
                            date_end=None,
                            raw_text=f"About {s_int}",
                        )
                    else:
                        merged = InterpretedDate(
                            modifier="BET",
                            date_start=f"{s_int:04d}",
                            date_end=f"{e_int:04d}",
                            raw_text=f"Between {s_int} and {e_int}",
                        )

                    return DateMergeResult(
                        date=merged,
                        reconciled=True,
                        strategy_used="INTERSECTION",
                        generated_note=None,
                    )

        # 3. Contradiction / Unmergeable: Fallback to Authoritative Winner
        tup_a = (cand_a.date_start or "", cand_a.modifier, quay_a)
        tup_b = (cand_b.date_start or "", cand_b.modifier, quay_b)
        winner_tup = cls.select_authoritative_date(tup_a, tup_b)

        winner = cand_a if winner_tup == tup_a else cand_b
        loser = cand_b if winner == cand_a else cand_a
        winner_quay = quay_a if winner == cand_a else quay_b
        loser_quay = quay_b if winner == cand_a else quay_a

        note = {
            "category": "DISCREPANCY",
            "title": "Date Reconcile Fallback",
            "text": (
                f"Assertion merged competing dates that could not be reconciled: "
                f"kept '{winner.raw_text or winner.date_start}' (Quay {winner_quay}), "
                f"discarded '{loser.raw_text or loser.date_start}' (Quay {loser_quay})."
            ),
        }

        LOGGER.debug(
            "[RECONCILE] Date contradiction fallback applied: retained %s",
            winner.date_start,
        )

        return DateMergeResult(
            date=winner,
            reconciled=False,
            strategy_used="QUAY_FALLBACK",
            generated_note=note,
        )

    @classmethod
    def export_schema(cls) -> Dict[str, Any]:
        """Export JSON Schema Draft 2020-12 specifications for all date models.

        Returns:
            Dictionary representing canonical _shared_dates.schema.json.
        """
        return {
            "_name": "_shared_dates.schema.json",
            "_path": "schemas/defs/_shared_dates.schema.json",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://genealogy.archive/schemas/defs/_shared_dates.schema.json",
            "title": "Shared Date Definitions",
            "version": "1.0.0",
            "description": "Code-first canonical date primitives, GEDCOM enums, intervals, and age schemas.",
            "$defs": {
                "enum_date_modifier": {
                    "type": "string",
                    "description": "GEDCOM standard date modifier tokens.",
                    "enum": list(cls.ENUM_DATE_MODIFIERS),
                    "default": "EXACT",
                },
                "enum_vital_modifier": {
                    "type": "string",
                    "description": "GEDCOM vital year modifier tokens.",
                    "enum": list(cls.ENUM_VITAL_MODIFIERS),
                    "default": "EXACT",
                },
                "date_iso": {
                    "type": "string",
                    "pattern": r"^\d{4}(-\d{2}(-\d{2})?)?$",
                    "description": "Standardized ISO 8601 calendar date (YYYY, YYYY-MM, or YYYY-MM-DD).",
                },
                "date_interpreted": {
                    "type": "object",
                    "unevaluatedProperties": False,
                    "required": ["modifier"],
                    "properties": {
                        "modifier": {
                            "$ref": "#/$defs/enum_date_modifier",
                        },
                        "date_start": {
                            "type": ["string", "null"],
                            "pattern": r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$",
                        },
                        "date_end": {
                            "type": ["string", "null"],
                            "pattern": r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$",
                        },
                        "raw_text": {"type": ["string", "null"]},
                    },
                },
                "vital_year": {
                    "type": "object",
                    "unevaluatedProperties": False,
                    "required": ["year", "modifier"],
                    "properties": {
                        "year": {"type": ["integer", "null"], "minimum": 1000, "maximum": 2100},
                        "modifier": {
                            "$ref": "#/$defs/enum_vital_modifier",
                        },
                    },
                },
                "age_record": {
                    "type": "object",
                    "unevaluatedProperties": False,
                    "properties": {
                        "years": {"type": ["integer", "null"], "minimum": 0, "maximum": 130},
                        "months": {"type": ["integer", "null"], "minimum": 0, "maximum": 11},
                        "days": {"type": ["integer", "null"], "minimum": 0, "maximum": 30},
                        "raw_text": {"type": ["string", "null"]},
                    },
                },
            },
        }

    @classmethod
    def write_schema(cls, output_path: Optional[Path] = None) -> Path:
        """Serialize and write canonical schema to disk formatted with 2 spaces indent.

        Args:
            output_path: Optional destination Path. Defaults to CONFIG.schema_defs.

        Returns:
            Resolved Path of the written schema file.
        """
        target_path = Path(output_path) if output_path is not None else CONFIG.schema_defs / "_shared_dates.schema.json"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        schema_dict = cls.export_schema()
        target_path.write_text(json.dumps(schema_dict, indent=2) + "\n", encoding="utf-8")
        LOGGER.info("[SCHEMA] Wrote _shared_dates.schema.json to %s", target_path)
        return target_path


# Aliases for package exports
GDADates = DateEngine
GDADateEngine = DateEngine