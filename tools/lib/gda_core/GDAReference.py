# Name: GDAReference.py
# Path: tools/lib/gda_core/GDAReference.py
# Version: 1.0.0+build.20260929.3

"""Centralized reference table and gazetteer provider for GDA framework.

Operational Role:
    Provides in-memory cached access to static lookup tables and historical
    gazetteers stored under data/reference/ to prevent redundant disk I/O
    and code-level dictionary bloat.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil


class GDAReference:
    """Centralized, cached reference table provider for gazetteers and lookup mappings."""

    _cache: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_reference_dir(cls) -> Path:
        """Resolves the canonical data/reference directory path."""
        # Anchors from GDAConfig root_dir if available, else standard fallback
        if hasattr(GDAConfig, "root_dir") and GDAConfig.root_dir:
            return GDAConfig.root_dir / "data" / "reference"
        return GDAConfig.entities_dir.parent / "reference"

    @classmethod
    def get_table(cls, table_name: str) -> dict[str, Any]:
        """Loads and caches reference tables from data/reference/<table_name>.json.

        Args:
            table_name: Stem name of the reference file (without .json).

        Returns:
            Parsed dictionary representing the reference table.

        Raises:
            FileNotFoundError: If the target reference table does not exist.
            ValueError: If the file content cannot be parsed as valid JSON.
        """
        clean_name = table_name.strip()
        if clean_name in cls._cache:
            return cls._cache[clean_name]

        ref_file = cls.get_reference_dir() / f"{clean_name}.json"
        if not ref_file.exists() or not ref_file.is_file():
            raise FileNotFoundError(
                f"Reference table '{clean_name}' not found at {ref_file}"
            )

        try:
            payload = GDAUtil.load_json(ref_file)
        except (json.JSONDecodeError, Exception) as exc:
            raise ValueError(
                f"Failed to parse reference table '{clean_name}': {exc}"
            ) from exc

        cls._cache[clean_name] = payload
        return cls._cache[clean_name]

    @classmethod
    def get_colloquial_states(cls) -> dict[str, str]:
        """Retrieves historical and colloquial US state abbreviation mappings.

        Returns:
            Dictionary mapping lowercase colloquial abbreviation strings to
            canonical full state names.
        """
        table = cls.get_table("states_colloquial")
        mappings: dict[str, str] = table.get("mappings", {})
        return mappings

    @classmethod
    def clear_cache(cls, table_name: Optional[str] = None) -> None:
        """Evicts cached tables from memory.

        Args:
            table_name: Specific table to evict, or None to clear all tables.
        """
        if table_name:
            cls._cache.pop(table_name, None)
        else:
            cls._cache.clear()