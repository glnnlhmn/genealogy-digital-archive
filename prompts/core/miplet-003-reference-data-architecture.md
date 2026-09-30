<!--
Name: miplet-003-reference-data-architecture.md
Path: prompts/core/miplet-003-reference-data-architecture.md
Target Baseline: v1.0.8
Target File: prompts/core/MIP-Core.md
Target Section: Section 2 (Directory Structure & File Routing)
Target Type: Addition
-->

### Operational Context & Addition Summary
Establishes the `data/reference/` data tier and the `GDAReference.py` core framework module to store and resolve immutable static lookup tables, historical gazetteers, and colloquial normalization mappings without code-level dictionary bloat.

---

### Delta Directives

#### 1. Section 2 Addition: Production Data Store (`data/reference/`)
Add the following directory specification under `data/`:

* `data/reference/`: Static, immutable reference tables, genealogical gazetteers, historical boundary maps, and controlled lookup tables (`states_colloquial.json`). Managed as read-only runtime fixtures distinct from mutable entity registries.

#### 2. Section 2 Addition: Core Framework Package (`tools/lib/gda_core/`)
Add the following module under `tools/lib/gda_core/`:

* `GDAReference.py`: Centralized singleton providing in-memory cached access to static lookup tables and historical gazetteers stored in `data/reference/`.