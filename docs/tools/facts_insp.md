# Technical Runbook: FACTS_INSP (Fact Registry Inspection Engine)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `facts_insp.py` |
| **Script Path** | `tools/ops/facts_insp.py` |
| **Version** | `1.0.1+build.20260922.1` |
| **Test Suite** | `tests/integration/test_facts_insp.py` |
| **Log Output** | `logs/facts_insp-[YYYYMMDD_HHMMSS].log` |
| **Summary Report** | `reports/facts_audit_summary_[timestamp].json` |
| **Merge Proposals** | `reports/fact_merge_candidates_[timestamp].csv` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
`facts_insp.py` is the validation and auditing engine for `data/entities/facts.json`. It verifies schema conformance, controlled vocabularies, biological plausibility against `people.json`, deduplication, and relational partnership reciprocity.

### CLI Syntax
```powershell
python tools/ops/facts_insp.py [-v] [--debug]
```

### Options & Parameter Reference
* `-v, --verbose`: Logs detailed diagnostic traces to `logs/facts_insp-[timestamp].log`.
* `--debug`: Outputs live execution traces directly to stderr.

### Quick Runbook
Execute fact inspection audit:
```powershell
python tools/ops/facts_insp.py
```
Execute audit with verbose logging:
```powershell
python tools/ops/facts_insp.py --verbose
```

---

## 2. Technical Architecture & Data Lifecycle

### The Four-Tier Audit Pipeline
* **Stage 1 (Schema & Vocabulary Conformance):** Verifies UUID formatting on fact IDs. Validates `fact_type` and date modifiers against `SchemaEnums`.
* **Stage 2 (Biological & Chronological Plausibility):** Traverses lifespans from `people.json`. Flags facts occurring before birth as errors. Flags post-mortem assertions as errors, with mandatory exemptions for post-mortem relational types: `Death`, `Burial`, `Probate`, `Association`, and `Parentage`.
* **Stage 3 (Deduplication & Merge Proposals):** Detects redundant extractions sharing identical source URNs (`Dedup-Source`) and corroborating records representing the same event (`Dedup-Event`). Emits `reports/fact_merge_candidates_[timestamp].csv`.
* **Stage 4 (Relational Consistency):** Validates spouse and partner linkages across records for reciprocal pairing.

### Framework Integration
* `tools.lib.gda_core.GDAConfig.CONFIG`: Resolves paths to facts, people, reports, and schemas.
* `tools.lib.gda_core.GDALogger.setup_logger`: Configures `[SYS]` event-aware logging.
* `tools.lib.gda_core.GDAUtil.GDAUtil`: Coordinates atomic JSON loading and reporting exports.
* `tools.lib.gda_core.registry.SchemaEnums`: Provides authoritative enums loaded from `_enums.schema.json`.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/integration/test_facts_insp.py`
* **Execution:**
```powershell
pytest tests/integration/test_facts_insp.py -v
```

### Diagnostic Matrix
* **Biological Error (`Post-mortem assertion`):** Non-exempt fact occurred after subject death year. If record represents an administrative/parentage assertion, verify `fact_type` matches an exempted type.
* **Merge Proposal CSV Emitted:** Inspect `reports/fact_merge_candidates_[timestamp].csv` for proposed fact consolidations.
