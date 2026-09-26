# Miplet 001: Testing Architecture & Isolated Verification Protocols
<!-- Target: MIP-Core Section 3 (Operational Protocols) & Section 4 (Data Integrity) -->

### 1. Differential Mutation Fixture Protocol
* **Derivation Requirement:** Failure fixtures in `tests/fixtures/failures/` must not be fabricated from scratch or built as disconnected, ad-hoc synthetic stubs.
* **Master Baseline Cloning:** All failure fixtures must originate as deep-copy clones of the verified golden baseline (`golden_people.json`).
* **Surgical Mutation Standard:** Target failure conditions (such as invalid biological chronology, reciprocal linkage omissions, or vital desynchronizations) must be introduced via discrete, surgical mutations applied to specific, connected records.
* **Collateral Integrity:** Fixtures must preserve overall graph reachability, envelope schemas, and node counts unless the specific test explicitly asserts envelope failure or topological disconnection (`TOPOLOGY_ISLAND`, `COUNT_MISMATCH`).

### 2. Standardized Pytest Marker Taxonomy
* **`@pytest.mark.unit`:** Applied to tests in `tests/unit/`. Exercises isolated functions, string parsers, empty input guards, and defensive branches in memory without cross-registry disk interactions.
* **`@pytest.mark.smoke` / `@pytest.mark.integrity`:** Applied to baseline health checks verifying that un-mutated golden datasets pass with zero critical errors.
* **`@pytest.mark.regression`:** Applied to integration tests that execute against mutated failure fixtures to assert that specific audit violation rules are caught.
* **`@pytest.mark.integration`:** Applied to CLI entry points and end-to-end execution routines.

### 3. Isolated Tool Coverage Protocol
* **Scoped Measurement:** When verifying individual operational tools under `tools/ops/`, coverage measurement must be explicitly scoped to that module (e.g., `--cov=tools.ops.gpa --cov-report=term-missing`).
* **Global Option Override:** To prevent repository-wide coverage thresholds (e.g., `--cov-fail-under=80` in `pytest.ini`) from failing focused tool runs due to unexercised peer modules, execute runs using the option override: `-o addopts=""`.
