# MIPLET 001: Operator Profile Path Relocation
* **Target Version:** MIP-Core-v1.0.5
* **Target Sections:**
  * `## 1. Core Principles & Communication Tone` -> `Modular Profile & Topic Integration`
  * `## 2. Directory Structure & File Routing` -> `Production Data Store (data/)`

### Changes:
1. Update user profile reference in Section 1 from `prompts/core/Glenn-User-Profile-v1.0.3.json` to `data/profiles/glenn_profile.json`.
2. Add new directory entry under `data/`:
   * `data/profiles/`: Active operator dossiers and system user profiles (`glenn_profile.json`).
