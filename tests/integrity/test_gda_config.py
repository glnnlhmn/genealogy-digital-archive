# Name: test_gda_config.py
# Path: tests/integrity/test_gda_config.py
# Version: 1.0.1+build.20260927.01

"""Integrity test harness for GDAConfig environment and directory topology.

Operational Role:
    Verifies that the physical filesystem topology strictly conforms to
    the architectural boundaries defined in MIP-Core Section 2. Validates
    the availability and structural integrity of production data stores,
    schemas, system profiles, runtime paths, and manifest asset tracking.

Test Structure & Protocol:
    - Atomized tests: Each class method targets a single directory or file path.
    - Fully decorated: Classified under @pytest.mark.integrity with critical
      anchors tagged as @pytest.mark.smoke.
    - Dependencies: Requires local repository workspace initialized with
      valid gda_config.json manifest.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from tools.lib.gda_core.GDAConfig import CONFIG, GDAConfig

pytestmark = pytest.mark.integrity


@pytest.fixture(scope="session")
def cfg() -> GDAConfig:
    """Fixture providing the active archive configuration instance."""
    return CONFIG


class TestGDAConfigRoot:
    """Validates root anchor existence and directory properties."""

    @pytest.mark.smoke
    def test_root_exists(self, cfg: GDAConfig) -> None:
        assert cfg.root.exists(), f"Configured root anchor does not exist: {cfg.root}"

    @pytest.mark.smoke
    def test_root_is_directory(self, cfg: GDAConfig) -> None:
        assert cfg.root.is_dir(), f"Configured root anchor is not a directory: {cfg.root}"


class TestProductionDataPaths:
    """Validates production data directories and authoritative entity files."""

    @pytest.mark.smoke
    def test_data_directory(self, cfg: GDAConfig) -> None:
        assert cfg.data.is_dir(), f"Missing production data directory: {cfg.data}"

    def test_archival_records_directory(self, cfg: GDAConfig) -> None:
        assert cfg.archival_records.is_dir(), f"Missing archival records directory: {cfg.archival_records}"

    @pytest.mark.smoke
    def test_entities_directory(self, cfg: GDAConfig) -> None:
        assert cfg.entities.is_dir(), f"Missing entities directory: {cfg.entities}"

    @pytest.mark.smoke
    def test_canonical_facts_file(self, cfg: GDAConfig) -> None:
        assert cfg.facts.is_file(), f"Canonical facts file missing: {cfg.facts}"

    @pytest.mark.smoke
    def test_canonical_people_file(self, cfg: GDAConfig) -> None:
        assert cfg.people.is_file(), f"Canonical people file missing: {cfg.people}"

    def test_canonical_locations_file(self, cfg: GDAConfig) -> None:
        if cfg.locations.exists():
            assert cfg.locations.is_file(), f"Locations target exists but is not a file: {cfg.locations}"

    def test_indexes_directory(self, cfg: GDAConfig) -> None:
        assert cfg.indexes.is_dir(), f"Missing indexes directory: {cfg.indexes}"

    def test_media_directory(self, cfg: GDAConfig) -> None:
        assert cfg.media.is_dir(), f"Missing media directory: {cfg.media}"

    def test_profiles_directory(self, cfg: GDAConfig) -> None:
        assert cfg.profiles.is_dir(), f"Missing profiles directory: {cfg.profiles}"

    @pytest.mark.smoke
    def test_glenn_profile_file_exists(self, cfg: GDAConfig) -> None:
        assert cfg.profile.is_file(), f"Active operator profile missing: {cfg.profile}"

    def test_glenn_profile_payload_structure(self, cfg: GDAConfig) -> None:
        with open(cfg.profile, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "Glenn-User-Profile" in data, "Profile JSON missing 'Glenn-User-Profile' root key"

    def test_stories_directory(self, cfg: GDAConfig) -> None:
        assert cfg.stories.is_dir(), f"Missing stories directory: {cfg.stories}"

    def test_transcript_directory(self, cfg: GDAConfig) -> None:
        assert cfg.transcript.is_dir(), f"Missing transcript directory: {cfg.transcript}"


class TestStagingAndRuntimePaths:
    """Validates staging intake, quarantine, backup, and runtime output directories."""

    def test_staging_directory(self, cfg: GDAConfig) -> None:
        assert cfg.staging.is_dir(), f"Missing staging directory (import): {cfg.staging}"

    def test_staging_hold_directory(self, cfg: GDAConfig) -> None:
        assert cfg.hold.is_dir(), f"Missing staging hold directory: {cfg.hold}"

    def test_temporary_workspace_directory(self, cfg: GDAConfig) -> None:
        assert cfg.temp.is_dir(), f"Missing ephemeral temp directory (gtemp): {cfg.temp}"

    @pytest.mark.smoke
    def test_backups_directory(self, cfg: GDAConfig) -> None:
        assert cfg.backups.is_dir(), f"Missing backups directory: {cfg.backups}"

    @pytest.mark.smoke
    def test_logs_directory(self, cfg: GDAConfig) -> None:
        assert cfg.logs.is_dir(), f"Missing logs directory: {cfg.logs}"

    def test_reports_directory(self, cfg: GDAConfig) -> None:
        assert cfg.reports.is_dir(), f"Missing reports directory: {cfg.reports}"


class TestSchemaTopology:
    """Validates JSON schema directories and central vocabulary sources."""

    def test_schemas_root_directory(self, cfg: GDAConfig) -> None:
        assert cfg.schemas.is_dir(), f"Missing schemas root directory: {cfg.schemas}"

    def test_schema_defs_directory(self, cfg: GDAConfig) -> None:
        assert cfg.schema_defs.is_dir(), f"Missing schema defs directory: {cfg.schema_defs}"

    def test_schema_entities_directory(self, cfg: GDAConfig) -> None:
        assert cfg.schema_entities.is_dir(), f"Missing schema entities directory: {cfg.schema_entities}"

    def test_schema_sources_directory(self, cfg: GDAConfig) -> None:
        assert cfg.schema_sources.is_dir(), f"Missing schema sources directory: {cfg.schema_sources}"

    def test_schema_indexes_directory(self, cfg: GDAConfig) -> None:
        assert cfg.schema_indexes.is_dir(), f"Missing schema indexes directory: {cfg.schema_indexes}"

    def test_schema_naming_directory(self, cfg: GDAConfig) -> None:
        assert cfg.schema_naming.is_dir(), f"Missing schema naming directory: {cfg.schema_naming}"

    @pytest.mark.smoke
    def test_central_enums_schema_file_exists(self, cfg: GDAConfig) -> None:
        assert cfg.enums.is_file(), f"Centralized enums schema missing: {cfg.enums}"

    def test_central_enums_schema_valid_json(self, cfg: GDAConfig) -> None:
        with open(cfg.enums, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "$schema" in data or "definitions" in data or "$defs" in data, (
            "Enums file is not a valid JSON schema definition"
        )


class TestToolingAndDocsTopology:
    """Validates script packages, prompt architectures, and documentation roots."""

    def test_tools_directory(self, cfg: GDAConfig) -> None:
        assert cfg.tools.is_dir(), f"Missing tools directory: {cfg.tools}"

    def test_tools_ops_directory(self, cfg: GDAConfig) -> None:
        assert cfg.ops.is_dir(), f"Missing tools/ops directory: {cfg.ops}"

    def test_tools_lib_directory(self, cfg: GDAConfig) -> None:
        assert cfg.lib.is_dir(), f"Missing tools/lib directory: {cfg.lib}"

    def test_tools_core_directory(self, cfg: GDAConfig) -> None:
        assert cfg.core.is_dir(), f"Missing tools/lib/gda_core directory: {cfg.core}"

    def test_prompts_directory(self, cfg: GDAConfig) -> None:
        assert cfg.prompts.is_dir(), f"Missing prompts directory: {cfg.prompts}"

    def test_docs_directory(self, cfg: GDAConfig) -> None:
        assert cfg.docs.is_dir(), f"Missing docs directory: {cfg.docs}"


class TestConfigManifestSync:
    """Validates physical presence of assets tracked in gda_config.json."""

    @pytest.mark.smoke
    def test_manifest_file_exists(self, cfg: GDAConfig) -> None:
        assert cfg.config_manifest.is_file(), f"System manifest missing: {cfg.config_manifest}"

    def test_manifest_dictionary_loaded(self, cfg: GDAConfig) -> None:
        assert cfg.manifest, "GDAConfig manifest dictionary failed to load"

    def test_manifest_tracked_schemas_exist_on_disk(self, cfg: GDAConfig) -> None:
        tracked = cfg.manifest.get("TrackedAssets", {})
        for item in tracked.get("schemas", []):
            asset_path = cfg.root / item["path"]
            assert asset_path.exists(), f"Tracked schema in manifest not found on disk: {item['path']}"

    def test_manifest_tracked_prompts_exist_on_disk(self, cfg: GDAConfig) -> None:
        tracked = cfg.manifest.get("TrackedAssets", {})
        for item in tracked.get("prompts", []):
            asset_path = cfg.root / item["path"]
            assert asset_path.exists(), f"Tracked prompt in manifest not found on disk: {item['path']}"