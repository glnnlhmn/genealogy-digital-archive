# Name: __init__.py
# Path: tools/lib/gdaschema/src/gdaschema/__init__.py
# Version: 1.0.0+build.20261007.2

"""GDASchema library root package exposing schema management and verification engines."""

from __future__ import annotations

from gdaschema.schema_manager import GDASchemaManager

__version__ = "1.0.0+build.20261007.2"

from gdaschema.schema_manager import GDASchemaManager

__all__ = [
    "__version__",
    "GDASchemaManager",
]