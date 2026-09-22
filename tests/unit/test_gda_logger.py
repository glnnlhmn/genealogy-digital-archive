# Name: test_gda_logger.py
# Path: tests/unit/test_gda_logger.py

import logging
from pathlib import Path
import pytest

from tools.lib.gda_core.GDALogger import GDALogFormatter, setup_logger


class TestGDALogFormatter:
    """Validates message formatting and system tag insertion."""

    def test_standard_formatting(self):
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
        assert not output.startswith("[SYS]")

    def test_sys_event_tagging(self):
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
        record.sys_event = True  # Emulate extra={"sys_event": True}
        output = formatter.format(record)
        assert "[INFO] [SYS] Database connection established" in output

    def test_sys_event_avoids_duplicate_tags(self):
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

    def test_logger_creation_in_custom_directory(self, tmp_path: Path):
        log_dir = tmp_path / "custom_logs"
        logger = setup_logger(tool_name="tool_alpha", log_dir=log_dir)

        assert logger.name == "tool_alpha"
        assert len(logger.handlers) == 2  # 1 FileHandler, 1 StreamHandler
        assert log_dir.exists()

        log_files = list(log_dir.glob("tool_alpha-*.log"))
        assert len(log_files) == 1

        logger.info("Executing alpha phase")
        # Flush handlers to disk
        for handler in logger.handlers:
            handler.flush()

        log_content = log_files[0].read_text(encoding="utf-8")
        assert "[INFO] Executing alpha phase" in log_content

    def test_logger_idempotence(self, tmp_path: Path):
        log_dir = tmp_path / "idempotent_logs"
        logger1 = setup_logger(tool_name="tool_beta", log_dir=log_dir)
        initial_handlers_count = len(logger1.handlers)

        logger2 = setup_logger(tool_name="tool_beta", log_dir=log_dir)
        assert logger1 is logger2
        assert len(logger2.handlers) == initial_handlers_count

    def test_ephemeral_routing(self, monkeypatch, tmp_path: Path):
        from tools.lib.gda_core import GDAConfig

        temp_target = tmp_path / "custom_temp"
        # Patch the class property getter so frozen dataclass assignment checks are bypassed
        monkeypatch.setattr(GDAConfig.GDAConfig, "temp", property(lambda self: temp_target))

        logger = setup_logger(tool_name="scratch_tool", ephemeral=True)
        assert temp_target.exists()

        log_files = list(temp_target.glob("scratch_tool-*.log"))
        assert len(log_files) == 1