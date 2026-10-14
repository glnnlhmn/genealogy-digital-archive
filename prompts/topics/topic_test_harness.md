<!--
Name: topic_test_harness.md
Path: prompts/topics/topic_test_harness.md
-->
# Topic Specification: Test Suite Architecture, Markers & Protocols
<!-- Version: 1.0.0 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Scope & Packaging Governance

This specification governs test architecture, execution isolation, marker semantics, fixture management, and quality gates across the digital archive.

* **Independent Packaging Configuration:** Every library under `tools/lib/` (e.g., `tools/lib/gdacore/`, `tools/lib/gdadomain/`) maintains its own dedicated `pyproject.toml` (PEP 518/621), alongside the workspace root `pyproject.toml`.
* **Test Suite Directory Placement:** Test suites are co-located with their architectural components:
  * Library Tests: Located directly inside the library package at `tools/lib/<gdalibraryname>/tests/`.
  * Operational Tool Tests: Located at `tests/ops/` (targeting `tools/ops/*.py`).
  * System Utility Tests: Located at `tests/sys/` (targeting `tools/sys/*.py`).

## 2. Test File Header & Structural Organization

### 2.1 File-Level Metadata Header

Every test file must open with standard metadata declarations within lines 1–3, followed by a module docstring defining its operational role and contract structure:

```python
# Name: test_[module].py
# Path: [relative/path/to/test_[module].py]
# Version: 1.0.0+build.r1

"""[One-line summary of test suite scope and target component].

Operational Role:
    [Concise description of the functional groups, tools, and contracts under test].

Test Structure & Protocol:
    - Atomized tests: [Description of 1:1 behavioral contract mapping].
    - Fully decorated: [Explicit enumeration of pytest markers used].
    - Dependencies: [Required fixtures, stubs, and sandboxes].
"""
```

### 2.2 Functional Group Section Dividers

Test files organize related test functions using standardized full-width ASCII comment banners rather than nested test classes:

```python
# ==============================================================================
# GROUP [N]: [Functional Category Title]
# Note: [Brief summary of invariants, behaviors, and boundaries tested]
# ==============================================================================
```

### 2.3 Test Function Conventions

* **Naming Syntax:** Test function names must follow the pattern:
  `test_<method_or_action>_<condition_or_scenario>_<expected_outcome>`
  (e.g., `test_add_auto_mint_initial_id`, `test_edit_missing_site_raises_key_error`).
* **Function Docstrings:** Every test function must contain a concise, single-line PEP 257 docstring starting with the imperative verb `"Verify..."` (e.g., `"""Verify len(sites) returns count of active sites, excluding tombstones."""`).
* **Clean Function Bodies:** Individual test functions must not contain metadata blocks, header boxes, or secondary author tags.

## 3. Behavioral Contract Atomization (1:1 Principle)

* **Single Behavioral Action:** Each test function must isolate and verify exactly one user action, state mutation, or failure boundary.
* **Cohesive Assertion Boundaries:** Testing the immediate, natural consequences of a single action within one function is standard practice (e.g., verifying that a deletion returns `True`, removes the entity from active queries, and places a tombstone in the graveyard partition).
* **No Unrelated Action Chaining:** Testing independent actions sequentially within a single test function (e.g., calling `.add()`, asserting it, then calling `.edit()`, then calling `.delete()`, then running `.search()`) is strictly prohibited. Disparate operations must be split into separate test functions.

## 4. Pytest Seven-Marker Taxonomy

Every test function must be decorated with at least one registered pytest marker (`--strict-markers` enforced):

