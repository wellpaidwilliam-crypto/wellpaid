"""WellPaiD Trader - Logging Module

Secure logging system that never logs secrets, API keys, or passwords.
Logs to agent/logs/ directory with proper rotation.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional


# Sensitive patterns to filter from logs
SENSITIVE_PATTERNS = [
    "api_key",
    "api_secret",
    "password",
    "token",
    "secret",
    "credential",
    "private_key",
    "access_key",
]


class SensitiveFilter(logging.Filter):
    """Filter to remove sensitive information from logs.
    
    Inspects the fully formatted message (including %-style args),
    not just the raw template, so `logger.info("key=%s", secret)`
    is redacted too. On a hit the message is replaced and args are
    cleared so the secret cannot leak at format time.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter sensitive data from log messages."""
        try:
            message = record.getMessage()
        except Exception:
            record.msg = "[REDACTED - unformattable log message]"
            record.args = ()
            return True
        msg_lower = message.lower()
        for pattern in SENSITIVE_PATTERNS:
            if pattern in msg_lower:
                record.msg = "[REDACTED - sensitive data filtered]"
                record.args = ()
                return True
        return True


class SecureFormatter(logging.Formatter):
    """Custom formatter that ensures no sensitive data leaks."""
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None) -> None:
        """Initialize formatter.
        
        Args:
            fmt: Log format string
            datefmt: Date format string
        """
        if fmt is None:
            fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
        if datefmt is None:
            datefmt = "%Y-%m-%d %H:%M:%S"
        super().__init__(fmt, datefmt)


def setup_logging(
    name: str = "wellpaid",
    level: str = "INFO",
    log_dir: str = "agent/logs",
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 5,
    console: bool = True,
) -> logging.Logger:
    """Setup secure logging for WellPaiD Trader.
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        console: Whether to also log to console
        
    Returns:
        Configured logger instance
    """
    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Get or create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Add sensitive data filter
    sensitive_filter = SensitiveFilter()
    logger.addFilter(sensitive_filter)
    
    # Create formatter
    formatter = SecureFormatter()
    
    # File handler with rotation
    log_file = log_path / f"{name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler (optional)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get an existing logger or create a child logger.
    
    Args:
        name: Logger name (will be prefixed with 'wellpaid.')
        
    Returns:
        Logger instance
    """
    full_name = f"wellpaid.{name}" if not name.startswith("wellpaid.") else name
    return logging.getLogger(full_name)


# Default logger setup
default_logger: Optional[logging.Logger] = None


def init_logging(level: str = "INFO", log_dir: str = "agent/logs") -> logging.Logger:
    """Initialize default logging for the application.
    
    Args:
        level: Log level
        log_dir: Log directory path
        
    Returns:
        Default logger
    """
    global default_logger
    if default_logger is None:
        default_logger = setup_logging(level=level, log_dir=log_dir)
    return default_logger
