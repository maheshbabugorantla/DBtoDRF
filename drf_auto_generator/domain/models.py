"""
Core domain models for DRF Auto Generator.

These models represent the essential business concepts and are independent
of specific implementations or frameworks. They serve as the foundation
for all code generation operations.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum
import uuid


class RelationshipType(Enum):
    """Types of database relationships."""

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class FieldType(Enum):
    """Categories of field types."""

    AUTO = "auto"
    INTEGER = "integer"
    FLOAT = "float"
    DECIMAL = "decimal"
    STRING = "string"
    TEXT = "text"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    UUID = "uuid"
    JSON = "json"
    BINARY = "binary"
    FILE = "file"
    FOREIGN_KEY = "foreign_key"
    MANY_TO_MANY = "many_to_many"
    UNKNOWN = "unknown"


@dataclass
class ColumnInfo:
    """
    Represents a database column with all its properties.

    This is the core model for database schema information,
    independent of any specific database implementation.
    """

    # Basic properties
    name: str
    db_type_string: str
    nullable: bool = True
    default: Optional[Any] = None

    # Size and precision
    internal_size: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None

    # Metadata
    collation: Optional[str] = None
    comment: Optional[str] = None

    # Constraints and relationships
    is_pk: bool = False
    is_unique: bool = False
    is_foreign_key: bool = False
    foreign_key_to: Optional[tuple] = None  # (table_name, column_name)

    # Special field types
    enum_values: Optional[List[str]] = None
    is_auto_increment: bool = False

    # Generation hints
    field_type: Optional[FieldType] = None
    django_field_type: Optional[str] = None

    def __post_init__(self):
        """Post-initialization validation and setup."""
        if self.is_pk and self.nullable:
            # Primary keys typically can't be null
            self.nullable = False

        # Infer field type if not provided
        if self.field_type is None:
            self.field_type = self._infer_field_type()

    def _infer_field_type(self) -> FieldType:
        """Infer the field type from database type string."""
        db_type_lower = self.db_type_string.lower()

        if 'auto' in db_type_lower or self.is_auto_increment:
            return FieldType.AUTO
        elif any(t in db_type_lower for t in ['int', 'serial']):
            return FieldType.INTEGER
        elif any(t in db_type_lower for t in ['float', 'real', 'double']):
            return FieldType.FLOAT
        elif any(t in db_type_lower for t in ['decimal', 'numeric']):
            return FieldType.DECIMAL
        elif any(t in db_type_lower for t in ['char', 'varchar']):
            return FieldType.STRING
        elif any(t in db_type_lower for t in ['text', 'clob']):
            return FieldType.TEXT
        elif any(t in db_type_lower for t in ['bool', 'bit']):
            return FieldType.BOOLEAN
        elif 'date' in db_type_lower and 'time' in db_type_lower:
            return FieldType.DATETIME
        elif 'date' in db_type_lower:
            return FieldType.DATE
        elif 'time' in db_type_lower:
            return FieldType.TIME
        elif any(t in db_type_lower for t in ['uuid', 'guid']):
            return FieldType.UUID
        elif any(t in db_type_lower for t in ['json', 'jsonb']):
            return FieldType.JSON
        elif any(t in db_type_lower for t in ['blob', 'binary']):
            return FieldType.BINARY
        else:
            return FieldType.UNKNOWN

    @property
    def is_required(self) -> bool:
        """Check if this field is required (not nullable and no default)."""
        return not self.nullable and self.default is None

    @property
    def has_choices(self) -> bool:
        """Check if this field has enum/choice values."""
        return bool(self.enum_values)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'name': self.name,
            'db_type_string': self.db_type_string,
            'nullable': self.nullable,
            'default': self.default,
            'internal_size': self.internal_size,
            'precision': self.precision,
            'scale': self.scale,
            'collation': self.collation,
            'comment': self.comment,
            'is_pk': self.is_pk,
            'is_unique': self.is_unique,
            'is_foreign_key': self.is_foreign_key,
            'foreign_key_to': self.foreign_key_to,
            'enum_values': self.enum_values,
            'is_auto_increment': self.is_auto_increment,
            'field_type': self.field_type.value if self.field_type else None,
            'django_field_type': self.django_field_type
        }


@dataclass
class RelationshipInfo:
    """
    Represents a relationship between tables.

    This model captures all the information needed to generate
    Django model relationships (ForeignKey, ManyToMany, etc.).
    """

    # Basic relationship info
    name: str
    relationship_type: RelationshipType
    source_table: str
    target_table: str

    # Column mappings
    source_columns: List[str]
    target_columns: List[str]

    # Django-specific options
    related_name: Optional[str] = None
    on_delete: str = "CASCADE"
    db_constraint: bool = True

    # Many-to-many specific
    through_table: Optional[str] = None
    through_fields: Optional[tuple] = None
    symmetrical: Optional[bool] = None

    # Metadata
    comment: Optional[str] = None
    is_self_referential: bool = False

    def __post_init__(self):
        """Post-initialization validation."""
        if not self.related_name:
            self.related_name = self._generate_related_name()

        if self.source_table == self.target_table:
            self.is_self_referential = True

    def _generate_related_name(self) -> str:
        """Generate a related name for the relationship."""
        if self.relationship_type == RelationshipType.MANY_TO_MANY:
            return f"{self.source_table}_set"
        else:
            return f"{self.source_table}s"

    @property
    def is_reverse_relationship(self) -> bool:
        """Check if this is the reverse side of a relationship."""
        return self.relationship_type in [
            RelationshipType.ONE_TO_MANY,
            RelationshipType.MANY_TO_MANY
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        # Build django_field_options for AST generation
        django_field_options = {}

        if self.related_name:
            django_field_options['related_name'] = self.related_name

        if self.relationship_type == RelationshipType.MANY_TO_MANY:
            django_field_options['blank'] = True
            if self.through_table:
                # Convert through_table to model name for Django
                through_model = self.through_table.replace('_', ' ').title().replace(' ', '')
                django_field_options['through'] = through_model
            if self.through_fields:
                django_field_options['through_fields'] = self.through_fields
            if self.symmetrical is not None:
                django_field_options['symmetrical'] = self.symmetrical
        elif self.relationship_type in [RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE]:
            django_field_options['on_delete'] = self.on_delete
            if not self.db_constraint:
                django_field_options['db_constraint'] = False

        return {
            'name': self.name,
            'type': self.relationship_type.value.replace('_', '-'),  # Convert to format expected by AST
            'relationship_type': self.relationship_type.value,
            'source_table': self.source_table,
            'target_table': self.target_table,
            'source_columns': self.source_columns,
            'target_columns': self.target_columns,
            'related_name': self.related_name,
            'on_delete': self.on_delete,
            'db_constraint': self.db_constraint,
            'through_table': self.through_table,
            'through_fields': self.through_fields,
            'symmetrical': self.symmetrical,
            'comment': self.comment,
            'is_self_referential': self.is_self_referential,
            'django_field_options': django_field_options
        }


@dataclass
class ConstraintInfo:
    """
    Represents a database constraint.

    This includes unique constraints, check constraints, indexes, etc.
    """

    name: str
    constraint_type: str  # 'unique', 'check', 'index', 'foreign_key'
    columns: List[str]
    definition: Optional[str] = None
    is_deferrable: bool = False
    initially_deferred: bool = False

    # Index-specific properties
    is_unique_index: bool = False
    index_method: Optional[str] = None  # btree, hash, gin, etc.

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'name': self.name,
            'constraint_type': self.constraint_type,
            'columns': self.columns,
            'definition': self.definition,
            'is_deferrable': self.is_deferrable,
            'initially_deferred': self.initially_deferred,
            'is_unique_index': self.is_unique_index,
            'index_method': self.index_method
        }


@dataclass
class TableInfo:
    """
    Represents a database table with all its properties.

    This is the main aggregate model that contains all information
    needed to generate Django models, serializers, views, etc.
    """

    # Basic table info
    name: str
    model_name: Optional[str] = None
    comment: Optional[str] = None

    # Columns and structure
    columns: List[ColumnInfo] = field(default_factory=list)
    primary_key_columns: List[str] = field(default_factory=list)

    # Relationships and constraints
    relationships: List[RelationshipInfo] = field(default_factory=list)
    constraints: List[ConstraintInfo] = field(default_factory=list)

    # Generation metadata
    fields: List[Dict[str, Any]] = field(default_factory=list)  # Processed field info
    meta_indexes: List[Dict[str, Any]] = field(default_factory=list)
    meta_constraints: List[Dict[str, Any]] = field(default_factory=list)

    # Raw database metadata (for compatibility)
    raw_constraints: Dict[str, Any] = field(default_factory=dict)
    raw_relations: Dict[str, Any] = field(default_factory=dict)

    # Many-to-many through table flag
    is_m2m_through_table: bool = False

    def __post_init__(self):
        """Post-initialization processing."""
        if not self.model_name:
            self.model_name = self._generate_model_name()

    def _generate_model_name(self) -> str:
        """Generate a Django model name from the table name."""
        # Convert snake_case to PascalCase
        words = self.name.split('_')
        return ''.join(word.capitalize() for word in words)

    @property
    def has_primary_key(self) -> bool:
        """Check if table has a primary key."""
        return bool(self.primary_key_columns)

    @property
    def has_composite_primary_key(self) -> bool:
        """Check if table has a composite primary key."""
        return len(self.primary_key_columns) > 1

    @property
    def foreign_key_columns(self) -> List[ColumnInfo]:
        """Get all foreign key columns."""
        return [col for col in self.columns if col.is_foreign_key]

    @property
    def unique_columns(self) -> List[ColumnInfo]:
        """Get all unique columns."""
        return [col for col in self.columns if col.is_unique]

    @property
    def required_columns(self) -> List[ColumnInfo]:
        """Get all required (non-nullable, no default) columns."""
        return [col for col in self.columns if col.is_required]

    def get_column_by_name(self, name: str) -> Optional[ColumnInfo]:
        """Get a column by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def get_relationships_by_type(self, rel_type: RelationshipType) -> List[RelationshipInfo]:
        """Get relationships of a specific type."""
        return [rel for rel in self.relationships if rel.relationship_type == rel_type]

    def is_many_to_many_through_table(self) -> bool:
        """
        Check if this table is likely a many-to-many through table.

        Heuristics:
        - Has exactly 2 foreign keys
        - Composite primary key matches the foreign key columns
        - No other significant columns
        """
        fk_columns = self.foreign_key_columns
        if len(fk_columns) != 2:
            return False

        fk_names = [col.name for col in fk_columns]
        pk_names = self.primary_key_columns

        # Check if PK columns match FK columns
        return sorted(fk_names) == sorted(pk_names)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'name': self.name,
            'model_name': self.model_name,
            'comment': self.comment,
            'columns': [col.to_dict() for col in self.columns],
            'primary_key_columns': self.primary_key_columns,
            'relationships': [rel.to_dict() for rel in self.relationships],
            'constraints': [const.to_dict() for const in self.constraints],
            'fields': self.fields,
            'meta_indexes': self.meta_indexes,
            'meta_constraints': self.meta_constraints,
            'has_primary_key': self.has_primary_key,
            'has_composite_primary_key': self.has_composite_primary_key,
            'is_many_to_many_through_table': self.is_many_to_many_through_table()
        }


