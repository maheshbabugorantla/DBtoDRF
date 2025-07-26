"""
Validation utilities for DRF Auto Generator.

This module provides comprehensive validation functions for configuration,
database connections, and other critical components.
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from .constants import SupportedDatabases, FieldNames
from .exceptions import ValidationError


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def __post_init__(self):
        """Ensure consistency."""
        if self.errors and self.is_valid:
            self.is_valid = False

    def add_error(self, error: str) -> None:
        """Add an error."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning."""
        self.warnings.append(warning)

    def raise_if_invalid(self) -> None:
        """Raise ValidationError if invalid."""
        if not self.is_valid:
            raise ValidationError(
                f"Validation failed: {'; '.join(self.errors)}",
                context={"errors": self.errors, "warnings": self.warnings}
            )


class DatabaseValidator:
    """Validates database configurations and connections."""

    @staticmethod
    def validate_engine(engine: str) -> ValidationResult:
        """Validate database engine."""
        result = ValidationResult(True, [], [])

        if not engine:
            result.add_error("Database engine is required")
            return result

        if engine not in SupportedDatabases.ALL:
            result.add_error(f"Unsupported database engine: {engine}")
            result.add_error(f"Supported engines: {', '.join(SupportedDatabases.ALL)}")
            return result

        if engine not in SupportedDatabases.SUPPORTED:
            result.add_warning(f"Database engine '{engine}' has limited support")

        return result

    @staticmethod
    def validate_connection_params(
        engine: str,
        name: str,
        user: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None
    ) -> ValidationResult:
        """Validate database connection parameters."""
        result = ValidationResult(True, [], [])

        # Validate database name
        if not name:
            result.add_error("Database name is required")
            return result

        # SQLite-specific validation
        if engine == SupportedDatabases.SQLITE:
            if user or password or host or port:
                result.add_warning("SQLite doesn't use user/password/host/port parameters")

            # Check if SQLite file path is valid
            if not name.startswith(':memory:'):
                db_path = Path(name)
                if not db_path.parent.exists():
                    result.add_error(f"SQLite database directory doesn't exist: {db_path.parent}")

        # PostgreSQL/MySQL validation
        elif engine in [SupportedDatabases.POSTGRESQL, SupportedDatabases.MYSQL]:
            if not user:
                result.add_error("Database user is required for PostgreSQL/MySQL")

            if not host:
                result.add_warning("Database host not specified, using 'localhost'")

            # Validate port ranges
            if port is not None:
                if port < 1 or port > 65535:
                    result.add_error(f"Invalid port number: {port}")
                elif engine == SupportedDatabases.POSTGRESQL and port != 5432:
                    result.add_warning(f"Non-standard PostgreSQL port: {port}")
                elif engine == SupportedDatabases.MYSQL and port != 3306:
                    result.add_warning(f"Non-standard MySQL port: {port}")

        return result

    @staticmethod
    def validate_database_name(name: str) -> ValidationResult:
        """Validate database name format."""
        result = ValidationResult(True, [], [])

        if not name:
            result.add_error("Database name cannot be empty")
            return result

        # Check for invalid characters
        if re.search(r'[^\w\-\.]', name):
            result.add_error("Database name contains invalid characters")

        # Check length
        if len(name) > 63:
            result.add_error("Database name is too long (max 63 characters)")

        # Check for reserved names
        reserved_names = ['postgres', 'mysql', 'information_schema', 'performance_schema']
        if name.lower() in reserved_names:
            result.add_error(f"Database name '{name}' is reserved")

        return result


