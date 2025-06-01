"""
Django AST-based Code Generation Main Module

This module provides the main entry point for AST-based Django code generation,
replacing the Jinja2-based approach with a more maintainable and flexible AST solution.
"""

import logging
import os
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional
from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
    ext as jinja2_extensions,
)
from inflect import engine as inflect_engine


# Import from the Django introspection module
from drf_auto_generator.introspection_django import TableInfo
from drf_auto_generator.config_validation import ToolConfigSchema

# Import the AST code generator components
from drf_auto_generator.ast_codegen import generate_django_project
from drf_auto_generator.ast_codegen.base import add_location
from drf_auto_generator.generate_tests_using_ast import (
    OpenAPISpecHandler,
    SchemaAnalyzer,
    EndpointAnalyzer,
    TestCaseGenerator,
)
from drf_auto_generator.codegen import generate_file_from_template
from drf_auto_generator.codegen_utils import format_python_code_using_black


# Define the path to the templates directory relative to this file
TEMPLATE_DIR = Path(__file__).parent / "templates"

_INFLECT_ENGINE_ = inflect_engine()


def jinja2_pluralize_filter(word):
    """
    Custom Jinja filter to pluralize a word using inflect.
    Includes error handling and fallback.
    """
    if not isinstance(word, str) or not word:
        return "" # Return empty for non-string or empty input
    try:
        plural = _INFLECT_ENGINE_.plural(word)
        # Handle cases where plural returns False or empty string
        if plural:
            return plural
        else:
            # Standard fallback: append 's' (or 'es' if needed - basic 's' for now)
            return word + "s"
    except Exception as e:
        # Log the error and return a simple fallback
        logger.error(f"Inflect pluralization failed for '{word}': {e}. Falling back to adding 's'.")
        return word + "s"


