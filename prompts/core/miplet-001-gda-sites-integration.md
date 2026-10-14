<!--
Name: miplet-001-gda-sites-integration.md
Path: prompts/core/miplet-001-gda-sites-integration.md
Target Baseline: v1.0.8
Target File: prompts/core/MIP-Core.md
Target Section: Section 2 (Directory Structure & File Routing)
Target Type: Addition
-->

### Operational Directives: Core Architecture Addition

* **Master Physical Site Registry (`sites.json`):**
  * Governed by `schemas/entities/site.schema.json` and `schemas/entities/site_registry.schema.json`.
  * Canonical physical landmarks, cemeteries, churches, facilities, residences, and organizations reside in `data/entities/sites.json`.
  * Entity Identifier Format: `SITE-[0-9]{5}` (e.g., `SITE-00001`, `SITE-00300`).
  * Referential Hierarchy: Every physical site strictly links to a valid civil jurisdiction in `locations.json` via foreign key `location_id` (`LOC-[0-9]{5}`).
* **Core Framework Library Addition (`GDASites.py`):**
  * `tools/lib/gda_core/GDASites.py`: Master service class managing `data/entities/sites.json`.
  * Implements atomic CRUD operations, internal auto-minting of monotonic identifiers (`SITE-XXXXX`), wildcard and fuzzy string resolution, stateful view filtering, and transactional batch updates across filtered sets (`update_filtered`).
  * Integrates with `GDAUtil.save_json(..., create_backup=True)` for single touch-point atomic persistence and Safe Backup Protocol snapshot creation.