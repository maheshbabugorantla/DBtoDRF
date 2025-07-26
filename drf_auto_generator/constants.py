"""
Centralized constants for DRF Auto Generator.

This module contains all configuration constants, field mappings, and default values
that were previously scattered across the codebase. This improves maintainability
and makes it easier for contributors to modify behavior.
"""

from typing import Dict, Set, List, Any


# =============================================================================
# CORE CONFIGURATION
# =============================================================================

class DefaultConfig:
    """Default configuration values."""

    # Project defaults
    OUTPUT_DIR = "./generated_api_django"
    PROJECT_NAME = "myapi_django"
    APP_NAME = "api"

    # OpenAPI defaults
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_TITLE = "Auto-Generated API"
    OPENAPI_VERSION_NUMBER = "1.0.0"
    OPENAPI_DESCRIPTION = "API generated automatically."
    OPENAPI_SERVER_URL = "http://127.0.0.1:8000/"

    # Generation options
    RELATION_STYLE = "pk"
    GENERATE_API_TESTS = True
    USE_TIMESTAMPS = True
    AUTO_ADD_STR_METHOD = True


class SupportedDatabases:
    """Supported database engines."""

    POSTGRESQL = 'django.db.backends.postgresql'
    SQLITE = 'django.db.backends.sqlite3'
    MYSQL = 'django.db.backends.mysql'
    ORACLE = 'django.db.backends.oracle'

    ALL = [POSTGRESQL, SQLITE, MYSQL, ORACLE]

    # Currently fully supported
    SUPPORTED = [POSTGRESQL, SQLITE, MYSQL]


# =============================================================================
# FIELD TYPE MAPPINGS
# =============================================================================

class DjangoFieldTypes:
    """Django model field types and their properties."""

    # Auto fields
    AUTO_FIELD = "AutoField"
    BIG_AUTO_FIELD = "BigAutoField"
    SMALL_AUTO_FIELD = "SmallAutoField"

    # Numeric fields
    INTEGER_FIELD = "IntegerField"
    BIG_INTEGER_FIELD = "BigIntegerField"
    SMALL_INTEGER_FIELD = "SmallIntegerField"
    POSITIVE_INTEGER_FIELD = "PositiveIntegerField"
    POSITIVE_BIG_INTEGER_FIELD = "PositiveBigIntegerField"
    POSITIVE_SMALL_INTEGER_FIELD = "PositiveSmallIntegerField"
    FLOAT_FIELD = "FloatField"
    DECIMAL_FIELD = "DecimalField"

    # String fields
    CHAR_FIELD = "CharField"
    TEXT_FIELD = "TextField"
    EMAIL_FIELD = "EmailField"
    URL_FIELD = "URLField"
    SLUG_FIELD = "SlugField"

    # Date/time fields
    DATE_FIELD = "DateField"
    DATE_TIME_FIELD = "DateTimeField"
    TIME_FIELD = "TimeField"
    DURATION_FIELD = "DurationField"

    # Other fields
    BOOLEAN_FIELD = "BooleanField"
    UUID_FIELD = "UUIDField"
    JSON_FIELD = "JSONField"
    BINARY_FIELD = "BinaryField"
    FILE_FIELD = "FileField"
    IMAGE_FIELD = "ImageField"
    GENERIC_IP_ADDRESS_FIELD = "GenericIPAddressField"
    FILE_PATH_FIELD = "FilePathField"


