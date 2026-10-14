# Name: vocabulary_manager.py
# Path: tools/lib/gdacore/src/gdacore/vocabulary_manager.py
# Version: 1.0.0+build.r3

"""Provide authoritative controlled vocabulary definitions, registries, and schema metadata."""

from __future__ import annotations

__version__ = "1.0.0+build.r3"

from abc import ABCMeta
from collections.abc import Collection, Iterator, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, ClassVar

from gdacore.introspectable import IntrospectableMixin


@dataclass(frozen=True)
class GDAVocabularyEntry:
    """Represent an authoritative controlled vocabulary definition and structural metadata.

    Attributes:
        name: Canonical identifier of the vocabulary (e.g., 'fact_type', 'sex').
        tokens: Tuple of immutable allowed categorical string tokens.
        description: Human-readable narrative explaining the scope of the taxonomy.
        nullable: Boolean indicating whether entity records permit None for this attribute.
        default: Fallback token string if attribute is unassigned; None if required.
    """

    name: str
    tokens: tuple[Any, ...]
    description: str | None = None
    nullable: bool = False
    default: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize vocabulary metadata into a pure dictionary.

        Returns:
            Dictionary containing description, nullable, default, and tokens list.
        """
        return {
            "description": self.description,
            "nullable": self.nullable,
            "default": self.default,
            "tokens": list(self.tokens),
        }


# ==============================================================================
# Master Taxonomic Registries Grouped by Archival Domain
# ==============================================================================

_RAW_DEFINITIONS: dict[str, dict[str, Any]] = {
    # --------------------------------------------------------------------------
    # Group A: Entity & Demographic Vocabularies
    # --------------------------------------------------------------------------
    "fact_type": {
        "description": "Standardized category of historical fact assertions.",
        "nullable": False,
        "default": None,
        "tokens": (
            "Association",
            "Award",
            "Baptism",
            "Birth",
            "Burial",
            "Census",
            "Civic",
            "Death",
            "Divorce",
            "Education",
            "Incident",
            "Legal",
            "Marriage",
            "Military",
            "Occupation",
            "Parentage",
            "Probate",
            "Property",
            "Residence",
            "Other",
            "Unknown",
        ),
    },
    "associated_role": {
        "description": "Standardized kinship, clerical, or legal roles in associated person links.",
        "nullable": False,
        "default": None,
        "tokens": (
            "CHIL",
            "HUSB",
            "WIFE",
            "MOTH",
            "FATH",
            "SPOU",
            "SIBL",
            "WITN",
            "GODP",
            "INFORMANT",
            "CLERGY",
            "OFFICIANT",
            "NEIGHBOR",
            "ATND",
            "UNDR",
            "DEC",
            "OTHR",
            "UNKNOWN",
        ),
    },
    "union_status": {
        "description": "Controlled vocabulary defining legal, domestic, or biological partnership status.",
        "nullable": False,
        "default": None,
        "tokens": (
            "MARRIED",
            "DIVORCED",
            "ANNULLED",
            "SEPARATED",
            "COMMON_LAW",
            "WIDOWED",
            "PARTNER",
            "UNKNOWN",
        ),
    },
    "sex": {
        "description": "Biological sex classification.",
        "nullable": True,
        "default": None,
        "tokens": (
            "Male",
            "Female",
            "Unknown",
        ),
    },
    "marital_status": {
        "description": "Marital status recorded on historical schedules.",
        "nullable": True,
        "default": None,
        "tokens": (
            "Single",
            "Married",
            "Widowed",
            "Divorced",
            "Unknown",
        ),
    },
    "manner_of_death": {
        "description": "Categorical manner of death classification.",
        "nullable": True,
        "default": "Natural",
        "tokens": (
            "Natural",
            "Accident",
            "Suicide",
            "Homicide",
            "Pending",
            "Unknown",
        ),
    },
    # --------------------------------------------------------------------------
    # Group B: Geographic & Physical Site Vocabularies
    # --------------------------------------------------------------------------
    "location_type": {
        "description": "Classification distinguishing civil jurisdictions from physical venues, landmarks, and cemeteries.",
        "nullable": False,
        "default": None,
        "tokens": (
            "CIVIL_JURISDICTION",
            "CEMETERY",
            "CHURCH",
            "HOSPITAL",
            "FACILITY",
            "RESIDENCE",
            "LANDMARK",
            "OTHER",
            "UNKNOWN",
        ),
    },
    "site_type": {
        "description": "Classification of physical venues, facilities, landmarks, and cemeteries.",
        "nullable": False,
        "default": None,
        "tokens": (
            "CEMETERY",
            "CHURCH",
            "HOSPITAL",
            "FACILITY",
            "RESIDENCE",
            "LANDMARK",
            "OTHER",
            "UNKNOWN",
        ),
    },
    "operational_status": {
        "description": "Operational lifecycle status of physical sites.",
        "nullable": False,
        "default": "ACTIVE",
        "tokens": (
            "ACTIVE",
            "DEFUNCT",
            "ABANDONED",
            "HISTORICAL",
            "UNKNOWN",
        ),
    },
    # --------------------------------------------------------------------------
    # Group C: Temporal & Modifier Vocabularies
    # --------------------------------------------------------------------------
    "date_modifier": {
        "description": "Standardized precision and boundary modifiers for historical dates.",
        "nullable": False,
        "default": "EXACT",
        "tokens": (
            "EXACT",
            "ABT",
            "BEF",
            "AFT",
            "BET",
            "FROM_TO",
            "UNKNOWN",
        ),
    },
    "vital_modifier": {
        "description": "Vital status certainty and boundary modifier.",
        "nullable": False,
        "default": "EXACT",
        "tokens": (
            "EXACT",
            "ABT",
            "BEF",
            "AFT",
            "BET",
            "FROM_TO",
            "LIVING",
            "UNKNOWN",
        ),
    },
    # --------------------------------------------------------------------------
    # Group D: Archival Note Vocabularies
    # --------------------------------------------------------------------------
    "note_type": {
        "description": "Archival contextual note classification.",
        "nullable": False,
        "default": "RESEARCH",
        "tokens": (
            "RESEARCH",
            "HISTORICAL",
            "TRANSCRIPTION",
            "DISCREPANCY",
            "PROVENANCE",
            "GENERAL",
        ),
    },
    "note_category": {
        "description": "Detailed archival workflow and discrepancy taxonomy.",
        "nullable": False,
        "default": "GENERAL",
        "tokens": (
            "GENERAL",
            "RESEARCH_TODO",
            "ANOMALY",
            "RESEARCH",
            "DISCREPANCY",
            "TRANSCRIPTION",
            "CORRECTION",
            "PROVENANCE",
            "UNKNOWN",
        ),
    },
    # --------------------------------------------------------------------------
    # Group E: Schedule & Record Vocabularies
    # --------------------------------------------------------------------------
    "census_year": {
        "description": "Federal decennial population census schedule years.",
        "nullable": False,
        "default": None,
        "tokens": (
            1790, 1800, 1810, 1820, 1830, 1840, 1850, 1860,
            1870, 1880, 1900, 1910, 1920, 1930, 1940, 1950,
        ),
    },
    "military_branch": {
        "description": "Standardized branches of the armed forces.",
        "nullable": False,
        "default": "ARMY",
        "tokens": (
            "ARMY",
            "NAVY",
            "MARINES",
            "AIR_FORCE",
            "COAST_GUARD",
            "MILITIA",
            "OTHER",
        ),
    },
    "military_war": {
        "description": "Standardized historical military conflicts and theaters.",
        "nullable": False,
        "default": "OTHER",
        "tokens": (
            "REVOLUTIONARY",
            "WAR_OF_1812",
            "CIVIL_WAR",
            "SPANISH_AMERICAN",
            "WWI",
            "WWII",
            "KOREAN",
            "VIETNAM",
            "OTHER",
        ),
    },
    "home_ownership": {
        "description": "Tenure status of home recorded on federal census schedules.",
        "nullable": True,
        "default": None,
        "tokens": (
            "Owned",
            "Rented",
            "Free",
            "Mortgaged",
            "Unknown",
        ),
    },
    "citizenship_status": {
        "description": "Naturalization and legal residency classification on census returns.",
        "nullable": True,
        "default": None,
        "tokens": (
            "Native Born",
            "Naturalized",
            "Alien",
            "Declarant",
            "Non-Declarant",
            "Unknown",
        ),
    },
    "wwi_card_type": {
        "description": "World War I draft registration schedule card classification.",
        "nullable": True,
        "default": None,
        "tokens": (
            "Card A (1917)",
            "Card B (1918)",
            "Card C (1918)",
            "Unknown",
        ),
    },
    "quality_assessment": {
        "description": "Archival source reliability and clarity rating.",
        "nullable": False,
        "default": "GOOD",
        "tokens": (
            "EXCELLENT",
            "GOOD",
            "FAIR",
            "POOR",
            "UNKNOWN",
        ),
    },
    "selective_service_class": {
        "description": "Selective service classification codes.",
        "nullable": False,
        "default": "1-A",
        "tokens": (
            "1-A",
            "1-C",
            "2-A",
            "2-B",
            "3-A",
            "4-A",
            "4-D",
            "4-F",
            "UNKNOWN",
        ),
    },
    "document_side": {
        "description": "Physical archival document side or orientation.",
        "nullable": False,
        "default": "FRONT",
        "tokens": (
            "FRONT",
            "BACK",
            "INSIDE",
            "OUTSIDE",
            "ENCLOSURE",
            "UNKNOWN",
        ),
    },
}

# Authoritative typed registry of GDAVocabularyEntry objects
TAXONOMY_REGISTRY: dict[str, dict[str, Any]] = {
    k: GDAVocabularyEntry(
        name=k,
        tokens=v["tokens"],
        description=v.get("description"),
        nullable=v.get("nullable", False),
        default=v.get("default"),
    ).to_dict()
    for k, v in _RAW_DEFINITIONS.items()
}

# Backward-compatible dictionary mapping vocabulary names to lists of tokens
CONTROLLED_VOCABULARIES: dict[str, list[Any]] = {
    k: list(v["tokens"]) for k, v in TAXONOMY_REGISTRY.items()
}


class _GDAVocabularyManagerMeta(ABCMeta):
    """Metaclass providing direct class-level subscription and iteration support."""

    def __getitem__(cls, enum_type: str) -> list[Any]:
        return cls.get_list(cls, enum_type)

    def __iter__(cls) -> Iterator[str]:
        return iter(cls.get_names())

    def __len__(cls) -> int:
        return len(cls.get_names())

    def __contains__(cls, item: Any) -> bool:
        return cls.contains_key(item)


class GDAVocabularyManager(IntrospectableMixin, Collection[str], metaclass=_GDAVocabularyManagerMeta):
    """Govern access to controlled vocabulary token lists, validation, and schema metadata.

    Supports both class-level static access (e.g., `GDAVocabularyManager['fact_type']`)
    and instantiated singleton access (e.g., `mgr = GDAVocabularyManager(); mgr.sex`).
    """

    _class_registry: ClassVar[dict[str, GDAVocabularyEntry]] = {
        k: GDAVocabularyEntry(
            name=k,
            tokens=_RAW_DEFINITIONS[k]["tokens"],
            description=_RAW_DEFINITIONS[k].get("description"),
            nullable=_RAW_DEFINITIONS[k].get("nullable", False),
            default=_RAW_DEFINITIONS[k].get("default"),
        )
        for k in _RAW_DEFINITIONS
    }
    _custom_schema_path: ClassVar[Path | None] = None
    _custom_registry: ClassVar[dict[str, GDAVocabularyEntry] | None] = None

    def __init__(
        self,
        registry: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Initialize vocabulary manager with default or custom registry mapping.

        Args:
            registry: Optional custom dictionary mapping vocabulary names to metadata.
        """
        self._instance_registry: dict[str, GDAVocabularyEntry] | None = None
        if registry is not None:
            self._instance_registry = {
                k: GDAVocabularyEntry(
                    name=k,
                    tokens=tuple(v.get("tokens", ())),
                    description=v.get("description"),
                    nullable=v.get("nullable", False),
                    default=v.get("default"),
                )
                for k, v in registry.items()
            }

    # -------------------------------------------------------------------------
    # Internal Registry Resolution
    # -------------------------------------------------------------------------
    @classmethod
    def _normalize_key(cls, key: Any) -> str:
        """Normalize vocabulary name string by stripping optional 'enum_' prefix.

        Args:
            key: Raw dictionary or attribute key.

        Returns:
            Normalized lowercase key.
        """
        clean = str(key).strip().lower()
        if clean.startswith("enum_"):
            return clean[5:]
        return clean

    @classmethod
    def _get_active_registry(cls) -> dict[str, GDAVocabularyEntry]:
        """Resolve the active vocabulary registry considering custom overrides."""
        if cls._custom_registry is not None:
            return cls._custom_registry
        return cls._class_registry

    def _resolve_context_registry(self) -> dict[str, GDAVocabularyEntry]:
        """Resolve registry context favoring instance override if present."""
        if self._instance_registry is not None:
            return self._instance_registry
        return self._get_active_registry()

    # -------------------------------------------------------------------------
    # Schema Override and Cache Management
    # -------------------------------------------------------------------------
    @classmethod
    def set_custom_schema_path(cls, path: Path | str | None) -> None:
        """Configure a custom JSON schema file path to override authoritative vocabularies.

        Args:
            path: Path to schema JSON file, or None to revert to default definitions.
        """
        if path is None:
            cls._custom_schema_path = None
            cls._custom_registry = None
            return

        resolved = Path(path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Custom schema file does not exist: {resolved}")

        content = json.loads(resolved.read_text(encoding="utf-8"))
        extracted: dict[str, GDAVocabularyEntry] = {}

        defs = None
        if isinstance(content, Mapping):
            defs = content.get("$defs") or content.get("definitions") or content

        if isinstance(defs, Mapping):
            for k, v in defs.items():
                if isinstance(v, Mapping) and "enum" in v and isinstance(v["enum"], (list, tuple)):
                    norm_name = cls._normalize_key(k)
                    extracted[norm_name] = GDAVocabularyEntry(
                        name=norm_name,
                        tokens=tuple(v["enum"]),
                        description=v.get("description"),
                    )

        cls._custom_schema_path = resolved
        cls._custom_registry = extracted

    @classmethod
    def clear_cache(cls) -> None:
        """Clear dynamic cache and reload default registry."""
        cls._custom_registry = None

    @classmethod
    def reset_cache(cls) -> None:
        """Reset custom paths and revert vocabulary manager to pristine state."""
        cls.set_custom_schema_path(None)

    # -------------------------------------------------------------------------
    # Mapping and Collection Protocol (Class & Instance Symmetrical)
    # -------------------------------------------------------------------------
    @classmethod
    def get_names(cls) -> list[str]:
        """Return a list of all registered vocabulary names.

        Returns:
            List of registered vocabulary name strings.
        """
        return list(cls._get_active_registry().keys())

    @classmethod
    def contains_key(cls, item: Any) -> bool:
        """Verify whether an enum name exists in the active registry.

        Args:
            item: String key to query.

        Returns:
            True if item (or enum_[item]) is registered; False otherwise.
        """
        if not isinstance(item, str):
            return False
        return cls._normalize_key(item) in cls._get_active_registry()

    def __iter__(self) -> Iterator[str]:
        """Yield registered vocabulary names."""
        reg = self._resolve_context_registry()
        return iter(reg.keys())

    def __len__(self) -> int:
        """Return the count of registered vocabularies."""
        reg = self._resolve_context_registry()
        return len(reg)

    def __contains__(self, item: Any) -> bool:
        """Verify whether a vocabulary name exists in the instance."""
        if not isinstance(item, str):
            return False
        clean = self._normalize_key(item)
        reg = self._resolve_context_registry()
        return clean in reg

    def __getitem__(self, enum_type: str) -> list[Any]:
        """Support subscription syntax: mgr['fact_type'].

        Args:
            enum_type: Vocabulary name.

        Returns:
            List of permitted token strings.
        """
        return self.get_list(enum_type)

    def __getattr__(self, name: str) -> list[Any]:
        """Support direct attribute access: mgr.sex, mgr.fact_type.

        Args:
            name: Vocabulary attribute identifier.

        Returns:
            List of permitted token strings.

        Raises:
            AttributeError: If name is not a registered vocabulary.
        """
        clean = self._normalize_key(name)
        reg = self._resolve_context_registry()
        if clean in reg:
            return list(reg[clean].tokens)
        raise AttributeError(f"'{type(self).__name__}' has no attribute or vocabulary '{name}'")

    def items(self) -> Iterator[tuple[str, list[Any]]]:
        """Yield (enum_name, token_list) pairs.

        Returns:
            Iterator yielding tuples of vocabulary name and list of tokens.
        """
        reg = self._resolve_context_registry()
        for key, entry in reg.items():
            yield key, list(entry.tokens)

    def keys(self) -> Iterator[str]:
        """Yield registered vocabulary names.

        Returns:
            Iterator yielding string vocabulary names.
        """
        reg = self._resolve_context_registry()
        return iter(reg.keys())

    def values(self) -> Iterator[list[Any]]:
        """Yield lists of registered vocabulary tokens.

        Returns:
            Iterator yielding token lists.
        """
        reg = self._resolve_context_registry()
        for entry in reg.values():
            yield list(entry.tokens)

    def entries(self) -> Iterator[tuple[str, dict[str, Any]]]:
        """Yield (enum_name, taxonomy_metadata_dict) pairs.

        Returns:
            Iterator yielding pairs of vocabulary name and metadata dictionary.
        """
        reg = self._resolve_context_registry()
        for key, entry in reg.items():
            yield key, entry.to_dict()

    # -------------------------------------------------------------------------
    # Dual-Access Retrieval and Validation Handlers
    # -------------------------------------------------------------------------
    @classmethod
    def _resolve_target_registry(
        cls,
        caller: Any,
    ) -> dict[str, GDAVocabularyEntry]:
        """Resolve the backing registry from either instance context or class scope."""
        if isinstance(caller, GDAVocabularyManager):
            return caller._resolve_context_registry()
        return cls._get_active_registry()

    def get_list(self_or_cls, *args: Any) -> list[Any]:
        """Retrieve the canonical list of allowed tokens for a vocabulary.

        Args:
            *args: enum_type string, optionally preceded by explicit instance/class.

        Returns:
            List of allowed tokens.

        Raises:
            KeyError: If enum_type is unregistered.
        """
        target = self_or_cls if len(args) == 1 else args[0]
        enum_type = args[0] if len(args) == 1 else args[1]
        clean = GDAVocabularyManager._normalize_key(enum_type)
        reg = GDAVocabularyManager._resolve_target_registry(target)
        if clean in reg:
            return list(reg[clean].tokens)
        raise KeyError(f"Unknown enum type '{enum_type}'. Available: {list(reg.keys())}")

    def get_set(self_or_cls, *args: Any) -> set[Any]:
        """Retrieve allowed values as a set of strings.

        Args:
            *args: enum_type string, optionally preceded by explicit instance/class.

        Returns:
            Set containing all valid token strings.
        """
        return set(GDAVocabularyManager.get_list(self_or_cls, *args))

    def get_metadata(self_or_cls, *args: Any) -> dict[str, Any]:
        """Retrieve full taxonomy metadata for an enum type.

        Args:
            *args: enum_type string, optionally preceded by explicit instance/class.

        Returns:
            Dictionary containing description, nullable, default, and tokens.

        Raises:
            KeyError: If enum_type is unregistered.
        """
        target = self_or_cls if len(args) == 1 else args[0]
        enum_type = args[0] if len(args) == 1 else args[1]
        clean = GDAVocabularyManager._normalize_key(enum_type)
        reg = GDAVocabularyManager._resolve_target_registry(target)
        if clean in reg:
            return reg[clean].to_dict()
        raise KeyError(f"Unknown enum type '{enum_type}'. Available: {list(reg.keys())}")

    def get_entry(self_or_cls, *args: Any) -> GDAVocabularyEntry:
        """Retrieve the typed GDAVocabularyEntry dataclass for an enum type.

        Args:
            *args: enum_type string, optionally preceded by explicit instance/class.

        Returns:
            Immutable GDAVocabularyEntry instance.

        Raises:
            KeyError: If enum_type is unregistered.
        """
        target = self_or_cls if len(args) == 1 else args[0]
        enum_type = args[0] if len(args) == 1 else args[1]
        clean = GDAVocabularyManager._normalize_key(enum_type)
        reg = GDAVocabularyManager._resolve_target_registry(target)
        if clean in reg:
            return reg[clean]
        raise KeyError(f"Unknown enum type '{enum_type}'. Available: {list(reg.keys())}")

    def is_valid(self_or_cls, *args: Any) -> bool:
        """Check whether a candidate value is permitted for an enum type.

        Args:
            *args: (enum_type, value) strings, optionally preceded by instance/class.

        Returns:
            True if value is an approved token; False if value is None or unlisted.
        """
        target = self_or_cls if len(args) == 2 else args[0]
        enum_type = args[0] if len(args) == 2 else args[1]
        value = args[1] if len(args) == 2 else args[2]

        if value is None:
            return False
        try:
            tokens = GDAVocabularyManager.get_set(target, enum_type)
            return value in tokens
        except KeyError:
            return False

    def resolve_token(self_or_cls, *args: Any) -> str | None:
        """Resolve a case-insensitive, whitespace-trimmed token to its canonical form.

        Args:
            *args: (enum_type, candidate) strings, optionally preceded by instance/class.

        Returns:
            Canonical token string matching defined case; None if unmatched or invalid.
        """
        target = self_or_cls if len(args) == 2 else args[0]
        enum_type = args[0] if len(args) == 2 else args[1]
        candidate = args[1] if len(args) == 2 else args[2]

        if not candidate or not isinstance(candidate, str):
            return None
        clean_target = candidate.strip().lower()
        if not clean_target:
            return None
        try:
            for token in GDAVocabularyManager.get_list(target, enum_type):
                if isinstance(token, str) and token.lower() == clean_target:
                    return token
        except KeyError:
            return None
        return None

    # -------------------------------------------------------------------------
    # Convenience Domain Getters (Class-Level)
    # -------------------------------------------------------------------------
    @classmethod
    def get_allowed(cls, enum_type: str) -> set[Any]:
        """Retrieve allowed tokens as a set at class level.

        Args:
            enum_type: Target vocabulary category.

        Returns:
            Set of valid tokens.
        """
        return cls.get_set(cls, enum_type)

    @classmethod
    def get_fact_types(cls) -> list[str]:
        """Retrieve all canonical historical fact assertion types."""
        return list(cls._get_active_registry()["fact_type"].tokens)

    @classmethod
    def get_operational_statuses(cls) -> list[str]:
        """Retrieve all canonical site operational status codes."""
        return list(cls._get_active_registry()["operational_status"].tokens)

    @classmethod
    def get_selective_service_classes(cls) -> list[str]:
        """Retrieve all canonical selective service classification codes."""
        return list(cls._get_active_registry()["selective_service_class"].tokens)

    @classmethod
    def get_document_sides(cls) -> list[str]:
        """Retrieve all canonical archival document side tokens."""
        return list(cls._get_active_registry()["document_side"].tokens)

    @classmethod
    def get_kinship_roles(cls) -> list[str]:
        """Retrieve all canonical kinship and association roles."""
        return list(cls._get_active_registry()["associated_role"].tokens)

    @classmethod
    def get_union_statuses(cls) -> list[str]:
        """Retrieve all canonical union status classification codes."""
        return list(cls._get_active_registry()["union_status"].tokens)


# Aliases for backward compatibility
GDASchemaEnums = GDAVocabularyManager
SchemaEnums = GDAVocabularyManager