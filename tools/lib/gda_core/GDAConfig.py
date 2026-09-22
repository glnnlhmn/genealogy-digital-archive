# Name: GDAConfig.py
# Path: tools/lib/gda_core/GDAConfig.py

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any

DEFAULT_ROOT_ANCHOR = Path("G:/My Drive/genealogy-digital-archive")


@dataclass(frozen=True)
class GDAConfig:
    """
    Centralized Archive Configuration and Path Resolution.
    Provides immutable pathlib.Path attributes across the entire digital archive topology.
    """
    root: Path
    manifest: Dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------
    # Core Production Data Paths
    # ---------------------------------------------------------
    @property
    def data(self) -> Path:
        """Root repository for verified production data, entities, registries, and assets."""
        return self.root / "data"

    @property
    def archival_records(self) -> Path:
        """Repository for primary digital record extractions, transcripts, and document metadata."""
        return self.data / "archival_records"

    @property
    def entities(self) -> Path:
        """Canonical master entity registries (people, facts, and staged assertions)."""
        return self.data / "entities"

    @property
    def quarantine(self) -> Path:
        """Staging buffer for non-conforming, unverified, or anomalous entity records."""
        return self.entities / "quarantine"

    @property
    def facts(self) -> Path:
        """The canonical fact assertions registry (facts.json)."""
        return self.entities / "facts.json"

    @property
    def people(self) -> Path:
        """The canonical person entity registry (people.json)."""
        return self.entities / "people.json"

    @property
    def locations(self) -> Path:
        """The canonical authority registry for geographic place names and hierarchies."""
        return self.entities / "locations.json"

    @property
    def indexes(self) -> Path:
        """Structured lookup tables, cross-reference registries, and master index files."""
        return self.data / "indexes"

    @property
    def media(self) -> Path:
        """Production media repository for cataloged images, scans, and verified digital assets."""
        return self.data / "media"

    @property
    def profiles(self) -> Path:
        """Directory housing active operator profiles and context configurations."""
        return self.data / "profiles"

    @property
    def stories(self) -> Path:
        """Compiled narratives, biographical sketches, and historical summaries."""
        return self.data / "stories"

    @property
    def transcript(self) -> Path:
        """Full-text document transcriptions, interviews, and oral history records."""
        return self.data / "transcript"

    # ---------------------------------------------------------
    # Staging & Ephemeral Workspaces
    # ---------------------------------------------------------
    @property
    def staging(self) -> Path:
        """Root intake staging area for raw, incoming, or uncataloged digital assets."""
        return self.root / "import"

    @property
    def hold(self) -> Path:
        """Staging buffer for problematic, incomplete, or unverified intake assets."""
        return self.staging / "hold"

    @property
    def temp(self) -> Path:
        """Ephemeral workspace (gtemp/) for scratchpads, one-off scripts, and ad-hoc runs."""
        return self.root / "gtemp"

    # ---------------------------------------------------------
    # System Runtime: Backups, Logs, Reports
    # ---------------------------------------------------------
    @property
    def backups(self) -> Path:
        """Repository for Safe Backup Protocol snapshots ([filename].[timestamp].bk)."""
        return self.root / "backups"

    @property
    def logs(self) -> Path:
        """Execution logs repository for permanent operational and maintenance tools."""
        return self.root / "logs"

    @property
    def reports(self) -> Path:
        """Output directory for audit findings, candidate merges, and validation summaries."""
        return self.root / "reports"

    # ---------------------------------------------------------
    # Schemas & Controlled Vocabularies
    # ---------------------------------------------------------
    @property
    def schemas(self) -> Path:
        """Root directory for JSON schema validation contracts and naming standards."""
        return self.root / "schemas"

    @property
    def schema_archive(self) -> Path:
        """Deprecated schema revisions and historical metadata standards."""
        return self.schemas / "archive"

    @property
    def schema_naming(self) -> Path:
        """Standardized file naming schemas and identifier formatting token specifications."""
        return self.schemas / "naming"

    @property
    def schema_sources(self) -> Path:
        """Specifications defining source citation templates and evidence containers."""
        return self.schemas / "sources"

    @property
    def schema_defs(self) -> Path:
        """Shared foundational types, reusable definitions, and enum constraints."""
        return self.schemas / "defs"

    @property
    def schema_indexes(self) -> Path:
        """Validation contracts governing structured indexes and lookup tables."""
        return self.schemas / "indexes"

    @property
    def schema_entities(self) -> Path:
        """Validation contracts for primary entities (person.schema.json, fact.schema.json)."""
        return self.schemas / "entities"

    @property
    def enums(self) -> Path:
        """The centralized single source of truth for controlled vocabularies (_enums.schema.json)."""
        return self.schema_defs / "_enums.schema.json"

    # ---------------------------------------------------------
    # Tooling Suite
    # ---------------------------------------------------------
    @property
    def tools(self) -> Path:
        """Root workspace for permanent maintenance, inspection, and remediation automation."""
        return self.root / "tools"

    @property
    def ops(self) -> Path:
        """Permanent operational CLI tools with archive read/write capabilities."""
        return self.tools / "ops"

    @property
    def lib(self) -> Path:
        """Shared utility modules, schema validators, and common helper packages."""
        return self.tools / "lib"

    @property
    def core(self) -> Path:
        """Core foundation library package (gda_core) housing base framework protocols."""
        return self.lib / "gda_core"

    # ---------------------------------------------------------
    # Prompts & System Documentation
    # ---------------------------------------------------------
    @property
    def prompts(self) -> Path:
        """Directory housing AI operating instructions, system personas, and topic protocols."""
        return self.root / "prompts"

    @property
    def docs(self) -> Path:
        """Permanent technical documentation, tool runbooks, and architectural specs."""
        return self.root / "docs"

    # ---------------------------------------------------------
    # System Metadata & User Context
    # ---------------------------------------------------------
    @property
    def profile(self) -> Path:
        """Operator preference profile and biometrics dossier (glenn_profile.json)."""
        return self.profiles / "glenn_profile.json"

    @property
    def config_manifest(self) -> Path:
        """Global system manifest tracking tracked asset versions and SHA256 hashes."""
        return self.root / "gda_config.json"

    @property
    def version(self) -> str:
        """Current system configuration version resolved from gda_config.json."""
        return self.manifest.get("ConfigVersion", "1.0.0")

    # ---------------------------------------------------------
    # Factory & Auto-Detection
    # ---------------------------------------------------------
    @classmethod
    def load(cls, custom_root: Path | str | None = None) -> "GDAConfig":
        """
        Resolves the root anchor in order of precedence:
        1. Explicit path passed as argument.
        2. GDA_ROOT environment variable.
        3. Standard Google Drive mount (G:/My Drive/genealogy-digital-archive).
        4. Local workspace root fallback.
        """
        if custom_root:
            root_path = Path(custom_root).resolve()
        elif os.getenv("GDA_ROOT") and Path(os.getenv("GDA_ROOT")).exists():
            root_path = Path(os.getenv("GDA_ROOT")).resolve()
        elif DEFAULT_ROOT_ANCHOR.exists():
            root_path = DEFAULT_ROOT_ANCHOR
        elif Path("data/entities").exists() or Path("data").exists():
            root_path = Path(".").resolve()
        else:
            root_path = DEFAULT_ROOT_ANCHOR

        manifest_data = {}
        manifest_file = root_path / "gda_config.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception:
                pass

        return cls(root=root_path, manifest=manifest_data)


# Pre-instantiated singleton ready for global import
CONFIG = GDAConfig.load()