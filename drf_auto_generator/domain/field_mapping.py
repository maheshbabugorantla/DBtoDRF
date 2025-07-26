"""
Field mapping domain logic for DRF Auto Generator.

This module contains the core business logic for mapping database fields
to Django model fields, OpenAPI schemas, and DRF serializer fields.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Protocol

from .models import ColumnInfo, FieldMapping, FieldType


class FieldMapperProtocol(Protocol):
    """Protocol for field mappers."""
    
    def can_handle(self, column: ColumnInfo) -> bool:
        """Check if this mapper can handle the given column."""
        ...
    
    def map_field(self, column: ColumnInfo) -> FieldMapping:
        """Map a column to a field mapping."""
        ...


class BaseFieldMapper(ABC):
    """Base class for field mappers."""
    
    @abstractmethod
    def can_handle(self, column: ColumnInfo) -> bool:
        """Check if this mapper can handle the given column."""
        pass
    
    @abstractmethod
    def map_field(self, column: ColumnInfo) -> FieldMapping:
        """Map a column to a field mapping."""
        pass
    
    def _validate_column(self, column: ColumnInfo) -> None:
        """Validate column information."""
        if not column.name:
            raise ValueError("Column name is required")
        
        if not column.db_type_string:
            raise ValueError("Database type string is required")


class FieldMapper:
    """
    Main field mapper that coordinates database field mapping.
    
    This is a simplified version for the domain layer that focuses
    on core mapping logic without external dependencies.
    """
    
    def __init__(self, database_engine: str = "postgresql"):
        """Initialize field mapper."""
        self.database_engine = database_engine.lower()
    
    def map_column(self, column: ColumnInfo) -> FieldMapping:
        """
        Map a database column to field mapping.
        
        Args:
            column: Database column information
            
        Returns:
            Basic field mapping
        """
        if not column.name:
            raise ValueError("Column name is required")
        
        if not column.db_type_string:
            raise ValueError("Database type string is required")
        
        # Create basic mapping - full implementation will be in service layer
        mapping = FieldMapping(
            column=column,
            django_field_type=self._get_django_field_type(column),
            django_field_options=self._get_basic_options(column),
            openapi_schema=self._get_basic_openapi_schema(column)
        )
        
        return mapping
    
    def _get_django_field_type(self, column: ColumnInfo) -> str:
        """Get Django field type for column."""
        if column.is_pk and column.field_type == FieldType.INTEGER:
            return "AutoField"
        
        if column.is_foreign_key:
            return "ForeignKey"
        
        # Basic field type mapping
        field_type_mapping = {
            FieldType.AUTO: "AutoField",
            FieldType.INTEGER: "IntegerField",
            FieldType.FLOAT: "FloatField",
            FieldType.DECIMAL: "DecimalField",
            FieldType.STRING: "CharField",
            FieldType.TEXT: "TextField",
            FieldType.BOOLEAN: "BooleanField",
            FieldType.DATE: "DateField",
            FieldType.DATETIME: "DateTimeField",
            FieldType.TIME: "TimeField",
            FieldType.UUID: "UUIDField",
            FieldType.JSON: "JSONField",
            FieldType.BINARY: "BinaryField",
            FieldType.FILE: "FileField",
        }
        
        return field_type_mapping.get(column.field_type, "CharField")
    
    def _get_basic_options(self, column: ColumnInfo) -> Dict[str, Any]:
        """Get basic Django field options."""
        options = {}
        
        if column.nullable and not column.is_pk:
            options['null'] = True
            options['blank'] = True
        
        if column.is_unique and not column.is_pk:
            options['unique'] = True
        
        if column.default is not None:
            options['default'] = column.default
        
        if column.internal_size and column.field_type == FieldType.STRING:
            options['max_length'] = column.internal_size
        
        return options
    
    def _get_basic_openapi_schema(self, column: ColumnInfo) -> Dict[str, Any]:
        """Get basic OpenAPI schema."""
        schema_mapping = {
            FieldType.INTEGER: {"type": "integer"},
            FieldType.FLOAT: {"type": "number", "format": "float"},
            FieldType.DECIMAL: {"type": "number", "format": "double"},
            FieldType.STRING: {"type": "string"},
            FieldType.TEXT: {"type": "string"},
            FieldType.BOOLEAN: {"type": "boolean"},
            FieldType.DATE: {"type": "string", "format": "date"},
            FieldType.DATETIME: {"type": "string", "format": "date-time"},
            FieldType.TIME: {"type": "string", "format": "time"},
            FieldType.UUID: {"type": "string", "format": "uuid"},
            FieldType.JSON: {"type": "object"},
        }
        
        schema = schema_mapping.get(column.field_type, {"type": "string"}).copy()
        
        if column.nullable:
            schema['nullable'] = True
        
        if column.default is not None:
            schema['default'] = column.default
        
        return schema