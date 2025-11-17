"""Centralized logging configuration for Blockscope."""

import logging
import logging.handlers
from pathlib import Path
from .config import Config


def setup_logging(config: Config) -> None:
    """
    Initialize logging system based on configuration.
    
    Args:
        config: Configuration instance with logging settings
    """
    # Determine log directory
    log_dir = config.log_dir
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    
    # Create archive subdirectory
    archive_dir = log_dir_path / "archive"
    archive_dir.mkdir(exist_ok=True)
    
    # Get log levels
    file_level = getattr(logging, config.log_level.upper(), logging.INFO)
    console_level = getattr(logging, config.console_level.upper(), logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(min(file_level, console_level))
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # File handler with rotation
    rotation_config = config.log_rotation
    main_log_path = log_dir_path / "feesentinel.log"
    error_log_path = log_dir_path / "feesentinel-error.log"
    
    # Main log file handler (rotating by time)
    if rotation_config.get("when") == "midnight":
        file_handler = logging.handlers.TimedRotatingFileHandler(
            main_log_path,
            when="midnight",
            interval=1,
            backupCount=rotation_config.get("backup_count", 30),
            encoding="utf-8"
        )
        # Move rotated files to archive directory
        def namer(name):
            return str(archive_dir / Path(name).name)
        file_handler.namer = namer
    else:
        # Size-based rotation
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_path,
            maxBytes=rotation_config.get("max_bytes", 10485760),
            backupCount=rotation_config.get("backup_count", 30),
            encoding="utf-8"
        )
    
    file_handler.setLevel(file_level)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Error-only log file handler
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_path,
        maxBytes=rotation_config.get("max_bytes", 10485760),
        backupCount=rotation_config.get("backup_count", 30),
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter(
        '[%(levelname)-8s] [%(name)s] %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific component.
    
    Args:
        name: Logger name (typically __name__ or component name)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