# Database type to Django field mapping
DJANGO_FIELD_MAP: Dict[str, str] = {
    # Auto fields
    DjangoFieldTypes.AUTO_FIELD: DjangoFieldTypes.AUTO_FIELD,
    DjangoFieldTypes.BIG_AUTO_FIELD: DjangoFieldTypes.BIG_AUTO_FIELD,
    DjangoFieldTypes.SMALL_AUTO_FIELD: DjangoFieldTypes.SMALL_AUTO_FIELD,

    # Numeric fields
    DjangoFieldTypes.INTEGER_FIELD: DjangoFieldTypes.INTEGER_FIELD,
    DjangoFieldTypes.BIG_INTEGER_FIELD: DjangoFieldTypes.BIG_INTEGER_FIELD,
    DjangoFieldTypes.SMALL_INTEGER_FIELD: DjangoFieldTypes.SMALL_INTEGER_FIELD,
    DjangoFieldTypes.POSITIVE_INTEGER_FIELD: DjangoFieldTypes.POSITIVE_INTEGER_FIELD,
    DjangoFieldTypes.POSITIVE_BIG_INTEGER_FIELD: DjangoFieldTypes.POSITIVE_BIG_INTEGER_FIELD,
    DjangoFieldTypes.POSITIVE_SMALL_INTEGER_FIELD: DjangoFieldTypes.POSITIVE_SMALL_INTEGER_FIELD,
    DjangoFieldTypes.FLOAT_FIELD: DjangoFieldTypes.FLOAT_FIELD,
    DjangoFieldTypes.DECIMAL_FIELD: DjangoFieldTypes.DECIMAL_FIELD,

    # String fields
    DjangoFieldTypes.CHAR_FIELD: DjangoFieldTypes.CHAR_FIELD,
    DjangoFieldTypes.TEXT_FIELD: DjangoFieldTypes.TEXT_FIELD,
    DjangoFieldTypes.EMAIL_FIELD: DjangoFieldTypes.EMAIL_FIELD,
    DjangoFieldTypes.URL_FIELD: DjangoFieldTypes.URL_FIELD,
    DjangoFieldTypes.SLUG_FIELD: DjangoFieldTypes.SLUG_FIELD,

    # Date/time fields
    DjangoFieldTypes.DATE_FIELD: DjangoFieldTypes.DATE_FIELD,
    DjangoFieldTypes.DATE_TIME_FIELD: DjangoFieldTypes.DATE_TIME_FIELD,
    DjangoFieldTypes.TIME_FIELD: DjangoFieldTypes.TIME_FIELD,
    DjangoFieldTypes.DURATION_FIELD: DjangoFieldTypes.DURATION_FIELD,

    # Other fields
    DjangoFieldTypes.BOOLEAN_FIELD: DjangoFieldTypes.BOOLEAN_FIELD,
    DjangoFieldTypes.UUID_FIELD: DjangoFieldTypes.UUID_FIELD,
    DjangoFieldTypes.JSON_FIELD: DjangoFieldTypes.JSON_FIELD,
    DjangoFieldTypes.BINARY_FIELD: DjangoFieldTypes.BINARY_FIELD,
    DjangoFieldTypes.FILE_FIELD: DjangoFieldTypes.FILE_FIELD,
    DjangoFieldTypes.IMAGE_FIELD: DjangoFieldTypes.IMAGE_FIELD,
    DjangoFieldTypes.GENERIC_IP_ADDRESS_FIELD: DjangoFieldTypes.GENERIC_IP_ADDRESS_FIELD,
    DjangoFieldTypes.FILE_PATH_FIELD: DjangoFieldTypes.FILE_PATH_FIELD,
}


# OpenAPI schema type mappings
OPENAPI_TYPE_MAP: Dict[str, Dict[str, Any]] = {
    # Auto fields
    DjangoFieldTypes.AUTO_FIELD: {"type": "integer", "readOnly": True},
    DjangoFieldTypes.BIG_AUTO_FIELD: {"type": "integer", "format": "int64", "readOnly": True},
    DjangoFieldTypes.SMALL_AUTO_FIELD: {"type": "integer", "readOnly": True},

    # Numeric fields
    DjangoFieldTypes.INTEGER_FIELD: {"type": "integer"},
    DjangoFieldTypes.BIG_INTEGER_FIELD: {"type": "integer", "format": "int64"},
    DjangoFieldTypes.SMALL_INTEGER_FIELD: {"type": "integer"},
    DjangoFieldTypes.POSITIVE_INTEGER_FIELD: {"type": "integer", "minimum": 0},
    DjangoFieldTypes.POSITIVE_BIG_INTEGER_FIELD: {"type": "integer", "format": "int64", "minimum": 0},
    DjangoFieldTypes.POSITIVE_SMALL_INTEGER_FIELD: {"type": "integer", "minimum": 0},
    DjangoFieldTypes.FLOAT_FIELD: {"type": "number", "format": "float"},
    DjangoFieldTypes.DECIMAL_FIELD: {"type": "number", "format": "double"},

    # String fields
    DjangoFieldTypes.CHAR_FIELD: {"type": "string"},
    DjangoFieldTypes.TEXT_FIELD: {"type": "string"},
    DjangoFieldTypes.EMAIL_FIELD: {"type": "string", "format": "email"},
    DjangoFieldTypes.URL_FIELD: {"type": "string", "format": "uri"},
    DjangoFieldTypes.SLUG_FIELD: {"type": "string", "pattern": r"^[-a-zA-Z0-9_]+$"},

    # Date/time fields
    DjangoFieldTypes.DATE_FIELD: {"type": "string", "format": "date"},
    DjangoFieldTypes.DATE_TIME_FIELD: {"type": "string", "format": "date-time"},
    DjangoFieldTypes.TIME_FIELD: {"type": "string", "format": "time"},
    DjangoFieldTypes.DURATION_FIELD: {"type": "string", "format": "duration"},

    # Other fields
    DjangoFieldTypes.BOOLEAN_FIELD: {"type": "boolean"},
    DjangoFieldTypes.UUID_FIELD: {"type": "string", "format": "uuid"},
    DjangoFieldTypes.JSON_FIELD: {"type": "object", "additionalProperties": True},
    DjangoFieldTypes.BINARY_FIELD: {"type": "string", "format": "byte"},
    DjangoFieldTypes.FILE_FIELD: {"type": "string", "format": "uri", "readOnly": True},
    DjangoFieldTypes.IMAGE_FIELD: {"type": "string", "format": "uri", "readOnly": True},
    DjangoFieldTypes.GENERIC_IP_ADDRESS_FIELD: {"type": "string", "format": "ipv4 or ipv6"},

    # Fallback
    "Unknown": {"type": "string", "description": "Type mapping fallback."}
}


