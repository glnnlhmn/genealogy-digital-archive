# Name: __init__.py
# Path: tools/lib/gdacore/src/gdacore/__init__.py
# Version: 1.0.0+build.rc1

"""Expose foundational singletons, configuration resolvers, and core utilities.

GDA Core Framework Package provides foundational, domain-agnostic infrastructure
services across operational tools, developer scripts, and test harnesses:
runtime configuration (GDAConfig), bracketed logging (GDALogger), atomic Safe
Backup Protocol and JSON serialization (GDAUtil), canonical URN and identifier
parsing (GDAReferenceManager), controlled vocabulary management
(GDAVocabularyManager), and runtime reflection (IntrospectableMixin).
"""

from __future__ import annotations

__version__ = "1.0.0+build.rc1"

from gdacore.config import CONFIG, GDAConfig
from gdacore.introspectable import IntrospectableMixin
from gdacore.logger import GDALogFormatter, GDALogger, get_logger, setup_logger
from gdacore.reference_manager import GDAReferenceManager
from gdacore.util import GDAUtil
from gdacore.vocabulary_manager import GDASchemaEnums, GDAVocabularyManager

__all__ = [
    "CONFIG",
    "GDAConfig",
    "GDALogFormatter",
    "GDALogger",
    "GDAReferenceManager",
    "GDASchemaEnums",
    "GDAVocabularyManager",
    "GDAUtil",
    "IntrospectableMixin",
    "get_logger",
    "setup_logger",
]