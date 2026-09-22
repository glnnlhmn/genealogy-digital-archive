# MIPLET 003: Entity Quarantine Buffer
* **Target Version:** MIP-Core-v1.0.5
* **Target Section:** `## 2. Directory Structure & File Routing` -> `Production Data Store (data/)`

### Changes:
1. Add explicit quarantine buffer under `data/entities/`:
   * `data/entities/quarantine/`: Staged quarantine buffer for non-conforming, unverified, or anomalous entity records isolated from production.
