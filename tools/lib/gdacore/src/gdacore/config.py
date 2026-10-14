# Name: config.py
# Path: tools/lib/gdacore/src/gdacore/config.py
# Version: 1.0.0+build.rc1

"""Provide centralized filesystem configuration and canonical path resolution.

Anchors immutable filesystem locations dynamically to the repository root or
active test sandboxes, exposing standard paths for operational data stores,
schema specifications, logging directories, safe backups, and ephemeral workspaces.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from gdacore.introspectable import IntrospectableMixin

__version__ = "1.0.0+build.rc1"


@dataclass(frozen=True)
class GDAConfig(IntrospectableMixin):
    """Immutable system configuration and canonical path registry.

    Anchors filesystem locations dynamically to the repository root or
    active test sandbox, exposing paths for data stores, schemas,
    logs, and ephemeral directories.
    """

    root: Path

    DEFAULT_PROD_ROOT: ClassVar[Path] = Path("G:/My Drive/genealogy-digital-archive")
    MARKER_FILES: ClassVar[Sequence[str]] = ("gda_config.json", ".git")

    @classmethod
    def load(cls, custom_root: Path | str | None = None) -> GDAConfig:
        """Resolve and initialize a validated GDAConfig instance.

        Discovers the archive root directory via an explicit override, the
        GDA_ROOT environment variable, canonical production mount points, or
        upward filesystem traversal for repository marker files.

        Args:
            custom_root: Optional explicit root directory path or string.

        Returns:
            An immutable GDAConfig instance anchored to the resolved root.

        Raises:
            FileNotFoundError: If the repository root marker cannot be located.
        """
        if custom_root is not None:
            resolved_root = Path(custom_root).resolve()
            if any((resolved_root / marker).exists() for marker in cls.MARKER_FILES):
                return cls(root=resolved_root)
            raise FileNotFoundError(f"Provided custom root is invalid: {custom_root}")

        env_root = os.getenv("GDA_ROOT")
        if env_root:
            env_path = Path(env_root).resolve()
            if env_path.exists():
                return cls(root=env_path)

        if cls.DEFAULT_PROD_ROOT.exists():
            return cls(root=cls.DEFAULT_PROD_ROOT.resolve())

        current = Path(__file__).resolve().parent
        candidates: list[Path] = [current, *current.parents, Path.cwd().resolve()]
        for candidate in candidates:
            if any((candidate / marker).exists() for marker in cls.MARKER_FILES):
                return cls(root=candidate)

        raise FileNotFoundError(
            "Could not resolve valid GDA repository root via GDA_ROOT, "
            "canonical mount point, or filesystem traversal."
        )

    # -------------------------------------------------------------------------
    # Core Workspace & Ephemeral Directories
    # -------------------------------------------------------------------------
    @property
    def temp(self) -> Path:
        """Return the transient scratch directory (gtemp/).

        Returns:
            Resolved Path to the temporary workspace directory.
        """
        return self.root / "gtemp"

    @property
    def logs(self) -> Path:
        """Return the execution log directory (logs/).

        Returns:
            Resolved Path to the permanent log storage directory.
        """
        return self.root / "logs"

    @property
    def backups(self) -> Path:
        """Return the safe backup snapshot directory (backups/).

        Returns:
            Resolved Path to the pre-execution backup directory.
        """
        return self.root / "backups"

    @property
    def reports(self) -> Path:
        """Return the reporting output directory (reports/).

        Returns:
            Resolved Path to the consolidation reports directory.
        """
        return self.root / "reports"

    # -------------------------------------------------------------------------
    # Intake & Staging Pipeline
    # -------------------------------------------------------------------------
    @property
    def intake(self) -> Path:
        """Return the root intake and staging pipeline directory (import/).

        Returns:
            Resolved Path to the inbound digital asset directory.
        """
        return self.root / "import"

    @property
    def intake_hold(self) -> Path:
        """Return the intake quarantined holding buffer (import/hold/).

        Returns:
            Resolved Path to the quarantined staging holding buffer.
        """
        return self.intake / "hold"

    # -------------------------------------------------------------------------
    # Production Data Stores
    # -------------------------------------------------------------------------
    @property
    def data(self) -> Path:
        """Return the root production data directory (data/).

        Returns:
            Resolved Path to the primary data repository.
        """
        return self.root / "data"

    @property
    def archival_records(self) -> Path:
        """Return the archival documents directory (data/archival_records/).

        Returns:
            Resolved Path to primary archival records and documents.
        """
        return self.data / "archival_records"

    @property
    def entities(self) -> Path:
        """Return the active entity registries directory (data/entities/).

        Returns:
            Resolved Path to the canonical entity store directory.
        """
        return self.data / "entities"

    @property
    def quarantine(self) -> Path:
        """Return the staging quarantine directory (data/entities/quarantine/).

        Returns:
            Resolved Path to the corrupted or invalid payload quarantine store.
        """
        return self.entities / "quarantine"

    @property
    def indexes(self) -> Path:
        """Return the master indices and cross-reference directory (data/indexes/).

        Returns:
            Resolved Path to the index registries directory.
        """
        return self.data / "indexes"

    @property
    def media(self) -> Path:
        """Return the production-ready media repository (data/media/).

        Returns:
            Resolved Path to the active archival media directory.
        """
        return self.data / "media"

    @property
    def profiles(self) -> Path:
        """Return the dossiers and system tracking ledgers directory (data/profiles/).

        Returns:
            Resolved Path to the operator and system profile directory.
        """
        return self.data / "profiles"

    @property
    def reference(self) -> Path:
        """Return the static reference lookup directory (data/reference/).

        Returns:
            Resolved Path to static tabular lookups and colloquial mappings.
        """
        return self.data / "reference"

    @property
    def stories(self) -> Path:
        """Return the narrative histories directory (data/stories/).

        Returns:
            Resolved Path to biographical profiles and historical narratives.
        """
        return self.data / "stories"

    @property
    def transcript(self) -> Path:
        """Return the full-text transcription directory (data/transcript/).

        Returns:
            Resolved Path to transcriptions and OCR extracts.
        """
        return self.data / "transcript"

    # -------------------------------------------------------------------------
    # Schemas & Specifications
    # -------------------------------------------------------------------------
    @property
    def schemas(self) -> Path:
        """Return the root schema definitions directory (schemas/).

        Returns:
            Resolved Path to the JSON schema specifications directory.
        """
        return self.root / "schemas"

    @property
    def schema_defs(self) -> Path:
        """Return the reusable primitives schema directory (schemas/defs/).

        Returns:
            Resolved Path to common enum and primitive schema definitions.
        """
        return self.schemas / "defs"

    @property
    def schema_entities(self) -> Path:
        """Return the core structural schemas directory (schemas/entities/).

        Returns:
            Resolved Path to entity schemas (person, fact, location, site).
        """
        return self.schemas / "entities"

    @property
    def schema_indexes(self) -> Path:
        """Return the index schemas directory (schemas/indexes/).

        Returns:
            Resolved Path to index validation schemas.
        """
        return self.schemas / "indexes"

    @property
    def token_registry(self) -> Path:
        """Return the controlled token registry specification file path.

        Returns:
            Resolved Path to schemas/naming/_token_registry.json.
        """
        return self.schemas / "naming" / "_token_registry.json"

    # -------------------------------------------------------------------------
    # Tooling Suite
    # -------------------------------------------------------------------------
    @property
    def tools(self) -> Path:
        """Return the permanent tooling root directory (tools/).

        Returns:
            Resolved Path to the tools repository.
        """
        return self.root / "tools"

    @property
    def tools_ops(self) -> Path:
        """Return the operational orchestrator tools directory (tools/ops/).

        Returns:
            Resolved Path to operational management scripts.
        """
        return self.tools / "ops"

    @property
    def tools_sys(self) -> Path:
        """Return the system administration utilities directory (tools/sys/).

        Returns:
            Resolved Path to system environment tools.
        """
        return self.tools / "sys"

    @property
    def tools_lib(self) -> Path:
        """Return the shared framework libraries directory (tools/lib/).

        Returns:
            Resolved Path to shared framework packages.
        """
        return self.tools / "lib"

    # -------------------------------------------------------------------------
    # Manifest Metadata
    # -------------------------------------------------------------------------
    @property
    def manifest_path(self) -> Path:
        """Return the repository manifest file path.

        Returns:
            Resolved Path to root gda_config.json.
        """
        return self.root / "gda_config.json"


try:
    CONFIG = GDAConfig.load()
except FileNotFoundError:
    # Graceful fallback for isolated test sandboxes or headless CI environments
    CONFIG = GDAConfig(root=Path.cwd().resolve())