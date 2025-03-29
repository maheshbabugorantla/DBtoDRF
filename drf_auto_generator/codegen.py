import logging
import os
import shutil
import stat  # For setting file permissions
from pathlib import Path
from typing import List, Dict, Any
from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
    ext as jinja2_extensions,
)
from inflect import engine as inflect_engine

# Import from the new Django introspection module
from .introspection_django import TableInfo

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
    logger.info("8. Run the production server (example using Gunicorn):")
    logger.info(f"   gunicorn {project_name}.wsgi:application --bind 0.0.0.0:8000")
    logger.info("   (Or run the development server: python manage.py runserver)")
    logger.info(
        "9. Access the API docs at: http://<your_host>:8000/api/schema/swagger-ui/"
    )
    logger.info("--------------------------------------------------")
