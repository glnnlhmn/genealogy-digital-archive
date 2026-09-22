# MIPLET 005: Structured Test Topology (tests/)
* **Target Version:** MIP-Core-v1.0.5
* **Target Section:** `## 2. Directory Structure & File Routing`

### Changes:
1. Define formal test harness topology anchored at root `tests/`:
   * **Test Suite & Verification Harness (`tests/`):**
     * Testing suite executed via `pytest` configured with `pytest.ini`.
     * Structure:
       * `tests/unit/`: Focused tests validating standalone modules, utilities, and formatters (`test_gtr.py`, `test_gda_logger.py`, `test_gda_util.py`).
       * `tests/integration/`: Pipeline tests verifying multi-module behaviors, data migrations, and tool workflows (`test_gpa.py`, `test_gpi.py`, `test_facts_insp.py`).
       * `tests/integrity/`: System topology, directory mapping, schema constraints, and manifest integrity smoke tests (`test_gda_config.py`, `test_schema_enums.py`).
