<!--
Name: miplet-001-mip-profile-tracking.md
Path: prompts/core/miplet-001-mip-profile-tracking.md
Target Baseline: v1.0.8
-->
### Scope
Integrate `data/profiles/mip_profile.md` into Section 1 (Core Principles & Communication Tone) and Section 2 (Directory Structure & File Routing) as the authoritative operational backlog ledger.

### Patch Instructions
1. In Section 1, update the operator context bullet:
   * **Operator & System Context Integration:** Dynamically load operator preferences and routines from `data/profiles/glenn_profile.json` (SchemaVersion 1.0.4) and active development priorities, architectural notes, and task backlogs from `data/profiles/mip_profile.md`.
2. In Section 2, under `Production Data Store (data/)`:
   * Update `data/profiles/`: Active operator dossiers (`glenn_profile.json`) and system task/backlog tracking ledgers (`gda_profile.md`).