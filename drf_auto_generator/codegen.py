import logging
import os
import stat  # For setting file permissions
from pathlib import Path
from typing import List, Dict, Any, Set
from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
    ext as jinja2_extensions,
)
from inflect import engine as inflect_engine

# Import from the new Django introspection module
from .introspection_django import TableInfo
from .config_validation import ToolConfigSchema
from .test_codegen_utils import _get_faker_value, _generate_invalid_value

logger = logging.getLogger(__name__)

# Define the path to the templates directory relative to this file
TEMPLATE_DIR = Path(__file__).parent / "templates"

_INFLECT_ENGINE_ = inflect_engine()


# --- Import Black ---
try:
    import black
    from black import (
        FileMode,
        format_str as black_format_str,
        NothingChanged as BlackNothingChanged,
    )

    BLACK_FORMATTER_AVAILABLE = True
    # Optional: Define default Black mode (can be customized if needed)
    # BLACK_MODE = FileMode(line_length=88) # Example: default line length
    BLACK_FORMATTER_MODE = FileMode(line_length=120)  # Use Black's standard defaults
except ImportError:
    BLACK_FORMATTER_AVAILABLE = False
    BLACK_FORMATTER_MODE = None  # Define to avoid NameError later
    logging.warning(
        "Package 'black' not found. Generated Python code will not be auto-formatted."
    )


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
    env.globals["p"] = _INFLECT_ENGINE_
    return env


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


def setup_project_structure(
    output_dir: str,
    project_name: str,
    app_name: str,
    env: Environment,
    config: Dict[str, Any],
):
    """Creates the basic Django project and app directory structure and generates core files."""
    logger.info(f"Setting up Django project structure in '{output_dir}'...")
    base_path = Path(output_dir)
    project_path = base_path / project_name
    app_path = base_path / app_name

    # --- Warning about existing directory ---
    if base_path.exists():
        logger.warning(
            f"Output directory '{output_dir}' already exists. Files may be overwritten."
        )
        # Consider adding a '--force' flag to control overwriting/deletion behavior
        # Example (use with extreme caution):
        # if force_overwrite_flag:
        #     logger.warning(f"Force flag enabled. Removing existing directory: {base_path}")
        #     shutil.rmtree(base_path)

    # --- Create necessary directories ---
    project_path.mkdir(parents=True, exist_ok=True)  # Creates base_path too
    app_path.mkdir(exist_ok=True)
    (app_path / "migrations").mkdir(exist_ok=True)

    # --- Prepare common context for templates ---
    # Use a temporary SECRET_KEY different from the one for setup if desired
    runtime_secret_key = os.urandom(50).hex()
    context = {
        "project_name": project_name,
        "app_name": app_name,
        "config": config,  # Pass full config for potential use in templates
        "secret_key": runtime_secret_key,  # Use a generated key for settings.py,
    }

    # --- Generate manage.py ---
    manage_py_path = base_path / "manage.py"
    generate_file_from_template(env, "manage.py.j2", context, manage_py_path)
    # Make manage.py executable
    try:
        current_st = os.stat(manage_py_path)
        os.chmod(
            manage_py_path,
            current_st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
        )
    except Exception as e:
        logger.warning(f"Could not make manage.py executable: {e}")

    # --- Generate project-level files ---
    generate_file_from_template(
        env, "__init__.py.j2", context, project_path / "__init__.py"
    )
    generate_file_from_template(
        env, "settings.py.j2", context, project_path / "settings.py"
    )
    generate_file_from_template(
        env, "root_urls.py.j2", context, project_path / "urls.py"
    )

    # --- Generate basic asgi.py/wsgi.py ---
    # Right now, only W
    generate_file_from_template(env, "wsgi.py.j2", context, project_path / "wsgi.py")
    generate_file_from_template(env, "asgi.py.j2", context, project_path / "asgi.py")

    # --- Generate basic app-level files ---
    generate_file_from_template(
        env, "__init__.py.j2", context, app_path / "__init__.py"
    )
    generate_file_from_template(env, "apps.py.j2", context, app_path / "apps.py")
    generate_file_from_template(
        env, "__init__.py.j2", context, app_path / "migrations" / "__init__.py"
    )

    logger.info("Generating sample .env and .gitignore files...")
    generate_file_from_template(env, ".env.j2", context, base_path / ".env")
    generate_file_from_template(env, ".gitignore.j2", context, base_path / ".gitignore")

    logger.info("Basic project structure and core files generated.")


