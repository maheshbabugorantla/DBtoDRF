"""
Domain module for DRF Auto Generator.

This module contains core business logic and domain models separated from
infrastructure concerns. These models represent the essential concepts
of the code generation domain.
"""

from .models import (
    ColumnInfo,
    TableInfo, 
    FieldMapping,
    RelationshipInfo,
    RelationshipType,
    FieldType,
    ConstraintInfo,
    GenerationContext,
    GenerationResult
)

from .field_mapping import (
    FieldMapper,
    FieldMapperProtocol,
    BaseFieldMapper
)

from .relationships import (
    RelationshipAnalyzer,
    RelationshipResolver
)

from .constraints import (
    ConstraintAnalyzer,
    ConstraintType,
    IndexInfo,
    UniqueConstraint
)

from .naming import (
    NamingConventions,
    to_snake_case,
    to_pascal_case, 
    clean_field_name,
    generate_model_name,
    generate_relationship_name,
    generate_related_name,
    validate_python_identifier
)

__all__ = [
    # Core models
    'ColumnInfo',
    'TableInfo',
    'FieldMapping', 
    'RelationshipInfo',
    'RelationshipType',
    'FieldType',
    'ConstraintInfo',
    'GenerationContext',
    'GenerationResult',
    
    # Field mapping
    'FieldMapper',
    'FieldMapperProtocol',
    'BaseFieldMapper',
    
    # Relationships
    'RelationshipAnalyzer',
    'RelationshipResolver',
    
    # Constraints  
    'ConstraintAnalyzer',
    'ConstraintType',
    'IndexInfo',
    'UniqueConstraint',
    
    # Naming
    'NamingConventions',
    'to_snake_case',
    'to_pascal_case', 
    'clean_field_name',
    'generate_model_name',
    'generate_relationship_name',
    'generate_related_name',
    'validate_python_identifier'
]