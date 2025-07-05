import yaml
import argparse
import logging
import sys
import os
import keyword
from pathlib import Path
from typing import List, Optional, Dict, Any, Literal, Union, TypedDict

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


logger = logging.getLogger(__name__)


# --- Validation Helper ---
def is_valid_python_identifier(name: str) -> bool:
    """Check if a string is a valid Python identifier and not a keyword."""
    if not isinstance(name, str):
        return False
    return name.isidentifier() and not keyword.iskeyword(name)


# --- Pydantic Models for Configuration Schema ---


class DatabaseSettings(BaseModel):
    """Schema for a single database connection within the DATABASES dict."""

    ENGINE: str = Field(
        ...,
        min_length=1,
        description="Django database engine (e.g., 'django.db.backends.postgresql').",
    )
    NAME: str = Field(..., min_length=1, description="Database name.")
    USER: Optional[str] = Field(None, description="Database user.")
    PASSWORD: Optional[str] = Field(None, description="Database password.")
    HOST: Optional[str] = Field(None, description="Database host address.")
    PORT: Optional[Union[str, int]] = Field(None, description="Database port number.")
    OPTIONS: Optional[Dict[str, Any]] = Field(
        {}, description="Database engine specific options."
    )

    @field_validator(
        "PORT", mode="before"
    )  # Use pre=True to handle string conversion early
    def validate_port(cls, v):
        """Ensure port is a number or string representation of one, and within range."""
        if v is None or v == "":  # Allow empty string/None to pass (becomes None)
            return None
        port_num: Optional[int] = None
        if isinstance(v, int):
            port_num = v
        elif isinstance(v, str) and v.isdigit():
            try:
                port_num = int(v)
            except ValueError:
                raise ValueError(f"Could not convert port '{v}' to a number")
        else:
            raise TypeError(
                f"Port must be an integer or string containing only digits, got {type(v).__name__}"
            )

        if port_num is not None and not 0 <= port_num <= 65535:
            raise ValueError(f"Port must be between 0 and 65535, got {port_num}")
        return port_num  # Return validated integer or None


class ToolConfigSchema(BaseModel):
    """Pydantic schema defining the expected structure and types for the configuration."""

    # Pydantic automatically uses default values from Field if key is missing

    databases: Dict[str, DatabaseSettings] = Field(
        ..., description="Django DATABASES setting dictionary."
    )
    output_dir: str = Field(
        "./generated_api_django",
        min_length=1,
        description="Directory for generated project output.",
    )
    project_name: str = Field(
        "myapi_django",
        min_length=1,
        description="Name for the generated Django project.",
    )
    app_name: str = Field(
        "api", min_length=1, description="Name for the generated Django app."
    )
    include_tables: Optional[List[str]] = Field(
        None, description="Optional list of specific tables to include."
    )
    exclude_tables: Optional[List[str]] = Field(
        None, description="Optional list of tables to exclude."
    )
    relation_style: Literal["pk", "link", "nested"] = Field(
        "pk",
        description="Style for representing relationships ('pk', 'link', 'nested').",
    )
    openapi_title: str = Field(
        "Auto-Generated API",
        min_length=1,
        description="Title for the OpenAPI specification.",
    )
    openapi_version: str = Field(
        "1.0.0",
        min_length=1,
        description="Version string for the OpenAPI specification.",
    )
    openapi_description: str = Field(
        "API generated automatically.",
        description="Description for the OpenAPI specification.",
    )
    openapi_server_url: str = Field(
        "http://127.0.0.1:8000/",
        description="Base URL for the API server in OpenAPI spec.",
    )

    # Internal field, usually added by load_config
    SECRET_KEY: Optional[str] = Field(
        None, description="Internal secret key for Django setup."
    )

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    # --- Custom Validators ---

    @field_validator("project_name", "app_name")
    def check_valid_identifier(cls, v, field):
        """Validate project_name and app_name are valid Python identifiers."""
        if not is_valid_python_identifier(v):
            raise ValueError(
                f"'{v}' is not a valid Python identifier or is a reserved keyword. Use snake_case, start with a letter or underscore."
            )
        return v

    @field_validator("include_tables", "exclude_tables", mode="before")
    def check_table_names_are_strings(cls, v):
        """Ensure table names in lists are non-empty strings."""
        if isinstance(v, list):
            for item in v:
                if not isinstance(item, str):
                    raise TypeError(
                        f"Table names in include/exclude lists must be strings, found: {type(item).__name__}"
                    )
                if not item.strip():
                    raise ValueError(
                        "Table names in include/exclude lists cannot be empty or just whitespace."
                    )
            return [item.strip() for item in v]
        else:
            raise TypeError("include_tables and exclude_tables must be lists.")

    @model_validator(mode="after")  # Runs after individual field validation
    def check_default_database_exists(cls, values):
        """Ensure the 'databases' dictionary contains a 'default' key."""
        databases_dict = values.get("databases")
        if databases_dict is not None and "default" not in databases_dict:
            raise ValueError(
                "The 'databases' configuration must contain a 'default' key specifying the database to introspect."
            )
        # Add other cross-field validation if needed
        # Example: Ensure include_tables and exclude_tables don't overlap?
        return values

    # Allow extra fields to be ignored rather than raising errors
    class Config:
        extra = "ignore"


