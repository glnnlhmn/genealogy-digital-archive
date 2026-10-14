<!--
Name: topic_system_tools.md
Path: prompts/topics/topic_system_tools.md
-->
# Topic Specification: System Utility Architecture (`tools/sys/`)
<!-- Version: 1.0.0 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Architectural Scope & Operational Role
System utilities under `tools/sys/` govern developer workstation environment configuration, Git hook deployment, and automated deliverable intake. Unlike operational tools that mutate canonical genealogical domain data (`data/`), system utilities maintain local workstation environment consistency, enforce workflow automation, and ensure repository onboarding integrity.

---

## 2. Production System Utility Inventory

| Utility Name | Subpath | Category | Core Purpose | Runbook |
| :--- | :--- | :--- | :--- | :--- |
| `gsi.py` | `tools/sys/` | System | Script importer: Parses metadata headers in root staging, creates pre-write backups, relocates files, and runs pytest. | `docs/tools/runbook-gsi.md` |
| `install_hooks.py` | `tools/sys/` | System | Git hook deployer: Installs pre-commit/pre-push hooks, enforces POSIX permissions, and validates git config. | `docs/tools/runbook-install_hooks.md` |

---

## 3. Mandatory System Utility Invariants
Every system utility within `tools/sys/` must strictly comply with three core standards:

* **PEP 440 Module Versioning:** Every utility must declare a module-level `__version__` string conforming to PEP 440 local build identifiers using cumulative build counters (`__version__ = "<major>.<minor>.<rev>+build.r<counter>"`). Pre-release development candidates use candidate tags preceding the build segment (`rc<candidate>+build.r<counter>`).
* **Workstation & OS Portability:** Utilities must execute hermetically across Windows and POSIX developer environments without hardcoded user-profile dependencies, resolving boundaries dynamically relative to the workspace root.
* **Standard CLI Interface:** Utilities must implement standard `argparse` arguments for `-h`/`--help`, `-v`/`--verbose`, and `--debug`, emitting execution feedback directly to standard streams (`stdout`/`stderr`).

---

## 4. Documentation & Promotion Standards
System utilities must maintain a corresponding 4-tier operational runbook in `docs/tools/runbook-[utility].md` and register in `docs/index.md` as specified in `topic_documentation_standards.md`. Specific method contracts, flags, and diagnostic matrices are maintained in their respective runbooks and PEP 257 / Google-style docstrings.

---

## 5. Verification Harness & Test Placement
System utilities must be validated by dedicated standalone test suites located strictly under `tests/sys/` (e.g., `tests/sys/test_gsi.py`, `tests/sys/test_install_hooks.py`). Test suites must execute within hermetic sandboxes (`tmp_path`) and satisfy branch and statement test coverage requirements before release.