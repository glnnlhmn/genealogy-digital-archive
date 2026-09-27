# Topic Specification: Facts Domain, Consolidation & Lifecycle
<!-- Version: 1.0.0 -->
<!-- Location: prompts/topics/MIP-Topic-Facts-Domain.md -->

## 1. Schema Authority & Identifier Topology
Governed by `schemas/entities/fact.schema.json` and `schemas/entities/fact_registry.schema.json`.

* **Master Entity File:** `data/entities/facts.json`
* **Fact Identifier:** Universally Unique Identifier Version 4 (`[a-f0-9-]{36}`).
* **Assertion Core:** Binds a single `person_id` to an approved `fact_type` (sourced from `_enums.schema.json`).

---

## 2. Six-Group Fact Consolidation Strategy (`facts_merge.py`)
When duplicate or corroborating assertions are consolidated into a canonical record:

* **Group 1 (Identity & Assertion Core):** Mints a new canonical assertion UUID. Preserves `person_id` and `fact_type`. Heterogeneous person IDs or fact types are rejected.
* **Group 2 (Spatiotemporal):**
  * *Dates:* Selects date with highest Quay score. Breaks ties by modifier precision (`Exact` > `About`) and ISO string length. Divergent dates offload as `RESEARCH` or `GENERAL` context notes.
  * *Locations:* Selects highest Quay location. Expands standard US state abbreviations (`PA` -> `Pennsylvania`). Standardizes spelled ordinals in address lines (`twenty-seventh` -> `27th`). Conflicting jurisdictions offload as `RESEARCH` notes. Verbatim text is set to the standard consolidated merge notice.
* **Group 3 (Narrative & Context):** Selects description with highest Quay score and token density. Alternative descriptions with RapidFuzz similarity < 75.0% offload as `GENERAL` notes. Deduplicates and merges `life_story` narratives.
* **Group 4 (Associated People):** Grounded person entries resolve against master entity IDs in `people.json`. Grounded entries deduplicate on `(person_id, role)`. Unlinked names cluster via Soundex and RapidFuzz (`score >= 85.0`).
* **Group 5 (Evidence & Notes):** Deduplicates identical `record_urn` sources with attribute backfilling. Normalizes string and dict notes, renumbers sequentially (`NOT-00001` through `NOT-NNNNN`), and unions `external_identifiers`.
* **Group 6 (Audit & Provenance):** Adopts the oldest constituent `created_at` timestamp. Updates `updated_at` to the current UTC timestamp. Marks all absorbed records with `canonical_fact_id` and `absorbed_at`.

---

## 3. Post-Mortem Relational Exemptions
Validation engines (`facts_insp.py`) must exempt post-mortem relational and administrative fact types from biological plausibility errors:
* Exempt Types: `Parentage`, `Death`, `Burial`, `Probate`, `Association`.
* Historical Rationale: Vital records created after an individual's death (e.g., adult child death certificates or probate administrations) assert kinship and parental facts post-mortem.

---

## 4. Index Synchronization Boundary
Fact mutations invalidate lookup tables in `data/indexes/`. Fact processing tools emit explicit terminal invalidation warnings; automated reciprocal rebuilds remain postponed pending dedicated GIX indexers.