# --- Validation Function (Internal) ---
def _validate_and_parse_config(config_dict: Dict[str, Any]) -> ToolConfigSchema:
    """
    Validates a raw configuration dictionary against the Pydantic schema.
    Internal use: Prints detailed errors and exits on validation failure.
    """
    try:
        # Attempt to parse the raw dictionary into the Pydantic model
        validated_config = ToolConfigSchema.parse_obj(config_dict)
        logger.debug("Configuration dictionary parsed and validated successfully.")
        return validated_config
    except ValidationError as e:
        logger.error(
            "Configuration validation failed. Please check your config file or arguments."
        )
        print("\n--- Configuration Errors ---", file=sys.stderr)
        for error in e.errors():
            # Format location path (e.g., databases -> default -> PORT)
            loc_parts = [str(loc_item) for loc_item in error.get("loc", ())]
            loc_str = " -> ".join(loc_parts) if loc_parts else "Top Level"

            msg = error.get("msg", "Unknown error")
            print(f"  - Location: '{loc_str}'", file=sys.stderr)
            print(f"    Error: {msg}", file=sys.stderr)

            # Provide specific hints based on error type or location
            err_type = error.get("type")
            if "value_error.identifier" in str(err_type) or (
                "value_error" in str(err_type)
                and any(x in loc_parts for x in ["project_name", "app_name"])
            ):
                print(
                    f"    Hint: Ensure the value is a valid Python variable name (letters, numbers, underscores, not starting with a number, not a keyword like 'class' or 'list').",
                    file=sys.stderr,
                )
            elif (
                "value_error.literal" in str(err_type) and "relation_style" in loc_parts
            ):
                allowed = error.get("ctx", {}).get("expected", "'pk', 'link', 'nested'")
                print(f"    Hint: Allowed values are: {allowed}", file=sys.stderr)
            elif "type_error.str" in str(err_type) and any(
                x in loc_parts for x in ["include_tables", "exclude_tables"]
            ):
                print(
                    f"    Hint: Items in this list should be strings (text).",
                    file=sys.stderr,
                )
            elif "value_error.str.not_empty" in str(err_type) and any(
                x in loc_parts for x in ["include_tables", "exclude_tables"]
            ):
                print(
                    f"    Hint: Table names cannot be empty strings.", file=sys.stderr
                )
            elif "value_error.port" in str(
                err_type
            ):  # Custom error type hint might be needed
                print(
                    f"    Hint: Port must be a number between 0 and 65535.",
                    file=sys.stderr,
                )

        print("----------------------------", file=sys.stderr)
        sys.exit(1)  # Exit the program due to invalid config


# Define the structure of the expected configuration dictionary
class GeneratorConfig(TypedDict, total=False):
    databases: Dict[str, Dict[str, Any]]  # Django DATABASES dict structure
    output_dir: str
    include_tables: Optional[List[str]]
    exclude_tables: Optional[List[str]]
    project_name: str
    app_name: str
    relation_style: str  # 'pk', 'link', 'nested'
    openapi_title: str
    openapi_version: str
    openapi_description: str
    openapi_server_url: str
    SECRET_KEY: str  # For django.setup()


# --- Main Configuration Loading Function ---


