import logging
import ast
from typing import List, Dict

from drf_auto_generator.ast_codegen.base import (
    create_import, create_assign, create_class_def,
    create_list_of_strings, create_string_constant,
    add_location, pluralize
)
from drf_auto_generator.domain.models import TableInfo
from drf_auto_generator.domain.naming import to_pascal_case


logger = logging.getLogger(__name__)


def _find_searchable_fields(table_info: TableInfo, limit: int = 5) -> List[str]:
    """Find fields suitable for search functionality using actual Django field names."""
    searchable_types = ["CharField", "TextField", "EmailField"]

    search_fields = []

    # Look through the actual Django fields that will exist in the model
    for field in table_info.fields:
        field_name = field.get("name")
        field_type = field.get("type", "")

        # Only include fields that:
        # 1. Actually exist in the Django model (not handled by relationships)
        # 2. Are text-based and searchable
        # 3. Have a reasonable field name length
        if (field_name and
            not field.get("is_handled_by_relation", False) and
            field_type in searchable_types and
            len(field_name) > 2):  # Avoid very short field names
            search_fields.append(field_name)

    return search_fields[:limit]


def _get_primary_key_field(table_info: TableInfo) -> str:
    """
    Get the primary key field name for ordering.

    Returns the actual Django field name (not the database column name).
    Handles M2M through tables (auto-generated 'id') and true composite PKs (CompositePrimaryKey 'pk').
    """
    # Check if this is a composite primary key table
    pk_count = len(table_info.primary_key_columns)

    logger.debug(f"Table {table_info.name}: pk_count = {pk_count}, pk_columns = {table_info.primary_key_columns}")

    if pk_count > 1:
        # Check if this is an M2M through table (same logic as in models.py)
        if table_info.is_m2m_through_table:
            # M2M through table - Django auto-generates 'id' field
            logger.debug(f"Table {table_info.name}: Using 'id' for M2M through table")
            return "id"
        else:
            # True composite primary key - Django 5.2+ uses CompositePrimaryKey with 'pk' field
            logger.debug(f"Table {table_info.name}: Using 'pk' for CompositePrimaryKey (columns: {table_info.primary_key_columns})")
            return "pk"
    elif pk_count == 1:
        # Single primary key - find the corresponding Django field name
        pk_column = table_info.primary_key_columns[0]

        # Find the Django field name for this column
        for field in table_info.fields:
            if (field.get("original_column_name") == pk_column and
                field.get("is_pk", False) and
                not field.get("is_handled_by_relation", False)):
                pk_field_name = field["name"]
                logger.debug(f"Table {table_info.name}: Using '{pk_field_name}' for single PK (column: {pk_column})")
                return pk_field_name

        # Fallback if field mapping not found
        logger.warning(f"Table {table_info.name}: Could not find Django field for PK column '{pk_column}', using 'pk' as fallback")
        return "pk"
    else:
        # No primary key found - fallback to 'pk'
        logger.warning(f"Table {table_info.name}: No PK found, using 'pk' as fallback")
        return "pk"


def _create_filterset_fields(table_info: TableInfo) -> Dict[str, List[str]]:
    """Create filterset_fields configuration for query parameter filtering."""
    filterset_fields = {}

    # Add foreign key fields for filtering
    for rel in table_info.relationships:
        if rel["type"] == "many-to-one":
            rel_name = rel["name"]
            filterset_fields[rel_name] = ['exact']

    # Add indexed fields for filtering
    for index in table_info.meta_indexes:
        for field_name in index.get("fields", []):
            # Skip if already added as relationship filter
            if field_name not in filterset_fields:
                field_info = next((f for f in table_info.fields if f.get("name") == field_name), None)
                if field_info and not field_info.get("is_pk", False) and not field_info.get("is_handled_by_relation", False):
                    field_type = field_info.get("type", "")

                    # Determine appropriate lookup types based on field type
                    if field_type in ["CharField", "TextField", "EmailField"]:
                        filterset_fields[field_name] = ['exact', 'icontains']
                    elif field_type in ["IntegerField", "BigIntegerField", "SmallIntegerField",
                                       "PositiveIntegerField", "PositiveBigIntegerField", "PositiveSmallIntegerField"]:
                        filterset_fields[field_name] = ['exact', 'gte', 'lte']
                    elif field_type in ["DateField", "DateTimeField"]:
                        filterset_fields[field_name] = ['exact', 'gte', 'lte']
                    elif field_type == "BooleanField":
                        filterset_fields[field_name] = ['exact']
                    else:
                        filterset_fields[field_name] = ['exact']

    # Add unique fields for filtering
    for field in table_info.fields:
        field_name = field.get("name")
        field_type = field.get("type", "")
        if (field.get("options", {}).get("unique", False) and
            not field.get("is_pk", False) and
            not field.get("is_handled_by_relation", False) and
            field_name not in filterset_fields):
            # Unique fields typically use exact matching
            filterset_fields[field_name] = ['exact']

    return filterset_fields


