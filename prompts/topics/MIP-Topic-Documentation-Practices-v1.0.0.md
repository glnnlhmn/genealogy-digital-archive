# Topic Specification: Digital Archive Documentation & Tool Promotion Standards
<!-- Version: 1.0.0 -->
<!-- Location: prompts/topics/MIP-Topic-Documentation-Practices-v1.0.0.md -->

## 1. Documentation Architecture (`docs/`)
All technical references, protocols, and tool runbooks anchor under `docs/` and are registered within `docs/index.md`.

* **Master Directory (`docs/index.md`):** Central catalog tracking active technical runbooks, architecture specifications, and workflow protocols.
* **Architecture Specifications (`docs/architecture/`):** Structural blueprints, environmental conventions, and filesystem layouts (e.g., `package_structure.md`).
* **Operational Definitions & Protocols (`docs/defs/`):** Formal governing specifications (e.g., `def-safe-backup-v1.0.0.md`).
* **Tool Runbooks (`docs/tools/`):** Standardized user and operational guides for permanent tools residing in `tools/ops/` (e.g., `gna-v1.0.0.md`, `gsi.md`).

---

## 2. Tool Promotion Lifecycle (`gtemp/` -> `tools/ops/`)

1. **Incubation (`gtemp/`):**
   * Experimental or single-purpose scripts incubate in `gtemp/XX_[purpose].py`.
   * Execution logs write to `gtemp/[script]-timestamp.log`.
2. **Promotion Gate:**
   * Script is migrated to `tools/ops/[tool].py`.
   * Logging is updated to target `logs/[tool]-[timestamp].log`.
   * Standard CLI parameters (`--help`, `--verbose`, `--debug`) and Safe Backup pre-checks are verified.
   * A dedicated Markdown runbook is authored in `docs/tools/[tool].md`.
   * The new runbook is linked under Section 2 of `docs/index.md`.

---

## 3. Tool Runbook Structure Standard
Every operational tool runbook in `docs/tools/` must contain the following standard sections:

* **Header Metadata:** Document title, Version tag (`<!-- Version: X.Y.Z -->`), and Tool path (`<!-- Location: tools/ops/... -->`).
* **Synopsis:** Plain-text description of operational scope, interfaces, and responsibilities.
* **Command Syntax:** Primary CLI invocation patterns.
* **Parameters:** Itemized flag descriptions, expected types, and default values.
* **Safety & Logging Rules:** Backup triggers, log destinations, and error handling behaviors.

---

## 4. Markdown Rendering Safeguards
To avoid rendering collisions and UI display errors:
* Do not nest raw 3-tick code fences within other 3-tick blocks.
* When presenting executable blocks inside documentation wrappers, use 4-tick fences (` ```` `) for the outer wrapper.
* Avoid raw HTML tags unless strictly using standardized HTML comment tags (`<!-- ... -->`) for internal version tracking.