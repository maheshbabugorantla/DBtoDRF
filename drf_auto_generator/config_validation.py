# File: drf_auto_generator/validation.py
import sys
import logging
import keyword
from typing import List, Optional, Dict, Any, Literal, Union

from pydantic import BaseModel, Field, validator, ValidationError, root_validator

logger = logging.getLogger(__name__)

# --- Helper Functions for Validation ---

def is_valid_python_identifier(name: str) -> bool:
    """Check if a string is a valid Python identifier and not a keyword."""
    return name.isidentifier() and not keyword.iskeyword(name)

# --- Pydantic Models for Configuration Schema ---

class DatabaseSettings(BaseModel):
    """Schema for a single database connection within the DATABASES dict."""
    ENGINE: str = Field(..., min_length=1, description="Django database engine (e.g., 'django.db.backends.postgresql').")
    NAME: str = Field(..., min_length=1, description="Database name.")
    USER: Optional[str] = Field(None, description="Database user.")
    PASSWORD: Optional[str] = Field(None, description="Database password.")
    HOST: Optional[str] = Field(None, description="Database host address.")
    PORT: Optional[Union[str, int]] = Field(None, description="Database port number.")
    OPTIONS: Optional[Dict[str, Any]] = Field({}, description="Database engine specific options.")

    @validator('PORT')
    def validate_port(cls, v):
        """Ensure port is a number or string representation of one."""
        if v is None:
            return v
        if isinstance(v, str):
            if not v.isdigit():
                raise ValueError(f"Port must be a number or string containing only digits, got '{v}'")
            try:
                return int(v) # Store as int if possible
            except ValueError:
                 raise ValueError(f"Could not convert port '{v}' to a number") # Should not happen if isdigit passed
        elif not isinstance(v, int):
            raise TypeError(f"Port must be an integer or string, got {type(v).__name__}")
        if not 0 <= v <= 65535:
             raise ValueError(f"Port must be between 0 and 65535, got {v}")
        return v


class ToolConfigSchema(BaseModel):
    """Pydantic schema defining the expected structure and types for the configuration."""

    # Use Field to define defaults and descriptions matching DEFAULT_CONFIG
    databases: Dict[str, DatabaseSettings] = Field(..., description="Django DATABASES setting dictionary.")
    output_dir: str = Field("./generated_api_django", min_length=1, description="Directory for generated project output.")
    project_name: str = Field("myapi_django", min_length=1, description="Name for the generated Django project.")
    app_name: str = Field("api", min_length=1, description="Name for the generated Django app.")
    include_tables: Optional[List[str]] = Field(None, description="Optional list of specific tables to include.")
    exclude_tables: Optional[List[str]] = Field(None, description="Optional list of tables to exclude.")
    relation_style: Literal['pk', 'link', 'nested'] = Field("pk", description="Style for representing relationships ('pk', 'link', 'nested').")
    openapi_title: str = Field("Auto-Generated API", min_length=1, description="Title for the OpenAPI specification.")
    openapi_version: str = Field("1.0.0", min_length=1, description="Version string for the OpenAPI specification.")
    openapi_description: str = Field("API generated automatically.", description="Description for the OpenAPI specification.")
    openapi_server_url: str = Field("http://127.0.0.1:8000/", description="Base URL for the API server in OpenAPI spec.")

    # Internal field, not directly from user config file usually
    SECRET_KEY: Optional[str] = Field(None, description="Internal secret key for Django setup.")

    # --- Custom Validators ---

    @validator('project_name', 'app_name')
    def check_valid_identifier(cls, v, field):
        """Validate project_name and app_name are valid Python identifiers."""
        if not is_valid_python_identifier(v):
            raise ValueError(f"'{v}' is not a valid Python identifier or is a reserved keyword. Use snake_case, start with a letter or underscore.")
        return v

    @validator('include_tables', 'exclude_tables', pre=True, each_item=True)
    def check_table_names_are_strings(cls, v):
        """Ensure table names in lists are strings."""
        if not isinstance(v, str):
            raise TypeError(f"Table names in include/exclude lists must be strings, found: {type(v).__name__}")
        if not v:
            raise ValueError("Table names in include/exclude lists cannot be empty strings.")
        return v

    @root_validator(pre=False) # Runs after individual field validation
    def check_default_database_exists(cls, values):
        """Ensure the 'databases' dictionary contains a 'default' key."""
        databases_dict = values.get('databases')
        if databases_dict and 'default' not in databases_dict:
            raise ValueError("The 'databases' configuration must contain a 'default' key specifying the database to introspect.")
        # Add other cross-field validation if needed
        return values


# --- Validation Function ---

def validate_config_dict(config_dict: Dict[str, Any]) -> ToolConfigSchema:
    """
    Validates a raw configuration dictionary against the Pydantic schema.

    Args:
        config_dict: The raw dictionary loaded from YAML/CLI args.

    Returns:
        A validated Pydantic model instance if successful.

    Raises:
        SystemExit: If validation fails, prints formatted errors and exits.
    """
    try:
        # Attempt to parse the raw dictionary into the Pydantic model
        validated_config = ToolConfigSchema.parse_obj(config_dict)
        logger.debug("Configuration validation successful.")
        return validated_config
    except ValidationError as e:
        logger.error("Configuration validation failed. Please check your config file or arguments.")
        print("\n--- Configuration Errors ---", file=sys.stderr)
        for error in e.errors():
            loc = " -> ".join(map(str, error.get('loc', ()))) # Location path (e.g., databases -> default -> PORT)
            msg = error.get('msg', 'Unknown error')
            print(f"  - Location: '{loc}'", file=sys.stderr)
            print(f"    Error: {msg}", file=sys.stderr)
            # Add specific hints based on error type if helpful
            if 'type' in error:
                err_type = error['type']
                if 'identifier' in err_type:
                    print("    Hint: Ensure the value is a valid Python variable name (letters, numbers, underscores, not starting with a number, not a keyword).", file=sys.stderr)
                elif 'literal' in err_type and loc == 'relation_style':
                    allowed = error.get('ctx', {}).get('expected', "'pk', 'link', 'nested'")
                    print(f"    Hint: Allowed values are {allowed}.", file=sys.stderr)
                elif 'value_error.list.str' in err_type:
                    print("    Hint: Items in this list should be non-empty strings.", file=sys.stderr)

        print("----------------------------", file=sys.stderr)
        import sys # Import sys locally if not already imported
        sys.exit(1) # Exit the program due to invalid config