def create_viewset_class(table_info: TableInfo) -> ast.ClassDef:
    """Creates the AST ClassDef node for a DRF ModelViewSet with just basic CRUD operations and query parameter filtering."""
    model_name = to_pascal_case(pluralize(table_info.name))
    viewset_name = f"{model_name}ViewSet"
    serializer_name = f"{model_name}Serializer"

    # Find fields suitable for search
    search_fields = _find_searchable_fields(table_info)

    # Get primary key field for ordering
    pk_field = _get_primary_key_field(table_info)

    # Create docstring
    docstring = add_location(ast.Expr(
        value=create_string_constant(f"""
        API endpoint that allows {model_name}s to be viewed or edited.

        Provides standard CRUD operations with query parameter filtering via filterset_fields.
        """)
    ))

    # Create queryset with proper ordering
    queryset_assign = create_assign(
        target="queryset",
        value=add_location(ast.Call(
            func=add_location(ast.Attribute(
                value=add_location(ast.Attribute(
                    value=add_location(ast.Name(id=model_name, ctx=ast.Load())),
                    attr="objects",
                    ctx=ast.Load()
                )),
                attr="all",
                ctx=ast.Load()
            )),
            args=[],
            keywords=[]
        ))
    )

    # Add ordering to queryset
    queryset_ordering_assign = create_assign(
        target="queryset",
        value=add_location(ast.Call(
            func=add_location(ast.Attribute(
                value=add_location(ast.Name(id="queryset", ctx=ast.Load())),
                attr="order_by",
                ctx=ast.Load()
            )),
            args=[add_location(ast.Constant(value=pk_field))],
            keywords=[]
        ))
    )

    # Create serializer class assignment
    serializer_class_assign = create_assign(
        target="serializer_class",
        value=add_location(ast.Name(id=serializer_name, ctx=ast.Load()))
    )

    # Create permission classes
    permission_classes_assign = create_assign(
        target="permission_classes",
        value=add_location(ast.List(
            elts=[add_location(ast.Attribute(
                value=add_location(ast.Name(id="permissions", ctx=ast.Load())),
                attr="IsAuthenticatedOrReadOnly",
                ctx=ast.Load()
            ))],
            ctx=ast.Load()
        ))
    )

    # Create filter backends - add DjangoFilterBackend for query parameter filtering
    filter_backends_assign = create_assign(
        target="filter_backends",
        value=add_location(ast.List(
            elts=[
                add_location(ast.Attribute(
                    value=add_location(ast.Name(id="filters", ctx=ast.Load())),
                    attr="OrderingFilter",
                    ctx=ast.Load()
                )),
                add_location(ast.Attribute(
                    value=add_location(ast.Name(id="filters", ctx=ast.Load())),
                    attr="SearchFilter",
                    ctx=ast.Load()
                )),
                add_location(ast.Name(id="DjangoFilterBackend", ctx=ast.Load()))
            ],
            ctx=ast.Load()
        ))
    )

    # Create ordering fields
    ordering_fields = [pk_field]  # pk_field is now correctly mapped to Django field name

    # Add other fields that actually exist in the Django model
    # Only include fields that are not handled by relationships and exist in the model
    for field in table_info.fields:
        field_name = field.get("name")
        field_type = field.get("type", "")

        # Only add fields that:
        # 1. Actually exist in the Django model (not handled by relationships)
        # 2. Are not the primary key (already added)
        # 3. Are suitable for ordering (text, date fields)
        if (field_name and
            field_name != pk_field and
            not field.get("is_pk", False) and
            not field.get("is_handled_by_relation", False) and
            field_type in ["CharField", "TextField", "DateField", "DateTimeField", "EmailField"]):
            ordering_fields.append(field_name)

    # Limit to a reasonable number of ordering fields
    ordering_fields = ordering_fields[:5]

    ordering_fields_assign = create_assign(
        target="ordering_fields",
        value=create_list_of_strings(ordering_fields)
    )

    # Create search fields
    search_fields_assign = create_assign(
        target="search_fields",
        value=create_list_of_strings(search_fields)
    )

    # Create filterset_fields for query parameter filtering
    filterset_fields = _create_filterset_fields(table_info)
    if filterset_fields:
        # Create AST dict for filterset_fields
        dict_keys = []
        dict_values = []
        for field_name, lookups in filterset_fields.items():
            dict_keys.append(add_location(ast.Constant(value=field_name)))
            # Create list of lookup strings
            lookup_list = add_location(ast.List(
                elts=[add_location(ast.Constant(value=lookup)) for lookup in lookups],
                ctx=ast.Load()
            ))
            dict_values.append(lookup_list)

        filterset_fields_assign = add_location(ast.Assign(
            targets=[add_location(ast.Name(id="filterset_fields", ctx=ast.Store()))],
            value=add_location(ast.Dict(
                keys=dict_keys,
                values=dict_values
            ))
        ))
    else:
        filterset_fields_assign = None

    # Assemble the viewset body
    viewset_body = [
        docstring,
        queryset_assign,
        queryset_ordering_assign,
        serializer_class_assign,
        permission_classes_assign,
        filter_backends_assign,
        ordering_fields_assign,
        search_fields_assign
    ]

    if filterset_fields_assign:
        viewset_body.append(filterset_fields_assign)

    # Create the class definition
    return create_class_def(
        name=viewset_name,
        bases=["viewsets.ModelViewSet"],
        body=viewset_body
    )


