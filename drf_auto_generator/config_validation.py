# File: drf_auto_generator/validation.py
from argparse import Namespace
import sys
import logging
import keyword
from typing import List, Optional, Dict, Any, Literal, Self
import yaml
import os
from pathlib import Path

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    field_validator,
    model_validator,
    ConfigDict,
)

logger = logging.getLogger(__name__)

# --- Helper Functions for Validation ---


def is_valid_python_identifier(name: str) -> bool:
    """Check if a string is a valid Python identifier and not a keyword."""
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
    USER: Optional[str] = Field(
        default=None, description="Database user."
    )  # Use default=None for clarity
    PASSWORD: Optional[str] = Field(default=None, description="Database password.")
    HOST: Optional[str] = Field(default=None, description="Database host address.")
    PORT: Optional[int] = Field(
        default=None, description="Database port number."
    )  # Store as int
    OPTIONS: Dict[str, Any] = Field(
        default_factory=dict, description="Database engine specific options."
    )  # Use default_factory

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @field_validator("ENGINE")
    @classmethod
    def validate_engine(cls, v: str) -> str:
        """Ensure engine is a valid Django database engine."""
        supported_db_engines = ['django.db.backends.postgresql', 'django.db.backends.sqlite3']
        if v not in supported_db_engines:
            raise ValueError(f"Database engine: {v} is not supported. Supported engines are: {', '.join(supported_db_engines)}")
        return v

    # --- Use @field_validator for PORT ---
    @field_validator(
        "PORT", mode="before"
    )  # mode='before' runs before Pydantic's type coercion
    @classmethod  # Keep classmethod
    def validate_port(cls, v: Any) -> Optional[int]:  # Input type is Any
        """Ensure port is a number or string representation of one, and within range."""
        if v is None or v == "":
            return None
        port_num: Optional[int] = None
        if isinstance(v, int):
            port_num = v
        elif isinstance(v, str):
            if not v.isdigit():
                raise ValueError(
                    f"Port must be a number or string containing only digits, got '{v}'"
                )
            try:
                port_num = int(v)
            except ValueError:
                raise ValueError(f"Could not convert port '{v}' to a number")
        else:
            raise TypeError(
                f"Port must be an integer or string containing digits, got {type(v).__name__}"
            )

        if port_num is not None and not 0 <= port_num <= 65535:
            raise ValueError(f"Port must be between 0 and 65535, got {port_num}")
        return port_num


