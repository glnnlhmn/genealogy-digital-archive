# Name: facts_insp.md
# Path: docs/tools/facts_insp.md

# Technical Runbook: Fact Registry Inspection Engine (`facts_insp.py`)

## 1. Overview
The `facts_insp.py` operational tool (Build 20) is the core validation and auditing engine for `data/entities/facts.json`. It performs comprehensive integrity checks across the archive's fact registry, ensuring schema conformance, vocabulary validity, chronological soundness, biological plausibility, duplication detection, and relational consistency.

---

## 2. Execution Syntax & Parameters

Execute the inspection tool from the root directory (`G:/My Drive/genealogy-digital-archive/`):

python tools/ops/facts_insp.py [--verbose] [--debug]

### Supported Arguments:
* `--verbose` / `-v`: Emits detailed diagnostic log entries directly to session logs in `logs/`.
* `--debug`: Routes runtime traces and verbose errors directly to `sys.stderr`.

---

## 3. The Four-Tier Audit Pipeline

### Stage 1: Record Validation & Formatting
* **Stage 1.1 (Schema Conformance):** Validates that all fact records conform to standard GUID/UUID formatting patterns. Violations are classified as **Warnings**.
* **Stage 1.2 (Typology & Vocabulary):** Evaluates `fact_type` strings against controlled vocabularies defined in `_enums.schema.json`. Unrecognized types are classified as **Errors**.
* **Stage 1.3 (Temporal Modifiers):** Validates date modifiers (`EXACT`, `ABT`, `BEF`, `AFT`, `BET`, `FROM_TO`, `UNKNOWN`) against controlled schemas. Unrecognized modifiers are classified as **Errors**.

### Stage 2: Biological & Chronological Plausibility
* **Deep Vitals Traversal:** Evaluates historical facts against individual lifespans loaded from `people.json`. The engine resolves birth and death years dynamically across nested wrappers (`vitals.birth`, `vitals.death`, and `canonical_name` year blocks).
* **Pre-Natal Checks:** Flags any non-exempt fact occurring prior to subject birth as a **Biological Error**.
* **Post-Mortem Checks:** Flags facts occurring after subject death as **Biological Errors**, with specific exemptions for post-mortem administrative and documentary types (`Death`, `Burial`, `Probate`, `Association`, and `Parentage`). The `Parentage` exemption permits post-mortem parent assertions (e.g., child death certificates or estate filings created after a parent's demise) without triggering false positives.

### Stage 3: Deduplication & Merge Proposals
* **Dedup-Source:** Identifies multiple redundant extractions for the same fact type originating from an identical source URN (**Warnings**).
* **Dedup-Event:** Detects multi-source corroborating records representing the same real-world historical event (**Warnings**).
* **Deliverable:** Automatically generates a merge candidate CSV report in `reports/` when proposals exist.

### Stage 4: Relational Reciprocal Consistency
* **Reciprocal Pairing:** Validates marriage and partner linkages across entity records. Unreciprocated partner assertions are classified as informational notes (**Info**).

---

## 4. Audit Deliverables & Outputs
* **Summary JSON:** Emits a comprehensive audit summary report to `reports/facts_audit_summary_[TIMESTAMP].json`.
* **Merge CSV:** Conditionally exports a remediation CSV file (`reports/fact_merge_candidates_[TIMESTAMP].csv`) if duplicate records or merge proposals are identified.