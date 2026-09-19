# Definition: Safe Backup Protocol
<!-- Version: v1.0.0 -->

* **Term:** Safe Backup (`safe_backup`)
* **Target Scope:** Core data files and indexes (`data/`) modified by operational scripts.
* **Anchor Location:** `G:/My Drive/genealogy-digital-archive`

---

### Core Definition
A **Safe Backup** is a mandatory pre-execution data protection routine executed automatically by operational scripts prior to writing, updating, or appending records to any active data file. It ensures that an intact prior state is programmatically isolated and preserved before modification occurs, preventing data loss or file corruption during runtime failures.

### Execution Standards

1. **Destination Directory:** `backups/` (rooted at project level)
2. **Naming Convention:** `[filename].[YYYYMMDD_HHMMSS].bk` (e.g., `backups/people.json.20260919_132100.bk`)
3. **Mechanism & Logging:** 
   * An atomic copy of the target file is generated with a precision timestamp before the script opens or writes to the live path.
   * **Logging Requirement:** When execution logging is enabled, the creation, pathing, and success status of the backup file must be explicitly recorded to the active session log.

### Integration Rule
No operational data modification script may execute a write, append, or atomic replacement (`os.replace`) without first verifying file existence and successfully completing the safe backup protocol.