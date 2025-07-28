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

# Import colored logging
from drf_auto_generator.colored_logging import (
    setup_colored_logging,
    get_colored_logger,
    log_success,
    log_progress,
    log_section
)

# Note: Colored logging will be configured after parsing args
logger = None


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
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose DEBUG logging for the generator tool.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output (useful for CI/CD environments).",
    )

    args = parser.parse_args()

    # --- Logging Setup ---
    # Configure colored logging based on command line arguments
    use_colors = not args.no_color
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_colored_logging(level=log_level, use_colors=use_colors)

    # Get logger for this module
    global logger
    logger = get_colored_logger(__name__)

    if args.verbose:
        logger.debug("Verbose mode enabled. DEBUG level logging activated.")
    if args.no_color:
        logger.debug("Color output disabled.")

    # --- Main Execution Pipeline ---
    try:
        # 1. Load Configuration
        log_progress(logger, "Loading configuration...")
        config = load_config(args.config, args)
        log_success(logger, "Configuration loaded and validated successfully.")
        logger.debug(
            f"Effective configuration loaded: {config}"
        )  # Debug log the full config

        # 2. Setup Django Environment (Crucial Step!)
        # This configures settings and calls django.setup()
        log_progress(logger, "Configuring Django settings for introspection...")
        setup_django(config["databases"], config["SECRET_KEY"])
        log_success(logger, "Django setup complete.")

        # 3. Introspect Database Schema (using Django connection)
        log_section(logger, "Database Schema Introspection")
        log_progress(logger, "Starting database schema introspection...")
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
        log_section(logger, "Intermediate Representation")
        log_progress(logger, "Mapping database schema to intermediate representation...")
        intermediate_repr: List[TableInfo] = build_intermediate_representation(
            raw_schema_info
        )
        log_success(logger, "Intermediate representation built successfully.")
        logger.debug(
            "Intermediate representation built."
        )  # Avoid logging the whole IR unless very verbose

        # 5. Generate OpenAPI Specification
        log_section(logger, "OpenAPI Specification")
        log_progress(logger, "Generating OpenAPI specification...")
        openapi_spec = generate_openapi_spec(intermediate_repr, config)
        # Save the spec file within the generated project directory
        save_openapi_spec(openapi_spec, config["output_dir"])
        log_success(logger, "OpenAPI specification generated and saved successfully.")

        # 6. Generate Django Project Code using AST-based generation
        log_section(logger, "Django Code Generation")
        log_progress(logger, "Generating Django project code using AST-based generation...")
        generate_django_code(intermediate_repr, config, openapi_spec)

        # --- Success ---
        log_section(logger, "COMPLETION")
        log_success(logger, "🎉 API Generation Process Completed Successfully! 🎉")
        logger.info("Follow the steps below to start the API server:")
        logger.info(f"   cd {config['output_dir']}")
        logger.info("   uv venv .venv && source .venv/bin/activate")
        logger.info("   uv pip install -r requirements.txt")
        logger.info("   python manage.py runserver")
        logger.info("   Open the browser and navigate to http://127.0.0.1:8000/api/schema/swagger-ui/#/")

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
