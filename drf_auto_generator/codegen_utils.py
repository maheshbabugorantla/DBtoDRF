import logging
from pathlib import Path


logger = logging.getLogger(__name__)

# --- Import Black ---
try:
    import black
    from black import (
        FileMode,
        format_str as black_format_str,
        NothingChanged as BlackNothingChanged,
    )

    BLACK_FORMATTER_AVAILABLE = True
    BLACK_FORMATTER_MODE = FileMode(line_length=120)  # Use Black's standard defaults
except ImportError:
    BLACK_FORMATTER_AVAILABLE = False
    BLACK_FORMATTER_MODE = None  # Define to avoid NameError later
    logging.warning(
        "Package 'black' not found. Generated Python code will not be auto-formatted."
    )


def format_python_code_using_black(filepath: Path, code_string: str) -> str:
    """Formats the given Python code using Black."""
    if not BLACK_FORMATTER_AVAILABLE:
        return code_string

    try:
        formatted_code = black_format_str(code_string, mode=BLACK_FORMATTER_MODE)
        logger.debug(f"Formatted code using Black: {filepath}")
        return formatted_code
    except BlackNothingChanged:
        logger.debug(f"Black formatter did not change the code: {filepath}")
        return code_string
    except Exception as e:
        # Log an error if Black fails for some reason (e.g., invalid syntax not caught earlier)
        logger.error(
            f"Could not format Python code using Black: {e}", exc_info=False
        )  # Keep log concise
        logger.warning("Writing unformatted Python code due to Black error.")
        return code_string  # Return the original string on error
