# Technical Runbook: GAM (Genealogy Archive Manager)

| Property | Value |
| :--- | :--- |
| **Tool Name** | `gam.py` (formerly `gna.py`) |
| **Script Path** | `tools/ops/gam.py` |
| **Version** | `1.0.7+build.20260922.1` |
| **Test Suite** | `tests/integration/test_gam.py` |
| **Log Output** | `logs/gam-[YYYYMMDD_HHMMSS].log` |
| **Report Output** | `reports/gam_audit_[YYYYMMDD_HHMMSS].[json/md]` |

---

## 1. Operator Reference & Quick-Start

### Operational Intent
GAM is the archive's baseline guardian. It ensures that every active JSON schema and Markdown prompt in the archive tree has a valid semantic version and matches its recorded SHA-256 baseline digest.

### CLI Syntax
```powershell
python tools/ops/gam.py [-a] [-g] [-r {json,md,all}] [--repair] [-v] [--debug]
```

### Options & Parameter Reference
* `-a, --audit`: Executes system integrity audit against `gda_config.json`.
* `-g, --generate-config`: Scans `schemas/` and `prompts/`, backs up existing manifest to `gda_config.json.bk`, and writes a new baseline.
* `-r, --report {json,md,all}`: Export format for reports in `reports/` (Default: `all`).
* `--repair`: Parses latest audit report and auto-repairs `UNKNOWN` versions to `0.0.999`.
* `-v, --verbose`: Logs detailed diagnostics to `logs/gam-[timestamp].log`.
* `--debug`: Outputs live execution traces directly to stderr.

### Quick Runbook
Refresh configuration baseline:
```powershell
python tools/ops/gam.py --generate-config
```
Execute full audit and export JSON + Markdown reports:
```powershell
python tools/ops/gam.py --audit --report all
```
Auto-repair unversioned assets:
```powershell
python tools/ops/gam.py --repair
```

---

## 2. Technical Architecture & Data Lifecycle

### Pipeline Execution Stages
1. **Asset Discovery:** Recursively scans `schemas/` (`*.json`) and `prompts/` (`*.md`), automatically omitting `archive/` folders and temporary backups.
2. **Metadata Extraction:** Extracts version strings from JSON (`SchemaVersion`, `version`, `FileVersion`) and Markdown headers (`<!-- Version: X.Y.Z -->`).
3. **Safe Backup & Baseline Generation:** Backs up `gda_config.json` to `gda_config.json.bk`, computes SHA-256 hashes via `GDAUtil.compute_sha256()`, and saves the manifest.
4. **Audit State Classification:**
   * `OK`: Match across path, version, and content hash.
   * `DRIFT`: Internal version modified or file content hash altered since baseline generation.
   * `UNTRACKED`: File exists on disk but is absent from `gda_config.json`.
   * `ERROR`: File version is `UNKNOWN`.
5. **Remediation Protocol:** Reads the latest `reports/gam_audit_*.json` run, injects `0.0.999` into non-compliant headers, and re-triggers baseline generation.

### Framework Integration
* `tools.lib.gda_core.GDAConfig.CONFIG`: Resolves root anchor and manifest path.
* `tools.lib.gda_core.GDALogger.setup_logger`: Configures `[SYS]` event-aware logging.
* `tools.lib.gda_core.GDAUtil.GDAUtil`: Coordinates atomic file writing and SHA-256 hashing.

---

## 3. Verification Harness & Diagnostics

### Test Suite
* **Location:** `tests/integration/test_gam.py`
* **Execution:**
```powershell
pytest tests/integration/test_gam.py -v
```

### Diagnostic Matrix
* **Exit Code 1 (`gda_config.json missing`):** Run `python tools/ops/gam.py --generate-config` to initialize the baseline manifest.
* **Audit State `DRIFT`:** Asset content changed legitimately. Run `--generate-config` to accept changes into the baseline.
* **Audit State `ERROR`:** Run `--repair` to force standard version headers into unversioned assets.
