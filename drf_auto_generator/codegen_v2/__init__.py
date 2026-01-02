"""
CodeGen V2 - A cleaner, more maintainable code generation architecture.

This module provides:
- Pydantic-based Intermediate Representation (IR) for database schemas
- CodeBuilder utility for Python code generation with proper indentation handling
- Plugin-based generator architecture for Django, MCP servers, and more

Key benefits over the AST-based approach:
- Much simpler and more readable code generation
- Automatic indentation handling (no more manual AST node location tracking)
- Type-safe schema definitions with Pydantic
- Easy to extend with new output plugins
"""

from .schema import (
    DatabaseSchema,
    TableSchema,
    ColumnSchema,
    RelationshipSchema,
    IndexSchema,
    ConstraintSchema,
    FieldType,
    RelationshipType,
)
from .code_builder import PythonCodeBuilder
from .base import CodeGenerator, GeneratorRegistry

__all__ = [
    # Schema models
    "DatabaseSchema",
    "TableSchema",
    "ColumnSchema",
    "RelationshipSchema",
    "IndexSchema",
    "ConstraintSchema",
    "FieldType",
    "RelationshipType",
    # Code builder
    "PythonCodeBuilder",
    # Generator base
    "CodeGenerator",
    "GeneratorRegistry",
]
