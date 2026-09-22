# MIPLET-001: Testing Protocol for Frozen Architecture & Dynamic Config Mocking
<!-- Version: 1.0.0 -->
<!-- Status: Staged for next MIP synthesis (Target: v1.0.6) -->

## Context & Problem Statement
GDAConfig is implemented as a @dataclass(frozen=True) where directory topology anchors
(CONFIG.backups, CONFIG.reports, CONFIG.logs, CONFIG.facts, etc.) are computed @property
methods derived from self.root.

Directly monkeypatching computed properties or attributes on the instantiated CONFIG
singleton (e.g., monkeypatch.setattr('tools.lib.gda_core.GDAConfig.CONFIG.backups', ...)
or monkeypatch.setattr(CONFIG, 'backups', ...)) raises:
  dataclasses.FrozenInstanceError: cannot assign to field 'backups'

## Standard Mocking Protocol for Pytest Harnesses
When testing tools or libraries that import CONFIG:
1. Never attempt in-place attribute assignment on an existing GDAConfig instance.
2. Instantiate an isolated configuration instance rooted at tmp_path:
   ```python
   mock_config = GDAConfig(root=tmp_path, manifest={})
   ```
3. Rebind the module-level singleton reference across the core framework and all
   consuming operational modules under test:
   ```python
   monkeypatch.setattr('tools.lib.gda_core.GDAConfig.CONFIG', mock_config)
   monkeypatch.setattr('tools.lib.gda_core.GDAUtil.CONFIG', mock_config)
   monkeypatch.setattr('tools.ops.[target_tool].CONFIG', mock_config)
   ```
4. All derived properties (mock_config.backups, mock_config.reports, mock_config.facts, etc.)
   automatically resolve within the isolated test temporary workspace without raising
   FrozenInstanceError.