class ToolConfigSchema(BaseModel):
    """Pydantic schema defining the expected structure and types for the configuration."""

    # Use Field with default=... for optional fields with defaults
    databases: Dict[str, DatabaseSettings] = Field(
        ...,
        description="Django DATABASES setting dictionary. Must contain a 'default' key.",
    )
    output_dir: str = Field(
        "./generated_api_django",
        min_length=1,
        description="Directory for generated project output.",
    )
    project_name: str = Field(
        "myapi_django",
        min_length=1,
        description="Name for the generated Django project (Python identifier).",
    )
    app_name: str = Field(
        "api",
        min_length=1,
        description="Name for the generated Django app (Python identifier).",
    )
    include_tables: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific table names (strings) to include.",
    )
    exclude_tables: Optional[List[str]] = Field(
        default=None, description="Optional list of table names (strings) to exclude."
    )
    auto_include_dependencies: bool = Field(
        default=False,
        description="If True and include_tables is set, automatically add tables related via FKs.",
    )
    relation_style: Literal["pk", "link", "nested"] = Field(
        default="pk",
        description="Style for representing relationships ('pk', 'link', 'nested').",
    )
    openapi_title: str = Field(
        default="Auto-Generated API",
        min_length=1,
        description="Title for the OpenAPI specification.",
    )
    openapi_version: str = Field(
        default="1.0.0",
        min_length=1,
        description="Version string for the OpenAPI specification.",
    )
    openapi_description: str = Field(
        default="API generated automatically.",
        description="Description for the OpenAPI specification.",
    )
    openapi_server_url: str = Field(
        default="http://127.0.0.1:8000/",
        description="Base URL for the API server in OpenAPI spec.",
    )
    generate_api_tests: bool = Field(
        default=True, description="Whether to generate basic Django APITestCase files."
    )

    # Internal field, usually added by load_config if not provided by user
    SECRET_KEY: Optional[str] = Field(
        default=None, description="Internal secret key for Django setup."
    )

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access for compatibility with existing code."""
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        """Allow dict.get() style access for compatibility with existing code."""
        return getattr(self, key, default)

    # --- Custom Field Validators using @field_validator ---

    @field_validator("project_name", "app_name")
    @classmethod
    def check_valid_identifier(
        cls, v: str
    ) -> str:  # Input is already validated as str by Pydantic
        """Validate project_name and app_name are valid Python identifiers."""
        if not is_valid_python_identifier(v):
            raise ValueError(
                f"'{v}' is not a valid Python identifier or is a reserved keyword."
            )
        return v

    # Use 'each_item=True' to validate items within the list
    # Use mode='before' to catch non-strings early
    @field_validator(
        "include_tables", "exclude_tables", mode="before", check_fields=False
    )  # check_fields=False needed for optional fields
    @classmethod
    def check_table_names_list(cls, v: Optional[List[Any]]) -> Optional[List[str]]:
        """Ensure items in table lists are non-empty strings."""
        if v is None:
            return None
        if not isinstance(v, list):
            # This might be caught by Pydantic typing, but check defensively
            raise TypeError("include_tables/exclude_tables must be a list.")
        processed_list = []
        for index, item in enumerate(v):
            if not isinstance(item, str):
                raise TypeError(
                    f"Item at index {index} must be a string, found: {type(item).__name__}"
                )
            stripped_item = item.strip()
            if not stripped_item:
                raise ValueError(
                    f"Item at index {index} cannot be empty or just whitespace."
                )
            processed_list.append(stripped_item)
        return processed_list

    # --- Custom Model Validator using @model_validator ---
    # mode='after' runs after field validation and model creation
    # Use 'Self' type hint for Python 3.11+ if available for the model instance
    @model_validator(mode="after")
    def check_db_and_dependency_config(self) -> Self:  # or -> 'ToolConfigSchema':
        """Perform cross-field validation checks."""
        # 1. Ensure the 'databases' dictionary contains a 'default' key.
        # Self here refers to the partially validated model instance
        if self.databases is not None and "default" not in self.databases:
            # Raise ValueError - Pydantic V2 associates this with the whole model
            raise ValueError(
                "The 'databases' configuration dictionary must contain a 'default' key."
            )

        # 2. Ensure auto_include_dependencies logic is consistent
        if self.auto_include_dependencies and not self.include_tables:
            logger.warning(
                "'auto_include_dependencies' is True but 'include_tables' is not specified. The option will have no effect unless an include_tables list is provided."
            )

        # Return the validated model instance
        return self

    # Use Pydantic V2 model_config instead of nested Class Config
    model_config = ConfigDict(
        extra="ignore",  # Allow and ignore extra fields from input dict
    )


# --- Validation Function ---
def validate_and_parse_config(config_dict: Dict[str, Any]) -> ToolConfigSchema:
    """
    Validates a raw configuration dictionary against the ToolConfigSchema.
    Exits with error messages if validation fails.
    """
    try:
        validated_config = ToolConfigSchema.model_validate(
            config_dict
        )  # Use model_validate in V2
        logger.debug(
            "Configuration dictionary parsed and validated successfully against schema."
        )
        return validated_config
    except ValidationError as e:
        logger.critical(
            "Configuration validation failed! Please check your config file or arguments."
        )
        print("\n--- Configuration Errors ---", file=sys.stderr)
        # Use e.errors() which is standard in V1 and V2
        for error in e.errors():
            loc_parts = [str(loc_item) for loc_item in error.get("loc", ())]
            loc_str = (
                " -> ".join(loc_parts) if loc_parts else "Model Level"
            )  # Adjust 'Top Level'
            msg = error.get("msg", "Unknown validation error")
            input_value = error.get("input", "N/A")

            print(f"  - Location: '{loc_str}'", file=sys.stderr)
            # Show input value if helpful
            # print(f"    Input:    '{input_value}' ({type(input_value).__name__})", file=sys.stderr)
            print(f"    Error:    {msg}", file=sys.stderr)

            # Provide specific hints (can be kept similar)
            err_type = error.get("type")
            ctx = error.get("ctx", {})
            if "identifier" in str(err_type) or (
                "value_error" in str(err_type)
                and any(x in loc_parts for x in ["project_name", "app_name"])
            ):
                print(
                    f"    Hint:     Value '{input_value}' must be a valid Python variable name.",
                    file=sys.stderr,
                )
            # ... (other hints remain similar) ...

        print("----------------------------", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.critical(
            f"An unexpected error occurred during configuration parsing: {e}",
            exc_info=True,
        )
        sys.exit(1)


def load_config(config_path: Optional[str], cli_args: Namespace) -> ToolConfigSchema:
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

    # 4. Validate using the function which uses Pydantic V2 style
    logger.info("Validating final configuration...")
    validated_config: ToolConfigSchema = validate_and_parse_config(raw_config)

    # 5. Perform any post-validation adjustments (like resolving paths)
    validated_config.output_dir = str(Path(validated_config.output_dir).resolve())

    logger.info("Configuration loaded and validated successfully.")
    return validated_config
