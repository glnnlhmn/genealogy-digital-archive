# Name: test_logger.py
# Path: tools/lib/gdacore/tests/test_logger.py
# Version: 1.0.0+build.rc1

"""Unit test harness for GDALogger logging infrastructure.

Operational Role:
    Validates message formatting, system tag insertion ([SYS]), record-level
    metadata handling, handler creation, target directory resolution, logger
    idempotency, factory mechanics, ephemeral routing, root fallback routing,
    console-only degradation, and GDALogger runtime introspection.

Test Structure & Protocol:
    - Atomized tests: 1:1 assertion mapping per test function.
    - Fully decorated: Explicitly decorated with @pytest.mark.unit; basic sanity
      checks tagged with @pytest.mark.smoke; boundary cases with @pytest.mark.regression.
    - Dependencies: Isolated to tools/lib/gdacore/src/gdacore/logger.py and config.py.
"""

from __future__ import annotations

__version__ = "1.0.0+build.rc1"

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from gdacore import config
from gdacore.config import GDAConfig
from gdacore.logger import GDALogFormatter, GDALogger, get_logger, setup_logger


# ==============================================================================
# GROUP 1: GDALogFormatter Formatting Contracts
# Note: Validates bracket parsing, level replacement, and custom format templates
# ==============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_formatter_renders_info_prefix() -> None:
    """Verify standard record renders with default level name in brackets."""
    formatter = GDALogFormatter()
    record = logging.LogRecord("tool", logging.INFO, __file__, 10, "Status update", (), None)
    assert "[INFO] Status update" in formatter.format(record)


@pytest.mark.unit
@pytest.mark.regression
def test_formatter_excludes_sys_tag_on_standard_record() -> None:
    """Verify standard record does not receive a SYS tag."""
    formatter = GDALogFormatter()
    record = logging.LogRecord("tool", logging.INFO, __file__, 10, "Status update", (), None)
    assert not formatter.format(record).startswith("[SYS]")


@pytest.mark.unit
@pytest.mark.smoke
def test_formatter_sys_event_prepends_sys_marker() -> None:
    """Verify sys_event=True assigns SYS tag to output."""
    formatter = GDALogFormatter()
    record = logging.LogRecord("tool", logging.INFO, __file__, 20, "DB connected", (), None)
    record.sys_event = True
    assert "[SYS] DB connected" in formatter.format(record)


@pytest.mark.unit
@pytest.mark.regression
def test_formatter_sys_event_avoids_duplicate_tags() -> None:
    """Verify already bracketed SYS message does not duplicate tags."""
    formatter = GDALogFormatter()
    record = logging.LogRecord("tool", logging.INFO, __file__, 30, "[SYS] Existing message", (), None)
    record.sys_event = True
    assert formatter.format(record).count("[SYS]") == 1


@pytest.mark.unit
@pytest.mark.regression
def test_formatter_extracts_custom_bracketed_tag() -> None:
    """Verify arbitrary bracketed tag replaces log level in output."""
    formatter = GDALogFormatter()
    record = logging.LogRecord("tool", logging.INFO, __file__, 40, "[ADD] Ingested entity", (), None)
    assert "[ADD] Ingested entity" in formatter.format(record)


@pytest.mark.unit
@pytest.mark.regression
def test_formatter_custom_bracketed_tag_suppresses_level_name() -> None:
    """Verify level name is omitted when bracketed tag is detected."""
    formatter = GDALogFormatter()
    record = logging.LogRecord("tool", logging.INFO, __file__, 40, "[ADD] Ingested entity", (), None)
    assert "[INFO]" not in formatter.format(record)


@pytest.mark.unit
@pytest.mark.regression
def test_formatter_custom_format_and_datefmt() -> None:
    """Verify custom fmt string template is respected by formatter."""
    formatter = GDALogFormatter(fmt="%(levelname)s|%(clean_msg)s", datefmt="%Y")
    record = logging.LogRecord("tool", logging.WARNING, __file__, 50, "Warn test", (), None)
    assert formatter.format(record) == "WARNING|Warn test"


# ==============================================================================
# GROUP 2: setup_logger & Handler Management
# Note: Validates stream/file handler lifecycle, flushing, and reconfig isolation
# ==============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_setup_logger_sets_tool_name(tmp_path: Path) -> None:
    """Verify logger instance name matches tool_name."""
    logger = setup_logger(tool_name="tool_alpha", log_dir=tmp_path)
    assert logger.name == "tool_alpha"


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_attaches_stream_and_file_handlers(tmp_path: Path) -> None:
    """Verify setup_logger attaches both console and file handlers."""
    logger = setup_logger(tool_name="tool_handlers", log_dir=tmp_path)
    assert len(logger.handlers) == 2


