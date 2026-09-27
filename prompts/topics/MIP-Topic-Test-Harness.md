# Topic Specification: Test Suite Architecture, Markers & Protocols
<!-- Version: 1.0.0 -->
<!-- Location: prompts/topics/MIP-Topic-Test-Harness.md -->

## 1. Test Configuration & Governance
Testing is executed via `pytest` configured strictly via root `pyproject.toml` (PEP 518/621). References to `pytest.ini` are deprecated.

---

## 2. Pytest Seven-Marker Taxonomy
All tests across `tests/` must be decorated with explicit markers:
* `smoke`: Fast sanity checks executed prior to commit (< 5s, in-memory or shallow validation).
* `regression`: Boundary, defect, and tiebreaker tests verifying defensive rules and offloading paths.
* `burnin`: Multi-item stress, deep graph traversal, and batch load tests.
* `integration`: Multi-file pipeline mutations, tool runs, safe backups, and filesystem commits.
* `unit`: Isolated standalone unit tests with zero disk I/O.
* `integrity`: Whole-archive schema, directory topology, enum constraint, and drift validation.
* `slow`: Tests with execution duration exceeding 2s.

---

## 3. Mandatory Test File Metadata Header Box
Every test file under `tests/` must begin with a standardized docstring block within the first 25 lines:

```python
# Name: [test_file_name.py]
# Path: tests/[subpath]/[test_file_name.py]
# Version: [PEP 440 version string]

"""[One-line summary of test suite scope].

Operational Role:
    [Concise description of the tools, modules, and invariants under test].

Test Structure & Protocol:
    - Atomized tests: [Description of 1:1 assertion mapping].
    - Fully decorated: [Explicit enumeration of marks used].
    - Dependencies: [Required fixtures, external tools, or sandboxes].
"""
```

---

## 4. Strict Test Atomization (1:1 Assertion Principle)
* **No Multi-Condition Bundling:** Test functions must never combine disparate error checks, multiple rule codes, or multi-stage batch validations into a single test function.
* **Isolated Failure Reporting:** Each test must assert exactly one defect rule or behavioral contract to ensure discrete reporting during regression passes.

---

## 5. Differential Mutation Fixture Protocol
* **Derivation Requirement:** Failure fixtures in `tests/fixtures/` must originate as deep-copy clones of the verified golden baseline (`golden_people.json`).
* **Surgical Mutation Standard:** Target defect conditions (such as invalid biological chronology or desynchronized vitals) must be introduced via discrete mutations applied to specific records.
* **Collateral Integrity:** Fixtures must preserve overall graph reachability and envelope schemas unless the test explicitly targets schema corruption.
