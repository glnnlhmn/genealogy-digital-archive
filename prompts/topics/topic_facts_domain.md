<!--
Name: topic_facts_domain.md
Path: prompts/topics/topic_facts_domain.md
-->
# Topic Specification: Facts Domain, Evidentiary Consolidation & Lifecycle
<!-- Version: 1.0.3 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Store Authority & Lifecycle Model
* **Master Fact Store:** `data/entities/facts.json` serves as the authoritative assertion store for all genealogical facts.
* **Tombstone Lifecycle:** Superseded, absorbed, or consolidated assertions are not purged or moved to an external archive. They are retained in-place as tombstones within `facts.json`, marked with deprecation/absorption metadata and the canonical replacement identifier for provenance and audit history.
* **Assertion Core:** Binds a single target `person_id` (`IND-[0-9]{5}`) to a controlled `fact_type`.
* **Identifier Standard:** Global unique identifier formatted strictly as lowercase UUIDv4.
* **Mandatory Timestamp Updates:** Any addition, edit, consolidation, or tombstone state change to a fact assertion strictly requires updating its `updated_at` / `last_modified` timestamp to the current UTC ISO 8601 timestamp.

---

## 2. Evidentiary Atomicity & Source Invariance
* **Singular Artifact Rule:** Fact records sharing an identical source `record_urn` represent a singular historical record or digital extract.
* **Non-Fragmentation:** Secondary citations must not diverge or fragment into artificial multi-page assertions. Duplicate source records consolidate through attribute backfilling and note aggregation.

---

## 3. Evidentiary Consolidation Guidelines
When competing, corroborating, or duplicate assertions are merged into a canonical record, evidentiary reconciliation follows a 6-group resolution strategy:

* **Group 1 (Identity & Core Assertion):** Mints a new canonical assertion UUIDv4 while preserving the single target `person_id` and `fact_type`. Heterogeneous person identifiers or mismatched fact types must never be consolidated into a single assertion.
* **Group 2 (Spatiotemporal Harmonization):**
  * *Dates:* Selects the date candidate with the highest evidentiary confidence (Quay score). Ties break by qualifier precision (`Exact` > `About` > `Estimated` > `Calculated`) and ISO 8601 string completeness. Divergent dates offload as research notes.
  * *Locations:* Resolves to canonical jurisdictions in `data/entities/locations.json`. Expands standard administrative abbreviations and normalizes address ordinals. Conflicting jurisdictions offload as research notes.
* **Group 3 (Narrative & Context):** Selects the description candidate with the highest evidentiary confidence and detail. Divergent narrative accounts offload into general notes to preserve historical context.
* **Group 4 (Associated People):** Grounded person entries resolve against canonical IDs in `data/entities/people.json`. Grounded participants deduplicate on `(person_id, role)`. Unlinked names cluster by phonetic and spelling similarity.
* **Group 5 (Evidence & Notes):** Deduplicates identical source references with metadata backfilling. Normalizes notes into sequentially numbered identifiers (`NOT-00001` through `NOT-NNNNN`) and aggregates external identifiers.
* **Group 6 (Audit & Lineage):** Preserves the earliest creation timestamp and updates `updated_at` to the current UTC timestamp. Absorbed assertions are tombstoned in-place with the canonical replacement ID and absorption timestamp.

---

## 4. Chronological Plausibility & Post-Mortem Exemptions
Chronological validation against an individual's vital lifecycle enforces biological boundaries while recognizing legitimate post-mortem documentation:

* **Exempt Fact Types:** `Parentage`, `Death`, `Burial`, `Probate`, `Association`.
  * *Exemption Rationale:* Vital records produced posthumously (such as probate administrations, estate distributions, or death certificates of adult offspring naming deceased parents) legitimately assert kinship, parental relationships, and legal associations after physical death.
* **Non-Exempt Violations:** Any non-exempt fact type asserting active living presence (such as `Residence`, `Census`, `Occupation`, `Military`, `Education`) dated after an individual's validated `Death` or `Burial` event constitutes a chronological integrity violation.

---

## 5. Decoupled Secondary Indexes
* Secondary lookup tables (such as place, timeline, and surname indexes in `data/indexes/`) are downstream consumers of the fact store.
* Fact operations remain strictly decoupled from index creation and synchronization. Secondary indexers independently evaluate the `last_modified` / `updated_at` timestamps on facts to determine when re-indexing is required.