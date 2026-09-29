<!--
Name: miplet-001-jupyter-registry-integration.md
Path: prompts/core/miplet-001-jupyter-registry-integration.md
Target Baseline: v1.0.8
Target File: prompts/core/MIP-Core.md
Target Section: Section 2 (Directory Structure & File Routing) and Section 3 (Operational Protocols & Scripting Safeguards)
Target Type: Addition
-->

### Operational Context & Addition Summary
Integrates Jupyter Notebooks as a permanent, first-class component of the GDA architecture for ad-hoc inspection, interactive registry queries, and surgical data maintenance across `GDASites` and `GDALocations`. Establishes the `notebooks/` directory topology, browser routing standards, and test harness marker integration.

---

### Delta Directives

#### 1. Section 2 Addition: Interactive Notebook Topology (`notebooks/`)
Add the following directory specification under `G:/My Drive/genealogy-digital-archive` in Section 2:

* **Interactive Notebook Environment (`notebooks/`):**
  * `notebooks/exploration/`: Read-only ad-hoc exploration, registry queries, and statistical analysis (e.g., `01_sites_api_tour.ipynb`, `02_locations_api_tour.ipynb`). Notebooks here must never perform unbuffered destructive mutations against production registries.
  * `notebooks/maintenance/`: Governed operational notebooks executing surgical entity fixes, manual data merges, geocoding backfills, and deduplication staging. Must strictly route persistence through `gtemp/` scratch targets or invoke Safe Backup protocols prior to committing changes to canonical stores.

#### 2. Section 2 Addition: GDA Core Registry Managers (`tools/lib/gda_core/`)
Register the two new foundational registry modules under `tools/lib/gda_core/` in Section 2:

    * `GDALocations.py`: Master civil jurisdiction manager handling hierarchical place normalization (Country > State > County > Local), offline US state validation via the `us` package, temporal boundary validity tracking (`date_established`, `date_dissolved`), predecessor/successor lineage splits, exact/wildcard/fuzzy searches, alias lifecycle management, and decoupled scratch persistence.
    * `GDASites.py`: Master physical site manager governing facilities, cemeteries, churches, landmarks, and residences. Handles geocoded coordinates, address structures, primary key auto-minting (`SITE-XXXXX`), foreign key integrity checks against `GDALocations`, alias management (`add_alias`, `remove_alias`), stateful filtering, batch updates, and isolated scratch persistence via `save(output_path=...)`.

#### 3. Section 3 Addition: Jupyter Environment Safeguards & Execution Rules
Add the following operational guidelines to Section 3:

* **JupyterLab Server & Browser Configuration:**
  * **Anchor Point:** The JupyterLab server root must anchor to the repository root `G:/My Drive/genealogy-digital-archive` via `c.ServerApp.root_dir`.
  * **Browser Binding:** Web launch must be explicitly bound to Google Chrome (`"C:/Program Files/Google/Chrome/Application/chrome.exe" %s`) via `c.ServerApp.browser` inside `~/.jupyter/jupyter_lab_config.py`.
  * **Direct Launch URL:** Set `c.ServerApp.use_redirect_file = False` to prevent localized HTML redirect token errors on Windows.
  * **Non-Elevated Execution:** Run `jupyter lab` exclusively within a standard, non-elevated user shell to avoid permission isolation between the Windows administrator token and virtualized filesystem mounts (`G:`).
  * **Dynamic Kernel Path Anchoring:** Notebooks must dynamically detect and anchor the working directory to the repository root within Cell 1 (`cwd = Path.cwd().resolve()`) and ensure `sys.path` contains the repository root.