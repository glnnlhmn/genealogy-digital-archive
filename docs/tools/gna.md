# Documentation: GNA System Manager Utility
<!-- Version: v1.0.0 -->

* **Tool Name:** gna.py
* **Path:** tools/ops/gna.py
* **Anchor Location:** G:/My Drive/genealogy-digital-archive
* **Documentation Location:** docs/tools/gna-v1.0.0.md

---

### Overview
The `gna.py` script is the primary permanent operational tool for managing the Genealogy Digital Archive. It handles configuration manifest generation, schema and prompt integrity auditing, hash drift detection, and automated discrepancy remediation.

---

### Key Operational Capabilities

1. **Baseline Configuration Generation (`--generate-config` / `-g`)**
   * Scans active repository paths (`schemas/` and `prompts/`) while automatically omitting archived assets.
   * Extracts internal metadata version strings and descriptions.
   * Automatically executes a safe backup of the existing manifest (`gda_config.json.bk`) in the project root before writing a fresh baseline manifest (`gda_config.json`).

2. **System Integrity Audit (`--audit` / `-a`)**
   * Cross-references disk assets against the `gda_config.json` baseline.
   * Identifies unversioned assets (`UNKNOWN`), version mismatches between filenames and internal headers, and SHA-256 hash drifts.
   * Exports timestamped audit logs and summaries to the `reports/` directory in both JSON and Markdown formats.

3. **Automated Remediation (`--repair`)**
   * Parses the most recent audit report generated in `reports/`.
   * Automatically patches version mismatches in markdown headers or forces an override version (`0.0.999`) for unrecognized legacy assets.
   * Automatically triggers a fresh configuration refresh upon successful repair execution.

---

### CLI Syntax & Parameter Reference

* **Interactive TUI Mode:** Run without arguments:
  `python tools/ops/gna.py`
* **Command-Line Arguments:**
  * `-h`, `--help`: Displays syntax, synopsis, and parameter guidance.
  * `-a`, `--audit`: Runs a full system integrity audit and generates reports.
  * `-g`, `--generate-config`: Generates or refreshes the `gda_config.json` baseline manifest.
  * `-r`, `--report [json|md|all]`: Specifies the export format for audit reports (default: `all`).
  * `--repair`: Executes automated remediation using the latest audit report.
  * `-v`, `--verbose`: Enables detailed debugging logs routed to the active session log.

---

### Logging & Path Standards
* **Execution Logs:** Runtime traces and diagnostic outputs are automatically routed to the root-level `logs/` directory using the naming format `logs/gna-[YYYYMMDD_HHMMSS].log`.
* **Backup Handling:** Configuration backups are safely isolated in the project root as `gda_config.json.bk`.