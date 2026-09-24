# Name: GDALogger.py
# Path: tools/lib/gda_core/GDALogger.py

import os
import sys
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from tools.lib.gda_core.GDAConfig import CONFIG


class GDALogFormatter(logging.Formatter):
    """
    Standardized log formatter for GDA operational tools.
    Renders timestamp, a single bracketed tag, and message.
    If a tag ([SYS], [NEW], [ADD], [SKIP], etc.) is present or sys_event is True,
    it replaces [%(levelname)s]; otherwise defaults to [%(levelname)s].
    """
    DEFAULT_FORMAT = "%(asctime)s [%(tag)s] %(clean_msg)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    TAG_REGEX = re.compile(r"^\s*\[([A-Za-z0-9_\-]+)\]\s*(.*)$")

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt=fmt or self.DEFAULT_FORMAT, datefmt=datefmt or self.DATE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        raw_msg = record.getMessage()

        # Check for inline tag in message
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


def setup_logger(
    tool_name: str,
    log_dir: Optional[Path] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    ephemeral: bool = False,
) -> logging.Logger:
    """
    Initializes and configures a standard logger for archive operations.
    """
    logger = logging.getLogger(tool_name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    target_dir = log_dir or (CONFIG.temp if ephemeral else CONFIG.logs)
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = target_dir / f"{tool_name}-{timestamp}.log"

    formatter = GDALogFormatter()

    # 1. File Handler (Full Detail)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 2. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger
