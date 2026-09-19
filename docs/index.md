# Technical Documentation Index
<!-- Version: 1.0.1 -->

Master directory of technical references, library specifications, and tool runbooks for the digital archive automation suite.

---

## 1. Architecture & Environment
* [Package & Directory Architecture](architecture/package_structure.md): Layout of `tools/`, `data/`, and PyCharm environment configs[cite: 3].

## 2. Tool Runbooks (`tools/`)
* [GSI Script Importer](tools/gsi.md): Header-driven artifact intake, collision backups, and execution dispatcher.
* [GNA System Manager](tools/gna.md): Configuration manifest generation, schema/prompt auditing, hash drift detection, and safe backup automation.

## 3. Shared Library APIs (`tools/lib/`)
* *(Empty)*

## 4. Operational Workflows & Definitions
* [Safe Backup Protocol](defs/def-safe-backup-v1.0.0.md): Mandatory pre-execution atomic data snapshot standard for scripts updating persistent records.