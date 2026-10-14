<!--
Name: config.md
Path: docs/lib/gda_core/config.md
-->
# Technical Specification: GDAConfig (Filesystem Configuration)
<!-- Version: 1.1.0+build.20260930.1 -->

| Property | Value |
| :--- | :--- |
| **Module Name** | `config.py` |
| **Module Path** | `tools/lib/gda_core/config.py` |
| **Version** | `1.1.0+build.20260930.2` |
| **Test Suite** | `tests/gda_core/test_config.py` |
| **Package** | `tools.lib.gda_core` |
| **Dependencies** | `dataclasses`, `pathlib`, `os`, `json` |

## 1. Developer Reference & API Specification

### Operational Intent
`GDAConfig` is an immutable dataclass providing the central authority for all filesystem path resolution across the archive[cite: 8]. It discovers the repository root via explicit override, `GDA_ROOT` environment variables, canonical mount points, or upward directory traversal for marker files (`gda_config.json`, `.git`)[cite: 8].

### Core API Methods & Properties

* `GDAConfig.load(custom_root: Optional[Path] = None) -> GDAConfig`: Resolves and instantiates an immutable `GDAConfig` singleton[cite: 8]. Raises `FileNotFoundError` if no valid repository root marker can be located[cite: 8].
* `CONFIG`: Pre-instantiated global singleton initialized at module import time via `GDAConfig.load()`[cite: 8].
* `load_manifest() -> Dict[str, Any]`: Reads and parses `gda_config.json` from the repository root[cite: 8].

#### Primary Path Accessors

| Property | Type | Target Resolution Path | Operational Role |
| :--- | :--- | :--- | :--- |
| `root` | `Path` | `G:/My Drive/genealogy-digital-archive` | Repository anchor base directory[cite: 8]. |
| `temp` | `Path` | `root / "gtemp"` | Transient scratch and debug workspace[cite: 8]. |
| `logs` | `Path` | `root / "logs"` | Permanent runtime execution logs[cite: 8]. |
| `backups` | `Path` | `root / "backups"` | Pre-execution Safe Backup snapshots[cite: 8]. |
| `reports` | `Path` | `root / "reports"` | Audit summaries and consolidation reports[cite: 8]. |
| `data` | `Path` | `root / "data"` | Master production data store[cite: 8]. |
| `entities` | `Path` | `data / "entities"` | Production entity JSON stores[cite: 8]. |
| `quarantine` | `Path` | `entities / "quarantine"` | Staging quarantine for corrupted payloads[cite: 8]. |
| `indexes` | `Path` | `data / "indexes"` | Master lookup tables and cross-references[cite: 8]. |
| `media` | `Path` | `data / "media"` | Archival ingested media repository[cite: 8]. |
| `profiles` | `Path` | `data / "profiles"` | Operator and system tracking dossiers[cite: 8]. |
| `schemas` | `Path` | `root / "schemas"` | JSON schema definitions directory[cite: 8]. |
| `schema_defs` | `Path` | `schemas / "defs"` | Primitives, enums, and shared definitions[cite: 8]. |
| `schema_entities` | `Path` | `schemas / "entities"` | Structural schemas (`person`, `fact`)[cite: 8]. |
| `schema_indexes` | `Path` | `schemas / "indexes"` | Derived index schemas[cite: 8]. |
| `token_registry` | `Path` | `schemas / naming / "_token_registry.json"` | Controlled vocabulary file path[cite: 8]. |

---

## 2. Invariants & Defensive Behaviors

1. **Immutable Configuration:** The `GDAConfig` class is decorated with `@dataclass(frozen=True)` to prevent runtime attribute mutation[cite: 8].
2. **Dynamic Fallback Cascade:** Discovery checks `custom_root` first, then the `GDA_ROOT` environment variable, then the default production mount (`G:/My Drive/genealogy-digital-archive`), and finally climbs the active directory hierarchy[cite: 8].
3. **Hermetic Test Isolation:** Unit and integration tests decouple from the live filesystem by providing isolated sandboxes (`GDAConfig(root=tmp_path)`) patched directly onto `config.CONFIG`[cite: 1, 8].

---

## 3. Verification Harness & Diagnostics

* **Test Suite:** `tests/gda_core/test_config.py`
* **Markers:** `@pytest.mark.unit`, `@pytest.mark.smoke`, `@pytest.mark.regression`
* **Statement & Branch Coverage:** 100.00% (87 statements, 18 branches)

Execution syntax:
```powershell
pytest tests/gda_core/test_config.py --cov=tools.lib.gda_core.config --cov-report=term-missing -v