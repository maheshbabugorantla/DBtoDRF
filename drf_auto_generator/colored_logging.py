"""
Colored logging formatter for DRF Auto Generator.

This module provides colored console output for better visibility of log messages
during code generation operations.
"""

import logging
import sys
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """
    Colored logging formatter that adds ANSI color codes to log messages.
    
    Different log levels get different colors for better visual distinction.
    """
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green  
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    
    # Special colors for specific messages
    SPECIAL_COLORS = {
        'success': '\033[92m',    # Bright Green
        'progress': '\033[94m',   # Bright Blue
        'highlight': '\033[96m',  # Bright Cyan
    }
    
    RESET = '\033[0m'         # Reset to default color
    BOLD = '\033[1m'          # Bold text
    
    def __init__(self, fmt: Optional[str] = None, use_colors: bool = True):
        """
        Initialize the colored formatter.
        
        Args:
            fmt: Log format string (uses default if None)
            use_colors: Whether to use colors (can be disabled for non-interactive environments)
        """
        if fmt is None:
            fmt = "%(levelname)s: %(message)s"
        super().__init__(fmt)
        
        # Disable colors if not in a TTY or explicitly disabled
        self.use_colors = use_colors and hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors."""
        if not self.use_colors:
            return super().format(record)
        
        # Get the original formatted message
        formatted_message = super().format(record)
        
        # Get the message content for pattern matching
        message = record.getMessage()
        
        # Priority 1: ERROR and CRITICAL messages are ALWAYS red (highest priority)
        if record.levelname in ('ERROR', 'CRITICAL'):
            level_color = self.COLORS.get(record.levelname, '')
            if level_color:
                formatted_message = f"{level_color}{formatted_message}{self.RESET}"
        
        # Priority 2: WARNING messages are ALWAYS yellow
        elif record.levelname == 'WARNING':
            level_color = self.COLORS.get(record.levelname, '')
            if level_color:
                formatted_message = f"{level_color}{formatted_message}{self.RESET}"
        
        # Priority 3: For INFO and DEBUG, check for special patterns first
        elif record.levelname in ('INFO', 'DEBUG'):
            if self._is_success_message(message):
                formatted_message = f"{self.SPECIAL_COLORS['success']}{self.BOLD}{formatted_message}{self.RESET}"
            elif self._is_progress_message(message):
                formatted_message = f"{self.SPECIAL_COLORS['progress']}{formatted_message}{self.RESET}"
            elif self._is_highlight_message(message):
                formatted_message = f"{self.SPECIAL_COLORS['highlight']}{formatted_message}{self.RESET}"
            elif self._is_section_message(message):
                # Section headers get special treatment
                formatted_message = f"{self.BOLD}{self.SPECIAL_COLORS['highlight']}{formatted_message}{self.RESET}"
            elif record.levelname == 'DEBUG':
                # Color debug messages that don't match special patterns
                level_color = self.COLORS.get(record.levelname, '')
                if level_color:
                    formatted_message = f"{level_color}{formatted_message}{self.RESET}"
            # For regular INFO messages that don't match special patterns, leave them uncolored
            
        return formatted_message
    
    def _is_success_message(self, message: str) -> bool:
        """Check if message indicates successful completion."""
        success_indicators = [
            'complete', 'successfully', 'generated', 'created', 'finished',
            'done', '✓', 'success'
        ]
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in success_indicators)
    
    def _is_progress_message(self, message: str) -> bool:
        """Check if message indicates progress/processing."""
        progress_indicators = [
            'processing', 'analyzing', 'generating', 'building', 'mapping',
            'introspecting', 'starting', 'loading'
        ]
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in progress_indicators)
    
    def _is_highlight_message(self, message: str) -> bool:
        """Check if message should be highlighted."""
        highlight_indicators = [
            'excluded', 'included', 'skipping', 'found', 'detected'
        ]
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in highlight_indicators)
    
    def _is_section_message(self, message: str) -> bool:
        """Check if message is a section header."""
        return '=' in message and len(message.strip()) > 20


def setup_colored_logging(level: int = logging.INFO, use_colors: bool = True) -> None:
    """
    Set up colored logging for the application.
    
    Args:
        level: Logging level (default: INFO)
        use_colors: Whether to use colors (default: True)
    """
    # Create colored formatter
    formatter = ColoredFormatter(use_colors=use_colors)
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Remove existing handlers to avoid duplication
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create and configure console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    root_logger.setLevel(level)


def get_colored_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Convenience functions for special message types
def log_success(logger: logging.Logger, message: str) -> None:
    """Log a success message with special formatting."""
    logger.info(f"✓ {message}")


def log_progress(logger: logging.Logger, message: str) -> None:
    """Log a progress message with special formatting."""
    logger.info(f"→ {message}")


def log_highlight(logger: logging.Logger, message: str) -> None:
    """Log a highlighted message with special formatting."""
    logger.info(f"• {message}")


def log_section(logger: logging.Logger, section_name: str) -> None:
    """Log a section header with special formatting."""
    separator = "=" * 60
    logger.info(f"\n{separator}")
    logger.info(f"  {section_name.upper()}")
    logger.info(f"{separator}")


# Example usage and testing
if __name__ == "__main__":
    # Test the colored logging
    setup_colored_logging()
    logger = get_colored_logger(__name__)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    # Test special message types
    log_success(logger, "Code generation completed successfully!")
    log_progress(logger, "Processing database schema...")
    log_highlight(logger, "Found 15 tables in database")
    log_section(logger, "Django Model Generation")
    
    logger.info("Generated file: /path/to/models.py")
    logger.info("Building intermediate representation...")
    logger.info("Analyzing relationships...")
    logger.warning("Table 'test' has no primary key, skipping...")