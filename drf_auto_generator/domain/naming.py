"""
Naming convention utilities for DRF Auto Generator.

This module provides utilities for converting between different naming conventions
used in database schemas, Django models, and Python code.
"""

import re
from typing import Set
import inflect

from ..constants import FieldNames


# Initialize inflect engine for pluralization
p = inflect.engine()


def to_snake_case(name: str) -> str:
    """
    Convert CamelCase or PascalCase to snake_case.
    
    This function handles various naming convention conversions including:
    - CamelCase -> snake_case
    - PascalCase -> snake_case  
    - Mixed case with numbers -> snake_case
    
    Args:
        name: The string to convert to snake_case
        
    Returns:
        The converted snake_case string
        
    Example:
        >>> to_snake_case("UserAccount")
        'user_account'
        >>> to_snake_case("XMLHttpRequest")
        'xml_http_request'
    """
    if not isinstance(name, str):
        raise TypeError(f"Expected string, got {type(name).__name__}")
        
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub("__([A-Z])", r"_\1", name)
    name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def to_pascal_case(name: str) -> str:
    """
    Convert snake_case to PascalCase (ClassName) with smart singularization.
    
    This function:
    1. Attempts to singularize plural table names
    2. Converts to PascalCase for Django model class names
    3. Handles edge cases and irregular plurals
    
    Args:
        name: The string to convert to PascalCase
        
    Returns:
        The converted PascalCase string, typically singular
        
    Example:
        >>> to_pascal_case("user_accounts")
        'UserAccount'
        >>> to_pascal_case("categories")
        'Category'
    """
    if not isinstance(name, str):
        raise TypeError(f"Expected string, got {type(name).__name__}")
        
    # Try to singularize table names for model names
    singular_name = p.singular_noun(name)
    if singular_name is False:  # inflect returns False if already singular or irregular
        singular_name = name
    # Handle cases like 'data' -> 'Data', 'series' -> 'Series' where singular is same
    if not singular_name:
        singular_name = name

    return "".join(word.capitalize() for word in singular_name.split("_"))


def clean_field_name(name: str) -> str:
    """
    Ensure field name is a valid Python identifier and not a reserved keyword.
    
    This function:
    1. Converts to snake_case
    2. Removes invalid characters
    3. Ensures it starts with a letter or underscore
    4. Handles Python keywords by appending underscore
    
    Args:
        name: The field name to clean
        
    Returns:
        A valid Python identifier safe for use as a field name
        
    Raises:
        ValueError: If the name cannot be converted to a valid identifier
        
    Example:
        >>> clean_field_name("class")
        'class_'
        >>> clean_field_name("123invalid")
        '_123invalid'
    """
    name = to_snake_case(name)
    # Remove invalid characters (allow underscore)
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    # Ensure it starts with a letter or underscore
    if name and not name[0].isalpha() and name[0] != "_":
        name = "_" + name
    
    # Handle Python keywords using constants
    keywords = FieldNames.PYTHON_KEYWORDS
    if name in keywords:
        name += "_"
    
    # Handle potential clash with 'pk' if the column name wasn't originally 'pk'
    if name == "pk" and name != "pk":
        name = "pk_val"  # Or another suitable suffix
    
    return name if name else "_field"  # Ensure non-empty name


def generate_model_name(table_name: str) -> str:
    """
    Generate a Django model name from a table name.
    
    Args:
        table_name: Database table name
        
    Returns:
        Pascal case model name
    """
    return to_pascal_case(table_name)


def generate_relationship_name(column_name: str) -> str:
    """
    Generate a relationship field name from a column name.
    
    Args:
        column_name: Database column name (e.g., 'author_id')
        
    Returns:
        Relationship field name (e.g., 'author')
    """
    # Remove common suffixes like '_id'
    if column_name.endswith('_id'):
        return column_name[:-3]
    return column_name


def generate_related_name(source_table: str, field_name: str = None) -> str:
    """
    Generate a related_name for a relationship.
    
    Args:
        source_table: Source table name
        field_name: Optional field name for disambiguation
        
    Returns:
        Related name for reverse relationship
    """
    base_name = p.plural(source_table)
    if field_name:
        return f"{base_name}_{field_name}"
    return base_name


def validate_python_identifier(name: str) -> bool:
    """
    Check if a string is a valid Python identifier.
    
    Args:
        name: String to validate
        
    Returns:
        True if valid identifier, False otherwise
    """
    if not name:
        return False
    
    # Check if it's a valid identifier and not a keyword
    return (name.isidentifier() and 
            name not in FieldNames.PYTHON_KEYWORDS)


class NamingConventions:
    """
    Centralized naming convention utilities.
    
    This class provides consistent naming across the codebase.
    """
    
    @staticmethod
    def table_to_model(table_name: str) -> str:
        """Convert table name to Django model name."""
        return generate_model_name(table_name)
    
    @staticmethod
    def column_to_field(column_name: str) -> str:
        """Convert column name to Django field name."""
        return clean_field_name(column_name)
    
    @staticmethod
    def foreign_key_to_relationship(column_name: str) -> str:
        """Convert foreign key column to relationship field name."""
        return generate_relationship_name(column_name)
    
    @staticmethod
    def generate_reverse_name(source_table: str, field_name: str = None) -> str:
        """Generate related_name for reverse relationship."""
        return generate_related_name(source_table, field_name)
    
    @staticmethod
    def is_valid_identifier(name: str) -> bool:
        """Check if name is valid Python identifier."""
        return validate_python_identifier(name)