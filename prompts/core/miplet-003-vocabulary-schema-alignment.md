<!--
Name: miplet-003-vocabulary-schema-alignment.md
Path: prompts/core/miplet-003-vocabulary-schema-alignment.md
Target Baseline: v1.0.8
Target File: prompts/topics/MIP-Topic-Library-Architecture.md
Target Section: Section 3.4 (GDAVocabularyManager)
Target Type: Modification
-->

### Modification to Section 3.4: Controlled Vocabulary Harmonization

#### Operational Purpose
Harmonizes `GDAVocabularyManager` public accessor contracts in `MIP-Topic-Library-Architecture.md` with canonical Draft 2020-12 controlled vocabularies defined in `schemas/defs/_enums.schema.json`.

#### Updated Text
Replace the existing method listing for `get_date_modifiers()` and `get_union_statuses()` with:

* **`get_date_modifiers() -> Set[str]`**: Returns permitted standard GEDCOM-style date qualifiers (`EXACT`, `ABT`, `BEF`, `AFT`, `BET`, `FROM_TO`, `UNKNOWN`). Natural language tokens (`ABOUT`, `ESTIMATED`, `CALCULATED`) are normalized through `GDADates` transformation pre-processors.
* **`get_union_statuses() -> Set[str]`**: Returns permitted relationship statuses (`MARRIED`, `DIVORCED`, `ANNULLED`, `SEPARATED`, `COMMON_LAW`, `WIDOWED`, `PARTNER`, `UNKNOWN`).
* **`get_kinship_roles() -> Set[str]`**: Returns permitted reciprocal family kinship, clerical, and associated event roles (`CHIL`, `HUSB`, `WIFE`, `MOTH`, `FATH`, `SPOU`, `SIBL`, `WITN`, `GODP`, `INFORMANT`, `CLERGY`, `OFFICIANT`, `NEIGHBOR`, `ATND`, `UNDR`, `DEC`, `OTHR`, `UNKNOWN`).