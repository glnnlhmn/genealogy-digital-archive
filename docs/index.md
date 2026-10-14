<!--
Name: index.md
Path: docs/index.md
-->
# Genealogy Digital Archive Documentation Index

## System Architecture
* [Topology & System Overview](architecture/overview.md)
* [Package & Directory Architecture](architecture/package_structure.md)
* [Data Store Structure & Routing](architecture/data-store.md)

## Framework Libraries (`tools.lib`)
* [GDA Core Framework Guide (`tools.lib.gda_core`)](lib/gda_core/index.md)
  * [GDAConfig: Centralized Environment & Paths](lib/gda_core/GDAConfig.md)
  * [GDAFacts: Transactional Fact Registry Manager](lib/gda_core/GDAFacts.md)
  * [GDAUtil: Safe Backup Protocol & File Utilities](lib/gda_core/GDAUtil.md)
  * [GDASchemaEnums: Controlled Vocabulary Registry](lib/gda_core/GDASchemaEnums.md)

## Core Protocols & Definitions
* [Safe Backup Protocol (def-safe-backup-v1.0.0)](defs/def-safe-backup-v1.0.0.md)

## Operational Tools & Runbooks
* [GAM: Genealogy Archive Manager](tools/gam.md)
* [GSI: Genealogy Script Importer](tools/gsi.md)
* [GPI: Genealogy Person Intake](tools/gpi.md)
* [GPA: Genealogy People Auditor](tools/gpa.md)
* [GFI: Genealogy Fact Intake](tools/gfi.md)
* [GTR: Genealogy Token Registry](tools/gtr.md)
* [FACTS_INSP: Fact Registry Inspection Engine](tools/facts_insp.md)
* [FACTS_MD: Fact Markdown Synchronizer](tools/facts_md.md)
* [FACTS_MERGE: Fact Consolidation & Assertion Merger](tools/facts_merge.md)
