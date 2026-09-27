# Name: test_gda_logger.py
# Path: tests/unit/test_gda_logger.py
# Version: 1.0.1+build.20260927.01

"""Unit test harness for GDALogger logging infrastructure.

Operational Role:
    Validates message formatting, system tag insertion ([SYS]), record-level
    metadata handling, handler creation, target directory resolution, logger
    idempotency, and ephemeral session routing.

Test Structure & Protocol:
    - Atomized tests: Separate methods evaluate standard formatting, sys_event
      tags, deduplication, file logging, handler counts, and temp routing.
    - Fully decorated: All tests marked with @pytest.mark.unit; basic sanity
      checks tagged with @pytest.mark.smoke; boundary cases with @pytest.mark.regression.
    - Dependencies: Isolated to tools/lib/gda_core/GDALogger.py.
"""

from __future__ import annotations

import logging
from pathlib import Path
import pytest

from tools.lib.gda_core.GDALogger import GDALogFormatter, setup_logger

pytestmark = pytest.mark.unit


class TestGDALogFormatter:
    """Validates message formatting and system tag insertion."""

    @pytest.mark.smoke
    def test_standard_formatting_renders_info_prefix(self) -> None:
        formatter = GDALogFormatter()
        record = logging.LogRecord(
            name="test_tool",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Standard status update",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "[INFO] Standard status update" in output

    @pytest.mark.regression
    def test_standard_formatting_excludes_sys_tag(self) -> None:
        formatter = GDALogFormatter()
        record = logging.LogRecord(
            name="test_tool",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Standard status update",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert not output.startswith("[SYS]")

    @pytest.mark.smoke
    def test_sys_event_tagging_prepends_sys_marker(self) -> None:
        formatter = GDALogFormatter()
        record = logging.LogRecord(
            name="test_tool",
            level=logging.INFO,
            pathname=__file__,
            lineno=20,
            msg="Database connection established",
            args=(),
            exc_info=None,
        )
        record.sys_event = True
        output = formatter.format(record)
        assert "[SYS] Database connection established" in output

    @pytest.mark.regression
    def test_sys_event_avoids_duplicate_tags(self) -> None:
        formatter = GDALogFormatter()
        record = logging.LogRecord(
            name="test_tool",
            level=logging.INFO,
            pathname=__file__,
            lineno=30,
            msg="[SYS] Already tagged message",
            args=(),
            exc_info=None,
        )
        record.sys_event = True
        output = formatter.format(record)
        assert output.count("[SYS]") == 1


class TestSetupLogger:
    """Validates logger configuration, handlers, and destination paths."""

    @pytest.mark.smoke
    def test_logger_creation_sets_proper_name(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "custom_logs"
        logger = setup_logger(tool_name="tool_alpha", log_dir=log_dir)
        assert logger.name == "tool_alpha"

    @pytest.mark.regression
    def test_logger_creation_attaches_dual_handlers(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "custom_logs"
        logger = setup_logger(tool_name="tool_alpha_handlers", log_dir=log_dir)
        assert len(logger.handlers) == 2  # 1 FileHandler, 1 StreamHandler

    @pytest.mark.smoke
    def test_logger_creates_destination_file(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "custom_logs"
        logger = setup_logger(tool_name="tool_alpha_file", log_dir=log_dir)
        logger.info("Executing alpha phase")
        for handler in logger.handlers:
            handler.flush()
        log_files = list(log_dir.glob("tool_alpha_file-*.log"))
        assert len(log_files) == 1
        log_content = log_files[0].read_text(encoding="utf-8")
        assert "[INFO] Executing alpha phase" in log_content

    @pytest.mark.regression
    def test_logger_idempotence_returns_same_instance(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "idempotent_logs"
        logger1 = setup_logger(tool_name="tool_beta", log_dir=log_dir)
        logger2 = setup_logger(tool_name="tool_beta", log_dir=log_dir)
        assert logger1 is logger2

    @pytest.mark.regression
    def test_logger_idempotence_preserves_handler_count(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "idempotent_logs"
        logger1 = setup_logger(tool_name="tool_beta_handlers", log_dir=log_dir)
        count = len(logger1.handlers)
        logger2 = setup_logger(tool_name="tool_beta_handlers", log_dir=log_dir)
        assert len(logger2.handlers) == count

    @pytest.mark.regression
    def test_ephemeral_routing_targets_temp_directory(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from tools.lib.gda_core import GDAConfig

        temp_target = tmp_path / "custom_temp"
        monkeypatch.setattr(GDAConfig.GDAConfig, "temp", property(lambda self: temp_target))

        logger = setup_logger(tool_name="scratch_tool", ephemeral=True)
        assert temp_target.exists()
        log_files = list(temp_target.glob("scratch_tool-*.log"))
        assert len(log_files) == 1