def generate_django_tests(
    ir_list: List[TableInfo], config: ToolConfigSchema, app_path: Path, env: Environment
):
    """Generates APITestCase files for each model in the IR."""
    logger.info(f"Generating Django test files for app '{config.app_name}'...")
    test_dir = app_path / "tests"
    test_dir.mkdir(exist_ok=True)

    # Create __init__.py if it doesn't exist
    init_file = test_dir / "__init__.py"
    if not init_file.exists():
        init_file.touch()

    # Model Lookup Dictionary (model_name -> TableInfo)
    model_lookup: Dict[str, TableInfo] = {table.model_name: table for table in ir_list}

    # Generate one test file per table/model
    for table in ir_list:
        logger.info(f"Generating tests for model: {table.model_name}")

        # --- Prepare Context for the Template ---
        model_name = table.model_name
        table_name = table.name  # Used for URL reversing basename

        # Identify related models needed for ForeignKey setup
        related_models_needed: Set[str] = set()
        create_payload_fields: Dict[str, Dict] = {}
        patch_payload_fields: List[Dict] = []
        invalid_payload_fields: Dict[str, str] = {}
        pk_field_name = "pk"  # Default lookup field

        # Collect fields needed for payload generation (exclude read-only like PK)
        # Also determine which related models need creation
        for field in table.fields:
            if field["is_pk"] or field["options"].get("primary_key"):
                # Use the actual PK field name if not default 'id'/'pk'
                # This assumes single PK for simplicity in tests
                if not field["type"].startswith("AutoField") and not field[
                    "type"
                ].startswith("BigAutoField"):
                    pk_field_name = field["name"]
                continue  # Skip PKs for payload

            # Skip fields likely auto-set (like created_at, updated_at - needs better detection)
            if field["name"] in [
                "created_at",
                "updated_at",
                "creation_date",
                "modified_date",
            ]:
                continue

            field_details = {
                "key": field["name"],
                "type": field["type"],
                "options": field["options"],
                "is_fk": field["is_fk"],
                "is_unique": field["options"].get("unique", False),
                "needs_unique_value": field["options"].get("unique", False)
                or field["type"] == "SlugField",  # Need unique slugs too
                "related_model": None,
                "fake_value": None,
                "unique_fake_value": None,
            }

            if field["is_fk"]:
                # Find the related model name from relationships
                related_rel = next(
                    (
                        rel
                        for rel in table.relationships
                        if field["original_column_name"]
                        in rel.get("source_columns", [])
                    ),
                    None,
                )
                if related_rel:
                    field_details["key"] = related_rel[
                        "name"
                    ]  # Use relation name for payload key
                    field_details["related_model"] = related_rel["target_model_name"]
                    related_models_needed.add(related_rel["target_model_name"])
                    # Value will be set in template using related instance PK
                else:
                    logger.warning(
                        f"Could not determine related model for FK field '{field['name']}' in {model_name}. Skipping for payload."
                    )
                    continue  # Skip if relation details missing
            else:
                # Generate fake data for non-FK fields
                field_details["fake_value"] = _get_faker_value(
                    field["type"], field["options"], unique=False
                )
                if field_details["needs_unique_value"]:
                    field_details["unique_fake_value"] = _get_faker_value(
                        field["type"], field["options"], unique=True
                    )
                else:
                    field_details["unique_fake_value"] = field_details[
                        "fake_value"
                    ]  # Use same value if unique not needed

            create_payload_fields[field_details["key"]] = field_details
            patch_payload_fields.append(
                field_details
            )  # Add all writable fields as candidates for patching
            # Generate invalid data for required fields or fields with constraints
            if not field["options"].get("null", True) or field["options"].get(
                "unique", False
            ):  # Example: generate invalid for required/unique
                invalid_payload_fields[field_details["key"]] = _generate_invalid_value(
                    field["type"]
                )

        related_models_setup_data = {}
        for related_model_name in related_models_needed:
            related_table = model_lookup.get(related_model_name)
            if related_table:
                related_fields_payload = {}
                has_required_fields = False
                for rel_field in related_table.fields:
                    # Include only required, non-PK, non-FK fields for basic creation
                    is_required = not rel_field["options"].get("null", True)
                    is_pk = rel_field["is_pk"] or rel_field["options"].get(
                        "primary_key"
                    )
                    is_fk = rel_field["is_fk"]
                    # Basic check: needs improvement for defaults etc.
                    if is_required and not is_pk and not is_fk:
                        related_fields_payload[rel_field["name"]] = _get_faker_value(
                            rel_field["type"],
                            rel_field["options"],
                            unique=rel_field["options"].get("unique", False),
                        )
                        has_required_fields = True
                    elif (
                        not is_pk and not is_fk
                    ):  # Include optional fields too if needed? For now, only required.
                        pass

                if not related_fields_payload and has_required_fields:
                    logger.warning(
                        f"Could not generate required fields for related model {related_model_name} setup."
                    )
                    # Store empty dict to indicate potential failure in template
                    related_models_setup_data[related_model_name] = {}
                else:
                    related_models_setup_data[related_model_name] = (
                        related_fields_payload
                    )

            else:
                logger.warning(
                    f"Could not find related model '{related_model_name}' in IR for test setup."
                )

        context = {
            "model_name": model_name,
            "table_name": table_name,  # Basename for reverse
            "app_name": config.app_name,
            "related_models_needed": sorted(list(related_models_needed)),
            # Provide related models that need creation in setUpTestData
            "related_models_to_create": related_models_setup_data,
            # Fields for creating a valid instance (excluding PKs, read-only)
            "create_payload_fields": create_payload_fields,
            # Fields that can be potentially patched (non-FK, non-PK, non-readonly)
            "patch_payload_fields": [f for f in patch_payload_fields if not f["is_fk"]],
            # Fields with intentionally invalid data for 400 tests
            "invalid_payload_fields": invalid_payload_fields,
            "pk_field_name": pk_field_name,  # Primary key field name for response checks
        }

        # Generate the test file
        output_filename = f"test_api_{table.name}.py"
        output_path = test_dir / output_filename
        generate_file_from_template(env, "api_test.py.j2", context, output_path)

    logger.info("Django test file generation complete.")


