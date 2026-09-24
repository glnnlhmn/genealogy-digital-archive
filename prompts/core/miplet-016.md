# Miplet 016: System Tooling (tools/sys) and Standardized Pytest Harness (pyproject.toml)
<!-- Target Baseline: MIP-Core v1.0.6 -> v1.0.7 -->

## Scope of Modification
- **Section 2 (Directory Structure & File Routing):**
  - Add `tools/sys/` definition under Permanent Automation & Tooling Suite (`tools/`).
  - Update `tests/` documentation to codify `tests/fixtures/` and root `tests/conftest.py`.
  - Deprecate `pytest.ini` and formalize `pyproject.toml` as the single source of truth for test configuration, marker enforcement, and coverage gates.

---

## Text Replacement Directives

### In Section 2, under "Permanent Automation & Tooling Suite (`tools/`):"
Append the following package definition alongside `tools/ops/` and `tools/lib/`:

* `tools/sys/`: Permanent system administration, workstation onboarding, and developer environment utilities with **System/Plumbing** scope:
  * Manages environment setup, dependency enforcement, and client-side Git hooks (`install_hooks.py`).
  * Explicitly separated from `tools/ops/` to maintain a strict boundary between host/git tooling and archive data manipulation.

---

### In Section 2, replace the "Test Suite & Verification Harness (`tests/`):" block with:

* **Test Suite & Verification Harness (`tests/`):**
  * Testing suite executed via `pytest` configured strictly via root `pyproject.toml` (PEP 518/621). Deprecates `pytest.ini`.
  * **Test Markers:** Tests are categorized with explicit markers (`smoke`, `unit`, `integration`, `integrity`, `slow`) with `--strict-markers` enforced.
  * **Centralized Fixtures & Hermetic Sandboxes:**
    * `tests/conftest.py`: Root pytest configuration providing shared, hermetic sandbox fixtures (`gda_sandbox`, `mock_config`, `test_logger`) with dynamic path monkeypatching. Individual test files must never define inline class-based config mocks or raw folder initializers.
    * `tests/fixtures/`: Central repository of static, schema-compliant JSON payloads (`sample_people.json`, `sample_facts.json`, `sample_aliases.json`) and corrupted edge-case datasets used across test tiers. Hardcoded, inline dictionary fixtures inside test files are prohibited.
  * **Test Tiers:**
    * `tests/unit/`: Focused tests validating standalone modules, parsers, formatters, and utilities with zero disk I/O (`test_gda_logger.py`, `test_gda_util.py`, `test_gda_util_name.py`).
    * `tests/integration/`: Multi-file operational pipeline tests validating tools that mutate state, manage safe backups, and run cross-registry intake (`test_gix.py`, `test_gam.py`, `test_gsi.py`, `test_gpi.py`, `test_gpa.py`, `test_gfi.py`, `test_gtr.py`, `test_facts_insp.py`, `test_facts_md.py`).
    * `tests/integrity/`: Archive topology, directory mapping, schema constraints, demographic plausibility, and manifest integrity smoke tests (`test_gda_config.py`, `test_schema_enums.py`, `test_demographic_integrity.py`).
