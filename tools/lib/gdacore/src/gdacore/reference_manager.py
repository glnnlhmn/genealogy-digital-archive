# Name: reference_manager.py
# Path: tools/lib/gdacore/src/gdacore/reference_manager.py
# Version: 1.0.0+build.rc1

"""Provide centralized entity identifier syntax validation, prefixes, and static reference table caching."""

from __future__ import annotations

__version__ = "1.0.0+build.rc1"

from collections.abc import Mapping
import json
from pathlib import Path
import re
from typing import Any, ClassVar

from gdacore import config
from gdacore.introspectable import IntrospectableMixin


class GDAReferenceManager(IntrospectableMixin):
    """Manage entity identifier syntax formatting, prefix extraction, and static reference tables.

    Attributes:
        PERSON_ID_PATTERN: Regex pattern validating canonical person IDs (IND-XXXXX).
        SITE_ID_PATTERN: Regex pattern validating canonical site IDs (SID-XXXXX).
        LEGACY_SITE_ID_PATTERN: Regex pattern supporting legacy site IDs (SITE-XXXXX).
        LOC_ID_PATTERN: Regex pattern validating canonical location IDs (LOC-XXXXX).
        SOURCE_ID_PATTERN: Regex pattern validating canonical source IDs (SRC-XXXXX).
        NOTE_ID_PATTERN: Regex pattern validating canonical note IDs (NOT-XXXXX).
        GUID_PATTERN: Regex pattern validating 36-character hexadecimal UUIDv4 strings.
        VALID_ID_PREFIXES: Frozenset of approved 3-character entity prefix tokens.
    """

    PERSON_ID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^IND-\d{5}$")
    SITE_ID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^SID-\d{5}$")
    LEGACY_SITE_ID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^SITE-\d{5}$")
    LOC_ID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^LOC-\d{5}$")
    SOURCE_ID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^SRC-\d{5}$")
    NOTE_ID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^NOT-\d{5}$")
    GUID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    VALID_ID_PREFIXES: ClassVar[frozenset[str]] = frozenset({"IND", "SID", "LOC", "SRC", "NOT"})

    _table_cache: ClassVar[dict[str, dict[str, Any]]] = {}

    # -------------------------------------------------------------------------
    # Entity Identifier Validation Services
    # -------------------------------------------------------------------------
    @classmethod
    def get_all_valid_id_prefixes(cls) -> set[str]:
        """Retrieve all approved canonical entity identifier prefixes.

        Returns:
            Defensive copy set containing canonical prefix tokens {'IND', 'SID', 'LOC', 'SRC', 'NOT'}.
        """
        return set(cls.VALID_ID_PREFIXES)

    @classmethod
    def extract_id_prefix(cls, entity_id: str | None) -> str | None:
        """Extract the leading prefix token from an entity identifier string.

        Args:
            entity_id: Candidate identifier string (e.g., 'IND-00042', 'SID-00001').

        Returns:
            Uppercase prefix string if hyphen delimited; None otherwise.
        """
        if not entity_id or not isinstance(entity_id, str):
            return None
        clean_id = entity_id.strip()
        if "-" not in clean_id:
            return None
        prefix = clean_id.split("-")[0].strip().upper()
        return prefix if prefix else None

    @classmethod
    def is_valid_guid(cls, candidate: str | None) -> bool:
        """Validate whether a string matches canonical lowercase UUIDv4 format.

        Args:
            candidate: Candidate identifier string to validate.

        Returns:
            True if candidate matches standard lowercase UUIDv4 format, False otherwise.
        """
        if not candidate or not isinstance(candidate, str):
            return False
        return bool(cls.GUID_PATTERN.match(candidate.strip().lower()))

    @classmethod
    def is_valid_fact_id(cls, fact_id: str | None) -> bool:
        """Validate whether a string matches canonical fact UUIDv4 format.

        Args:
            fact_id: Identifier string to validate.

        Returns:
            True if the identifier matches standard lowercase UUIDv4 format, False otherwise.
        """
        return cls.is_valid_guid(fact_id)

    @classmethod
    def is_valid_person_id(cls, person_id: str | None) -> bool:
        """Validate whether a string matches the canonical person ID pattern (IND-XXXXX).

        Args:
            person_id: Identifier string to validate.

        Returns:
            True if the identifier matches IND-XXXXX, False otherwise.
        """
        if not person_id or not isinstance(person_id, str):
            return False
        return bool(cls.PERSON_ID_PATTERN.match(person_id.strip()))

    @classmethod
    def is_valid_site_id_format(cls, site_id: str | None) -> bool:
        """Validate whether a string matches canonical site ID (SID-XXXXX) or legacy (SITE-XXXXX).

        Args:
            site_id: Identifier string to validate.

        Returns:
            True if matching ^SID-[0-9]{5}$ or legacy ^SITE-[0-9]{5}$, False otherwise.
        """
        if not site_id or not isinstance(site_id, str):
            return False
        clean_id = site_id.strip()
        return bool(cls.SITE_ID_PATTERN.match(clean_id) or cls.LEGACY_SITE_ID_PATTERN.match(clean_id))

    @classmethod
    def is_valid_location_id_format(cls, location_id: str | None) -> bool:
        """Validate whether a string matches the canonical location ID pattern (LOC-XXXXX).

        Args:
            location_id: Identifier string to validate.

        Returns:
            True if matching ^LOC-[0-9]{5}$, False otherwise.
        """
        if not location_id or not isinstance(location_id, str):
            return False
        return bool(cls.LOC_ID_PATTERN.match(location_id.strip()))

    @classmethod
    def is_valid_source_id(cls, source_id: str | None) -> bool:
        """Validate whether a string matches the canonical source ID pattern (SRC-XXXXX).

        Args:
            source_id: Identifier string to validate.

        Returns:
            True if matching ^SRC-[0-9]{5}$, False otherwise.
        """
        if not source_id or not isinstance(source_id, str):
            return False
        return bool(cls.SOURCE_ID_PATTERN.match(source_id.strip()))

    @classmethod
    def is_valid_note_id(cls, note_id: str | None) -> bool:
        """Validate whether a string matches the canonical note ID pattern (NOT-XXXXX).

        Args:
            note_id: Identifier string to validate.

        Returns:
            True if matching ^NOT-[0-9]{5}$, False otherwise.
        """
        if not note_id or not isinstance(note_id, str):
            return False
        return bool(cls.NOTE_ID_PATTERN.match(note_id.strip()))

    @classmethod
    def is_valid_gda_id(
        cls,
        entity_id: str | None,
        entity_type: str = "AUTO",
    ) -> bool:
        """Validate entity identifier syntax across all archive domain registries.

        Args:
            entity_id: Candidate identifier string to validate.
            entity_type: Expected category token ('AUTO', 'LOCATION'/'LOC',
                'SITE'/'SID', 'PERSON'/'IND', 'SOURCE'/'SRC', 'NOTE'/'NOT',
                'FACT'/'UUID'/'GUID'). Case-insensitive.

        Returns:
            True if entity_id structurally conforms to the specified pattern,
            False otherwise.
        """
        if not entity_id or not isinstance(entity_id, str):
            return False
        if not entity_type or not isinstance(entity_type, str):
            return False

        clean_id = entity_id.strip()
        target_type = entity_type.strip().upper()

        if target_type == "AUTO":
            if clean_id.startswith("IND-"):
                return cls.is_valid_person_id(clean_id)
            if clean_id.startswith("SID-") or clean_id.startswith("SITE-"):
                return cls.is_valid_site_id_format(clean_id)
            if clean_id.startswith("LOC-"):
                return cls.is_valid_location_id_format(clean_id)
            if clean_id.startswith("SRC-"):
                return cls.is_valid_source_id(clean_id)
            if clean_id.startswith("NOT-"):
                return cls.is_valid_note_id(clean_id)
            return cls.is_valid_guid(clean_id)

        if target_type in ("PERSON", "IND"):
            return cls.is_valid_person_id(clean_id)

        if target_type in ("SITE", "SID"):
            return cls.is_valid_site_id_format(clean_id)

        if target_type in ("LOCATION", "LOC"):
            return cls.is_valid_location_id_format(clean_id)

        if target_type in ("SOURCE", "SRC"):
            return cls.is_valid_source_id(clean_id)

        if target_type in ("NOTE", "NOT"):
            return cls.is_valid_note_id(clean_id)

        if target_type in ("FACT", "UUID", "GUID"):
            return cls.is_valid_guid(clean_id)

        return False

    # -------------------------------------------------------------------------
    # Option A Compatibility Bridges (Deprecated: Slated for removal)
    # NOTE: These bridge methods exist strictly for temporary backward compatibility
    # with downstream callers in gdadomain and tools/ops. They are slated for removal
    # once those callers are updated to call GDAVocabularyManager directly.
    # -------------------------------------------------------------------------
    @classmethod
    def get_kinship_roles(cls) -> set[str]:
        """Retrieve canonical kinship roles set (Deprecated: use GDAVocabularyManager).

        Returns:
            Set containing canonical kinship role tokens.
        """
        return set(cls.get_kinship_roles_list())

    @classmethod
    def get_kinship_roles_list(cls) -> list[str]:
        """Retrieve canonical kinship roles list (Deprecated: use GDAVocabularyManager).

        Returns:
            List containing canonical kinship role tokens.
        """
        return [
            "FATH",
            "MOTH",
            "PARENT",
            "CHIL",
            "SON",
            "DAUG",
            "SPOU",
            "HUSB",
            "WIFE",
            "SIBL",
            "BROT",
            "SIST",
            "WITN",
            "OFFICIANT",
            "INFORMANT",
        ]

    @classmethod
    def get_union_statuses(cls) -> set[str]:
        """Retrieve canonical union statuses set (Deprecated: use GDAVocabularyManager).

        Returns:
            Set containing canonical union status tokens.
        """
        return set(cls.get_union_statuses_list())

    @classmethod
    def get_union_statuses_list(cls) -> list[str]:
        """Retrieve canonical union statuses list (Deprecated: use GDAVocabularyManager).

        Returns:
            List containing canonical union status tokens.
        """
        return [
            "MARRIED",
            "DIVORCED",
            "SEPARATED",
            "COMMON_LAW",
            "PARTNER",
            "ANNULLED",
            "UNKNOWN",
        ]

    # -------------------------------------------------------------------------
    # Static Reference Table and Caching Services
    # -------------------------------------------------------------------------
    @classmethod
    def get_reference_dir(cls) -> Path:
        """Retrieve the canonical directory path housing static reference tables.

        Returns:
            Path resolving to data/reference/ under active configuration.
        """
        return config.CONFIG.data / "reference"

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all in-memory cached static reference tables."""
        cls._table_cache.clear()

    @classmethod
    def get_table(cls, table_name: str) -> dict[str, Any]:
        """Load and cache a static reference table from data/reference/.

        Args:
            table_name: Base filename or identifier of the reference table.

        Returns:
            Parsed JSON dictionary representing the reference table.

        Raises:
            FileNotFoundError: If the target reference file does not exist on disk.
            ValueError: If the file contains malformed or unparseable JSON.
        """
        clean_name = table_name.strip()
        if not clean_name.endswith(".json"):
            clean_name = f"{clean_name}.json"

        if clean_name in cls._table_cache:
            return cls._table_cache[clean_name]

        target_file = cls.get_reference_dir() / clean_name
        if not target_file.is_file():
            raise FileNotFoundError(f"Reference table '{table_name}' not found: {target_file}")

        try:
            content = target_file.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception as err:
            raise ValueError(f"Failed to parse reference table '{table_name}': {err}") from err

        cls._table_cache[clean_name] = data
        return data

    @classmethod
    def get_colloquial_states(cls) -> dict[str, str]:
        """Retrieve colloquial US state abbreviations and historical alias mappings.

        Returns:
            Dictionary mapping colloquial state abbreviations to canonical names.
        """
        table = cls.get_table("states_colloquial")
        if "mappings" in table and isinstance(table["mappings"], Mapping):
            return dict(table["mappings"])
        return {}

    @classmethod
    def resolve_colloquial_state(cls, candidate: str | None) -> str | None:
        """Resolve a state alias or abbreviation to its canonical full name.

        Handles whitespace stripping and case-insensitive resolution against
        the cached states_colloquial reference table.

        Args:
            candidate: State abbreviation or colloquial token (e.g., 'penn', 'NH', 'Mass').

        Returns:
            Canonical state name (e.g., 'Pennsylvania') if matched; None otherwise.
        """
        if not candidate or not isinstance(candidate, str):
            return None

        clean_token = candidate.strip().lower()
        if not clean_token:
            return None

        mappings = cls.get_colloquial_states()
        return mappings.get(clean_token)