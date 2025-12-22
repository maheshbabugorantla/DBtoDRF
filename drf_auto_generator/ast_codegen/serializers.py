import logging
import ast
from typing import List, Tuple, Dict, Any

from drf_auto_generator.ast_codegen.base import (
    create_import, create_class_def, create_assign,
    create_meta_class, create_string_constant, pluralize,
    add_location, create_keyword, create_boolean_constant
)
from drf_auto_generator.domain.models import TableInfo
from drf_auto_generator.domain.naming import to_pascal_case


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


def _create_pk_relation_field(rel_name: str, target_model_name: str, many: bool = False) -> ast.Assign:
    """
    Creates a PrimaryKeyRelatedField for 'pk' relation style.

    Generates:
        <rel_name> = serializers.PrimaryKeyRelatedField(queryset=Model.objects.all())
    or for read-only reverse relations:
        <rel_name> = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    """
    keywords = []

    if many:
        keywords.append(create_keyword("many", create_boolean_constant(True)))
        keywords.append(create_keyword("read_only", create_boolean_constant(True)))
    else:
        # For FK fields, use queryset
        queryset_call = add_location(ast.Call(
            func=add_location(ast.Attribute(
                value=add_location(ast.Attribute(
                    value=add_location(ast.Name(id=target_model_name, ctx=ast.Load())),
                    attr="objects",
                    ctx=ast.Load()
                )),
                attr="all",
                ctx=ast.Load()
            )),
            args=[],
            keywords=[]
        ))
        keywords.append(create_keyword("queryset", queryset_call))

    return create_assign(
        target=rel_name,
        value=add_location(ast.Call(
            func=add_location(ast.Attribute(
                value=add_location(ast.Name(id="serializers", ctx=ast.Load())),
                attr="PrimaryKeyRelatedField",
                ctx=ast.Load()
            )),
            args=[],
            keywords=keywords
        ))
    )


def _create_nested_relation_field(rel_name: str, target_serializer_name: str, many: bool = False) -> ast.Assign:
    """
    Creates a nested serializer field for 'nested' relation style.

    Generates:
        <rel_name> = <TargetSerializer>(read_only=True)
    or for many relations:
        <rel_name> = <TargetSerializer>(many=True, read_only=True)
    """
    keywords = [create_keyword("read_only", create_boolean_constant(True))]
    if many:
        keywords.append(create_keyword("many", create_boolean_constant(True)))

    return create_assign(
        target=rel_name,
        value=add_location(ast.Call(
            func=add_location(ast.Name(id=target_serializer_name, ctx=ast.Load())),
            args=[],
            keywords=keywords
        ))
    )


def _create_hyperlink_relation_field(rel_name: str, view_name: str, many: bool = False) -> ast.Assign:
    """
    Creates a HyperlinkedRelatedField for 'link' relation style.

    Generates:
        <rel_name> = serializers.HyperlinkedRelatedField(view_name='<view>-detail', read_only=True)
    or for many relations:
        <rel_name> = serializers.HyperlinkedRelatedField(many=True, view_name='<view>-detail', read_only=True)
    """
    keywords = [
        create_keyword("view_name", create_string_constant(f"{view_name}-detail")),
        create_keyword("read_only", create_boolean_constant(True))
    ]
    if many:
        keywords.insert(0, create_keyword("many", create_boolean_constant(True)))

    return create_assign(
        target=rel_name,
        value=add_location(ast.Call(
            func=add_location(ast.Attribute(
                value=add_location(ast.Name(id="serializers", ctx=ast.Load())),
                attr="HyperlinkedRelatedField",
                ctx=ast.Load()
            )),
            args=[],
            keywords=keywords
        ))
    )


def _get_relation_fields(table_info: TableInfo, config: Dict[str, Any]) -> List[ast.Assign]:
    """
    Generate explicit relationship field declarations based on relation_style config.

    relation_style options:
    - 'pk' (default): FK fields as integer IDs (PrimaryKeyRelatedField)
    - 'nested': Full nested object representation
    - 'link': URI references (HyperlinkedRelatedField)
    """
    relation_style = config.get("relation_style", "pk")
    fields = []

    for rel in table_info.relationships:
        rel_name = rel.get("name")
        rel_type = rel.get("type")
        target_model_name = rel.get("target_model_name", "")

        if not rel_name or not target_model_name:
            continue

        # Determine if this is a "many" relationship
        is_many = rel_type in ["one-to-many", "many-to-many"]

        # Generate view_name for hyperlinks (lowercase, pluralized table name)
        view_name = target_model_name.lower()

        target_serializer_name = f"{target_model_name}Serializer"

        if relation_style == "nested":
            fields.append(_create_nested_relation_field(rel_name, target_serializer_name, many=is_many))
        elif relation_style == "link":
            fields.append(_create_hyperlink_relation_field(rel_name, view_name, many=is_many))
        elif relation_style == "pk":
            # Only generate explicit fields for FK relationships
            # DRF handles reverse relations (one-to-many) automatically
            if rel_type == "many-to-one":
                fields.append(_create_pk_relation_field(rel_name, target_model_name, many=False))

    return fields


def create_serializer_class(table_info: TableInfo, config: Dict[str, Any] = None) -> ast.ClassDef:
    """
    Creates the AST ClassDef node for a DRF ModelSerializer.

    Respects relation_style config:
    - 'pk': Default DRF behavior (PrimaryKeyRelatedField)
    - 'nested': Nested serializer representation
    - 'link': Hyperlinked representation
    """
    config = config or {}
    serializer_name = f"{to_pascal_case(pluralize(table_info.name))}Serializer"

    serializer_body: List[ast.stmt] = []

    # Add explicit relationship fields based on relation_style
    relation_style = config.get("relation_style", "pk")
    if relation_style in ["nested", "link"]:
        relation_fields = _get_relation_fields(table_info, config)
        serializer_body.extend(relation_fields)

    # Add Meta class
    serializer_body.append(create_serializer_meta(table_info))

    # Determine base class based on relation_style
    if relation_style == "link":
        base_class = "serializers.HyperlinkedModelSerializer"
    else:
        base_class = "serializers.ModelSerializer"

    return create_class_def(
        name=serializer_name,
        bases=[base_class],
        body=serializer_body
    )


def generate_serializers_ast(
    tables_info: List[TableInfo],
    models_module: str = ".models",
    config: Dict[str, Any] = None
) -> ast.Module:
    """
    Generates the complete AST Module for the serializers.py file.

    Supports relation_style config for customizing relationship representation.
    """
    config = config or {}

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
            serializer_classes.append(create_serializer_class(table, config))
        else:
            logger.warning(f"Table {table.name} does not have a primary key, skipping serializer generation...")

    module_body = imports + serializer_classes
    return ast.Module(body=module_body, type_ignores=[])


def generate_serializers_code(
    tables_info: List[TableInfo],
    models_module: str = ".models",
    config: Dict[str, Any] = None
) -> str:
    """Generates the Python code string for serializers.py."""
    module_ast = generate_serializers_ast(tables_info, models_module, config)
    return ast.unparse(module_ast)
