"""
Django Admin Code Generator

This module generates Django admin.py code using AST.
"""

import logging
import ast
from typing import List

from drf_auto_generator.ast_codegen.base import (
    create_import, create_class_def, create_assign, create_list_of_strings, pluralize
)
from drf_auto_generator.introspection_django import TableInfo
from drf_auto_generator.mapper import to_pascal_case


logger = logging.getLogger(__name__)


def create_admin_class(table_info: TableInfo) -> ast.ClassDef:
    """Creates the AST ClassDef node for a Django ModelAdmin."""
    model_name = to_pascal_case(pluralize(table_info.name))
    admin_name = f"{model_name}Admin"

    # Get the actual field names that exist in the Django model
    # This includes fields that are NOT handled by relationships, plus relationship fields
    available_field_names = []

    # Add fields that are not handled by relationships
    for field_dict in table_info.fields:
        if not field_dict.get("is_handled_by_relation", False):
            available_field_names.append(field_dict["name"])

    # Add relationship field names
    for rel in table_info.relationships:
        available_field_names.append(rel["name"])

    # Find primary key field name
    pk_field_name = None
    for field_dict in table_info.fields:
        if field_dict.get("is_pk") and not field_dict.get("is_handled_by_relation", False):
            pk_field_name = field_dict["name"]
            break

    # Find fields that would be good for list_display
    # Prefer string-like fields, unique fields, and avoid huge text fields
    list_display_fields = []

    # Always include PK if available
    if pk_field_name:
        list_display_fields.append(pk_field_name)

    # Add other suitable fields
    for field_dict in table_info.fields:
        if (not field_dict.get("is_handled_by_relation", False) and
            not field_dict.get("is_pk", False) and
            field_dict["name"] in available_field_names):

            field_type = field_dict.get("type", "")
            # Include string fields and other display-friendly types
            if (field_type in ("CharField", "TextField", "EmailField", "URLField") or
                field_dict["name"] in ("name", "title", "email", "username", "code", "status")):
                list_display_fields.append(field_dict["name"])

    # Add some relationship fields for context
    for rel in table_info.relationships:
        if rel["type"] == "many-to-one":  # Foreign keys are good for list_display
            list_display_fields.append(rel["name"])
        if len(list_display_fields) >= 5:  # Limit to avoid clutter
            break

    # Limit to a reasonable number of fields
    list_display_fields = list_display_fields[:5]

    # Find fields that would be good for search_fields
    search_fields = []
    for field_dict in table_info.fields:
        if (not field_dict.get("is_handled_by_relation", False) and
            field_dict.get("type") in ("CharField", "TextField", "EmailField") and
            field_dict["name"] in available_field_names):
            search_fields.append(field_dict["name"])

    # Find fields that would be good for list_filter
    list_filter = []
    for field_dict in table_info.fields:
        if (not field_dict.get("is_handled_by_relation", False) and
            field_dict.get("type") in ("BooleanField", "DateField", "DateTimeField", "IntegerField", "FloatField", "DecimalField") and
            field_dict["name"] in available_field_names):
            list_filter.append(field_dict["name"])

    # Add foreign key relationships to list_filter (they're good for filtering)
    for rel in table_info.relationships:
        if rel["type"] == "many-to-one":
            list_filter.append(rel["name"])

    list_filter = list_filter[:5]  # Limit to avoid clutter

    # Create the model admin class body
    admin_body = []

    if list_display_fields:
        admin_body.append(
            create_assign(
                target="list_display",
                value=create_list_of_strings(list_display_fields)
            )
        )

    if search_fields:
        admin_body.append(
            create_assign(
                target="search_fields",
                value=create_list_of_strings(search_fields)
            )
        )

    if list_filter:
        admin_body.append(
            create_assign(
                target="list_filter",
                value=create_list_of_strings(list_filter)
            )
        )

    return create_class_def(
        name=admin_name,
        bases=["admin.ModelAdmin"],
        body=admin_body
    )


def generate_admin_code(tables_info: List[TableInfo], models_module: str = ".models") -> str:
    """Generate code for the Django admin.py file."""
    imports = [
        create_import("django.contrib", ["admin"]),
        # Import all models from the models module
        create_import(models_module, [to_pascal_case(pluralize(table.name)) for table in tables_info if table.primary_key_columns])
    ]

    # Create admin class registrations
    registrations = []
    for table in tables_info:
        if not table.primary_key_columns:
            logger.warning(f"Table {table.name} does not have a primary key, skipping admin generation...")
            continue

        model_name = to_pascal_case(pluralize(table.name))

        # Create the ModelAdmin class
        admin_class = create_admin_class(table)
        registrations.append(admin_class)

        # Create the registration statement
        register_stmt = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="admin", ctx=ast.Load()),
                    attr="site.register",
                    ctx=ast.Load()
                ),
                args=[
                    ast.Name(id=model_name, ctx=ast.Load()),
                    ast.Name(id=f"{model_name}Admin", ctx=ast.Load())
                ],
                keywords=[]
            )
        )
        registrations.append(register_stmt)

    # Create the complete module
    module = ast.Module(body=imports + registrations, type_ignores=[])

    # Convert to code
    return ast.unparse(module)
