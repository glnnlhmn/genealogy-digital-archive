<!--
Name: logger.md
Path: docs/lib/gda_core/logger.md
-->
# Technical Specification: GDALogger (Operational Logging)
<!-- Version: 1.1.0+build.20260930.1 -->

| Property | Value |
| :--- | :--- |
| **Module Name** | `logger.py` |
| **Module Path** | `tools/lib/gda_core/logger.py` |
| **Version** | `1.1.0+build.20260930.1` |
| **Test Suite** | `tests/gda_core/test_logger.py` |
| **Package** | `tools.lib.gda_core` |
| **Dependencies** | `logging`, `pathlib`, `datetime`, `re`, `sys` |

## 1. Developer Reference & API Specification

### Operational Intent
The logging subsystem provides standardized formatting, bracketed action tag extraction, dual interactive/file handlers, deterministic re-initialization guards, and fail-safe root fallbacks across all operational CLI workflows.

### Core API Methods

* `setup_logger(tool_name: str, log_dir: Optional[Path] = None, console_level: int = INFO, file_level: int = DEBUG, ephemeral: bool = False, force_reconfigure: bool = False) -> logging.Logger`
  * Attaches a console `StreamHandler` (defaulting to `INFO`) and a persistent `FileHandler` (defaulting to `DEBUG`).
  * Filename structure: `[tool_name]-[YYYYMMDD_HHMMSS].log`.
  * If `ephemeral=True`, routes logs to `config.CONFIG.temp` (`gtemp/`) instead of `logs/`.
  * If the target log directory cannot be created or written to, degrades safely to `config.CONFIG.root`, or falls back to console-only mode if the root is unwritable.
* `get_logger(name: str) -> logging.Logger`
  * Convenience accessor retrieving an active logger enriched with `GDALogFormatter`.
* `GDALogFormatter`
  * Custom log formatter parsing messages beginning with bracketed tags (e.g. `[SYS]`, `[NEW]`, `[ADD]`, `[SKIP]`) into normalized records:
    ```text
    2026-09-30 08:15:00 [NEW] Staged person entity IND-00042
    ```