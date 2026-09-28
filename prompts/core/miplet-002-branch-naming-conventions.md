<!--
Name: miplet-002-branch-naming-conventions.md
Path: prompts/core/miplet-002-branch-naming-conventions.md
Target Baseline: v1.0.8
-->
### Scope
Establish standard Git branch naming conventions using fictional leading roles from musical theater.

### Patch Instructions
1. In Section 3 (Operational Protocols & Scripting Safeguards), add a dedicated rule for **Git Branch Naming Standard**:
   * **Thematic Decoupling:** Feature and work branches are deliberately decoupled from specific technical tasks and follow a structured cultural theme.
   * **Convention (Musical Theater Leading Roles):** All development branches must follow the pattern `role/<character-slug>`.
   * **Formatting Rules:** Slugs must be entirely lowercase, kebab-cased, and represent notable leading roles from musical theater (e.g., `role/tevye`, `role/harold-hill`, `role/jean-valjean`, `role/orpheus`, `role/elphaba`, `role/sky-masterson`).
   * **Branch Lifecycle:** Create from updated `main` via `git checkout -b role/<character-slug>`, verify pre-commit and pre-push hooks, and squash/merge cleanly back into `main` before deleting the working branch.
