# Name: GDALogger.py
# Path: tools/lib/gda_core/GDALogger.py

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from tools.lib.gda_core.GDAConfig import CONFIG


class GDALogFormatter(logging.Formatter):
    """
    Standardized log formatter for GDA operational tools.
    Formats logs with timestamp, level tag, and optional record tags.
    """
    DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt=fmt or self.DEFAULT_FORMAT, datefmt=datefmt or self.DATE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        # Prepend [SYS] tag to system events if marked via extra
        if getattr(record, "sys_event", False) and not record.msg.startswith("[SYS]"):
            record.msg = f"[SYS] {record.msg}"
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
    
    Args:
        tool_name: The script/tool name (e.g., 'facts_md', 'gsi').
        log_dir: Optional target log directory. Defaults to CONFIG.logs (or CONFIG.temp if ephemeral).
        console_level: Minimum logging level for stdout/stderr.
        file_level: Minimum logging level for file log.
        ephemeral: If True, writes to CONFIG.temp rather than CONFIG.logs.
    """
    logger = logging.getLogger(tool_name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if logger was already initialized
    if logger.handlers:
        return logger

    # Resolve target directory
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

    # 2. Console Handler (Streamlined Output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger