# Name: schema_validator.py
# Path: tools/lib/gdaschema/src/gdaschema/schema_validator.py
# Version: 1.0.0+build.rc2

"""JSON Schema Draft 2020-12 validation engine with local resource registry.

Operational Role:
    Provides validation of in-memory dictionaries and on-disk files
    against JSON Schema specifications. Resolves local $ref schemas
    (e.g., schemas/defs/) using the referencing library without external HTTP calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from gdacore.config import CONFIG, GDAConfig
from gdacore.introspectable import IntrospectableMixin
from gdacore.logger import GDALogger
from gdacore.util import GDAUtil
from gdaschema.schema_util import CANONICAL_SCHEMA_BASE_URI, resolve_schema_id

__version__ = "1.0.0+build.rc2"


class GDASchemaValidator(IntrospectableMixin):
    """Validation engine enforcing JSON Schema Draft 2020-12 compliance."""

    def __init__(
        self,
        config: Optional[GDAConfig] = None,
        schemas_dir: Optional[Path] = None,
    ) -> None:
        """Initialize validator with local referencing registry.

        Args:
            config: Optional GDAConfig instance. Defaults to CONFIG.
            schemas_dir: Optional root directory containing schemas/. Defaults
                to config.schemas.
        """
        self._config = config or CONFIG
        self._schemas_dir = Path(schemas_dir) if schemas_dir is not None else self._config.schemas
        self._logger = GDALogger.get_logger("gda_schema_validator")
        self._registry = self._build_local_registry()

    def _build_local_registry(self) -> Registry:
        """Pre-populate referencing.Registry with all schemas found under schemas_dir.

        Returns:
            Populated Registry with canonical URIs and relative path references.
        """
        registry: Registry = Registry()
        if not self._schemas_dir.exists():
            return registry

        for schema_file in self._schemas_dir.rglob("*.json"):
            if not schema_file.is_file():
                continue
            try:
                content = json.loads(schema_file.read_text(encoding="utf-8"))
                if not isinstance(content, dict):
                    continue
                resource = Resource.from_contents(content, default_specification=DRAFT202012)

                # Register by canonical $id if present
                if "$id" in content and isinstance(content["$id"], str):
                    registry = registry.with_resource(content["$id"], resource)

                # Register by relative subpath (e.g., 'defs/_shared_defs.schema.json')
                rel_path = schema_file.relative_to(self._schemas_dir).as_posix()
                registry = registry.with_resource(rel_path, resource)
                registry = registry.with_resource(f"schemas/{rel_path}", resource)
                registry = registry.with_resource(schema_file.name, resource)

                # Register under canonical URI base
                canonical_uri = resolve_schema_id(rel_path)
                registry = registry.with_resource(canonical_uri, resource)
            except Exception as exc:
                self._logger.debug("Skipped indexing %s into schema registry: %s", schema_file.name, exc)

        return registry

    def register_resource(self, uri: str, schema_dict: Dict[str, Any]) -> None:
        """Register an in-memory schema dictionary directly into the resolver registry.

        Args:
            uri: Canonical URI or key identifier for the schema.
            schema_dict: Draft 2020-12 schema specification dictionary.
        """
        resource = Resource.from_contents(schema_dict, default_specification=DRAFT202012)
        self._registry = self._registry.with_resource(uri, resource)

    def validate_instance(
        self,
        instance: Any,
        schema: Dict[str, Any],
    ) -> List[str]:
        """Validate an in-memory instance against a schema specification.

        Args:
            instance: Data structure (typically a dictionary or list) to validate.
            schema: Draft 2020-12 JSON Schema specification dictionary.

        Returns:
            List of violation error descriptions. Empty list indicates valid instance.
        """
        validator = Draft202012Validator(schema, registry=self._registry)
        errors: List[str] = []
        for error in validator.iter_errors(instance):
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            errors.append(f"[{path}] {error.message}")
        return errors

    def is_valid(
        self,
        instance: Any,
        schema: Dict[str, Any],
    ) -> bool:
        """Check whether an instance satisfies a schema specification without details.

        Args:
            instance: Data structure to evaluate.
            schema: Draft 2020-12 JSON Schema specification dictionary.

        Returns:
            True if valid, False if violations exist.
        """
        validator = Draft202012Validator(schema, registry=self._registry)
        return validator.is_valid(instance)

    def validate_file(
        self,
        file_path: Path | str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Validate a JSON file on disk against a schema specification.

        If schema is omitted, attempts to locate the schema referenced in the
        payload's '$schema' property or file headers.

        Args:
            file_path: Filesystem path to the JSON file being evaluated.
            schema: Optional explicit schema dictionary to validate against.

        Returns:
            List of validation errors. Empty list indicates compliance.

        Raises:
            FileNotFoundError: If target file does not exist on disk.
            ValueError: If file is not valid JSON or schema cannot be determined.
        """
        target = Path(file_path)
        if not target.exists():
            raise FileNotFoundError(f"Target file for validation not found: {target}")

        try:
            data = GDAUtil.load_json(target)
        except Exception as exc:
            raise ValueError(f"Failed to parse JSON file {target}: {exc}") from exc

        if schema is not None:
            return self.validate_instance(data, schema)

        schema_ref = data.get("$schema") if isinstance(data, dict) else None
        if not schema_ref or not isinstance(schema_ref, str):
            raise ValueError(
                f"No schema provided and target file {target.name} does not declare a '$schema' string."
            )

        resolved_schema = self._resolve_schema_from_ref(schema_ref)
        if not resolved_schema:
            raise ValueError(f"Unable to resolve referenced schema: '{schema_ref}'")

        return self.validate_instance(data, resolved_schema)

    def _resolve_schema_from_ref(self, ref: str) -> Optional[Dict[str, Any]]:
        """Resolve a schema dictionary from a URI or relative path reference."""
        try:
            resolved = self._registry.resolver().lookup(ref)
            return resolved.contents  # type: ignore[no-any-return]
        except Exception:
            pass

        clean_ref = ref.replace("\\", "/")
        candidates: List[Path] = [
            self._schemas_dir / clean_ref,
            self._schemas_dir / clean_ref.replace("schemas/", ""),
            self._config.root / clean_ref,
        ]

        for cand in candidates:
            if cand.is_file():
                try:
                    return GDAUtil.load_json(cand)
                except Exception:
                    continue

        return None