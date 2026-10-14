<!--
Name: miplet_001_vocabulary_manager_native_taxonomy.md
Path: prompts/core/miplet_001_vocabulary_manager_native_taxonomy.md
Target Baseline: v1.0.8
Target File: prompts/core/MIP-Core.md
Target Section: Section 2 (schemas/defs/ & Permanent Automation & Tooling Suite -> tools/lib/gdacore/)
Target Type: Modification
-->

### Modification to Section 2: Decouple Vocabulary Manager Completely from JSON Schema

#### Operational Purpose
Removes JSON Schema resolution, disk file I/O (`_enums.schema.json`), and schema generator dependencies (`gdaschema._schema_defs.build_enums`) from `gdacore.vocabulary_manager`. Establishes `GDAVocabularyManager` as a self-contained, native Python controlled vocabulary and domain taxonomy registry. Re-anchors `schemas/defs/` to compiled validation artifacts emitted from procedural schema builders rather than runtime dependencies.

#### Updated Description: `schemas/defs/`
Under **Schema Definitions & Architecture (`schemas/`)**, replace the existing `schemas/defs/` entry with:
* `schemas/defs/`: Base data types, field definitions, reusable primitives, and compiled enum constraints. Generated via procedural schema builders and audited via `gsm.py` strictly for Draft 2020-12 validation artifacts.

#### Updated Description: `src/gdacore/vocabulary_manager.py`
Under **Permanent Automation & Tooling Suite (`tools/lib/gdacore/`)**, replace the existing `src/gdacore/vocabulary_manager.py` entry with:
* `src/gdacore/vocabulary_manager.py`: Centralized controlled vocabulary and domain taxonomy registry (`GDAVocabularyManager`, aliased as `GDASchemaEnums` / `SchemaEnums`) defining authoritative domain taxonomies natively in Python into immutable, attribute-accessible `VocabularySet` containers with zero JSON Schema dependencies and zero disk I/O.