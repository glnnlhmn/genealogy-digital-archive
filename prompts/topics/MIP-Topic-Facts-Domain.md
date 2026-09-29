<!--
Name: MIP-Topic-Facts-Domain.md
Path: prompts/topics/MIP-Topic-Facts-Domain.md
-->
# Topic Specification: Facts Domain, Consolidation & Lifecycle
<!-- Version: 1.0.1 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Schema Authority & Store Taxonomy
Governed by `schemas/entities/fact.schema.json` and `schemas/entities/fact_registry.schema.json`.

* **Active Assertion Store:** `data/entities/facts.json` houses active, canonical fact assertions referenced across personas and stories.
* **Archival Fact Store:** `data/entities/facts_archive.json` serves as the long-term repository for absorbed, superseded, or consolidated assertions pruned from active registries. Records preserved here retain full structural integrity and original identifiers for provenance tracking.
* **Entity Registries & Geocoding Stores:** Grounded entities resolve against canonical registries in `data/entities/`:
  * `people.json`: Master person registry providing canonical `person_id` resolution.
  * `locations.json`: Canonical geographic jurisdiction store validating place hierarchies and coordinates.
* **Assertion Core:** Binds a single `person_id` to an approved `fact_type` (sourced dynamically via `GDASchemaEnums.py` from `schemas/defs/_enums.schema.json`).

---

## 2. Six-Group Fact Consolidation Strategy (`facts_merge.py`)
When duplicate, corroborating, or competing assertions are consolidated into a canonical record:

* **Group 1 (Identity & Assertion Core):** Mints a new canonical assertion UUID (`[a-f0-9-]{36}`). Preserves target `person_id` and `fact_type`. Heterogeneous person IDs or mismatched fact types are strictly rejected.
* **Group 2 (Spatiotemporal Harmonization):**
  * *Dates:* Selects the date candidate with the highest Quay score. Ties break by modifier precision (`Exact` > `About` > `Estimated` > `Calculated`) and ISO 8601 string length. Divergent dates offload as `RESEARCH` or `GENERAL` context notes.
  * *Locations:* Selects highest Quay location cross-referenced against `locations.json`. Automatically expands standard US state abbreviations (`PA` -> `Pennsylvania`). Standardizes spelled ordinals in address lines (`twenty-seventh` -> `27th`). Conflicting jurisdictions offload as `RESEARCH` notes. Verbatim text is set to the standard consolidated merge notice.
* **Group 3 (Narrative & Context):** Selects the description with the highest Quay score and token density. Alternative descriptions with RapidFuzz similarity < 75.0% offload as `GENERAL` notes. Deduplicates and merges `life_story` narrative fragments.
* **Group 4 (Associated People):** Grounded person entries resolve against master entity IDs in `data/entities/people.json`. Grounded entries deduplicate on `(person_id, role)`. Unlinked names cluster via Soundex and RapidFuzz (`score >= 85.0`).
* **Group 5 (Evidence & Notes):** Deduplicates identical `record_urn` sources with attribute backfilling. Normalizes string and dictionary notes, renumbers sequentially (`NOT-00001` through `NOT-NNNNN`), and unions `external_identifiers`.
* **Group 6 (Audit & Provenance):** Adopts the oldest constituent `created_at` timestamp. Updates `updated_at` to the current UTC timestamp. Absorbed source records are marked with `canonical_fact_id` and `absorbed_at` before offloading to `data/entities/facts_archive.json`.

---

## 3. Biological Plausibility & Post-Mortem Exemptions (`facts_insp.py`)
Fact inspection engines evaluating chronology against person vital lifecycles must enforce standard plausibility thresholds while exempting administrative post-mortem records:

* **Exempt Fact Types:** `Parentage`, `Death`, `Burial`, `Probate`, `Association`.
* **Exemption Rationale:** Vital documents created after an individual's physical death (e.g., adult child death certificates naming deceased parents, probate administrations, or estate settlements) legitimately assert kinship, parental identity, and associations post-mortem.
* **Non-Exempt Violations:** Any non-exempt fact type (e.g., `Residence`, `Census`, `Occupation`, `Military`, `Education`) dated strictly after a validated `Death` or `Burial` event triggers a biological chronology violation flag during inspection.

---

## 4. Index Invalidation & Decoupled Synchronization
Fact mutations directly invalidate reciprocal lookup tables in `data/indexes/`.
* Mutation tools emit explicit terminal warnings identifying affected indexes (e.g., `timeline_index`, `place_index`).
* In-place synchronous rebuilding during fact intake is prohibited to ensure single-responsibility isolation. Rebuilding indexes is delegated to dedicated GIX indexers.