class ProjectValidator:
    """Validates project configuration and structure."""

    @staticmethod
    def validate_project_name(name: str) -> ValidationResult:
        """Validate Django project name."""
        result = ValidationResult(True, [], [])

        if not name:
            result.add_error("Project name is required")
            return result

        # Check Python identifier rules
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            result.add_error("Project name must be a valid Python identifier")

        # Check for Python keywords
        if name in FieldNames.PYTHON_KEYWORDS:
            result.add_error(f"Project name '{name}' is a Python keyword")

        # Check for Django reserved names
        django_reserved = ['django', 'test', 'admin', 'auth', 'contenttypes', 'sessions']
        if name.lower() in django_reserved:
            result.add_error(f"Project name '{name}' conflicts with Django")

        # Check length
        if len(name) > 50:
            result.add_warning("Project name is quite long, consider shortening")

        return result

    @staticmethod
    def validate_app_name(name: str) -> ValidationResult:
        """Validate Django app name."""
        result = ValidationResult(True, [], [])

        if not name:
            result.add_error("App name is required")
            return result

        # Check Python identifier rules
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            result.add_error("App name must be a valid Python identifier")

        # Check for Python keywords
        if name in FieldNames.PYTHON_KEYWORDS:
            result.add_error(f"App name '{name}' is a Python keyword")

        # Check for Django reserved names
        django_reserved = ['django', 'test', 'admin', 'auth', 'contenttypes', 'sessions']
        if name.lower() in django_reserved:
            result.add_error(f"App name '{name}' conflicts with Django")

        return result

    @staticmethod
    def validate_output_directory(path: str) -> ValidationResult:
        """Validate output directory."""
        result = ValidationResult(True, [], [])

        if not path:
            result.add_error("Output directory is required")
            return result

        output_path = Path(path)

        # Check if path is absolute
        if not output_path.is_absolute():
            result.add_warning("Output directory is not absolute, resolving relative to current directory")

        # Check if parent directory exists
        if not output_path.parent.exists():
            result.add_error(f"Parent directory does not exist: {output_path.parent}")

        # Check if path already exists and is not a directory
        if output_path.exists() and not output_path.is_dir():
            result.add_error(f"Output path exists but is not a directory: {output_path}")

        # Check write permissions
        try:
            # Try to create directory if it doesn't exist
            output_path.mkdir(parents=True, exist_ok=True)

            # Test write permissions
            test_file = output_path / '.write_test'
            test_file.touch()
            test_file.unlink()

        except PermissionError:
            result.add_error(f"No write permission for output directory: {output_path}")
        except Exception as e:
            result.add_error(f"Cannot access output directory: {e}")

        return result


class TableValidator:
    """Validates table names and configurations."""

    @staticmethod
    def validate_table_name(name: str) -> ValidationResult:
        """Validate table name for Django model generation."""
        result = ValidationResult(True, [], [])

        if not name:
            result.add_error("Table name cannot be empty")
            return result

        # Check for invalid characters
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            result.add_error("Table name must be a valid identifier")

        # Check for Python keywords
        if name in FieldNames.PYTHON_KEYWORDS:
            result.add_error(f"Table name '{name}' is a Python keyword")

        # Check length
        if len(name) > 63:
            result.add_error("Table name is too long (max 63 characters)")

        # Check for Django reserved names
        django_reserved = ['user', 'group', 'permission', 'contenttype', 'session']
        if name.lower() in django_reserved:
            result.add_warning(f"Table name '{name}' may conflict with Django built-ins")

        return result

    @staticmethod
    def validate_field_name(name: str) -> ValidationResult:
        """Validate field name for Django model generation."""
        result = ValidationResult(True, [], [])

        if not name:
            result.add_error("Field name cannot be empty")
            return result

        # Check for invalid characters
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            result.add_error("Field name must be a valid identifier")

        # Check for Python keywords
        if name in FieldNames.PYTHON_KEYWORDS:
            result.add_error(f"Field name '{name}' is a Python keyword")

        # Check for Django reserved field names
        django_reserved = ['id', 'pk', 'clean', 'clean_fields', 'save', 'delete']
        if name.lower() in django_reserved:
            result.add_warning(f"Field name '{name}' may conflict with Django methods")

        return result


