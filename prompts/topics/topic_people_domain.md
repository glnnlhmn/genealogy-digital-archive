<!--
Name: topic_people_domain.md
Path: prompts/topics/topic_people_domain.md
-->
# Topic Specification: People Domain Entities, Kinship & Demographics
<!-- Version: 1.0.3 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Entity Authority & Identifier Standards
* **Canonical Registry:** `data/entities/people.json` governs all person records.
* **Identifier Format:** Global unique identifier adhering strictly to `IND-[0-9]{5}` (e.g., `IND-00000`, `IND-00019`).
* **Canonical Name Structure:** Comprises `given`, `middle`, `surname`, `suffix`, and `maiden_name`.
* **Vital Indicators:** Root-level integer years (`birth_year`, `death_year`) with precision qualifiers (`EXACT`, `APPROX`, `ESTIMATED`) represent cached indicators; canonical vital events reside in `data/entities/facts.json`.

---

## 2. Reciprocal Kinship Graph Invariants
All kinship relationships asserted in `associated_people` must maintain reciprocal edges across both subject entities:

| Outbound Role | Expected Reciprocal Role | Relational Invariant |
| :--- | :--- | :--- |
| `FATH` (Father) | `CHIL` (Child) | Directed parent-to-child lineage edge. |
| `MOTH` (Mother) | `CHIL` (Child) | Directed parent-to-child lineage edge. |
| `CHIL` (Child) | `FATH` or `MOTH` | Resolved dynamically by biological sex attribute of parent. |
| `SPOU` (Spouse) | `SPOU` (Spouse) | Undirected marital / cohabitation bond. |
| `SIBL` (Sibling) | `SIBL` (Sibling) | Undirected collateral kinship edge. |
| `WITN` (Witness) | Unreciprocated | Contextual fact assertion role; no subject graph edge. |
| `OFFICIANT` | Unreciprocated | Contextual clerical role; no subject graph edge. |

---

## 3. Union Pairing Rules
* **Union Structure:** Documented under the `unions[]` collection on the person entity.
* **Required Attributes:** `spouse_id` (valid `IND-XXXXX`) and controlled `status` (`MARRIED`, `DIVORCED`, `SEPARATED`, `COMMON_LAW`).
* **Reciprocal Synchronization:** A union asserted on Person A pointing to Person B requires a mirrored union entry on Person B pointing to Person A with synchronized dates and status codes.

---

## 4. Demographic & Biological Plausibility Boundaries
Archival verification and demographic audits enforce strict chronological boundaries across vital events:

* **Death After Birth:** An individual's death event must not chronologically precede their birth event (`CHRONO_DEATH_BEFORE_BIRTH`).
* **Minimum Parental Biological Age:** Parents must be at least 12 years of age at the birth of a child (`CHRONO_PARENT_TOO_YOUNG`).
* **Maternal Maximum Age:** Mothers delivering past age 55 trigger a boundary violation (`CHRONO_MOTHER_TOO_OLD`).
* **Posthumous Child Timing:** Children born after a mother's death, or more than 9 months (270 days) after a father's death, trigger a biological violation (`CHRONO_BORN_AFTER_PARENT_DEATH`).
* **Maximum Lifespan Limit:** Subject lifespans exceeding 115 years trigger an implausible longevity violation (`CHRONO_IMPLAUSIBLE_LIFESPAN`).

### Note-Based Audit Suppression
Automated chronological violation flags are suppressed when specific verified evidence strings reside within the subject's `notes[]` collection:
* `Verified Longevity`: Suppresses lifespan plausibility warnings.
* `Late delivery` or `Late pregnancy`: Suppresses maternal age boundary warnings.