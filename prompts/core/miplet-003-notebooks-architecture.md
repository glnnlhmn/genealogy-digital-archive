<!--
Name: miplet-003-notebooks-architecture.md
Path: prompts/core/miplet-003-notebooks-architecture.md
Target Baseline: v1.0.8
Target File: prompts/core/MIP-Core.md
Target Section: Section 2 (Directory Structure & File Routing)
Target Type: Addition
-->

### Operational Directives: Permanent Interactive Notebook Topology

* **Interactive Notebook Architecture (`notebooks/`):**
  * `notebooks/`: Master directory for permanent Jupyter exploration, component demonstration, and guarded registry maintenance.
  * `notebooks/exploration/`: Read-only laboratory notebooks demonstrating core libraries (`GDASites`, `GDALocations`, `GDAUtil`), profiling algorithms, and verifying schema enums.
  * `notebooks/maintenance/`: Guarded administrative notebooks for visual data inspection, orphan resolution, coordinate anomalies, and single-record surgical remediations.
  * **Operational Standards & Guardrails:**
    * **Path Anchoring:** Notebook kernels must programmatically verify and anchor `Path.cwd()` to the archive root (`G:/My Drive/genealogy-digital-archive`) to resolve imports (`tools.lib.gda_core`) without `sys.path` tampering.
    * **Safe Pre-Write Protocol:** In-place entity modifications executed from notebooks must trigger atomic pre-write backups via `GDAUtil.save_json(..., create_backup=True)` or `GDAUtil.create_safe_backup(...)`.
    * **Scratch Output Routing:** Exploratory notebooks saving output files must write to `gtemp/` (e.g. `gtemp/sites_scratch.json`), leaving production data untouched.
    * **Clean Diff Rule:** All cell execution outputs must be cleared (`Restart Kernel and Clear All Outputs`) prior to Git commits to prevent repository bloat. Checkpoint directories (`.ipynb_checkpoints/`) remain strictly git-ignored.