# =============================================================================
# FIELD CATEGORIES
# =============================================================================

class FieldCategories:
    """Categorized field types for different operations."""

    # Field option categories
    BOOLEAN_OPTIONS: Set[str] = {"primary_key", "unique", "null", "blank"}
    NUMERIC_OPTIONS: Set[str] = {"max_length", "max_digits", "decimal_places"}
    STRING_OPTIONS: Set[str] = {"max_length", "choices"}

    # Searchable field types (for Django admin and filters)
    SEARCHABLE_TYPES: List[str] = [
        DjangoFieldTypes.CHAR_FIELD,
        DjangoFieldTypes.TEXT_FIELD,
        DjangoFieldTypes.EMAIL_FIELD
    ]

    # Display-friendly field types (for admin list_display)
    DISPLAY_TYPES: List[str] = [
        DjangoFieldTypes.CHAR_FIELD,
        DjangoFieldTypes.TEXT_FIELD,
        DjangoFieldTypes.EMAIL_FIELD,
        DjangoFieldTypes.URL_FIELD
    ]

    # Filterable field types (for admin list_filter)
    FILTER_TYPES: List[str] = [
        DjangoFieldTypes.BOOLEAN_FIELD,
        DjangoFieldTypes.DATE_FIELD,
        DjangoFieldTypes.DATE_TIME_FIELD,
        DjangoFieldTypes.INTEGER_FIELD,
        DjangoFieldTypes.FLOAT_FIELD,
        DjangoFieldTypes.DECIMAL_FIELD
    ]

    # Integer field types
    INTEGER_TYPES: List[str] = [
        DjangoFieldTypes.INTEGER_FIELD,
        DjangoFieldTypes.BIG_INTEGER_FIELD,
        DjangoFieldTypes.SMALL_INTEGER_FIELD,
        DjangoFieldTypes.POSITIVE_INTEGER_FIELD,
        DjangoFieldTypes.POSITIVE_BIG_INTEGER_FIELD,
        DjangoFieldTypes.POSITIVE_SMALL_INTEGER_FIELD
    ]

    # Date/time field types
    DATE_TIME_TYPES: List[str] = [
        DjangoFieldTypes.DATE_FIELD,
        DjangoFieldTypes.DATE_TIME_FIELD,
        DjangoFieldTypes.TIME_FIELD
    ]

    # Text field types
    TEXT_TYPES: List[str] = [
        DjangoFieldTypes.CHAR_FIELD,
        DjangoFieldTypes.TEXT_FIELD,
        DjangoFieldTypes.EMAIL_FIELD,
        DjangoFieldTypes.URL_FIELD,
        DjangoFieldTypes.SLUG_FIELD
    ]


# =============================================================================
# NAMING CONVENTIONS
# =============================================================================

