# Name: registry.py
# Path: tools/lib/gda_core/registry.py

import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path("G:/My Drive/genealogy-digital-archive")
ENUMS_PATH = ROOT_DIR / "schemas/defs/_enums.schema.json"
LEGACY_ENUMS_PATH = ROOT_DIR / "schemas/defs/enums.schema.json"
SHARED_DEFS_PATH = ROOT_DIR / "schemas/defs/_shared_defs.schema.json"


class SchemaEnums:
    """Provides lookup and validation against archive controlled vocabularies."""

    _cached_enums: dict[str, set[Any]] | None = None

    @classmethod
    def _load_enums(cls) -> dict[str, set[Any]]:
        if cls._cached_enums is not None:
            return cls._cached_enums

        target_file = None
        if ENUMS_PATH.exists():
            target_file = ENUMS_PATH
        elif LEGACY_ENUMS_PATH.exists():
            target_file = LEGACY_ENUMS_PATH
        elif SHARED_DEFS_PATH.exists():
            target_file = SHARED_DEFS_PATH

        if not target_file:
            cls._cached_enums = {}
            return cls._cached_enums

        try:
            data = json.loads(target_file.read_text(encoding="utf-8"))
            defs = data.get("$defs", {})
            result: dict[str, set[Any]] = {}

            for key, def_obj in defs.items():
                if isinstance(def_obj, dict) and "enum" in def_obj:
                    result[key] = set(def_obj["enum"])

            # Cross-populate from _shared_defs if primary was _enums
            if target_file != SHARED_DEFS_PATH and SHARED_DEFS_PATH.exists():
                shared_data = json.loads(SHARED_DEFS_PATH.read_text(encoding="utf-8"))
                for key, def_obj in shared_data.get("$defs", {}).items():
                    if isinstance(def_obj, dict) and "enum" in def_obj and key not in result:
                        result[key] = set(def_obj["enum"])

            cls._cached_enums = result
            return cls._cached_enums
        except Exception:
            cls._cached_enums = {}
            return cls._cached_enums

    @classmethod
    def is_valid(cls, enum_name: str, value: Any) -> bool:
        enums = cls._load_enums()
        valid_set = enums.get(enum_name)
        if valid_set is None:
            return True
        return value in valid_set

    @classmethod
    def get_allowed(cls, enum_name: str) -> set[Any]:
        return cls._load_enums().get(enum_name, set())

    @classmethod
    def reset_cache(cls):
        cls._cached_enums = None