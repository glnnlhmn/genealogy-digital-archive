# Name: schema_manager.py
# Path: tools/lib/gdaschema/src/gdaschema/schema_manager.py
# Version: 1.0.0+build.r4

"""Genealogy Schema Manager compilation, validation, disk emission, and drift service."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import jsonschema
from gdacore.config import CONFIG, GDAConfig
from gdacore.introspectable import IntrospectableMixin
from gdacore.logger import GDALogger
from gdacore.util import GDAUtil

from gdaschema.defs.base import BaseCatalog
from gdaschema.defs.entities import EntityCatalog
from gdaschema.defs.indexes import IndexCatalog
from gdaschema.defs.xrefs import XRefCatalog
from gdaschema.schema_validator import GDASchemaValidator
from gdaschema.sources.enumeration import EnumerationSourcesCatalog
from gdaschema.sources.legal import LegalSourcesCatalog
from gdaschema.sources.registries import SourceRegistriesCatalog
from gdaschema.sources.specialized import SpecializedSourcesCatalog
from gdaschema.sources.vital import VitalSourcesCatalog

__version__ = "1.0.0+build.r4"


class SchemaItem:
    """Encapsulates an individual schema, its procedural builder, and disk state."""

    def __init__(
        self,
        key: str,
        target_path: Path,
        builder: Callable[[], Dict[str, Any]],
        schema_type: str = "def",
    ) -> None:
        """Initialize schema item metadata and builder callable.

        Args:
            key: Canonical identifier key for the schema.
            target_path: Physical destination path on disk.
            builder: Zero-argument callable producing Draft 2020-12 schema dict.
            schema_type: Category grouping (e.g., 'def', 'entity', 'index', 'xref', 'source').
        """
        self.key = key
        self.target_path = target_path
        self.builder = builder
        self.schema_type = schema_type

    def build(self) -> Dict[str, Any]:
        """Synthesize the in-memory canonical schema payload.

        Returns:
            Dictionary representing compiled JSON Schema.
        """
        return self.builder()

    def validate(self) -> Tuple[bool, Optional[str]]:
        """Validate compiled schema against JSON Schema Draft 2020-12 meta-schema.

        Returns:
            Tuple of (is_valid, error_message).
        """
        payload = self.build()
        try:
            validator_cls = jsonschema.validators.validator_for(payload)
            validator_cls.check_schema(payload)
            return True, None
        except jsonschema.exceptions.SchemaError as err:
            return False, err.message

    def inspect_drift(self) -> Tuple[bool, Optional[str]]:
        """Inspect whether disk content matches the in-memory procedural generator.

        Returns:
            Tuple of (has_drift, description_or_none).
        """
        if not self.target_path.exists():
            return True, f"Target schema file does not exist on disk: {self.target_path}"

        try:
            disk_content = GDAUtil.load_json(self.target_path)
        except Exception as exc:
            return True, f"Failed to parse disk schema from {self.target_path}: {exc}"

        compiled = self.build()
        if disk_content != compiled:
            return True, f"Schema drift detected for key: '{self.key}'"

        return False, None

    @property
    def has_drift(self) -> bool:
        """Return True if disk schema is missing or divergent from generator."""
        drifted, _ = self.inspect_drift()
        return drifted

    def write(self, dry_run: bool = False, create_backup: bool = True) -> Path:
        """Write compiled payload to disk using GDA Safe Backup protocols.

        Args:
            dry_run: If True, bypasses actual filesystem modification.
            create_backup: If True, creates pre-write timestamped backup.

        Returns:
            Target destination path on disk.
        """
        if not dry_run:
            payload = self.build()
            self.target_path.parent.mkdir(parents=True, exist_ok=True)
            GDAUtil.save_json(
                self.target_path,
                payload,
                indent=2,
                create_backup=create_backup,
            )
        return self.target_path


class GDASchemaManager(Mapping[str, SchemaItem], IntrospectableMixin):
    """Primary authority orchestrating repository schema compilation, validation, and emission."""

    def __init__(
        self,
        config: Optional[GDAConfig] = None,
        schemas_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize registry directories and register catalog builders.

        Args:
            config: Runtime GDAConfig instance or default CONFIG.
            schemas_dir: Root destination folder for schemas (defaults to GDAConfig.schemas_dir).
            logger: Custom logging adapter or default GDA logger.
        """
        self._config = config or CONFIG
        self._logger = logger or GDALogger.get_logger("gda_schema_manager")

        if schemas_dir:
            self._schemas_dir = Path(schemas_dir)
        elif hasattr(self._config, "schemas_dir") and self._config.schemas_dir:
            self._schemas_dir = Path(self._config.schemas_dir)
        elif hasattr(self._config, "root_dir") and self._config.root_dir:
            self._schemas_dir = Path(self._config.root_dir) / "schemas"
        else:
            self._schemas_dir = Path("schemas")

        self._schemas: Dict[str, SchemaItem] = {}
        self._key_aliases: Dict[str, str] = {}
        self._register_all_catalogs()

    def _register_all_catalogs(self) -> None:
        """Enumerate and register all catalog builders across repositories."""
        base_cat = BaseCatalog()
        for key in base_cat:
            filename = f"_{key}.schema.json" if not key.startswith("_") else f"{key}.schema.json"
            target_path = self._schemas_dir / "defs" / filename
            self.register(key, target_path, base_cat._BUILDERS[key], schema_type="def")
            self._key_aliases[filename] = key

        ent_cat = EntityCatalog()
        for key in ent_cat:
            filename = f"{key}.schema.json"
            target_path = self._schemas_dir / "entities" / filename
            self.register(key, target_path, ent_cat._BUILDERS[key], schema_type="entity")
            self._key_aliases[filename] = key

        idx_cat = IndexCatalog()
        for key in idx_cat:
            filename = f"{key}.schema.json"
            target_path = self._schemas_dir / "indexes" / filename
            self.register(key, target_path, idx_cat._BUILDERS[key], schema_type="index")
            self._key_aliases[filename] = key

        xref_cat = XRefCatalog()
        for key in xref_cat:
            filename = f"{key}.schema.json"
            target_path = self._schemas_dir / "xrefs" / filename
            self.register(key, target_path, xref_cat._BUILDERS[key], schema_type="xref")
            self._key_aliases[filename] = key

        source_catalogs = [
            VitalSourcesCatalog(),
            EnumerationSourcesCatalog(),
            LegalSourcesCatalog(),
            SpecializedSourcesCatalog(),
            SourceRegistriesCatalog(),
        ]
        for catalog in source_catalogs:
            for key in catalog:
                filename = f"{key}.schema.json"
                target_path = self._schemas_dir / "sources" / filename
                self.register(key, target_path, catalog._BUILDERS[key], schema_type="source")
                self._key_aliases[filename] = key

    def register(
        self,
        key: str,
        target_path: Path,
        builder: Callable[[], Dict[str, Any]],
        schema_type: str = "def",
    ) -> None:
        """Register a schema item into the active registry.

        Args:
            key: Logical key identifier.
            target_path: Destination path on disk.
            builder: Callable producing Draft 2020-12 schema dict.
            schema_type: Category identifier.
        """
        self._schemas[key] = SchemaItem(key, target_path, builder, schema_type=schema_type)

    def _resolve_key(self, key: str) -> str:
        raw = str(key or "").strip().lower()
        if raw in self._schemas:
            return raw
        if raw in self._key_aliases:
            return self._key_aliases[raw]
        raise KeyError(f"No schema registered matching key: '{key}'")

    def __getitem__(self, key: str) -> SchemaItem:
        return self._schemas[self._resolve_key(key)]

    def __len__(self) -> int:
        return len(self._schemas)

    def __iter__(self) -> Iterator[str]:
        return iter(self._schemas)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        raw = key.strip().lower()
        return raw in self._schemas or raw in self._key_aliases

    def get_schema(self, key: str) -> Dict[str, Any]:
        """Compile and return the in-memory schema dictionary by key.

        Args:
            key: Schema logical name or filename.

        Returns:
            Dictionary payload matching Draft 2020-12 schema contract.
        """
        return self[key].build()

    def inspect_drift(self) -> Dict[str, str]:
        """Scan all registered schemas against disk to detect missing files or drift.

        Returns:
            Dictionary mapping drifted schema keys to drift description messages.
        """
        drift_report: Dict[str, str] = {}
        for key, item in self._schemas.items():
            drifted, reason = item.inspect_drift()
            if drifted:
                drift_report[key] = reason or "Drift detected"
        return drift_report

    def write_all(self, dry_run: bool = False, create_backup: bool = True) -> List[Path]:
        """Emit all procedurally generated schemas to disk under the schemas directory.

        Args:
            dry_run: If True, skips actual filesystem write operations.
            create_backup: If True, writes Safe Backup copies before committing changes.

        Returns:
            List of target paths processed.
        """
        written: List[Path] = []
        for item in self._schemas.values():
            written.append(item.write(dry_run=dry_run, create_backup=create_backup))
        return written

    def create_validator(self) -> GDASchemaValidator:
        """Create a GDASchemaValidator pre-registered with all in-memory definitions.

        Returns:
            Configured GDASchemaValidator ready for instance evaluation.
        """
        validator = GDASchemaValidator()
        for item in self._schemas.values():
            schema = item.build()
            if "$id" in schema:
                validator.register_resource(schema["$id"], schema)
            validator.register_resource(item.key, schema)
            validator.register_resource(item.target_path.name, schema)
            validator.register_resource(f"defs/{item.target_path.name}", schema)
            validator.register_resource(f"../defs/{item.target_path.name}", schema)
            validator.register_resource(f"entities/{item.target_path.name}", schema)
            validator.register_resource(f"indexes/{item.target_path.name}", schema)
            validator.register_resource(f"xrefs/{item.target_path.name}", schema)
            validator.register_resource(f"sources/{item.target_path.name}", schema)
        return validator

    def validate_instance(self, instance: Any, schema_key: str) -> List[str]:
        """Validate an arbitrary JSON data payload against a registered schema.

        Args:
            instance: Python dictionary or data structure to validate.
            schema_key: Key of the schema contract to validate against.

        Returns:
            List of validation error strings (empty if valid).
        """
        validator = self.create_validator()
        schema = self.get_schema(schema_key)
        return validator.validate_instance(instance, schema)