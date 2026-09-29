<!--
Name: MIP-Topic-Test-Harness.md
Path: prompts/topics/MIP-Topic-Test-Harness.md
-->
# Topic Specification: Test Suite Architecture, Markers & Protocols
<!-- Version: 1.0.1 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Test Configuration & Governance
Testing is executed via `pytest` configured strictly through root `pyproject.toml` (PEP 518/621). Strict marker validation (`--strict-markers`) is enforced across all test discovery suites.

---

## 2. Pytest Seven-Marker Taxonomy
Every test function across `tests/` must be decorated with at least one marker from the seven registered markers:
* `smoke`: Fast sanity checks (< 5s, in-memory or shallow validation).
* `regression`: Boundary, defect, and tiebreaker tests verifying defensive rules and offloading paths.
* `burnin`: Multi-item stress, deep graph traversal, and batch load tests.
* `integration`: Multi-file pipeline mutations, tool runs, safe backups, and filesystem commits.
* `unit`: Isolated standalone unit tests with zero disk I/O.
* `integrity`: Whole-archive schema, directory topology, enum constraint, and drift validation.
* `slow`: Tests with execution duration exceeding 2s.

---

## 3. Mandatory Test File Metadata Header Box
Every test file under `tests/` must open with a standardized docstring block within the first 25 lines:

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
* **Single Failure Boundary:** Test functions must strictly isolate a single failure assertion or behavioral contract.
* **No Multi-Condition Bundling:** Combining disparate error checks, multiple validation rule codes, or multi-stage batch mutations into a single test function is prohibited.

---

## 5. Fixture Hierarchy & Directory Standards
All static mock payloads and test fixtures reside in `tests/fixtures/`, segregated strictly by domain subject and variant:

```text
tests/fixtures/
  └── [subject]/
        ├── golden/
        │     └── golden_[subject].json
        └── failure/
              └── corrupt_[subject]_[defect_type].json
```

* **Golden Baselines (`tests/fixtures/[subject]/golden/`):** Referentially intact, schema-compliant synthetic baselines (e.g., `tests/fixtures/people/golden/golden_people.json`, `tests/fixtures/facts/golden/golden_facts.json`)[cite: 3].
* **Failure Payloads (`tests/fixtures/[subject]/failure/`):** Surgically mutated payloads for error boundary and negative testing (e.g., `corrupt_facts_bad_json.json`, `corrupt_people_cycle.json`)[cite: 3].
* **Root Placement Prohibited:** Direct placement of fixture files in the root of `tests/fixtures/` or unsegregated subject folders is prohibited[cite: 3].
* **Explicit Fixture Paths:** Test suites loading fixtures must reference explicit canonical paths (`tests/fixtures/[subject]/golden/[filename].json` or `tests/fixtures/[subject]/failure/[filename].json`)[cite: 3]. Speculative candidate search arrays or fallback paths in test harnesses are prohibited[cite: 3].
* **Zero Inlining Rule:** Inlining dictionary payloads directly inside test functions or test files is prohibited. Common sandbox fixtures (`mock_config`, `test_logger`) are housed exclusively in `tests/conftest.py`.

---

## 6. Synthetic Mock Family Architecture & Mutation Rules
* **Handcrafted Synthetic Datasets:** To eliminate risks of living-person data leakage, partial boundary pruning, and referential drift, tests rely on handcrafted synthetic family clusters rather than live production data slices[cite: 15].
* **Generational Coverage:** Synthetic mock clusters emulate multi-generational families (e.g., spanning 1780–1950) with valid reciprocal kinship pointers, paired unions, and full vital fact lifecycles (birth, marriage, death, probate, census, military)[cite: 15].
* **Surgical Mutation Standard:** Failure fixtures must derive as copies of a verified golden baseline, introducing single target defect conditions (e.g., invalid biological chronology, corrupt foreign keys, or non-conforming URNs) while preserving envelope schema compliance unless testing raw parser crashes.