def generate_django_code(ir_list: List[TableInfo], config: Dict[str, Any]):
    """Orchestrates the generation of all Django code files."""
    output_dir = config["output_dir"]
    project_name = config["project_name"]
    app_name = config["app_name"]

    # 1. Setup Jinja2 Environment
    env = setup_jinja_env()

    # 2. Setup Project Structure and Core Files
    setup_project_structure(output_dir, project_name, app_name, env, config)

    # 3. Prepare Context Specific to App File Generation
    app_path = Path(output_dir) / app_name
    app_context = {
        "tables": ir_list,  # The core Intermediate Representation list
        "project_name": project_name,
        "app_name": app_name,
        "config": config,  # Include config for access in templates (e.g., relation_style)
    }

    logger.info(f"Generating specific files for Django app '{app_name}'...")

    logger.info("Generating admin.py...")

    # --- Add this DEBUG block ---
    logger.debug(
        f"Context check for admin.py - tables type: {type(app_context.get('tables'))}"
    )
    if isinstance(app_context.get("tables"), list):
        logger.debug(
            f"Context check for admin.py - tables length: {len(app_context['tables'])}"
        )
        if app_context["tables"]:  # Check if list is not empty
            logger.debug(
                f"Context check for admin.py - first table model name: {app_context['tables'][0].model_name}"
            )
        else:
            logger.debug("Context check for admin.py - 'tables' list is empty.")
    else:
        logger.debug(
            "Context check for admin.py - 'tables' key not found or not a list."
        )
    # --- End DEBUG block ---
    generate_file_from_template(env, "admin.py.j2", app_context, app_path / "admin.py")

    # 4. Generate models.py
    logger.info("Generating models.py...")
    generate_file_from_template(
        env, "models.py.j2", app_context, app_path / "models.py"
    )

    # 5. Generate serializers.py
    logger.info("Generating serializers.py...")
    generate_file_from_template(
        env, "serializers.py.j2", app_context, app_path / "serializers.py"
    )

    # 6. Generate views.py
    logger.info("Generating views.py...")
    generate_file_from_template(env, "views.py.j2", app_context, app_path / "views.py")

    # 7. Generate urls.py (app-level)
    logger.info("Generating app urls.py...")
    generate_file_from_template(env, "urls.py.j2", app_context, app_path / "urls.py")

    # 8. Generate requirements.txt
    logger.info("Generating requirements.txt...")
    # Context needs the config object for the template's conditional logic
    req_context = {
        "config": config,
    }
    generate_file_from_template(
        env, "requirements.txt.j2", req_context, Path(output_dir) / "requirements.txt"
    )

    # 9. Generate Django API Tests
    generate_api_tests_flag = config.dict().get("generate_api_tests", True)
    if generate_api_tests_flag:
        generate_django_tests(ir_list, config, app_path, env)
    else:
        logger.info(
            "Skipping Django API Tests generation. Please set 'generate_api_tests' to True in your config to enable."
        )

    logger.info(
        f"Django project '{project_name}' generated successfully in '{output_dir}'"
    )
    logger.info("--------------------------------------------------")
    logger.info("Next Steps:")
    logger.info(f'1. cd "{output_dir}"')
    logger.info(
        "2. Create and activate a virtual environment (e.g., python -m venv venv && source venv/bin/activate)"
    )
    logger.info("3. Install requirements: pip install -r requirements.txt")
    logger.info(
        f"4. Configure DATABASES in '{project_name}/settings.py' (passwords, etc.)"
    )
    logger.info(
        f"5. Review/Configure production settings in '{project_name}/settings.py':"
    )
    logger.info("     - Set DEBUG = False")
    logger.info("     - Configure ALLOWED_HOSTS = ['your_domain.com', ...]")
    logger.info("     - Configure CORS_ALLOWED_ORIGINS or related CORS settings.")
    logger.info("     - Ensure STATIC_ROOT is correctly set.")
    logger.info(
        "     - Consider uncommenting SECURE_* settings, STATICFILES_STORAGE, GZipMiddleware."
    )
    logger.info("6. Collect static files: python manage.py collectstatic")
    logger.info("7. Run Django migrations: python manage.py migrate")
    if generate_api_tests_flag:
        logger.info(f"8. Run the API tests: python manage.py test {app_name}.tests")
        logger.info("9. Run the production server (example using Gunicorn):")
        logger.info(f"   gunicorn {project_name}.wsgi:application --bind 0.0.0.0:8000")
        logger.info("   (Or run the development server: python manage.py runserver)")
        logger.info(
            "10. Access the API docs at: http://<your_host>:8000/api/schema/swagger-ui/"
        )
    else:
        logger.info("8. Run the production server (example using Gunicorn):")
        logger.info(f"   gunicorn {project_name}.wsgi:application --bind 0.0.0.0:8000")
        logger.info("   (Or run the development server: python manage.py runserver)")
        logger.info(
            "9. Access the API docs at: http://<your_host>:8000/api/schema/swagger-ui/"
        )
    logger.info("--------------------------------------------------")