@dataclass
class FieldMapping:
    """
    Represents the mapping from a database column to Django field.

    This encapsulates all the information needed to generate
    Django model field code.
    """

    # Source column information
    column: ColumnInfo

    # Django field mapping
    django_field_type: str
    django_field_options: Dict[str, Any] = field(default_factory=dict)

    # OpenAPI schema mapping
    openapi_schema: Dict[str, Any] = field(default_factory=dict)

    # Serializer field mapping
    serializer_field_type: Optional[str] = None
    serializer_field_options: Dict[str, Any] = field(default_factory=dict)

    # Additional metadata
    is_relationship_field: bool = False
    relationship_info: Optional[RelationshipInfo] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'column': self.column.to_dict(),
            'django_field_type': self.django_field_type,
            'django_field_options': self.django_field_options,
            'openapi_schema': self.openapi_schema,
            'serializer_field_type': self.serializer_field_type,
            'serializer_field_options': self.serializer_field_options,
            'is_relationship_field': self.is_relationship_field,
            'relationship_info': self.relationship_info.to_dict() if self.relationship_info else None
        }


@dataclass
class GenerationContext:
    """
    Context information for code generation operations.

    This carries all the information needed during the generation
    process and can be passed between different generators.
    """

    # Input data
    tables: List[TableInfo]
    config: Dict[str, Any]

    # Generation options
    output_dir: str
    project_name: str
    app_name: str

    # Processing state
    current_table: Optional[TableInfo] = None
    processed_tables: Set[str] = field(default_factory=set)
    generated_components: Set[str] = field(default_factory=set)

    # Generation ID for tracking
    generation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Metadata
    generation_timestamp: Optional[str] = None
    generator_version: Optional[str] = None

    def mark_table_processed(self, table_name: str):
        """Mark a table as processed."""
        self.processed_tables.add(table_name)

    def mark_component_generated(self, component_name: str):
        """Mark a component as generated."""
        self.generated_components.add(component_name)

    def is_table_processed(self, table_name: str) -> bool:
        """Check if a table has been processed."""
        return table_name in self.processed_tables

    def is_component_generated(self, component_name: str) -> bool:
        """Check if a component has been generated."""
        return component_name in self.generated_components

    def get_table_by_name(self, name: str) -> Optional[TableInfo]:
        """Get a table by name."""
        for table in self.tables:
            if table.name == name:
                return table
        return None


@dataclass
class GenerationResult:
    """
    Result of a code generation operation.

    This contains the generated code and metadata about the
    generation process.
    """

    # Generated content
    code: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Generation info
    component_type: str = "unknown"  # 'models', 'serializers', 'views', etc.
    table_name: Optional[str] = None
    file_path: Optional[str] = None

    # Status and validation
    is_formatted: bool = False
    has_syntax_errors: bool = False
    validation_errors: List[str] = field(default_factory=list)

    # Performance metrics
    generation_time_ms: Optional[float] = None
    code_lines: Optional[int] = None

    def __post_init__(self):
        """Post-initialization processing."""
        if self.code_lines is None:
            self.code_lines = len(self.code.splitlines())

    def add_validation_error(self, error: str):
        """Add a validation error."""
        self.validation_errors.append(error)
        self.has_syntax_errors = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'code': self.code,
            'metadata': self.metadata,
            'component_type': self.component_type,
            'table_name': self.table_name,
            'file_path': self.file_path,
            'is_formatted': self.is_formatted,
            'has_syntax_errors': self.has_syntax_errors,
            'validation_errors': self.validation_errors,
            'generation_time_ms': self.generation_time_ms,
            'code_lines': self.code_lines
        }