class FieldNames:
    """Common field names and patterns."""

    # Common descriptive field names for __str__ method
    DESCRIPTIVE_NAMES: List[str] = [
        'name', 'title', 'username', 'email', 'description', 'label', 'slug'
    ]

    # Timestamp field names
    TIMESTAMP_NAMES: List[str] = [
        'created_at', 'updated_at', 'created', 'modified',
        'creation_date', 'modification_date', 'timestamp'
    ]

    # Common admin display field names
    ADMIN_DISPLAY_NAMES: List[str] = [
        'name', 'title', 'email', 'username', 'code', 'status'
    ]

    # Reserved Python keywords (for field name validation)
    PYTHON_KEYWORDS: Set[str] = {
        "False", "None", "True", "and", "as", "assert", "async", "await",
        "break", "class", "continue", "def", "del", "elif", "else", "except",
        "finally", "for", "from", "global", "if", "import", "in", "is",
        "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
        "while", "with", "yield"
    }


# =============================================================================
# HTTP AND API CONSTANTS
# =============================================================================

class HTTPResponses:
    """Standard HTTP response codes and descriptions."""

    SUCCESS_CODES = {
        200: "OK",
        201: "Created",
        204: "No Content"
    }

    CLIENT_ERROR_CODES = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        422: "Unprocessable Entity"
    }

    SERVER_ERROR_CODES = {
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable"
    }

    @classmethod
    def get_all_codes(cls) -> Dict[int, str]:
        """Get all HTTP response codes."""
        return {**cls.SUCCESS_CODES, **cls.CLIENT_ERROR_CODES, **cls.SERVER_ERROR_CODES}


class URLPatterns:
    """URL pattern constants."""

    ROOT = "/"
    EMPTY = ""
    ADMIN = "admin/"
    API = "api/"
    SCHEMA = "api/schema/"
    SWAGGER_UI = "api/schema/swagger-ui/"
    REDOC = "api/schema/redoc/"
    AUTH_TOKEN = "api/auth-token/"


# =============================================================================
# PACKAGE VERSIONS
# =============================================================================

class PackageVersions:
    """Required package versions."""

    # Core dependencies
    DJANGO = ">= 5.2"
    DJANGORESTFRAMEWORK = ">= 3.16.0"
    DRF_SPECTACULAR = ">= 0.28.0"

    # Database drivers
    PSYCOPG2_BINARY = ">= 2.9.10"
    MYSQLCLIENT = ">= 2.2.3"
    DJANGO_MSSQL_BACKEND = ">= 1.1.0"
    PYODBC = ">= 5.1.0"

    # Optional dependencies
    PYTHON_DOTENV = ">= 0.24.0"
    IPYTHON = ">= 8.17.0"
    DJANGO_ENVIRON = ">= 0.11.2"
    DJANGO_FILTER = ">= 23.2"
    DJANGORESTFRAMEWORK_SIMPLEJWT = ">= 5.0"
    DJANGO_CORS_HEADERS = ">= 4.6.0"

    # Testing dependencies
    SCHEMATHESIS = ">= 3.19.0"
    HYPOTHESIS = ">= 6.82.0"
    REQUESTS = ">= 2.31.0"

    # Deployment
    GUNICORN = ">= 23.0.0"
    WHITENOISE = ">= 6.0"


# =============================================================================
# UTILITY CONSTANTS
# =============================================================================

class FileExtensions:
    """Common file extensions."""

    PYTHON = ".py"
    YAML = ".yaml"
    JSON = ".json"
    JINJA2 = ".j2"
    MARKDOWN = ".md"
    TEXT = ".txt"


class RelationshipDefaults:
    """Default values for relationships."""

    ON_DELETE_CASCADE = "CASCADE"
    ON_DELETE_PROTECT = "PROTECT"
    ON_DELETE_SET_NULL = "SET_NULL"

    RELATED_NAME_SUFFIX = "_set"
    THROUGH_SUFFIX = "_through"

    DEFAULT_ON_DELETE = ON_DELETE_CASCADE


class GenerationOptions:
    """Code generation options."""

    DEFAULT_INDENT = "    "  # 4 spaces
    DEFAULT_LINE_LENGTH = 88  # Black default

    # Template directories
    TEMPLATE_DIR = "templates"
    AST_CODEGEN_DIR = "ast_codegen"

    # Generated file suffixes
    MODEL_SUFFIX = "_models"
    SERIALIZER_SUFFIX = "_serializers"
    VIEW_SUFFIX = "_views"
    URL_SUFFIX = "_urls"
    ADMIN_SUFFIX = "_admin"