@pytest.mark.unit
@pytest.mark.smoke
def test_setup_logger_creates_destination_file(tmp_path: Path) -> None:
    """Verify setup_logger creates log file on disk in target directory."""
    logger = setup_logger(tool_name="tool_file", log_dir=tmp_path)
    logger.info("Executing alpha phase")
    for handler in logger.handlers:
        handler.flush()
    assert len(list(tmp_path.glob("tool_file-*.log"))) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_file_contains_logged_message(tmp_path: Path) -> None:
    """Verify log file contains formatted message content."""
    logger = setup_logger(tool_name="tool_msg", log_dir=tmp_path)
    logger.info("Content check message")
    for handler in logger.handlers:
        handler.flush()
    log_file = list(tmp_path.glob("tool_msg-*.log"))[0]
    assert "[INFO] Content check message" in log_file.read_text(encoding="utf-8")


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_idempotence_returns_same_instance(tmp_path: Path) -> None:
    """Verify repeated setup calls return identical logger instance."""
    logger1 = setup_logger(tool_name="tool_beta", log_dir=tmp_path)
    logger2 = setup_logger(tool_name="tool_beta", log_dir=tmp_path)
    assert logger1 is logger2


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_idempotence_preserves_handler_count(tmp_path: Path) -> None:
    """Verify repeated setup calls do not duplicate attached handlers."""
    logger1 = setup_logger(tool_name="tool_beta_handlers", log_dir=tmp_path)
    count = len(logger1.handlers)
    logger2 = setup_logger(tool_name="tool_beta_handlers", log_dir=tmp_path)
    assert len(logger2.handlers) == count


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_force_reconfigure_removes_old_handlers(tmp_path: Path) -> None:
    """Verify force_reconfigure flushes and detaches original handlers."""
    logger1 = setup_logger(tool_name="tool_reconfig", log_dir=tmp_path / "d1")
    old_file_handler = logger1.handlers[1]
    logger2 = setup_logger(tool_name="tool_reconfig", log_dir=tmp_path / "d2", force_reconfigure=True)
    assert old_file_handler not in logger2.handlers


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_force_reconfigure_targets_new_directory(tmp_path: Path) -> None:
    """Verify force_reconfigure routes subsequent logs to the new directory."""
    d2 = tmp_path / "d2"
    logger = setup_logger(tool_name="tool_reconfig_dir", log_dir=tmp_path / "d1")
    logger = setup_logger(tool_name="tool_reconfig_dir", log_dir=d2, force_reconfigure=True)
    logger.info("Redirected message")
    for handler in logger.handlers:
        handler.flush()
    assert len(list(d2.glob("tool_reconfig_dir-*.log"))) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_force_reconfigure_handles_handler_close_failure(tmp_path: Path) -> None:
    """Verify force_reconfigure gracefully handles exceptions raised during handler close."""
    logger = logging.getLogger("tool_reconfig_failing_handler")
    logger.handlers.clear()

    faulty_handler = MagicMock(spec=logging.Handler)
    faulty_handler.flush.side_effect = RuntimeError("Flush failure")
    faulty_handler.close.side_effect = RuntimeError("Close failure")
    logger.addHandler(faulty_handler)

    reconfigured = setup_logger(
        tool_name="tool_reconfig_failing_handler",
        log_dir=tmp_path,
        force_reconfigure=True,
    )
    assert faulty_handler not in reconfigured.handlers
    assert len(reconfigured.handlers) == 2


# ==============================================================================
# GROUP 3: Destination Routing & Fallback Degradation
# Note: Validates ephemeral routing, root fallback on disk errors, and console mode
# ==============================================================================

