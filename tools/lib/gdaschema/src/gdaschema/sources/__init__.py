# Name: __init__.py
# Path: tools/lib/gdaschema/src/gdaschema/sources/__init__.py
# Version: 1.0.0+build.r5

"""Archival source schema definitions partitioned by documentary provenance domain."""

from __future__ import annotations

from gdaschema.sources.enumeration import EnumerationSourcesCatalog
from gdaschema.sources.legal import LegalSourcesCatalog
from gdaschema.sources.registries import SourceRegistriesCatalog
from gdaschema.sources.specialized import SpecializedSourcesCatalog
from gdaschema.sources.vital import VitalSourcesCatalog

__version__ = "1.0.0+build.r5"

__all__ = [
    "EnumerationSourcesCatalog",
    "LegalSourcesCatalog",
    "SourceRegistriesCatalog",
    "SpecializedSourcesCatalog",
    "VitalSourcesCatalog",
]