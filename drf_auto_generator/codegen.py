import logging
import os
import stat  # For setting file permissions
import ast
import astor
from pathlib import Path
from typing import List, Dict, Any, Set, Optional
from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
    ext as jinja2_extensions,
)
from inflect import engine as inflect_engine

# Import from the new Django introspection module
from drf_auto_generator.introspection_django import TableInfo
from drf_auto_generator.config_validation import ToolConfigSchema
from drf_auto_generator.test_codegen_utils import _get_faker_value, _generate_invalid_value
from .generate_tests_using_ast import (
    OpenAPISpecHandler,
    SchemaAnalyzer,
    EndpointAnalyzer,
    TestCaseGenerator,
)
from drf_auto_generator.codegen_utils import format_python_code_using_black


logger = logging.getLogger(__name__)

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


def generate_file_from_template(
    env: Environment, template_name: str, context: Dict[str, Any], output_path: Path
):
    """Renders a Jinja template and saves the output to the specified path."""
    try:
        template = env.get_template(template_name)
        rendered_content = template.render(context)
        # Format the generated python code before writing it to the file
        if output_path.suffix == ".py":
            logger.debug(f"Formatting Python code using Black: {output_path}")
            final_content = format_python_code_using_black(
                output_path, rendered_content
            )
        else:
            final_content = rendered_content

        # Ensure the parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Write the rendered content to the file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_content)
        logger.debug(f"Generated file: {output_path}")
    except Exception as e:
        logger.error(
            f"Error generating file from template '{template_name}' to '{output_path}': {e}",
            exc_info=True,
        )
        # Decide if we should raise the exception or just log it
        raise e


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

        # Convert AST module to source code using astor
        code = astor.to_source(module)

        # Format the generated code using Black
        output_filename = f"test_api_{resource_name.lower()}.py"
        output_path = test_dir / output_filename

        # Format the code using Black and Write to file
        formatted_code = format_python_code_using_black(output_path, code)
        with open(output_path, "w") as f:
            f.write(formatted_code)

        logger.info(f"Generated test file: {output_filename}")
    logger.info("Django test file generation complete.")
