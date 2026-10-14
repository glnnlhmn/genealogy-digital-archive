# Name: __init__.py
# Path: tools/lib/gdadomain/src/gdadomain/__init__.py
# Version: 1.0.0+build.r1

"""Domain entity managers and business logic for the Genealogy Digital Archive.

Operational Role:
    Exposes high-level transaction managers governing canonical entity
    registries: facts, people, locations, and sites.
"""

from __future__ import annotations

from gdadomain.facts import GDAFacts
from gdadomain.locations import GDALocations
from gdadomain.people import GDAPeople
from gdadomain.sites import GDASites

__version__ = "1.0.0+build.r1"

__all__ = [
    "GDAFacts",
    "GDALocations",
    "GDAPeople",
    "GDASites",
    "__version__",
]