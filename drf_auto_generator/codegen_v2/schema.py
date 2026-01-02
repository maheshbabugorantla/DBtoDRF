"""
Pydantic-based Intermediate Representation (IR) for database schemas.

This module defines the schema models that serve as the single source of truth
for code generation. These models can be:
- Generated from database introspection
- Loaded from YAML/JSON configuration files
- Serialized for caching or version control
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
import inflect

_inflect_engine = inflect.engine()


class FieldType(str, Enum):
    """Database/Django field types."""
    # Auto fields
    AUTO = "AutoField"
    BIG_AUTO = "BigAutoField"
    SMALL_AUTO = "SmallAutoField"

    # Integer fields
    INTEGER = "IntegerField"
    BIG_INTEGER = "BigIntegerField"
    SMALL_INTEGER = "SmallIntegerField"
    POSITIVE_INTEGER = "PositiveIntegerField"
    POSITIVE_BIG_INTEGER = "PositiveBigIntegerField"
    POSITIVE_SMALL_INTEGER = "PositiveSmallIntegerField"

    # String fields
    CHAR = "CharField"
    TEXT = "TextField"
    EMAIL = "EmailField"
    URL = "URLField"
    SLUG = "SlugField"

    # Numeric fields
    FLOAT = "FloatField"
    DECIMAL = "DecimalField"

    # Boolean
    BOOLEAN = "BooleanField"
    NULL_BOOLEAN = "NullBooleanField"

    # Date/Time
    DATE = "DateField"
    DATETIME = "DateTimeField"
    TIME = "TimeField"
    DURATION = "DurationField"

    # Binary/File
    BINARY = "BinaryField"
    FILE = "FileField"
    IMAGE = "ImageField"

    # Special
    UUID = "UUIDField"
    JSON = "JSONField"
    IP_ADDRESS = "GenericIPAddressField"

    # Relationships
    FOREIGN_KEY = "ForeignKey"
    ONE_TO_ONE = "OneToOneField"
    MANY_TO_MANY = "ManyToManyField"


class RelationshipType(str, Enum):
    """Types of database relationships."""
    MANY_TO_ONE = "many-to-one"
    ONE_TO_ONE = "one-to-one"
    MANY_TO_MANY = "many-to-many"
    ONE_TO_MANY = "one-to-many"  # Reverse of many-to-one


class ColumnSchema(BaseModel):
    """Represents a database column with all its properties."""

    name: str = Field(..., description="Column name in the database")
    field_type: FieldType = Field(..., description="Django field type")

    # Constraints
    nullable: bool = Field(default=True, description="Whether the column allows NULL")
    primary_key: bool = Field(default=False, description="Is this a primary key")
    unique: bool = Field(default=False, description="Is this column unique")

    # Size/precision
    max_length: Optional[int] = Field(default=None, description="Max length for char fields")
    max_digits: Optional[int] = Field(default=None, description="Max digits for decimal fields")
    decimal_places: Optional[int] = Field(default=None, description="Decimal places for decimal fields")

    # Default value
    default: Optional[Any] = Field(default=None, description="Default value")

    # Enum/choices
    choices: Optional[list[tuple[str, str]]] = Field(default=None, description="Choice tuples for enum fields")

    # Original database info (for reference)
    db_type: Optional[str] = Field(default=None, description="Original database type")
    db_column: Optional[str] = Field(default=None, description="Database column name if different from field name")

    # Metadata
    comment: Optional[str] = Field(default=None, description="Column comment/description")

    @property
    def django_field_name(self) -> str:
        """Get the Django-friendly field name (snake_case, cleaned)."""
        # Remove trailing _id for FK fields, clean reserved words, etc.
        name = self.name.lower()
        # Handle Python reserved words
        if name in ('class', 'def', 'return', 'import', 'from', 'as', 'is', 'in', 'not', 'and', 'or'):
            name = f"{name}_field"
        return name

    def get_field_options(self) -> dict[str, Any]:
        """Generate Django field options dictionary."""
        options: dict[str, Any] = {}

        # Primary key is handled by AutoField or explicit primary_key=True
        if self.primary_key and self.field_type not in (FieldType.AUTO, FieldType.BIG_AUTO, FieldType.SMALL_AUTO):
            options["primary_key"] = True

        # Nullability
        if self.nullable:
            options["null"] = True
            if self.field_type in (FieldType.CHAR, FieldType.TEXT, FieldType.EMAIL, FieldType.URL, FieldType.SLUG):
                options["blank"] = True

        # Unique
        if self.unique and not self.primary_key:
            options["unique"] = True

        # Size constraints
        if self.max_length is not None:
            options["max_length"] = self.max_length
        if self.max_digits is not None:
            options["max_digits"] = self.max_digits
        if self.decimal_places is not None:
            options["decimal_places"] = self.decimal_places

        # Default value
        if self.default is not None:
            options["default"] = self.default

        # Choices
        if self.choices:
            options["choices"] = self.choices

        # DB column name
        if self.db_column and self.db_column != self.name:
            options["db_column"] = self.db_column

        return options


class RelationshipSchema(BaseModel):
    """Represents a relationship between tables."""

    name: str = Field(..., description="Relationship field name")
    type: RelationshipType = Field(..., description="Type of relationship")
    target_table: str = Field(..., description="Target table name")
    target_model: Optional[str] = Field(default=None, description="Target model name (auto-generated if not provided)")

    # Columns involved
    source_column: Optional[str] = Field(default=None, description="Source column (for FK)")
    target_column: Optional[str] = Field(default=None, description="Target column (usually PK)")

    # Django options
    related_name: Optional[str] = Field(default=None, description="Related name for reverse access")
    on_delete: str = Field(default="CASCADE", description="On delete behavior")
    db_column: Optional[str] = Field(default=None, description="Database column name")

    # M2M specific
    through_table: Optional[str] = Field(default=None, description="Through table for M2M")
    through_model: Optional[str] = Field(default=None, description="Through model name")
    through_fields: Optional[tuple[str, str]] = Field(default=None, description="Through fields tuple")
    symmetrical: Optional[bool] = Field(default=None, description="Symmetrical for self-referential M2M")

    # Metadata
    nullable: bool = Field(default=True, description="Whether the FK is nullable")

    @property
    def django_field_type(self) -> str:
        """Get the Django field type for this relationship."""
        type_map = {
            RelationshipType.MANY_TO_ONE: "ForeignKey",
            RelationshipType.ONE_TO_ONE: "OneToOneField",
            RelationshipType.MANY_TO_MANY: "ManyToManyField",
        }
        return type_map.get(self.type, "ForeignKey")

    def get_field_options(self) -> dict[str, Any]:
        """Generate Django field options dictionary."""
        options: dict[str, Any] = {}

        if self.related_name:
            options["related_name"] = self.related_name

        if self.db_column:
            options["db_column"] = self.db_column

        if self.type in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE):
            options["on_delete"] = self.on_delete
            if self.nullable:
                options["null"] = True
                options["blank"] = True

        if self.type == RelationshipType.MANY_TO_MANY:
            options["blank"] = True
            if self.through_model:
                options["through"] = self.through_model
            if self.through_fields:
                options["through_fields"] = self.through_fields
            if self.symmetrical is not None:
                options["symmetrical"] = self.symmetrical

        return options


class IndexSchema(BaseModel):
    """Represents a database index."""

    name: Optional[str] = Field(default=None, description="Index name")
    fields: list[str] = Field(..., description="Fields in the index")
    unique: bool = Field(default=False, description="Is this a unique index")

    # Advanced options
    condition: Optional[str] = Field(default=None, description="Partial index condition")
    include: Optional[list[str]] = Field(default=None, description="Included columns (covering index)")


class ConstraintSchema(BaseModel):
    """Represents a database constraint."""

    name: str = Field(..., description="Constraint name")
    type: str = Field(..., description="Constraint type: unique, check, exclusion")
    fields: list[str] = Field(default_factory=list, description="Fields in the constraint")
    condition: Optional[str] = Field(default=None, description="Check constraint condition")


class TableSchema(BaseModel):
    """Represents a database table with all its properties."""

    name: str = Field(..., description="Table name in the database")
    model_name: Optional[str] = Field(default=None, description="Django model name (auto-generated if not provided)")

    # Structure
    columns: list[ColumnSchema] = Field(default_factory=list, description="Table columns")
    relationships: list[RelationshipSchema] = Field(default_factory=list, description="Relationships to other tables")

    # Constraints and indexes
    primary_key_columns: list[str] = Field(default_factory=list, description="Primary key column names")
    indexes: list[IndexSchema] = Field(default_factory=list, description="Table indexes")
    constraints: list[ConstraintSchema] = Field(default_factory=list, description="Table constraints")

    # Metadata
    comment: Optional[str] = Field(default=None, description="Table comment/description")
    is_m2m_through_table: bool = Field(default=False, description="Is this a M2M through table")

    def model_post_init(self, __context) -> None:
        """Generate model name from table name if not provided."""
        if self.model_name is None:
            # Convert snake_case to PascalCase and singularize
            words = self.name.split('_')
            pascal = ''.join(word.capitalize() for word in words)
            # Try to singularize (users -> User)
            singular = _inflect_engine.singular_noun(pascal)
            object.__setattr__(self, 'model_name', singular if singular else pascal)

    @property
    def has_composite_pk(self) -> bool:
        """Check if table has a composite primary key."""
        return len(self.primary_key_columns) > 1

    @property
    def pk_column(self) -> Optional[str]:
        """Get the primary key column (for single PK tables)."""
        if len(self.primary_key_columns) == 1:
            return self.primary_key_columns[0]
        return None

    def get_column(self, name: str) -> Optional[ColumnSchema]:
        """Get a column by name."""
        return next((c for c in self.columns if c.name == name), None)

    def get_searchable_fields(self, limit: int = 5) -> list[str]:
        """Get fields suitable for search functionality."""
        searchable_types = {FieldType.CHAR, FieldType.TEXT, FieldType.EMAIL}
        return [
            col.name for col in self.columns
            if col.field_type in searchable_types
        ][:limit]

    def get_filterable_fields(self) -> list[str]:
        """Get fields suitable for filtering."""
        # Include FK relationships and indexed fields
        fields = [rel.name for rel in self.relationships if rel.type == RelationshipType.MANY_TO_ONE]
        for idx in self.indexes:
            fields.extend(idx.fields)
        return list(set(fields))


class DatabaseSchema(BaseModel):
    """
    Complete database schema - the main IR for code generation.

    This is the single source of truth that can be:
    - Generated from database introspection
    - Loaded from YAML/JSON configuration
    - Cached and versioned
    """

    tables: list[TableSchema] = Field(default_factory=list, description="All tables in the database")

    # Generation metadata
    database_name: Optional[str] = Field(default=None, description="Database name")
    database_type: str = Field(default="postgresql", description="Database type")

    # Project configuration
    project_name: str = Field(default="django_project", description="Django project name")
    app_name: str = Field(default="api", description="Django app name")

    def get_table(self, name: str) -> Optional[TableSchema]:
        """Get a table by name."""
        return next((t for t in self.tables if t.name == name), None)

    def get_non_through_tables(self) -> list[TableSchema]:
        """Get tables that are not M2M through tables."""
        return [t for t in self.tables if not t.is_m2m_through_table]

    def to_yaml(self) -> str:
        """Serialize to YAML format."""
        import yaml
        # Use mode='json' to convert enums to their values
        data = self.model_dump(mode='json', exclude_none=True)
        return yaml.dump(data, default_flow_style=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "DatabaseSchema":
        """Load from YAML string."""
        import yaml
        data = yaml.safe_load(yaml_str)
        return cls.model_validate(data)

    @classmethod
    def from_yaml_file(cls, path: str) -> "DatabaseSchema":
        """Load from YAML file."""
        with open(path, 'r') as f:
            return cls.from_yaml(f.read())

    def save_yaml(self, path: str) -> None:
        """Save to YAML file."""
        with open(path, 'w') as f:
            f.write(self.to_yaml())
