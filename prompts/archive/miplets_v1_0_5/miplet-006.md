# MIPLET 006: Safe Backup Protocol Enhancements (Labels, Restore & Pruning)
* **Target Version:** MIP-Core-v1.0.5
* **Target Sections:**
  * `## 2. Directory Structure & File Routing` -> `Safe Backups (backups/)`
  * `## 3. Operational Protocols & Scripting Safeguards` -> `Safe Backup Protocol`

### Changes:
1. Expand snapshot naming syntax: `[filename].[timestamp].bk` or `[filename].[label].bk`.
2. Allow label parameter to substitute timestamps for deliberate checkpoints.
3. Formalize programmatic restore (latest or explicit label/timestamp), automated backup pruning (keep last X), and scratch workspace hygiene (`clear_gtemp()`).
