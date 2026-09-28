<!--
Name: miplet-003-direct-file-emission-and-gsi-routing.md
Path: prompts/core/miplet-003-direct-file-emission-and-gsi-routing.md
Target Baseline: v1.0.8
-->
### Scope
Deprecate temporary Python generator wrappers (`gtemp/XX_[purpose].py`) for delivering code, test files, and documentation. Authorize direct native file emission relying on `tools/ops/gsi.py` header metadata for automated filing.

### Patch Instructions
1. In Section 0 (Versioning Protocol & System Identity), under the **Miplet Protocol & Version-Tagged Archiving** bullet:
   * Remove the requirement stating miplet patch emitters must be delivered wrapped inside temporary Python scripts.
   * State that miplets and all system assets must be delivered directly as standalone files containing valid target header metadata.
2. In Section 2 (Directory Structure & File Routing), under **Temporary Workspace (`gtemp/`)**:
   * Remove the phrase: *"All miplet patch emitters must be delivered wrapped inside temporary Python scripts."*
   * Reframe `gtemp/` strictly as an ephemeral workspace for scratch exploration, manual intermediate data transforms, and local debugging runs.
3. In Section 3 (Operational Protocols & Scripting Safeguards):
   * Add a dedicated instruction under **Direct Native File Emission & GSI Intake**:
     * Prohibit wrapping Python scripts, test suites, PowerShell scripts, or documentation inside secondary Python string-emitter scripts.
     * Emit all files directly in their target format (.py, .md, .ps1, .txt, .json) with their mandatory standardized header lines placed in the first 15 lines.
     * Rely exclusively on `tools/ops/gsi.py` to parse headers, generate pre-write Safe Backups, and automatically route downloaded or staged files to their definitive repository locations.