def load_config(
    config_path: Optional[str], cli_args: argparse.Namespace
) -> ToolConfigSchema:
    """
    Loads configuration from YAML file, merges with CLI arguments,
    validates the result, and returns a validated Pydantic model instance.
    Exits with error messages if validation fails.
    """
    raw_config: Dict[str, Any] = {}  # Start with empty raw config

    # 1. Load from YAML file if path is provided
    if config_path:
        try:
            config_file = Path(config_path)
            if config_file.is_file():
                with open(config_file, "r", encoding="utf-8") as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config and isinstance(yaml_config, dict):
                        raw_config.update(yaml_config)
                        logger.debug(f"Loaded configuration from {config_path}")
                    elif yaml_config:
                        logger.warning(
                            f"Content in config file {config_path} is not a dictionary. Ignoring file content."
                        )
            else:
                logger.warning(
                    f"Config file not found at {config_path}. Using defaults and CLI arguments."
                )
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {config_path}: {e}")
            logger.warning("Proceeding with defaults and CLI arguments only.")
        except Exception as e:
            logger.error(f"Error reading config file {config_path}: {e}")
            logger.warning("Proceeding with defaults and CLI arguments only.")

    # 2. Override with CLI arguments (only those explicitly provided)
    cli_dict = vars(cli_args)
    overridden_keys = set()
    for key, value in cli_dict.items():
        # Only override if the CLI arg was actually given (is not None)
        # And don't override 'databases' via simple CLI args for now
        if (
            value is not None and key != "databases" and hasattr(ToolConfigSchema, key)
        ):  # Check if it's a valid config key
            raw_config[key] = value
            overridden_keys.add(key)
    if overridden_keys:
        logger.debug(f"Overridden config keys from CLI arguments: {overridden_keys}")

    # 3. Add internal SECRET_KEY if not present (needed for django.setup)
    if "SECRET_KEY" not in raw_config:
        raw_config["SECRET_KEY"] = os.urandom(50).hex()

    # 4. Validate the combined configuration dictionary using Pydantic
    # This function now handles detailed error reporting and exits on failure.
    logger.info("Validating final configuration...")
    validated_config: ToolConfigSchema = _validate_and_parse_config(raw_config)

    # 5. Perform any post-validation adjustments (like resolving paths)
    validated_config.output_dir = str(Path(validated_config.output_dir).resolve())

    logger.info("Configuration loaded and validated successfully.")
    return validated_config


# Default configuration values
DEFAULT_CONFIG: GeneratorConfig = {
    "output_dir": "./generated_api_django",
    "project_name": "myapi_django",
    "app_name": "api",
    "relation_style": "pk",
    "openapi_title": "Auto-Generated API",
    "openapi_version": "1.0.0",
    "openapi_description": "API generated automatically.",
    "openapi_server_url": "http://127.0.0.1:8000/",
    "include_tables": None,
    "exclude_tables": None,
}

# def load_config(config_path: Optional[str], cli_args: argparse.Namespace) -> GeneratorConfig:
#     """Loads configuration from YAML file and merges with CLI arguments."""
#     config: GeneratorConfig = DEFAULT_CONFIG.copy()

#     # Load from YAML file if path is provided
#     if config_path:
#         try:
#             config_file = Path(config_path)
#             if config_file.is_file():
#                 with open(config_file, 'r') as f:
#                     yaml_config = yaml.safe_load(f)
#                     if yaml_config:
#                         config.update(yaml_config)
#             else:
#                 print(f"Warning: Config file not found at {config_path}")
#         except Exception as e:
#             print(f"Error loading config file {config_path}: {e}")
#             # Decide whether to exit or continue

#     # Override with CLI arguments if they were provided
#     cli_dict = vars(cli_args)
#     for key, value in cli_dict.items():
#         # Don't allow overriding 'databases' via simple CLI arg for simplicity
#         if value is not None and key in config and key != 'databases':
#             config[key] = value # type: ignore

#     # --- Validation ---
#     if 'databases' not in config or 'default' not in config.get('databases', {}):
#         raise ValueError("Django 'databases' setting with a 'default' key is required in config.")

#     default_db = config['databases']['default']
#     if not all(k in default_db for k in ['ENGINE', 'NAME']):
#          raise ValueError("The 'default' database config must contain at least 'ENGINE' and 'NAME'.")

#     if not config.get('output_dir'):
#         raise ValueError("'output_dir' cannot be empty.")
#     if not config.get('project_name') or not config['project_name'].isidentifier():
#         raise ValueError("'project_name' must be a valid Python identifier.")
#     if not config.get('app_name') or not config['app_name'].isidentifier():
#          raise ValueError("'app_name' must be a valid Python identifier.")

#     # Ensure output_dir is an absolute path
#     config['output_dir'] = str(Path(config['output_dir']).resolve())

#     # Add a dummy secret key needed for django.setup() if not provided
#     if 'SECRET_KEY' not in config:
#         config['SECRET_KEY'] = os.urandom(50).hex()

#     # Ensure table lists are lists (or None)
#     if config.get('include_tables') and not isinstance(config['include_tables'], list):
#         config['include_tables'] = list(config['include_tables']) # type: ignore
#     if config.get('exclude_tables') and not isinstance(config['exclude_tables'], list):
#         config['exclude_tables'] = list(config['exclude_tables']) # type: ignore


#     return config