def setup_jinja_env() -> Environment:
    """Sets up and returns the Jinja2 environment."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(
            ["html", "xml", "j2"]
        ),  # Enable autoescaping for safety
        trim_blocks=True,  # Remove first newline after a block tag
        lstrip_blocks=True,  # Strip leading whitespace from lines with block tags
        extensions=[
            jinja2_extensions.do,  # Add do extension for {% do ... %}
            jinja2_extensions.loopcontrols,  # Add loopcontrols extension for {% break, continue, etc. %}
        ],
    )
    # Add custom filters or globals if needed
    # env.filters['custom_filter'] = my_custom_filter
    # Add repr filter for debugging or specific quoting needs
    env.filters["repr"] = repr
    env.filters["pluralize"] = jinja2_pluralize_filter
    env.globals["p"] = _INFLECT_ENGINE_
    return env


logger = logging.getLogger(__name__)

def generate_django_tests_using_ast(
    openapi_spec_dict: Dict[str, Any], config: ToolConfigSchema, app_path: Path
):
    """
    Generates APITestCase classes for each resource in the OpenAPI spec using AST,
    and writes them to the individual test files in the app_path / tests directory.
    """
    logger.info(f"Generating Django test files for app '{config.app_name}'...")
    test_dir = app_path / "tests"
    test_dir.mkdir(exist_ok=True)

    # Create __init__.py if it doesn't exist
    init_file = test_dir / "__init__.py"
    if not init_file.exists():
        init_file.touch()

    # Generate test files using AST
    openapi_spec_handler = OpenAPISpecHandler(openapi_spec_dict)
    schema_analyzer = SchemaAnalyzer(openapi_spec_handler)
    endpoint_analyzer = EndpointAnalyzer(openapi_spec_handler)

    # Instantiate the test generator to generate the test case classes using AST
    api_base = "/api"
    test_generator = TestCaseGenerator(endpoint_analyzer, schema_analyzer, api_base)

    # Get CRUD Groups to generate one test file per resource
    crud_groups = endpoint_analyzer.identify_crud_groups()

    # Generate test files for each resource
    for resource_name, crud_ops in crud_groups.items():
        logger.info(f"Generating tests for resource: {resource_name}")

        # Generate the test class
        test_class = test_generator.generate_testcase_class(resource_name, crud_ops)

        # Create AST Module with imports and generated test class
        module = ast.Module(
            body=test_generator._create_import_statements() + [test_class],
            type_ignores=[]
        )

        # Add location information to the module for Python 3.13+ compatibility
        module = add_location(module)

        # Convert AST module to source code using ast.unparse
        code = ast.unparse(module)

        # Format the generated code using Black
        output_filename = f"test_api_{resource_name.lower()}.py"
        output_path = test_dir / output_filename

        # Format the code using Black and Write to file
        formatted_code = format_python_code_using_black(output_path, code)
        with open(output_path, "w") as f:
            f.write(formatted_code)

        logger.info(f"Generated test file: {output_path}")


def generate_django_code(
    tables_info: List[TableInfo],
    config: Dict[str, Any],
    openapi_spec_dict: Optional[Dict[str, Any]] = None
):
    """
    Generate Django code using AST-based code generation.
    This function replaces the template-based approach with AST-based generation.

    Args:
        tables_info: List of TableInfo objects representing the database schema
        config: Configuration dictionary with project settings
        openapi_spec_dict: Optional OpenAPI specification for test generation
    """
    logger.info("Starting Django code generation using AST...")

    # Extract core settings from config
    output_dir = config.get("output_dir", "./output")
    project_name = config.get("project_name", "django_project")
    app_name = config.get("app_name", "api")

    # Create output directory path
    output_path = Path(output_dir)

    # Setup Jinja2 Environment
    env = setup_jinja_env()

    # Generate the Django project structure
    generate_django_project(tables_info, output_dir, project_name, app_name, env, config)

    logger.info("Generating requirements.txt...")
    # Context needs the config object for the template's conditional logic
    req_context = {
        "config": config,
    }
    generate_file_from_template(
        env, "requirements.txt.j2", req_context, Path(output_dir) / "requirements.txt"
    )

    # Generate tests if OpenAPI spec is provided
    if openapi_spec_dict:
        app_path = output_path / app_name
        generate_django_tests_using_ast(openapi_spec_dict, config, app_path)

    logger.info(f"Django code generation complete. Project created at {output_dir}")
    logger.info(f"Run 'cd {output_dir} && python manage.py runserver' to start the development server.")


def generate_code_from_schema(
    db_alias: str,
    output_dir: str,
    app_name: str,
    project_name: str = "django_project",
    include_tables: Optional[List[str]] = None,
    exclude_tables: Optional[List[str]] = None,
):
    """
    Main entry point for generating Django code from a database schema.

    Args:
        db_alias: Database alias name (as configured in Django settings)
        output_dir: Directory where the generated code will be placed
        app_name: Name of the Django app to create
        project_name: Name of the Django project to create
        include_tables: Optional list of tables to include (all by default)
        exclude_tables: Optional list of tables to exclude (none by default)
    """
    # Import here to prevent circular imports
    from drf_auto_generator.introspection_django import get_table_info_from_database, filter_tables

    # Create a config object with the provided parameters
    config = {
        "output_dir": output_dir,
        "project_name": project_name,
        "app_name": app_name,
    }

    # Get table information from the database
    logger.info(f"Inspecting database '{db_alias}'...")
    all_tables_info = get_table_info_from_database(db_alias)

    # Filter tables based on include/exclude lists
    filtered_tables_info = filter_tables(all_tables_info, include_tables, exclude_tables)

    if not filtered_tables_info:
        logger.error("No tables found after filtering. Check your include/exclude lists.")
        return

    # Generate Django code
    generate_django_code(filtered_tables_info, config)

    logger.info("Code generation complete.")

# Example usage:
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Example: generate code from a database schema
    # generate_code_from_schema(
    #     db_alias="default",
    #     output_dir="./output",
    #     app_name="myapp",
    #     project_name="myproject"
    # )