def generate_views_ast(tables_info: List[TableInfo], models_module: str = ".models", serializers_module: str = ".serializers") -> ast.Module:
    """Generates the complete AST Module for the views.py file."""
    # Create file docstring
    file_docstring = add_location(ast.Expr(
        value=create_string_constant("""
Generated by drf-auto-generator.
Defines ViewSets for handling API requests with filterset_fields for query parameter filtering.
""")
    ))

    # Get all model names for imports, excluding M2M through tables
    model_names = []
    serializer_names = []
    for table in tables_info:
        if table.primary_key_columns and not table.is_m2m_through_table:
            model_name = to_pascal_case(pluralize(table.name))
            model_names.append(model_name)
            serializer_names.append(f"{model_name}Serializer")

    # Create comprehensive imports
    imports = [
        create_import("rest_framework", ["viewsets", "permissions", "filters"]),
        create_import("django_filters.rest_framework", ["DjangoFilterBackend"]),
        create_import(models_module, model_names),
        create_import(serializers_module, serializer_names)
    ]

    # Create viewset classes, excluding M2M through tables
    viewset_classes = []
    for table in tables_info:
        if table.primary_key_columns:
            if table.is_m2m_through_table:
                logger.info(f"Skipping ViewSet generation for M2M through table: {table.name}")
                continue
            viewset_classes.append(create_viewset_class(table))
        else:
            logger.warning(f"Table {table.name} does not have a primary key, skipping viewset generation...")

    # Assemble the module body
    module_body = [file_docstring] + imports + viewset_classes
    return add_location(ast.Module(body=module_body, type_ignores=[]))


def generate_views_code(tables_info: List[TableInfo], models_module: str = ".models", serializers_module: str = ".serializers") -> str:
    """Generates the Python code string for views.py."""
    module_ast = generate_views_ast(tables_info, models_module, serializers_module)
    return ast.unparse(module_ast)
