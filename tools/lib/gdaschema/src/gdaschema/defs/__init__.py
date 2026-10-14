# Name: __init__.py
# Path: tools/lib/gdaschema/src/gdaschema/defs/__init__.py
# Version: 1.0.0+build.r2

"""Authoritative JSON Schema definition generators partitioned by structural domain."""

from __future__ import annotations

from gdaschema.defs.base import BaseCatalog, BaseDefsCatalog
from gdaschema.defs.entities import EntityCatalog
from gdaschema.defs.indexes import IndexCatalog
from gdaschema.defs.xrefs import XRefCatalog

__version__ = "1.0.0+build.r2"

__all__ = [
    "BaseCatalog",
    "BaseDefsCatalog",
    "EntityCatalog",
    "IndexCatalog",
    "XRefCatalog",
]