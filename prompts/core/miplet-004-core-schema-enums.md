<!--
Name: miplet-004-core-schema-enums.md
Path: prompts/core/miplet-004-core-schema-enums.md
Target Baseline: v1.0.8
-->
# MIPLET-004: Core Controlled Vocabulary Registry Alignment (GDASchemaEnums)

## 1. Intent & Scope
Synchronize Section 2 (`Directory Structure & File Routing -> tools/lib/gda_core/`) of `prompts/core/MIP-Core.md` to reflect the rename of `registry.py` to `GDASchemaEnums.py`. The module maintains full backward-compatibility aliasing for `SchemaEnums`.

## 2. Text Replacements

### Target: `prompts/core/MIP-Core.md` (Section 2, tools/lib/gda_core/)

#### Original Text:
```markdown
    * `registry.py`: Centralized vocabulary registry (`SchemaEnums`) resolving definitions directly via `GDAConfig`.
```

#### Replacement Text:
```markdown
    * `GDASchemaEnums.py`: Centralized controlled vocabulary registry (`GDASchemaEnums`, aliased as `SchemaEnums`) resolving JSON schema definitions directly via `GDAConfig`.
```