* `@pytest.mark.smoke`: Fast sanity checks (< 5s, in-memory validation, critical smoke paths).
* `@pytest.mark.regression`: Boundary, defect, and tiebreaker tests verifying defensive edge cases and offloading logic.
* `@pytest.mark.burnin`: Multi-item stress tests, deep graph traversals, and large batch operations.
* `@pytest.mark.integration`: Multi-component tests involving filesystem commits, tool pipelines, or Safe Backups.
* `@pytest.mark.unit`: Isolated standalone component tests with zero production disk I/O.
* `@pytest.mark.integrity`: Whole-archive schema constraints, directory topology, enum invariants, and manifest drift checks.
* `@pytest.mark.slow`: Tests with execution duration exceeding 2.0s.

## 5. Fixture Hierarchy, Sandboxing & Privacy Rules

### 5.1 Static Fixture Hierarchy

All shared static baselines and defect payloads reside under `tests/fixtures/`, segregated strictly by domain subject and variant:

```text
tests/fixtures/
  └── [subject]/
        ├── golden/
        │     └── golden_[subject].json
        └── failure/
              └── corrupt_[subject]_[defect_type].json
```

* **Golden Baselines:** Referentially intact, schema-compliant synthetic baselines shared across suites.
* **Failure Payloads:** Derived copies of golden baselines surgically mutated to introduce a single defect condition (e.g., malformed syntax, cyclic relationship, invalid foreign key).
* **No Root Fixtures:** Placing loose fixture files in the root of `tests/fixtures/` or unsegregated subject folders is prohibited.
* **Explicit Paths:** Test suites must load fixtures using explicit paths resolved relative to the test file. Speculative search arrays or arbitrary fallback paths are prohibited.

### 5.2 Baseline Data vs. Inline Parameters

* **Full Entity Stores:** Inlining entire entity registries or multi-record database payloads directly into test code is strictly prohibited; these must load from `tests/fixtures/`.
* **Unit Mutation Inputs:** Lightweight parameter dictionaries passed into methods under test (e.g., `.edit()`, `.add()`, `.search()`, or specific malformed values) are permitted inline within test functions or parameterized fixtures.

### 5.3 Synthetic Privacy Policy

All fixture records must use strictly handcrafted, synthetic data. Real living persons, actual family records, or unredacted archival extracts must never appear in test fixtures, ensuring all test payloads remain safe for public Git repositories.

### 5.4 Hermetic Sandboxing & Windows Path Isolation

* **Zero Production Disk Writes:** Any test performing state mutations or file persistence must execute within an isolated temporary sandbox (`tmp_path`).
* **Windows DACL & File-Locking Safeguard:** Pytest execution must route temporary storage through `gtemp/pytest_tmp` to eliminate discretionary access control list (DACL) permission faults and file-locking collisions in Windows `AppData/Local/Temp`:
  ```powershell
  pytest <target> -v --basetemp=gtemp/pytest_tmp
  ```
* **Shared Environment Fixtures:** Centralized sandbox fixtures (`mock_config`, `test_logger`) reside in `tests/conftest.py` or package-level `conftest.py`.

## 6. Coverage Quality Gates & Introspection

* **Coverage Thresholds:** Production libraries under `tools/lib/` must satisfy >= 95% statement and branch test coverage. Operational domain managers require >= 85% minimum fail-under, targeting >= 95%.
* **Introspection Verification:** Any class inheriting `IntrospectableMixin` must have its `.help()` directory generation and member signature formatting explicitly verified under test.
* **Execution with Coverage:** Standard verification commands enforce branch coverage reporting:
  ```powershell
  pytest <target> -v --cov=<package> --cov-branch --cov-report=term-missing --basetemp=gtemp/pytest_tmp
  ```

## 7. Native Delivery & GSI Execution Intake

* **Direct Native File Emission:** Test suites must be delivered directly as pure `.py` source files (never wrapped inside Python string-generator or file-writer scripts).
* **GSI Intake Protocol:** Staged test files placed in workspace root must contain `# Name:` and `# Path:` within lines 1–15 so `tools/sys/gsi.py` can create pre-execution Safe Backups, relocate the file to its target path, and dispatch automated verification with coverage reporting.