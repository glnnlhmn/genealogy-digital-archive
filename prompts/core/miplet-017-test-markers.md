# Miplet 017: Pytest Marker Taxonomy & Execution Protocol
<!-- Target: MIP-Core.md Section 2 (Test Suite & Verification Harness) -->

### Pytest Marker Taxonomy
All test suites across `tests/` must classify test functions using the standard repository markers:
* `smoke`: Fast sanity checks executed prior to commit (< 5s, in-memory or shallow assertion validation).
* `regression`: Boundary and defect tests verifying specific defensive rules, tiebreakers, and offloading paths.
* `burnin`: Multi-item stress, deep graph traversal, and batch load tests.
* `integration`: Multi-file pipeline mutations, tool runs, safe backup creations, and filesystem commits.
* `unit`: Isolated standalone unit tests with zero disk I/O.
* `integrity`: Whole-archive schema, directory topology, enum constraint, and drift validation.
* `slow`: Tests with execution duration exceeding 2s.

### Execution Policy
* Pre-commit verification: `pytest -m smoke -v`
* Fast regression pass: `pytest -m "not slow and not burnin" -v`
* Full repository audit: `pytest -v`
