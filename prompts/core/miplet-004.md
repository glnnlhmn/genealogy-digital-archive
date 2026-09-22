# MIPLET 004: Core Framework Package (gda_core)
* **Target Version:** MIP-Core-v1.0.5
* **Target Section:** `## 2. Directory Structure & File Routing` -> `Permanent Automation & Tooling Suite (tools/)`

### Changes:
1. Introduce and document the `tools/lib/gda_core/` framework package:
   * `tools/lib/gda_core/`: Core archive framework package housing shared baseline architecture, configuration classes, path resolvers, and protocol handlers:
     * `tools/lib/gda_core/GDAConfig.py`: Centralized singleton configuration module managing environment resolution, directory topology anchors, manifest metadata (`gda_config.json`), and standard archive paths.
     * `tools/lib/gda_core/GDALogger.py`: Standardized logging subsystem utilizing `GDALogFormatter` with `[SYS]` tags and dedicated record-level action formatting.
     * `tools/lib/gda_core/GDAUtil.py`: Shared atomic Safe Backup Protocol handlers, audit report resolvers, rollback and pruning engines, and UTF-8 JSON I/O routines.
     * `tools/lib/gda_core/registry.py`: Centralized vocabulary registry (`SchemaEnums`) resolving definitions directly via `GDAConfig`.
