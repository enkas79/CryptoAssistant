"""
Logger Module for CryptoAssistant
Provides centralized logging configuration for the application.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class CryptoLogger:
    """
    Centralized logger for CryptoAssistant application.
    Configures logging to both file and console with rotating file handler.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one logger instance."""
        if cls._instance is None:
            cls._instance = super(CryptoLogger, cls).__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        name: str = "CryptoAssistant",
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        max_bytes: int = 5 * 1024 * 1024,  # 5MB
        backup_count: int = 5
    ):
        """
        Initialize the logger.
        
        Args:
            name (str): Name of the logger.
            log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            log_file (Optional[str]): Path to the log file. If None, uses default location.
            max_bytes (int): Maximum size of log file before rotation.
            backup_count (int): Number of backup log files to keep.
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Set up formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with rotation
        if log_file is None:
            # Default log directory
            project_root = Path(__file__).parent.parent.parent
            log_dir = project_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"crypto_assistant_{datetime.now().strftime('%Y%m%d')}.log"
        else:
            log_dir = Path(log_file).parent
            if log_dir.exists() or log_dir == Path('.'):
                pass
            else:
                log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # File gets all messages
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
        
        self._initialized = True
        self.log_file = str(log_file)
        
        # Initial log message
        self.logger.info(f"Logger initialized - Log level: {log_level}")
        self.logger.info(f"Log file: {self.log_file}")
    
    def get_logger(self) -> logging.Logger:
        """Get the configured logger instance."""
        return self.logger
    
    def set_level(self, level: str) -> None:
        """Change the logging level."""
        new_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.setLevel(new_level)
        for handler in self.logger.handlers:
            handler.setLevel(new_level)
        self.logger.info(f"Log level changed to: {level}")
    
    def debug(self, message: str, *args, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs) -> None:
        """Log info message."""
        self.logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs) -> None:
        """Log error message."""
        self.logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs) -> None:
        """Log critical message."""
        self.logger.critical(message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs) -> None:
        """Log exception with traceback."""
        self.logger.exception(message, *args, **kwargs)


# Global logger instance
logger = None


def get_logger(
    name: str = "CryptoAssistant",
    log_level: str = "INFO",
    log_file: Optional[str] = None
) -> CryptoLogger:
    """
    Get or create the global logger instance.
    
    Args:
        name (str): Name of the logger.
        log_level (str): Logging level.
        log_file (Optional[str]): Path to the log file.
    
    Returns:
        CryptoLogger: Configured logger instance.
    """
    global logger
    if logger is None:
        logger = CryptoLogger(name=name, log_level=log_level, log_file=log_file)
    return logger


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None
) -> CryptoLogger:
    """
    Setup logging for the application.
    This is the recommended way to initialize logging at application startup.
    
    Args:
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file (Optional[str]): Custom path to the log file.
    
    Returns:
        CryptoLogger: Configured logger instance.
    
    Example:
        >>> from utils.logger import setup_logging
        >>> logger = setup_logging(log_level="DEBUG")
        >>> logger.info("Application started")
    """
    return get_logger(log_level=log_level, log_file=log_file)


# Convenience function for quick logging without instance
# This creates a temporary logger for simple use cases
def quick_log(
    message: str,
    level: str = "INFO",
    name: str = "QuickLog"
) -> None:
    """
    Quick logging function for simple use cases.
    
    Args:
        message (str): Message to log.
        level (str): Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        name (str): Logger name.
    """
    temp_logger = logging.getLogger(name)
    temp_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    temp_logger.handlers.clear()
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    temp_logger.addHandler(handler)
    
    log_method = getattr(temp_logger, level.lower(), temp_logger.info)
    log_method(message)
