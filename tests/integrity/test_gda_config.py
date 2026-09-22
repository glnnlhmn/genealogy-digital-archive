# Name: test_gda_config.py
# Path: tests/test_gda_config.py

import json
import pytest
from pathlib import Path
from tools.lib.gda_core.GDAConfig import CONFIG, GDAConfig


@pytest.fixture(scope="session")
def cfg() -> GDAConfig:
    """Fixture providing the active archive configuration instance."""
    return CONFIG


class TestGDAConfigRoot:
    """Validates the root anchor resolution."""

    def test_root_exists(self, cfg: GDAConfig):
        assert cfg.root.exists(), f"Configured root anchor does not exist: {cfg.root}"
        assert cfg.root.is_dir(), f"Configured root anchor is not a directory: {cfg.root}"


class TestProductionDataPaths:
    """Validates core production directories and registry files."""

    def test_data_directory(self, cfg: GDAConfig):
        assert cfg.data.is_dir(), f"Missing production data directory: {cfg.data}"

    def test_archival_records_directory(self, cfg: GDAConfig):
        assert cfg.archival_records.is_dir(), f"Missing archival records directory: {cfg.archival_records}"

    def test_entities_directory(self, cfg: GDAConfig):
        assert cfg.entities.is_dir(), f"Missing entities directory: {cfg.entities}"

    def test_canonical_entity_files(self, cfg: GDAConfig):
        assert cfg.facts.is_file(), f"Canonical facts file missing: {cfg.facts}"
        assert cfg.people.is_file(), f"Canonical people file missing: {cfg.people}"
        if cfg.locations.exists():
            assert cfg.locations.is_file(), f"Locations target exists but is not a file: {cfg.locations}"

    def test_indexes_directory(self, cfg: GDAConfig):
        assert cfg.indexes.is_dir(), f"Missing indexes directory: {cfg.indexes}"

    def test_media_directory(self, cfg: GDAConfig):
        assert cfg.media.is_dir(), f"Missing media directory: {cfg.media}"

    def test_profiles_directory(self, cfg: GDAConfig):
        assert cfg.profiles.is_dir(), f"Missing profiles directory: {cfg.profiles}"

    def test_glenn_profile_file(self, cfg: GDAConfig):
        assert cfg.profile.is_file(), f"Active operator profile missing: {cfg.profile}"
        with open(cfg.profile, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "Glenn-User-Profile" in data, "Profile JSON missing 'Glenn-User-Profile' root key"

    def test_stories_directory(self, cfg: GDAConfig):
        assert cfg.stories.is_dir(), f"Missing stories directory: {cfg.stories}"

    def test_transcript_directory(self, cfg: GDAConfig):
        assert cfg.transcript.is_dir(), f"Missing transcript directory: {cfg.transcript}"

class TestStagingAndRuntimePaths:
    """Validates intake, staging, backup, and logging directories."""

    def test_staging_directories(self, cfg: GDAConfig):
        assert cfg.staging.is_dir(), f"Missing staging directory (import): {cfg.staging}"
        assert cfg.hold.is_dir(), f"Missing staging hold directory: {cfg.hold}"
        assert cfg.temp.is_dir(), f"Missing ephemeral temp directory (gtemp): {cfg.temp}"

    def test_runtime_directories(self, cfg: GDAConfig):
        assert cfg.backups.is_dir(), f"Missing backups directory: {cfg.backups}"
        assert cfg.logs.is_dir(), f"Missing logs directory: {cfg.logs}"
        assert cfg.reports.is_dir(), f"Missing reports directory: {cfg.reports}"


class TestSchemaTopology:
    """Validates JSON schema directories and vocabulary single source of truth."""

    def test_schema_directories(self, cfg: GDAConfig):
        assert cfg.schemas.is_dir(), f"Missing schemas root directory: {cfg.schemas}"
        assert cfg.schema_defs.is_dir(), f"Missing schema defs directory: {cfg.schema_defs}"
        assert cfg.schema_entities.is_dir(), f"Missing schema entities directory: {cfg.schema_entities}"
        assert cfg.schema_sources.is_dir(), f"Missing schema sources directory: {cfg.schema_sources}"
        assert cfg.schema_indexes.is_dir(), f"Missing schema indexes directory: {cfg.schema_indexes}"
        assert cfg.schema_naming.is_dir(), f"Missing schema naming directory: {cfg.schema_naming}"

    def test_enums_schema_file(self, cfg: GDAConfig):
        assert cfg.enums.is_file(), f"Centralized enums schema missing: {cfg.enums}"
        with open(cfg.enums, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "$schema" in data or "definitions" in data or "$defs" in data, (
            "Enums file is not a valid JSON schema definition"
        )


class TestToolingAndDocsTopology:
    """Validates automation code, documentation, and prompt directories."""

    def test_tools_directories(self, cfg: GDAConfig):
        assert cfg.tools.is_dir(), f"Missing tools directory: {cfg.tools}"
        assert cfg.ops.is_dir(), f"Missing tools/ops directory: {cfg.ops}"
        assert cfg.lib.is_dir(), f"Missing tools/lib directory: {cfg.lib}"
        assert cfg.core.is_dir(), f"Missing tools/lib/gda_core directory: {cfg.core}"

    def test_prompts_and_docs_directories(self, cfg: GDAConfig):
        assert cfg.prompts.is_dir(), f"Missing prompts directory: {cfg.prompts}"
        assert cfg.docs.is_dir(), f"Missing docs directory: {cfg.docs}"


class TestConfigManifestSync:
    """Validates that assets tracked in gda_config.json exist on disk."""

    def test_manifest_file_exists(self, cfg: GDAConfig):
        assert cfg.config_manifest.is_file(), f"System manifest missing: {cfg.config_manifest}"

    def test_manifest_tracked_assets(self, cfg: GDAConfig):
        assert cfg.manifest, "GDAConfig manifest dictionary failed to load"
        tracked = cfg.manifest.get("TrackedAssets", {})

        # Verify all schemas tracked in the manifest exist
        for item in tracked.get("schemas", []):
            asset_path = cfg.root / item["path"]
            assert asset_path.exists(), f"Tracked schema in manifest not found on disk: {item['path']}"

        # Verify all prompt specifications tracked in the manifest exist
        for item in tracked.get("prompts", []):
            asset_path = cfg.root / item["path"]
            assert asset_path.exists(), f"Tracked prompt in manifest not found on disk: {item['path']}"