class ConfigValidator:
    """Validates complete configuration objects."""

    @staticmethod
    def validate_config(config_dict: Dict[str, Any]) -> ValidationResult:
        """Validate complete configuration dictionary."""
        result = ValidationResult(True, [], [])

        # Validate required sections
        required_sections = ['database']
        for section in required_sections:
            if section not in config_dict:
                result.add_error(f"Missing required configuration section: {section}")

        if not result.is_valid:
            return result

        # Validate database section
        db_config = config_dict['database']
        db_result = DatabaseValidator.validate_engine(db_config.get('engine', ''))
        result.errors.extend(db_result.errors)
        result.warnings.extend(db_result.warnings)

        conn_result = DatabaseValidator.validate_connection_params(
            db_config.get('engine', ''),
            db_config.get('name', ''),
            db_config.get('user'),
            db_config.get('password'),
            db_config.get('host'),
            db_config.get('port')
        )
        result.errors.extend(conn_result.errors)
        result.warnings.extend(conn_result.warnings)

        # Validate generation section if present
        if 'generation' in config_dict:
            gen_config = config_dict['generation']

            # Validate project name
            if 'project_name' in gen_config:
                proj_result = ProjectValidator.validate_project_name(gen_config['project_name'])
                result.errors.extend(proj_result.errors)
                result.warnings.extend(proj_result.warnings)

            # Validate app name
            if 'app_name' in gen_config:
                app_result = ProjectValidator.validate_app_name(gen_config['app_name'])
                result.errors.extend(app_result.errors)
                result.warnings.extend(app_result.warnings)

            # Validate output directory
            if 'output_dir' in gen_config:
                dir_result = ProjectValidator.validate_output_directory(gen_config['output_dir'])
                result.errors.extend(dir_result.errors)
                result.warnings.extend(dir_result.warnings)

        # Update validation status
        if result.errors:
            result.is_valid = False

        return result

    @staticmethod
    def validate_table_filters(
        include_tables: List[str],
        exclude_tables: List[str],
        available_tables: List[str]
    ) -> ValidationResult:
        """Validate table inclusion/exclusion filters."""
        result = ValidationResult(True, [], [])

        # Check for conflicts
        if include_tables and exclude_tables:
            result.add_warning("Both include_tables and exclude_tables specified. include_tables takes precedence.")

        # Validate include_tables
        if include_tables:
            for table in include_tables:
                if table not in available_tables:
                    result.add_warning(f"Table '{table}' in include_tables not found in database")

        # Validate exclude_tables
        if exclude_tables:
            for table in exclude_tables:
                if table not in available_tables:
                    result.add_warning(f"Table '{table}' in exclude_tables not found in database")

            # Check if excluding all tables
            if len(exclude_tables) >= len(available_tables):
                result.add_warning("Excluding most or all tables - no models will be generated")

        return result


def validate_config_file(file_path: Union[str, Path]) -> ValidationResult:
    """
    Validate configuration file.

    Args:
        file_path: Path to configuration file

    Returns:
        Validation result
    """
    result = ValidationResult(True, [], [])

    config_path = Path(file_path)

    # Check if file exists
    if not config_path.exists():
        result.add_error(f"Configuration file not found: {config_path}")
        return result

    # Check if file is readable
    if not config_path.is_file():
        result.add_error(f"Configuration path is not a file: {config_path}")
        return result

    # Try to read and validate file
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if not isinstance(config_data, dict):
            result.add_error("Configuration file must contain a dictionary")
            return result

        # Validate configuration content
        config_result = ConfigValidator.validate_config(config_data)
        result.errors.extend(config_result.errors)
        result.warnings.extend(config_result.warnings)

    except yaml.YAMLError as e:
        result.add_error(f"Invalid YAML syntax: {e}")
    except Exception as e:
        result.add_error(f"Error reading configuration file: {e}")

    # Update validation status
    if result.errors:
        result.is_valid = False

    return result


def validate_python_identifier(name: str, context: str = "identifier") -> ValidationResult:
    """
    Validate Python identifier.

    Args:
        name: Identifier to validate
        context: Context for error messages

    Returns:
        Validation result
    """
    result = ValidationResult(True, [], [])

    if not name:
        result.add_error(f"{context} cannot be empty")
        return result

    # Check Python identifier rules
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        result.add_error(f"{context} must be a valid Python identifier")

    # Check for Python keywords
    if name in FieldNames.PYTHON_KEYWORDS:
        result.add_error(f"{context} '{name}' is a Python keyword")

    return result
