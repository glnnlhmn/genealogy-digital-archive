# Technical Runbook: FACTS_MERGE (Fact Consolidation & Assertion Merger)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `facts_merge.py` |
| **Script Path** | `tools/ops/facts_merge.py` |
| **Version** | `1.0.0+build.20260927.10` |
| **Test Suite** | `tests/unit/test_facts_merge.py` |
| **Log Output** | `logs/facts_merge-[YYYYMMDD_HHMMSS].log` |
| **Audit Report** | `reports/facts_merge_report_[YYYYMMDD_HHMMSS].md` |
| **Safe Backup** | `backups/facts.json.[YYYYMMDD_HHMMSS].bk` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
`facts_merge.py` consolidates duplicate, variant, or overlapping assertions within `data/entities/facts.json` into newly minted canonical facts. It enforces a deterministic 6-group merge strategy, safeguards existing data through the Safe Backup Protocol and pre-flight batch collision validation, and records complete provenance for constituent assertions.

### CLI Syntax
```powershell
python tools/ops/facts_merge.py (-f FACT_ID [FACT_ID ...] | --csv CSV_FILE) [-r] [-v] [--debug]
```

### Options & Parameter Reference
* `-f, --facts FACT_ID ...`: Space-delimited list of fact IDs to merge as a single cluster (minimum 2). Mutually exclusive with `--csv`.
* `--csv CSV_FILE`: Path to a CSV file where each row contains comma-separated fact IDs defining one cluster. Mutually exclusive with `-f`.
* `-r, --run, --apply`: Execute the commit pipeline. Generates an atomic Safe Backup snapshot in `backups/`, commits modifications to `data/entities/facts.json`, and outputs a markdown audit report in `reports/`. Defaults to safe dry-run mode when omitted.
* `-v, --verbose`: Logs operational diagnostics directly to the active session log in `logs/`.
* `--debug`: Streams trace diagnostics and errors directly to stdout.

### Quick Runbook

#### Dry-Run Evaluation (No Changes Committed)
Evaluate a single cluster from the command line:
```powershell
python tools/ops/facts_merge.py -f 00000001-0000-4000-8000-000000000001 00000001-0000-4000-8000-000000000002
```

Evaluate multiple clusters via a batch CSV file:
```powershell
python tools/ops/facts_merge.py --csv import/clusters.csv
```

#### Active Execution (Atomic Commit with Safe Backup)
Consolidate a cluster and commit to disk:
```powershell
python tools/ops/facts_merge.py -f 00000001-0000-4000-8000-000000000001 00000001-0000-4000-8000-000000000002 -r
```

Execute a full batch merge with verbose diagnostic logging:
```powershell
python tools/ops/facts_merge.py --csv import/clusters.csv -r -v
```

---

## 2. Technical Architecture & Data Lifecycle

### The 6-Group Merge Strategy
* **Group 1 (Identity & Assertion Core):** Mints a new canonical assertion UUID. Preserves `person_id` and `fact_type`. Rejects attempts to merge heterogeneous fact types or assertions across different individuals.
* **Group 2 (Spatiotemporal):**
  * *Dates:* Selects the highest Quay score date assertion. Breaks ties by modifier precision (`Exact`) and granularity length. Offloads divergent dates as `RESEARCH` or `GENERAL` context notes.
  * *Locations:* Selects the highest Quay location. Standardizes US state names (e.g., `PA` to `Pennsylvania`) and expands spelled ordinals in street addresses (e.g., `twenty-seventh` to `27th`). Offloads conflicting jurisdictions as `RESEARCH` notes and unifies granular address fields. Verbatim text is set to the standard consolidated notice.
* **Group 3 (Narrative & Context):** Selects the description with the highest Quay score, breaking ties by token density. Uses RapidFuzz token matching; alternate descriptions with similarity below 75.0% are preserved as `GENERAL` notes. De-duplicates and merges qualitative `life_story` entries.
* **Group 4 (Associated People):**
  * *Phase 1 (Pre-Intake Grounding):* Resolves unlinked names against master entity records in `people.json` via Soundex and token matching.
  * *Phase 2 (Partitioned Deduplication):* Deduplicates grounded persons on `(person_id, role)`, setting canonical display names from the registry. Unlinked persons are clustered via phonetic Soundex and RapidFuzz (`score >= 85.0`).
* **Group 5 (Evidence & Notes):** Deduplicates identical `record_urn` source citations while backfilling missing file paths or repository paths. Normalizes string notes into structured dictionaries, appends all offloaded Group 2/3/4 context notes, appends the consolidation provenance audit note, and renumbers notes sequentially (`NOT-00001` through `NOT-NNNNN`). Merges `external_identifiers`.
* **Group 6 (Audit & Provenance):** Adopts the oldest constituent `created_at` timestamp. Updates `updated_at` to the current UTC timestamp. Marks all absorbed records with `canonical_fact_id` and `absorbed_at`.

### Safety & Batch Validation
* **Pre-Flight Validation:** Prior to any mutation, `validate_batch_clusters()` scans the entire batch to catch intra-batch duplicates, overlapping clusters, or facts that have already been absorbed (`absorbed_at != null`).
* **Safe Backup Protocol:** Under active mode (`-r`), generates an atomic pre-write snapshot `backups/facts.json.[timestamp].bk` before writing to disk.
* **Index Invalidation Notice:** Fact consolidation invalidates existing index files in `data/indexes/`. The tool emits an explicit terminal warning on completion, with internal index regeneration hooks postponed pending dedicated GIX tool development.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/unit/test_facts_merge.py`
* **Test Count:** 35 passing tests categorized by pytest markers (`smoke`, `regression`, `unit`, `integration`).
* **Execution:**
```powershell
# Fast smoke validation (< 2s)
pytest -m smoke tests/unit/test_facts_merge.py -v

# Full suite verification
pytest tests/unit/test_facts_merge.py -v
```

### Diagnostic Matrix
* **Error (`Cannot merge heterogeneous fact types`):** The specified cluster contains mixed assertion types (e.g., merging `Birth` with `Death`). Group only homogeneous facts.
* **Error (`Batch collision detected: fact_id ... referenced in multiple clusters`):** A single fact ID appears in more than one cluster in the CSV input. Remove the overlap so that each assertion is mapped to only one canonical cluster.
* **Error (`Fact ... is already absorbed into canonical fact`):** One of the cluster facts was absorbed in a prior consolidation run. Use only active, unabsorbed facts.
* **Warning (`Existing index files referencing facts are now stale`):** Informational notice indicating that lookup tables in `data/indexes/` must be rebuilt using external index tools.
