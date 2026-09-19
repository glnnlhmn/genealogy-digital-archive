# TOOL INSTRUCTION: Fact Ingestion & Reconciliation Protocol
<!-- Version: 1.0.3 -->

## 0. Versioning & Scope
* **Tool Name:** Fact Ingestion & Reconciliation Protocol
* **Module Version:** v1.0.3
* **Target Scope:** Fact extraction, staging triage, 4-rule audit proposal, user confirmation gate, mandatory ledger backup, and safe-keeping archival.
* **Target Personas:** Ingestion specialists, batch reconcilers, and data integrity auditors.
* **Root Anchor:** `G:/My Drive/genealogy-digital-archive`

---

## 1. Architectural Philosophy: Staging vs. Canonical Ledger
To preserve non-destructive data processing and prevent write-blocking, all fact processing is split into two operational tiers:

1. **Extraction / Staging Tier (`data/entities/factoid-[GUID].json`):**
   * Atomic, isolated assertions generated directly from a single physical document, register entry, or article.
   * **Zero Cross-Validation Requirement:** Extraction tools stage facts independently without querying or validating against the existing master dataset. Staged factoids may temporarily contain duplicate events or shared person pointers.
2. **Canonical Tier (`data/entities/facts.json` & `data/entities/people.json`):**
   * Authoritative, validated relational repositories containing normalized entities and facts.
   * Updates occur exclusively via automated or audited **Batch Reconciliation Passes**.

---

## 2. Five-Stage Gated Lifecycle Pipeline

* **Stage 1: Extraction & Generation**
  * Extract historical assertions from primary/secondary records (vital certificates, census schedules, newspaper clippings, deeds).
  * Emit each assertion as an independent `data/entities/factoid-[GUID].json`.
  * Validate output strictly against the active on-disk schema: `schemas/entities/fact.schema.json`.
  * When a single record yields multiple assertions (e.g., a census return listing occupation and residence), emit separate factoid files with distinct UUIDs.

* **Stage 2: Staging**
  * Factoids accumulate directly inside `data/entities/`.
  * Preliminary factoids may utilize provisional quay scores or missing cross-references while awaiting verification.

* **Stage 3: The 4-Rule Pre-Audit Proposal**
  Scan staged factoids against `data/entities/facts.json` and generate an itemized proposal based on the 4-Rule Audit:
  1. **Primary Record Collision (`source_urn` + `person_id` + `fact_type`):**
     * Detects accidental duplicate extractions of the exact same document for the same subject.
     * **Action:** Proposal marks the most descriptive record for retention and redundant staged entries for disposal.
  2. **Semantic Event Matching (`person_id` + `fact_type` + `date` + `location`):**
     * Detects distinct records referencing the exact same real-world event (e.g., multiple newspaper reports of an accident).
     * **Action:** Proposal merges corroborating citations into the primary record's `source_urn` and merges unique notes.
  3. **Reciprocal Relationship Triangulation:**
     * Identifies bilateral relational events (e.g., `Marriage`, `Divorce`).
     * **Action:** **Retain both perspectives.** Proposal ensures each party retains their reciprocal fact asserting their respective participation and linking to their spouse.
  4. **Registry Integrity Verification (`data/entities/people.json`):**
     * Verifies that all `person_id` references exist in `people.json`.
     * **Action:** Resolve alias references to canonical `IND-XXXXX` IDs. Never renumber existing `person_id` keys.

* **Stage 4: User Confirmation Gate**
  * Output the full itemized proposal (records to prune, citations to merge, new facts to append).
  * Explicitly pause and request confirmation: *"Do you want to proceed with this update?"*
  * **Hard Stop:** No writes, merges, or deletions may occur until explicit user approval is received.

* **Stage 5: Backup, Commit & Archive**
  1. **Mandatory Ledger Backup:**
     * Upon receiving user confirmation, immediately snapshot `data/entities/facts.json`:
       `data/entities/facts_backup_[YYYYMMDD_HHMMSS].json`
     * Verify the backup exists and is non-empty before writing changes.
  2. **Commit Ledger:**
     * Append approved factoids to `data/entities/facts.json`.
     * Regenerate metadata counters (`total_facts`) and timestamps (`updated_at`).
     * Cross-reference target person profiles in `data/entities/people.json` if vital markers are updated.
  3. **Safe-Keeping Archival:**
     * Relocate merged `data/entities/factoid-*.json` files directly into:
       `data/entities/archive/factoids-[YYYYMMDD]/`
     * Confirm all staged files are cleared from `data/entities/`.

---

## 3. Operational Invariants
* **Dynamic Schema Referencing:** Never hardcode schema definitions or payload examples in instructions. Reference `schemas/entities/fact.schema.json` directly on disk.
* **Score Validation:** Use `quay_score` (`0`, `1`, `2`, or `3`) as mandated by `fact.schema.json`. Unofficial fields like `confidence_score` are prohibited.
* **Mandatory Gate:** Never bypass Stage 4 confirmation, even during automated CLI batch runs.
* **Pre-Merge Backup Rule:** Writing to `data/entities/facts.json` is strictly blocked until a verified backup snapshot exists on disk.
* **Safe-Keeping Archival Rule:** Staged factoid files are archived into `data/entities/archive/factoids-[YYYYMMDD]/` rather than deleted.
* **Path Standardization:** All file paths must use forward slashes (`/`).
