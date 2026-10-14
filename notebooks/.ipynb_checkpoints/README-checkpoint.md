<!--
Name: README.md
Path: notebooks/README.md
-->
# Interactive Notebook Architecture (`notebooks/`)

This directory houses permanent Jupyter Notebooks used for interactive library exploration, API dry-runs, data visualization, and surgical registry maintenance.

## Directory Layout

* `exploration/`: Read-only laboratory notebooks demonstrating core libraries (`GDASites`, `GDALocations`, `GDAUtil`), profiling search algorithms, and verifying schema enums.
* `maintenance/`: Guarded administrative notebooks for inspecting orphan personas, validating coordinate anomalies, and staging emergency single-record repairs.

## Operational Standards & Guardrails

1. **Kernel Anchoring:** Notebook kernels must always execute with the project root (`G:/My Drive/genealogy-digital-archive`) as the working directory. Always run the boilerplate anchor cell at the top of every notebook.
2. **Safe Pre-Write Protocol:** Any maintenance notebook modifying entities in `data/entities/` must execute pre-write backups via `GDAUtil.save_json(..., create_backup=True)` or `GDAUtil.create_safe_backup(...)`.
3. **Scratch Outputs:** Notebooks experimenting with file saves should write to `gtemp/` (e.g. `gtemp/sites_scratch.json`), leaving production data untouched.
4. **Git Hygiene:** Always clear all cell outputs before committing:
   `Kernel` -> `Restart Kernel and Clear All Outputs`.