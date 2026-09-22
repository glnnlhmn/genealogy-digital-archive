# Name: registry.py
# Path: tools/lib/gda_core/registry.py

import json
from pathlib import Path
from typing import Any

from tools.lib.gda_core.GDAConfig import CONFIG


class SchemaEnums:
    """Provides lookup and validation against archive controlled vocabularies."""

    _cached_lists: dict[str, list[Any]] | None = None
    _cached_sets: dict[str, set[Any]] | None = None

    @classmethod
    def _load_enums(cls) -> None:
        if cls._cached_lists is not None and cls._cached_sets is not None:
            return

        target_file = None
        if CONFIG.enums.exists():
            target_file = CONFIG.enums
        else:
            legacy_path = CONFIG.schema_defs / "enums.schema.json"
            shared_defs_path = CONFIG.schema_defs / "_shared_defs.schema.json"
            if legacy_path.exists():
                target_file = legacy_path
            elif shared_defs_path.exists():
                target_file = shared_defs_path

        if not target_file:
            cls._cached_lists = {}
            cls._cached_sets = {}
            return

        try:
            data = json.loads(target_file.read_text(encoding="utf-8"))
            defs = data.get("$defs", {})
            lists: dict[str, list[Any]] = {}
            sets: dict[str, set[Any]] = {}

            for key, def_obj in defs.items():
                if isinstance(def_obj, dict) and "enum" in def_obj:
                    enum_vals = list(def_obj["enum"])
                    lists[key] = enum_vals
                    sets[key] = set(enum_vals)

            # Cross-populate from _shared_defs if present and not primary target
            shared_defs_path = CONFIG.schema_defs / "_shared_defs.schema.json"
            if target_file != shared_defs_path and shared_defs_path.exists():
                shared_data = json.loads(shared_defs_path.read_text(encoding="utf-8"))
                for key, def_obj in shared_data.get("$defs", {}).items():
                    if isinstance(def_obj, dict) and "enum" in def_obj and key not in lists:
                        enum_vals = list(def_obj["enum"])
                        lists[key] = enum_vals
                        sets[key] = set(enum_vals)

            cls._cached_lists = lists
            cls._cached_sets = sets
        except Exception:
            cls._cached_lists = {}
            cls._cached_sets = {}

    @classmethod
    def __class_getitem__(cls, enum_name: str) -> list[Any]:
        """Allows direct subscription: SchemaEnums['enum_fact_type']"""
        cls._load_enums()
        assert cls._cached_lists is not None
        if enum_name not in cls._cached_lists:
            raise KeyError(f"Enum '{enum_name}' not found in archive schemas.")
        return cls._cached_lists[enum_name]

    @classmethod
    def is_valid(cls, enum_name: str, value: Any) -> bool:
        """Validates if value is permitted under the specified enum."""
        if value is None:
            return True
        cls._load_enums()
        assert cls._cached_sets is not None
        valid_set = cls._cached_sets.get(enum_name)
        if valid_set is None:
            return True
        return value in valid_set

    @classmethod
    def get_allowed(cls, enum_name: str) -> set[Any]:
        """Returns allowed values as a set."""
        cls._load_enums()
        assert cls._cached_sets is not None
        return cls._cached_sets.get(enum_name, set())

    @classmethod
    def reset_cache(cls) -> None:
        """Flushes the in-memory enum caches."""
        cls._cached_lists = None
        cls._cached_sets = None