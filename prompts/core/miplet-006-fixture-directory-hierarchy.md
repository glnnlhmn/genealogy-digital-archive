<!--
Name: miplet-006-fixture-directory-hierarchy.md
Path: prompts/core/miplet-006-fixture-directory-hierarchy.md
Target Baseline: v1.0.8
-->
# MIPLET-006: Test Fixture Directory Hierarchy Standard

### Scope
Formalizes the directory taxonomy for test fixtures in Section 2 (`tests/` architecture) and Section 3 (`Mandatory Test File Metadata Headers & Atomization`) of `prompts/core/MIP-Core.md`. Standardizes all static synthetic baselines and mutated failure payloads under `tests/fixtures/[Subject]/[golden|failure]/`.

### Patch Instructions

1. **Section 2 (`Directory Structure & File Routing`), under `Test Suite & Verification Harness (tests/)`:**
   Replace the `tests/fixtures/` bullet with:
   * `tests/fixtures/`: Central repository of static JSON payloads organized strictly by domain subject and variant:
     * `tests/fixtures/[Subject]/golden/`: Schema-compliant, referentially intact synthetic baselines (e.g., `tests/fixtures/people/golden/golden_people.json`, `tests/fixtures/facts/golden/golden_facts.json`).
     * `tests/fixtures/[Subject]/failure/`: Surgically mutated payloads for error boundary and validation testing (e.g., `tests/fixtures/facts/failure/corrupt_facts_bad_json.json`).
     * Direct placement of fixture files in the root of `tests/fixtures/` or unsegregated subject folders is prohibited.

2. **Section 3 (`Operational Protocols & Scripting Safeguards`), under `Mandatory Test File Metadata Headers & Atomization`:**
   Add the following fixture path rule:
   * **Explicit Fixture Paths:** Test suites loading fixtures must reference explicit canonical paths (`tests/fixtures/[Subject]/golden/[filename].json` or `tests/fixtures/[Subject]/failure/[filename].json`). Speculative candidate search arrays or fallback paths in test harnesses are prohibited.
