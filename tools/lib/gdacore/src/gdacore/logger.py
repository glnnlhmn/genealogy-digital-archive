# Name: logger.py
# Path: tools/lib/gdacore/src/gdacore/logger.py
# Version: 1.0.0+build.rc1

"""Provide standardized logging subsystems for GDA operational workflows.

Provides consistent log formatting (GDALogFormatter), dual interactive/file
handlers, system event tagging ([SYS]), ephemeral session routing,
deterministic re-initialization guards, and fail-safe root directory fallbacks.
"""

from __future__ import annotations

__version__ = "1.0.0+build.rc1"

from datetime import datetime
import logging
from pathlib import Path
import re
import sys

from gdacore import config
from gdacore.introspectable import IntrospectableMixin


class GDALogFormatter(logging.Formatter):
    """Standardize log formatting across GDA operational tools.

    Renders timestamps, a single bracketed action tag, and clean message content.
    If an explicit bracketed tag ([SYS], [NEW], [ADD], [SKIP], etc.) is detected
    in the payload or sys_event is True, it replaces the default [%(levelname)s]
    segment.
    """

    DEFAULT_FORMAT = "%(asctime)s [%(tag)s] %(clean_msg)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    TAG_REGEX = re.compile(r"^\s*\[([A-Za-z0-9_\-]+)\]\s*(.*)$")

    def __init__(self, fmt: str | None = None, datefmt: str | None = None):
        """Initialize formatter with custom or default templates.

        Args:
            fmt: Optional log format template string.
            datefmt: Optional strftime-compatible date format template.
        """
        super().__init__(fmt=fmt or self.DEFAULT_FORMAT, datefmt=datefmt or self.DATE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        """Format the specified record with parsed bracketed action tags.

        Args:
            record: The logging.LogRecord instance to format.

        Returns:
            Fully formatted and tag-resolved log string.
        """
        raw_msg = record.getMessage()

        match = self.TAG_REGEX.match(raw_msg)
        if match:
            record.tag = match.group(1).upper()
            record.clean_msg = match.group(2)
        elif getattr(record, "sys_event", False):
            record.tag = "SYS"
            record.clean_msg = raw_msg
        else:
            record.tag = record.levelname
            record.clean_msg = raw_msg

        return super().format(record)


class GDALogger(IntrospectableMixin):
    """Provide centralized logging management and factory dispatchers.

    Acts as an introspectable facade over setup_logger and get_logger, exposing
    standardized logger configuration for tools and library components.
    """

    @classmethod
    def setup_logger(
        cls,
        tool_name: str,
        log_dir: Path | None = None,
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        ephemeral: bool = False,
        force_reconfigure: bool = False,
    ) -> logging.Logger:
        """Initialize and configure a standard logger for archive operations.

        If target directory creation or file handler attachment fails, logs fall
        back directly to config.CONFIG.root. If root is unwriteable, execution
        degrades to console-only output with an alert emitted to sys.stderr.

        Args:
            tool_name: Name of the operational tool or script.
            log_dir: Optional explicit directory for destination log files.
            console_level: Logging severity threshold for the console StreamHandler.
            file_level: Logging severity threshold for the persistent FileHandler.
            ephemeral: If True, defaults storage to config.CONFIG.temp (gtemp/).
            force_reconfigure: If True, flushes and resets existing handlers.

        Returns:
            Configured logging.Logger instance.
        """
        return setup_logger(
            tool_name=tool_name,
            log_dir=log_dir,
            console_level=console_level,
            file_level=file_level,
            ephemeral=ephemeral,
            force_reconfigure=force_reconfigure,
        )

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Retrieve a standard GDA logger enriched with GDALogFormatter console output.

        Args:
            name: Name or hierarchical category of the logger.

        Returns:
            A logging.Logger instance with GDALogFormatter attached.
        """
        return get_logger(name)


def setup_logger(
    tool_name: str,
    log_dir: Path | None = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    ephemeral: bool = False,
    force_reconfigure: bool = False,
) -> logging.Logger:
    """Initialize and configure a standard logger for archive operations.

    Args:
        tool_name: Name of the operational tool or script.
        log_dir: Optional explicit directory for destination log files.
        console_level: Logging severity threshold for the console StreamHandler.
        file_level: Logging severity threshold for the persistent FileHandler.
        ephemeral: If True, defaults storage to config.CONFIG.temp (gtemp/).
        force_reconfigure: If True, flushes and resets existing handlers.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(tool_name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers and not force_reconfigure:
        return logger

    if force_reconfigure:
        for handler in list(logger.handlers):
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
            logger.removeHandler(handler)

    formatter = GDALogFormatter()

    # 1. Console Handler (Always attached first)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. File Handler Resolution & Safe Fallback
    target_dir = log_dir or (config.CONFIG.temp if ephemeral else config.CONFIG.logs)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        log_file = target_dir / f"{tool_name}-{timestamp}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as err:
        fallback_dir = config.CONFIG.root
        fallback_file = fallback_dir / f"{tool_name}-{timestamp}.log"
        try:
            file_handler = logging.FileHandler(fallback_file, encoding="utf-8")
            file_handler.setLevel(file_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            sys.stderr.write(
                f"[WARN] Failed to write to {target_dir} ({err}). Logging redirected to root: {fallback_dir}\n"
            )
        except (OSError, PermissionError) as fallback_err:
            sys.stderr.write(
                f"[WARN] Failed to attach root file logging ({fallback_err}). Running in console-only mode.\n"
            )

    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Retrieve a standard GDA logger enriched with GDALogFormatter console output.

    Args:
        name: Name or hierarchical category of the logger.

    Returns:
        A logging.Logger instance with GDALogFormatter attached.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(GDALogFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger