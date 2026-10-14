# Name: conftest.py
# Path: tools/lib/gdadomain/tests/conftest.py
# Version: 1.0.0+build.r5

"""Shared test fixtures, synthetic stubs, and sandbox providers for gdadomain.

Operational Role:
    Exposes hermetic golden fixtures, specialized failure payloads, and mock provider
    stubs across domain entity test suites (locations, sites, people, facts) adhering
    strictly to topic_test_harness.md and topic_library_architecture.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set
import pytest

FIXTURES_ROOT = (
    Path(__file__).resolve().parents[4]
    / "tests/fixtures"
)

# Locations Fixture Paths
LOCATIONS_GOLDEN_PATH = FIXTURES_ROOT / "locations/golden/golden_locations.json"
LOCATIONS_FAILURE_DIR = FIXTURES_ROOT / "locations/failure"

# Sites Fixture Paths
SITES_GOLDEN_PATH = FIXTURES_ROOT / "sites/golden/golden_sites.json"
SITES_FAILURE_DIR = FIXTURES_ROOT / "sites/failure"

# People Fixture Paths
PEOPLE_GOLDEN_PATH = FIXTURES_ROOT / "people/golden/golden_people.json"
PEOPLE_FAILURE_DIR = FIXTURES_ROOT / "people/failure"
PEOPLE_NONCONFORMING_IDS_PATH = PEOPLE_FAILURE_DIR / "corrupt_people_nonconforming_ids.json"

# Facts Fixture Paths
FACTS_GOLDEN_DIR = FIXTURES_ROOT / "facts/golden"
FACTS_FAILURE_DIR = FIXTURES_ROOT / "facts/failure"
FACTS_GOLDEN_PATH = FACTS_GOLDEN_DIR / "golden_facts.json"
FACTS_RAW_LIST_PATH = FACTS_GOLDEN_DIR / "raw_list_facts.json"
FACTS_SCALAR_PATH = FACTS_FAILURE_DIR / "corrupt_facts_scalar.json"


# ==============================================================================
# MOCK PROVIDERS
# ==============================================================================


class MockSitesProvider:
    """Mock sites provider recording repoint_locations cascade invocations."""

    def __init__(self) -> None:
        self.repointed_calls: List[tuple[str, List[str]]] = []

    def repoint_locations(self, new_loc_id: str, old_loc_ids: List[str]) -> int:
        """Record primary target and secondary list, returning simulated repoint count."""
        self.repointed_calls.append((new_loc_id, old_loc_ids))
        return len(old_loc_ids) * 2


class MockLocationsProvider:
    """Hermetic mock satisfying the locations_provider exists() protocol."""

    def __init__(self, known_ids: Optional[Set[str]] = None) -> None:
        self.known_ids = known_ids or {
            "LOC-00042",
            "LOC-00101",
            "LOC-00205",
            "LOC-00312",
            "LOC-00450",
            "LOC-00501",
            "LOC-00615",
            "LOC-00720",
            "LOC-00810",
            "LOC-00925",
            "LOC-01033",
            "LOC-01140",
            "LOC-01255",
        }

    def exists(self, location_id: str) -> bool:
        """Return True if location_id is recognized in known mock registry."""
        return location_id in self.known_ids


# ==============================================================================
# LOCATIONS FIXTURES
# ==============================================================================


@pytest.fixture
def mock_sites() -> MockSitesProvider:
    """Provide a hermetic mock sites provider stub."""
    return MockSitesProvider()


@pytest.fixture
def golden_locations_file() -> Path:
    """Path to the golden locations fixture baseline."""
    return LOCATIONS_GOLDEN_PATH


@pytest.fixture
def golden_fixture_file(tmp_path: Path) -> Path:
    """Provide an isolated, writable copy of the canonical golden locations registry."""
    dest = tmp_path / "locations.json"
    dest.write_text(LOCATIONS_GOLDEN_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_locations_syntax() -> Path:
    """Path to corrupt_locations_syntax.json fixture."""
    return LOCATIONS_FAILURE_DIR / "corrupt_locations_syntax.json"


@pytest.fixture
def failure_fixture_syntax(tmp_path: Path) -> Path:
    """Provide an isolated copy of corrupt_locations_syntax.json."""
    src = LOCATIONS_FAILURE_DIR / "corrupt_locations_syntax.json"
    dest = tmp_path / "corrupt_syntax.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_locations_missing_id() -> Path:
    """Path to corrupt_locations_missing_id.json fixture."""
    return LOCATIONS_FAILURE_DIR / "corrupt_locations_missing_id.json"


@pytest.fixture
def failure_fixture_missing_id(tmp_path: Path) -> Path:
    """Provide an isolated copy of corrupt_locations_missing_id.json."""
    src = LOCATIONS_FAILURE_DIR / "corrupt_locations_missing_id.json"
    dest = tmp_path / "corrupt_missing_id.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_fixture_circular_graveyard(tmp_path: Path) -> Path:
    """Provide an isolated copy of corrupt_locations_circular_graveyard.json."""
    src = LOCATIONS_FAILURE_DIR / "corrupt_locations_circular_graveyard.json"
    dest = tmp_path / "corrupt_circular.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_fixture_schema_violations(tmp_path: Path) -> Path:
    """Provide an isolated copy of corrupt_locations_schema_violations.json."""
    src = LOCATIONS_FAILURE_DIR / "corrupt_locations_schema_violations.json"
    dest = tmp_path / "corrupt_violations.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


# ==============================================================================
# SITES FIXTURES
# ==============================================================================


@pytest.fixture
def mock_loc() -> MockLocationsProvider:
    """Provide a hermetic mock locations provider stub."""
    return MockLocationsProvider()


@pytest.fixture
def golden_sites_file(tmp_path: Path) -> Path:
    """Provide an isolated, writable copy of the canonical golden sites registry."""
    dest = tmp_path / "sites.json"
    dest.write_text(SITES_GOLDEN_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_sites_syntax(tmp_path: Path) -> Path:
    """Provide an isolated copy of corrupt_sites_syntax.json."""
    src = SITES_FAILURE_DIR / "corrupt_sites_syntax.json"
    dest = tmp_path / "corrupt_sites_syntax.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_sites_missing_id(tmp_path: Path) -> Path:
    """Provide an isolated copy of corrupt_sites_missing_id.json."""
    src = SITES_FAILURE_DIR / "corrupt_sites_missing_id.json"
    dest = tmp_path / "corrupt_sites_missing_id.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_sites_circular_graveyard(tmp_path: Path) -> Path:
    """Provide an isolated copy of corrupt_sites_circular_graveyard.json."""
    src = SITES_FAILURE_DIR / "corrupt_sites_circular_graveyard.json"
    dest = tmp_path / "corrupt_sites_circular.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_sites_transitive_graveyard(tmp_path: Path) -> Path:
    """Provide an isolated copy of corrupt_sites_transitive_graveyard.json."""
    src = SITES_FAILURE_DIR / "corrupt_sites_transitive_graveyard.json"
    dest = tmp_path / "corrupt_sites_transitive.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


# ==============================================================================
# PEOPLE FIXTURES (Golden & Failure Baselines)
# ==============================================================================

@pytest.fixture
def failure_people_nonconforming_ids(tmp_path: Path) -> Path:
    """Provide an isolated, writable copy of corrupt_people_nonconforming_ids.json."""
    dest = tmp_path / "corrupt_nonconforming_ids.json"
    dest.write_text(PEOPLE_NONCONFORMING_IDS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return dest

@pytest.fixture
def golden_people_file(tmp_path: Path) -> Path:
    """Provide an isolated, writable copy of the canonical golden people registry."""
    dest = tmp_path / "people.json"
    if PEOPLE_GOLDEN_PATH.exists():
        dest.write_text(PEOPLE_GOLDEN_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        dest.write_text('{"schema_version":"1.0.0","people":[]}', encoding="utf-8")
    return dest


@pytest.fixture
def failure_people_syntax(tmp_path: Path) -> Path:
    """Provide an isolated copy of corrupt_people_syntax.json."""
    src = PEOPLE_FAILURE_DIR / "corrupt_people_syntax.json"
    dest = tmp_path / "corrupt_people_syntax.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_people_missing_id(tmp_path: Path) -> Path:
    """Provide an isolated copy of corrupt_people_missing_id.json."""
    src = PEOPLE_FAILURE_DIR / "corrupt_people_missing_id.json"
    dest = tmp_path / "corrupt_people_missing_id.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_vital_sync_death() -> Path:
    """Path to failed_vital_sync_death.json fixture."""
    return PEOPLE_FAILURE_DIR / "failed_vital_sync_death.json"


@pytest.fixture
def failure_biological_chronology() -> Path:
    """Path to failed_biological_chronology.json fixture."""
    return PEOPLE_FAILURE_DIR / "failed_biological_chronology.json"


@pytest.fixture
def failure_dedup_and_drift() -> Path:
    """Path to failed_dedup_and_drift.json fixture."""
    return PEOPLE_FAILURE_DIR / "failed_dedup_and_drift.json"


@pytest.fixture
def failure_envelope_and_schema() -> Path:
    """Path to failed_envelope_and_schema.json fixture."""
    return PEOPLE_FAILURE_DIR / "failed_envelope_and_schema.json"


@pytest.fixture
def failure_kinship_and_unions() -> Path:
    """Path to failed_kinship_and_unions.json fixture."""
    return PEOPLE_FAILURE_DIR / "failed_kinship_and_unions.json"


@pytest.fixture
def failure_kinship_unknown_role() -> Path:
    """Path to failed_kinship_unknown_role.json fixture."""
    return PEOPLE_FAILURE_DIR / "failed_kinship_unknown_role.json"


@pytest.fixture
def failure_locations_and_redirects() -> Path:
    """Path to failed_locations_and_redirects.json fixture."""
    return PEOPLE_FAILURE_DIR / "failed_locations_and_redirects.json"


@pytest.fixture
def failure_topology_and_orphans() -> Path:
    """Path to failed_topology_and_orphans.json fixture."""
    return PEOPLE_FAILURE_DIR / "failed_topology_and_orphans.json"


# ==============================================================================
# FACTS FIXTURES (Golden & Failure Baselines)
# ==============================================================================


@pytest.fixture
def golden_facts_file(tmp_path: Path) -> Path:
    """Provide an isolated, writable copy of the canonical golden facts registry."""
    dest = tmp_path / "golden_facts.json"
    if FACTS_GOLDEN_PATH.exists():
        dest.write_text(FACTS_GOLDEN_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        dest.write_text('{"schema_version":"1.2.0","facts":[]}', encoding="utf-8")
    return dest


@pytest.fixture
def raw_list_facts_file(tmp_path: Path) -> Path:
    """Provide an isolated, writable copy of the raw list facts fixture."""
    dest = tmp_path / "raw_list_facts.json"
    dest.write_text(FACTS_RAW_LIST_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_facts_scalar(tmp_path: Path) -> Path:
    """Provide an isolated, writable copy of the corrupt scalar facts fixture."""
    dest = tmp_path / "corrupt_facts_scalar.json"
    dest.write_text(FACTS_SCALAR_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


@pytest.fixture
def failure_facts_syntax() -> Path:
    """Path to corrupt_facts_syntax.json fixture."""
    return FACTS_FAILURE_DIR / "corrupt_facts_syntax.json"


@pytest.fixture
def failure_facts_missing_id() -> Path:
    """Path to corrupt_facts_missing_id.json fixture."""
    return FACTS_FAILURE_DIR / "corrupt_facts_missing_id.json"