<!--
Name: MIP-Topic-People-Domain.md
Path: prompts/topics/MIP-Topic-People-Domain.md
-->
# Topic Specification: People Domain Entities, Kinship & Demographics
<!-- Version: 1.0.1 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Schema Authority & Entity Structure
Governed by `schemas/entities/person.schema.json` and `schemas/entities/person_registry.schema.json`.

* **Master Entity File:** `data/entities/people.json`
* **Identifier Format:** `IND-[0-9]{5}` (e.g., `IND-00000`, `IND-00019`).
* **Canonical Name Object:** Contains `given`, `middle`, `surname`, `suffix`, `maiden_name`, and optional integer year objects (`birth_year`, `death_year`) with qualifiers (`EXACT`, `APPROX`, `ESTIMATED`).

---

## 2. Kinship Reciprocal Association Matrix
All personal connections asserted in `associated_people` must maintain reciprocal edges across both subject entities:

| Outbound Role | Expected Reciprocal Role | Kinship Note |
| :--- | :--- | :--- |
| `FATH` (Father) | `CHIL` (Child) | Parentage linkage |
| `MOTH` (Mother) | `CHIL` (Child) | Parentage linkage |
| `CHIL` (Child) | `FATH` or `MOTH` | Determined by subject sex attribute |
| `SPOU` (Spouse) | `SPOU` (Spouse) | Reciprocal marriage partnership |
| `SIBL` (Sibling) | `SIBL` (Sibling) | Collateral kinship |
| `WITN` (Witness) | Unreciprocated | Contextual fact role |
| `OFFICIANT` | Unreciprocated | Contextual clerical role |

---

## 3. Union State Machine & Pairing
* **Union Structure:** Defined under `unions[]` array inside the person payload.
* **Required Properties:** `spouse_id` (valid `IND-XXXXX`), `status` (`MARRIED`, `DIVORCED`, `SEPARATED`, `COMMON_LAW`).
* **Reciprocity Requirement:** A union entry on Person A pointing to Person B requires a corresponding union entry on Person B pointing to Person A with synchronized dates and statuses.

---

## 4. Biological & Demographic Plausibility Rules
Audit tools (`tools/ops/gpa.py`) enforce the following chronological boundaries:
1. **Death After Birth:** Subject death date must never precede birth date (`CHRONO_DEATH_BEFORE_BIRTH`).
2. **Parent Minimum Biological Age:** Parents must be at least 12 years older than their children (`CHRONO_PARENT_TOO_YOUNG`).
3. **Maternal Maximum Age:** Mothers delivering past age 55 trigger `CHRONO_MOTHER_TOO_OLD` unless documented.
4. **Child Born After Parent Death:** Children born after a mother's death, or more than 9 months after a father's death, trigger `CHRONO_BORN_AFTER_PARENT_DEATH`.
5. **Maximum Plausible Lifespan:** Documented lifespans exceeding 115 years trigger `CHRONO_IMPLAUSIBLE_LIFESPAN`.

### Note-Based Audit Exemptions
Automated warnings are suppressed when specific verified strings reside within the subject's `notes[]` array:
* `Verified Longevity`: Suppresses lifespan plausibility warnings.
* `Late delivery` or `Late pregnancy`: Suppresses maternal age boundary warnings.