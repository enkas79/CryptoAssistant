# Utils Module for CryptoAssistant
# Contains utility functions for calculations, currency conversion, PDF generation, and logging.

# Only import what doesn't require external dependencies
from .logger import setup_logging, get_logger, CryptoLogger

# Lazy imports for modules that require external dependencies
# These will be imported when needed, not at module load time

__all__ = [
    'setup_logging', 'get_logger', 'CryptoLogger',
]
