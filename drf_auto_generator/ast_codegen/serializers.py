import logging
import ast
from typing import List, Tuple

from drf_auto_generator.ast_codegen.base import (
    create_import, create_class_def,
    create_meta_class, create_string_constant, pluralize
)
from drf_auto_generator.introspection_django import TableInfo
from drf_auto_generator.mapper import to_pascal_case


logger = logging.getLogger(__name__)


def _is_m2m_through_table(table_info: TableInfo) -> bool:
    """
    Determine if this table is an M2M through table that should not have serializers generated.

    M2M through tables typically:
    1. Have exactly 2 foreign key relationships
    2. Have exactly 2 primary key columns
    3. Those PK columns are the same as the FK columns
    """
    if len(table_info.primary_key_columns) != 2:
        return False

    fk_relationships = [rel for rel in table_info.relationships if rel["type"] == "many-to-one"]

    if len(fk_relationships) != 2:
        return False

    # Check if all PK columns are handled by FK relationships
    pk_cols_handled_by_fk = 0
    for pk_col in table_info.primary_key_columns:
        for rel in fk_relationships:
            if pk_col in rel.get("source_columns", []):
                pk_cols_handled_by_fk += 1
                break

    return pk_cols_handled_by_fk == len(table_info.primary_key_columns)


def create_serializer_meta(table_info: TableInfo) -> ast.ClassDef:
    """Creates the AST node for the inner Meta class of a serializer."""
    meta_options: List[Tuple[str, ast.expr]] = [
        ("model", ast.Name(id=to_pascal_case(pluralize(table_info.name)), ctx=ast.Load())), # Reference the model class
        ("fields", create_string_constant("__all__")) # Or generate a list of fields
        # Alternatively, generate specific fields:
        # (
        #     "fields",
        #     create_list_of_strings([col.name for col in table_info.columns] + [rel['name'] for rel in table_info.relationships])
        # )
    ]
    return create_meta_class(meta_options)


def create_serializer_class(table_info: TableInfo) -> ast.ClassDef:
    """Creates the AST ClassDef node for a DRF ModelSerializer."""
    serializer_name = f"{to_pascal_case(pluralize(table_info.name))}Serializer"
    serializer_body: List[ast.stmt] = [
        # Meta class
        create_serializer_meta(table_info)
    ]

    return create_class_def(
        name=serializer_name,
        bases=["serializers.ModelSerializer"],
        body=serializer_body
    )


def generate_serializers_ast(tables_info: List[TableInfo], models_module: str = ".models") -> ast.Module:
    """Generates the complete AST Module for the serializers.py file."""
    imports = [
        create_import("rest_framework", ["serializers"]),
        # Import all models from the models module, excluding M2M through tables
        create_import(models_module, [to_pascal_case(pluralize(table.name)) for table in tables_info if table.primary_key_columns and not _is_m2m_through_table(table)])
        # Or import the models module directly:
        # create_import(models_module)
    ]

    serializer_classes = []
    for table in tables_info:
        if table.primary_key_columns:
            if _is_m2m_through_table(table):
                logger.info(f"Skipping serializer generation for M2M through table: {table.name}")
                continue
            serializer_classes.append(create_serializer_class(table))
        else:
            logger.warning(f"Table {table.name} does not have a primary key, skipping serializer generation...")

    module_body = imports + serializer_classes
    return ast.Module(body=module_body, type_ignores=[])


def generate_serializers_code(tables_info: List[TableInfo], models_module: str = ".models") -> str:
    """Generates the Python code string for serializers.py."""
    module_ast = generate_serializers_ast(tables_info, models_module)
    return ast.unparse(module_ast)