@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_ephemeral_routing_creates_temp_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify ephemeral=True directs log destination to CONFIG.temp."""
    sandbox_config = GDAConfig(root=tmp_path.resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)
    setup_logger(tool_name="tool_ephemeral", ephemeral=True, force_reconfigure=True)
    assert len(list(sandbox_config.temp.glob("tool_ephemeral-*.log"))) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_default_routing_creates_logs_dir_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify default routing directs log destination to CONFIG.logs."""
    sandbox_config = GDAConfig(root=tmp_path.resolve())
    monkeypatch.setattr(config, "CONFIG", sandbox_config)
    setup_logger(tool_name="tool_prod", ephemeral=False, force_reconfigure=True)
    assert len(list(sandbox_config.logs.glob("tool_prod-*.log"))) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_fallback_to_root_writes_log_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify target directory failure redirects log file creation to repository root."""
    root_dir = (tmp_path / "repo_root").resolve()
    root_dir.mkdir()
    sandbox_config = GDAConfig(root=root_dir)
    monkeypatch.setattr(config, "CONFIG", sandbox_config)

    target_dir = (tmp_path / "failing_dir").resolve()
    original_mkdir = Path.mkdir

    def mock_mkdir(self, *args, **kwargs):
        if self.resolve() == target_dir:
            raise OSError("Target drive inaccessible")
        return original_mkdir(self, *args, **kwargs)

    with patch.object(Path, "mkdir", side_effect=mock_mkdir, autospec=True):
        setup_logger(tool_name="tool_root_fallback", log_dir=target_dir, force_reconfigure=True)

    assert len(list(root_dir.glob("tool_root_fallback-*.log"))) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_fallback_to_root_emits_stderr_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify directory failure logs warning message to stderr."""
    root_dir = (tmp_path / "repo_root").resolve()
    root_dir.mkdir()
    sandbox_config = GDAConfig(root=root_dir)
    monkeypatch.setattr(config, "CONFIG", sandbox_config)

    target_dir = (tmp_path / "failing_dir").resolve()
    original_mkdir = Path.mkdir

    def mock_mkdir(self, *args, **kwargs):
        if self.resolve() == target_dir:
            raise OSError("Target drive inaccessible")
        return original_mkdir(self, *args, **kwargs)

    with patch.object(Path, "mkdir", side_effect=mock_mkdir, autospec=True):
        setup_logger(tool_name="tool_root_warn", log_dir=target_dir, force_reconfigure=True)

    assert "Logging redirected to root" in capsys.readouterr().err


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_unwriteable_root_degrades_to_single_handler(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify failure of root file logging degrades logger to single console handler."""
    root_dir = (tmp_path / "repo_root").resolve()
    root_dir.mkdir()
    sandbox_config = GDAConfig(root=root_dir)
    monkeypatch.setattr(config, "CONFIG", sandbox_config)

    target_dir = (tmp_path / "failing_dir").resolve()

    with patch.object(Path, "mkdir", side_effect=OSError("Disk failure")):
        with patch("logging.FileHandler", side_effect=PermissionError("Permission denied")):
            logger = setup_logger(tool_name="tool_console_degrade", log_dir=target_dir, force_reconfigure=True)

    assert len(logger.handlers) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_setup_logger_unwriteable_root_emits_console_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify failure of root file logging emits console-only warning to stderr."""
    root_dir = (tmp_path / "repo_root").resolve()
    root_dir.mkdir()
    sandbox_config = GDAConfig(root=root_dir)
    monkeypatch.setattr(config, "CONFIG", sandbox_config)

    target_dir = (tmp_path / "failing_dir").resolve()

    with patch.object(Path, "mkdir", side_effect=OSError("Disk failure")):
        with patch("logging.FileHandler", side_effect=PermissionError("Permission denied")):
            setup_logger(tool_name="tool_console_warn", log_dir=target_dir, force_reconfigure=True)

    assert "Running in console-only mode" in capsys.readouterr().err


# ==============================================================================
# GROUP 4: get_logger & GDALogger Facade Contracts
# Note: Validates stream logger reuse and IntrospectableMixin integration
# ==============================================================================

@pytest.mark.unit
@pytest.mark.smoke
def test_get_logger_attaches_single_handler() -> None:
    """Verify get_logger creates a stream handler on a fresh logger."""
    logger = get_logger("tool_get_logger_count")
    assert len(logger.handlers) == 1


@pytest.mark.unit
@pytest.mark.regression
def test_get_logger_uses_stream_handler() -> None:
    """Verify attached handler is an instance of StreamHandler."""
    logger = get_logger("tool_get_logger_type")
    assert isinstance(logger.handlers[0], logging.StreamHandler)


@pytest.mark.unit
@pytest.mark.regression
def test_get_logger_uses_gda_formatter() -> None:
    """Verify attached handler uses GDALogFormatter."""
    logger = get_logger("tool_get_logger_formatter")
    assert isinstance(logger.handlers[0].formatter, GDALogFormatter)


@pytest.mark.unit
@pytest.mark.regression
def test_get_logger_idempotent_handler_count() -> None:
    """Verify repeated get_logger calls preserve single handler attachment."""
    get_logger("tool_get_idempotent")
    logger = get_logger("tool_get_idempotent")
    assert len(logger.handlers) == 1


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_logger_facade_setup_delegates_to_setup_logger(tmp_path: Path) -> None:
    """Verify GDALogger.setup_logger returns a properly configured logger."""
    logger = GDALogger.setup_logger(tool_name="tool_facade_setup", log_dir=tmp_path)
    assert logger.name == "tool_facade_setup"


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_logger_facade_get_logger_delegates_to_get_logger() -> None:
    """Verify GDALogger.get_logger returns a valid logger instance."""
    logger = GDALogger.get_logger("tool_facade_get")
    assert logger.name == "tool_facade_get"


@pytest.mark.unit
@pytest.mark.smoke
def test_gda_logger_facade_introspectable_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify GDALogger inherits IntrospectableMixin and renders directory help."""
    GDALogger.help()
    captured = capsys.readouterr().out
    assert "=== GDALogger Public Directory ===" in captured