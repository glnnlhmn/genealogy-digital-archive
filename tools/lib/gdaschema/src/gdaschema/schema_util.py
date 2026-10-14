# Name: schema_util.py
# Path: tools/lib/gdaschema/src/gdaschema/schema_util.py
# Version: 1.0.0rc1+build.r4

"""Schema utility helpers for Draft 2020-12 envelope generation and normalization.

Operational Role:
    Provides canonical URI resolution, Draft 2020-12 schema envelope scaffolding
    including top-level _name and _path metadata for GSI intake, deterministic
    JSON serialization, and title casing utilities.
"""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any, Dict, Optional

__version__ = "1.0.0rc1+build.r4"

SCHEMA_DRAFT_2020_12: str = "https://json-schema.org/draft/2020-12/schema"
CANONICAL_SCHEMA_BASE_URI: str = "https://genealogy.archive/schemas/"


def normalize_schema_subpath(schema_subpath: str) -> str:
    """Normalize a relative schema subpath to clean POSIX format.

    Strips leading 'schemas/' or slashes to yield canonical relative paths
    (e.g., 'defs/_enums.schema.json').

    Args:
        schema_subpath: Relative path or filename of the target schema.

    Returns:
        Cleaned POSIX relative path string.
    """
    clean = str(schema_subpath).replace("\\", "/").strip().lstrip("/")
    if clean.startswith("schemas/"):
        clean = clean[len("schemas/") :]
    return clean.lstrip("/")


def resolve_schema_id(schema_subpath: str) -> str:
    """Resolve a relative schema subpath to its canonical $id URI.

    Args:
        schema_subpath: Relative path or filename (e.g., 'defs/_shared_defs.schema.json').

    Returns:
        Fully qualified canonical URI (e.g., 'https://genealogy.archive/schemas/defs/_shared_defs.schema.json').
    """
    normalized = normalize_schema_subpath(schema_subpath)
    return f"{CANONICAL_SCHEMA_BASE_URI}{normalized}"


def build_schema_envelope(
    title: str,
    version: str,
    description: str,
    schema_id: str,
    schema_type: Optional[str] = "object",
) -> Dict[str, Any]:
    """Scaffold a standard JSON Schema Draft 2020-12 envelope dictionary.

    Includes _name and canonical _path properties required for automated
    GSI script and schema intake.

    Args:
        title: Descriptive human-readable schema title.
        version: Semantic schema specification version string.
        description: Functional summary of the schema's purpose.
        schema_id: Target canonical schema filename or subpath.
        schema_type: Primary schema validation type, defaulting to 'object'.

    Returns:
        Dictionary initialized with standard Draft 2020-12 and GSI metadata fields.
    """
    normalized_subpath = normalize_schema_subpath(schema_id)
    canonical_filename = PurePosixPath(normalized_subpath).name
    canonical_repo_path = f"schemas/{normalized_subpath}"

    resolved_id = (
        schema_id
        if str(schema_id).startswith("http://") or str(schema_id).startswith("https://")
        else resolve_schema_id(schema_id)
    )

    envelope: Dict[str, Any] = {
        "_name": canonical_filename,
        "_path": canonical_repo_path,
        "$schema": SCHEMA_DRAFT_2020_12,
        "$id": resolved_id,
        "title": title.strip(),
        "version": version.strip(),
        "description": description.strip(),
    }
    if schema_type:
        envelope["type"] = schema_type

    return envelope


def format_schema_json(payload: Dict[str, Any]) -> str:
    """Serialize dictionary payload to deterministic JSON format.

    Enforces 2-space indentation, preserved dictionary ordering, and a trailing
    newline per GDA repository formatting invariants.

    Args:
        payload: In-memory dictionary representing schema or data payload.

    Returns:
        Deterministic formatted JSON string.
    """
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"