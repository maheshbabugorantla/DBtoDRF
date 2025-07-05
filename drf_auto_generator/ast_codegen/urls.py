import logging
import ast
from typing import List

from drf_auto_generator.ast_codegen.base import (
    create_import, create_assign, create_call, create_attribute_call,
    create_string_constant, create_keyword, pluralize
)
from drf_auto_generator.introspection_django import TableInfo
from drf_auto_generator.mapper import to_snake_case, to_pascal_case


logger = logging.getLogger(__name__)


def generate_urls_ast(tables_info: List[TableInfo], views_module: str = ".views") -> ast.Module:
    """Generates the complete AST Module for the urls.py file."""
    imports = [
        create_import("django.urls", ["path", "include"]),
        create_import("rest_framework.routers", ["DefaultRouter"]),
        create_import(views_module)
    ]

    # Create router instance: router = DefaultRouter()
    router_assign = create_assign(
        target="router",
        value=create_call("DefaultRouter")
    )

    # Register viewsets
    registrations = []
    for table in tables_info:
        if not table.primary_key_columns:
            logger.warning(f"Table {table.name} does not have a primary key, skipping URL registration...")
            continue

        if table.is_m2m_through_table:
            logger.info(f"Skipping URL registration for M2M through table: {table.name}")
            continue

        viewset_name = f"{to_pascal_case(pluralize(table.name))}ViewSet"
        # Convert model name to snake_case for URL path
        url_path = pluralize(to_snake_case(table.name))
        register_call = create_attribute_call(
            obj_name="router",
            attr_name="register",
            args=[
                # Use an f-string equivalent if needed, or simple string concat
                create_string_constant(url_path), # r'model_name'
                ast.Attribute(
                    value=ast.Name(id='views', ctx=ast.Load()),
                    attr=viewset_name,
                    ctx=ast.Load()
                )
            ],
            keywords=[create_keyword("basename", create_string_constant(table.name.lower()))]
        )
        registrations.append(ast.Expr(value=register_call))

    # urlpatterns = [...] assignment
    urlpatterns_assign = create_assign(
        target="urlpatterns",
        value=ast.List(
            elts=[
                create_call(
                    func_name="path",
                    args=[
                        create_string_constant(''),
                        create_call("include", args=[ast.Attribute(value=ast.Name(id='router', ctx=ast.Load()), attr='urls', ctx=ast.Load())])
                    ]
                )
            ],
            ctx=ast.Load()
        )
    )

    module_body = imports + [router_assign] + registrations + [urlpatterns_assign]
    return ast.Module(body=module_body, type_ignores=[])


def generate_urls_code(tables_info: List[TableInfo], views_module: str = ".views") -> str:
    """Generates the Python code string for urls.py."""
    module_ast = generate_urls_ast(tables_info, views_module)
    return ast.unparse(module_ast)
