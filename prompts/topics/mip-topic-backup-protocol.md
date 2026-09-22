# MIP-Topic: Data Protection and Backup Architecture
<!-- Version: 1.0.0 -->

* **Topic ID:** `mip-topic-backup-protocol`
* **Target Scope:** Operational scripts modifying JSON records, indexes, and system configurations.
* **Anchor Location:** `G:/My Drive/genealogy-digital-archive`

---

### Core Backup Specifications

1. **Core Data Files & Indexes (`data/`)**
   * **Destination Directory:** `backups/`
   * **Naming Pattern:** `[filename].[YYYYMMDD_HHMMSS].bk` (e.g., `backups/people.json.20260919_132100.bk`)
   * **Execution Rule:** Executed automatically via an atomic write pattern prior to record appends or updates.

2. **System Configuration Files (`gda_config.json`)**
   * **Destination Directory:** Project Root (`G:/My Drive/genealogy-digital-archive/`)
   * **Naming Pattern:** `[filename].bk` (e.g., `gda_config.json.bk`)
   * **Execution Rule:** Single-level static backup overwritten upon each configuration schema update.

3. **Code, Schemas, and Prompts**
   * **Version Control:** Managed 100% through Git tracking, tags, and designated archive subdirectories (`schemas/archive/`, `prompts/archive/`). No manual file-level runtime backups required.