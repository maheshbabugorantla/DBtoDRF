import argparse
import logging
import sys
from typing import List

# Use the Django-specific introspection module
from drf_auto_generator.introspection_django import (
    setup_django,
    introspect_schema_django,
    TableInfo,
)

# Keep other necessary imports
from drf_auto_generator.config_validation import load_config
from drf_auto_generator.mapper import build_intermediate_representation
from drf_auto_generator.openapi_gen import generate_openapi_spec, save_openapi_spec

# Change from the template-based to AST-based code generation
from drf_auto_generator.ast_codegen_main import generate_django_code

# Configure root logger
logging.basicConfig(level=logging.INFO, format="%(name)s:%(levelname)s: %(message)s")
# Get logger for this module
logger = logging.getLogger(__name__)  # Use __name__ for module-specific logger


def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="Generate a Django REST Framework API from an existing database schema using Django introspection."
    )
    parser.add_argument(
        "-c",
        "--config",
        help="Path to the YAML configuration file (containing Django DATABASES dict).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Directory to generate the Django project in. Overrides config file setting.",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        help="Specific tables to include (space-separated). Overrides config file setting.",
    )
    parser.add_argument(
        "--exclude-tables",
        nargs="+",
        help="Tables to exclude (space-separated). Overrides config file setting.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose DEBUG logging for the generator tool.",
    )
    # Add AST-based code generation option (defaults to True to use AST)
    parser.add_argument(
        "--use-ast",
        action="store_true",
        default=True,
        help="Use AST-based code generation (default) instead of template-based.",
    )
    # Add more CLI overrides if needed (e.g., --project-name, --app-name)

    args = parser.parse_args()

    # --- Logging Level Setup ---
    if args.verbose:
        # Set level on the root logger to affect all loggers (including library logs if needed)
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled. DEBUG level logging activated.")
    else:
        # Ensure our logger respects INFO level if not verbose
        logger.setLevel(logging.INFO)

    # --- Main Execution Pipeline ---
    try:
        # 1. Load Configuration
        logger.info("Loading configuration...")
        config = load_config(args.config, args)
        logger.debug(
            f"Effective configuration loaded: {config}"
        )  # Debug log the full config

        # 2. Setup Django Environment (Crucial Step!)
        # This configures settings and calls django.setup()
        setup_django(config["databases"], config["SECRET_KEY"])

        # 3. Introspect Database Schema (using Django connection)
        logger.info("Starting database schema introspection...")
        raw_schema_info: List[TableInfo] = introspect_schema_django(
            # db_alias=DEFAULT_DB_ALIAS, # Can be made configurable if needed
            include_tables=config.get("include_tables"),
            exclude_tables=config.get("exclude_tables"),
        )
        # Check if introspection yielded any tables
        if not raw_schema_info:
            logger.warning(
                "Introspection did not find any tables matching the criteria. Exiting."
            )
            sys.exit(0)  # Exit normally if no tables found/selected

        # 4. Build Intermediate Representation (Mapping)
        logger.info("Mapping database schema to intermediate representation...")
        intermediate_repr: List[TableInfo] = build_intermediate_representation(
            raw_schema_info
        )
        logger.debug(
            "Intermediate representation built."
        )  # Avoid logging the whole IR unless very verbose

        # 5. Generate OpenAPI Specification
        logger.info("Generating OpenAPI specification...")
        openapi_spec = generate_openapi_spec(intermediate_repr, config)
        # Save the spec file within the generated project directory
        save_openapi_spec(openapi_spec, config["output_dir"])

        # 6. Generate Django Project Code using AST-based generation
        logger.info("Generating Django project code using AST-based generation...")
        generate_django_code(intermediate_repr, config, openapi_spec)

        # --- Success ---
        logger.info("-----------------------------------------")
        logger.info("API Generation Process Completed Successfully.")
        logger.info("-----------------------------------------")

    # --- Error Handling ---
    except ValueError as e:
        logger.error(
            f"Configuration Error: {e}", exc_info=args.verbose
        )  # Show traceback if verbose
        sys.exit(1)  # Exit with error code
    except RuntimeError as e:
        logger.error(f"Runtime Error: {e}", exc_info=args.verbose)
        sys.exit(1)
    except ImportError as e:
        logger.error(
            f"Import Error: {e}. Ensure Django and necessary database drivers are installed.",
            exc_info=args.verbose,
        )
        logger.error("Example: pip install django psycopg2-binary (for PostgreSQL)")
        sys.exit(1)
    except Exception as e:
        # Catch any other unexpected exceptions
        logger.error(
            f"An unexpected error occurred during generation: {e}", exc_info=True
        )  # Always show traceback for unexpected
        sys.exit(1)


# --- Script Entry Point ---
if __name__ == "__main__":
    main()
