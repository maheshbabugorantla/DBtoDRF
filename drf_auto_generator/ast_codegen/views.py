import logging
import ast
from typing import List, Dict, Any

from drf_auto_generator.ast_codegen.base import (
    create_import, create_assign, create_class_def,
    create_attribute_call, create_list_of_strings,
    create_string_constant, add_location, pluralize
)
from drf_auto_generator.introspection_django import TableInfo, ColumnInfo
from drf_auto_generator.mapper import to_pascal_case, clean_field_name


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
    """Get the primary key field name for ordering."""
    # If there are multiple primary key columns, Django creates an auto 'id' field
    # This happens for through tables like FilmActor that have composite PKs
    if len(table_info.primary_key_columns) > 1:
        return "id"

    # If there's exactly one primary key column, find the corresponding Django field name
    if len(table_info.primary_key_columns) == 1:
        pk_column_name = table_info.primary_key_columns[0]

        # Look up the actual Django field name from table_info.fields
        for field in table_info.fields:
            if (field.get("original_column_name") == pk_column_name and
                field.get("is_pk", False) and
                not field.get("is_handled_by_relation", False)):
                return field.get("name")

        # If we can't find the field in table_info.fields, it might be handled by a relationship
        # In that case, Django auto-generates an 'id' field
        return "id"

    # If no primary key columns found, Django auto-generates 'id'
    return "id"


def _create_action_decorator(detail: bool = False, methods: List[str] = None, url_path: str = None) -> ast.Call:
    """Create an @action decorator AST node."""
    if methods is None:
        methods = ["get"]

    keywords = [
        add_location(ast.keyword(arg="detail", value=add_location(ast.Constant(value=detail)))),
        add_location(ast.keyword(arg="methods", value=add_location(ast.List(
            elts=[add_location(ast.Constant(value=method)) for method in methods],
            ctx=ast.Load()
        ))))
    ]

    if url_path:
        keywords.append(add_location(ast.keyword(arg="url_path", value=add_location(ast.Constant(value=url_path)))))

    return add_location(ast.Call(
        func=add_location(ast.Name(id="action", ctx=ast.Load())),
        args=[],
        keywords=keywords
    ))


def _create_constraint_lookup_method(field_name: str, is_unique: bool = False) -> ast.FunctionDef:
    """Create a custom action method for constraint-based lookups."""
    method_name = f"get_by_{field_name}" if is_unique else f"filter_by_{field_name}"
    url_path = f"by_{field_name}/{{value}}" if is_unique else f"filter_by_{field_name}/{{value}}"

    # Create the method
    method_def = ast.FunctionDef(
        name=method_name,
        args=ast.arguments(
            posonlyargs=[],
            args=[
                add_location(ast.arg(arg="self", annotation=None)),
                add_location(ast.arg(arg="request", annotation=None)),
                add_location(ast.arg(arg="value", annotation=None))
            ],
            vararg=add_location(ast.arg(arg="args", annotation=None)),
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=add_location(ast.arg(arg="kwargs", annotation=None)),
            defaults=[]
        ),
        body=[
            # Create docstring
            add_location(ast.Expr(value=add_location(ast.Constant(value=f"""
            Retrieve by {field_name} lookup endpoint.

            Returns {'a single object' if is_unique else 'a filtered queryset'} matching the {field_name} parameter.
            """)))),

            # Create method body
            add_location(ast.If(
                test=add_location(ast.Constant(value=is_unique)),
                body=[
                    # For unique fields: get_object_or_404
                    add_location(ast.Assign(
                        targets=[add_location(ast.Name(id="instance", ctx=ast.Store()))],
                        value=add_location(ast.Call(
                            func=add_location(ast.Name(id="get_object_or_404", ctx=ast.Load())),
                            args=[
                                add_location(ast.Attribute(
                                    value=add_location(ast.Name(id="self", ctx=ast.Load())),
                                    attr="queryset",
                                    ctx=ast.Load()
                                ))
                            ],
                            keywords=[add_location(ast.keyword(arg=field_name, value=add_location(ast.Name(id="value", ctx=ast.Load()))))]
                        ))
                    )),
                    add_location(ast.Assign(
                        targets=[add_location(ast.Name(id="serializer", ctx=ast.Store()))],
                        value=add_location(ast.Call(
                            func=add_location(ast.Attribute(
                                value=add_location(ast.Name(id="self", ctx=ast.Load())),
                                attr="get_serializer",
                                ctx=ast.Load()
                            )),
                            args=[add_location(ast.Name(id="instance", ctx=ast.Load()))],
                            keywords=[]
                        ))
                    )),
                    add_location(ast.Return(
                        value=add_location(ast.Call(
                            func=add_location(ast.Name(id="Response", ctx=ast.Load())),
                            args=[add_location(ast.Attribute(
                                value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
                                attr="data",
                                ctx=ast.Load()
                            ))],
                            keywords=[]
                        ))
                    ))
                ],
                orelse=[
                    # For non-unique fields: filter and paginate
                    add_location(ast.Assign(
                        targets=[add_location(ast.Name(id="queryset", ctx=ast.Store()))],
                        value=add_location(ast.Call(
                            func=add_location(ast.Attribute(
                                value=add_location(ast.Attribute(
                                    value=add_location(ast.Name(id="self", ctx=ast.Load())),
                                    attr="queryset",
                                    ctx=ast.Load()
                                )),
                                attr="filter",
                                ctx=ast.Load()
                            )),
                            args=[],
                            keywords=[add_location(ast.keyword(arg=field_name, value=add_location(ast.Name(id="value", ctx=ast.Load()))))]
                        ))
                    )),
                    add_location(ast.Assign(
                        targets=[add_location(ast.Name(id="page", ctx=ast.Store()))],
                        value=add_location(ast.Call(
                            func=add_location(ast.Attribute(
                                value=add_location(ast.Name(id="self", ctx=ast.Load())),
                                attr="paginate_queryset",
                                ctx=ast.Load()
                            )),
                            args=[add_location(ast.Name(id="queryset", ctx=ast.Load()))],
                            keywords=[]
                        ))
                    )),
                    add_location(ast.If(
                        test=add_location(ast.Name(id="page", ctx=ast.Load())),
                        body=[
                            add_location(ast.Assign(
                                targets=[add_location(ast.Name(id="serializer", ctx=ast.Store()))],
                                value=add_location(ast.Call(
                                    func=add_location(ast.Attribute(
                                        value=add_location(ast.Name(id="self", ctx=ast.Load())),
                                        attr="get_serializer",
                                        ctx=ast.Load()
                                    )),
                                    args=[add_location(ast.Name(id="page", ctx=ast.Load()))],
                                    keywords=[add_location(ast.keyword(arg="many", value=add_location(ast.Constant(value=True))))]
                                ))
                            )),
                            add_location(ast.Return(
                                value=add_location(ast.Call(
                                    func=add_location(ast.Attribute(
                                        value=add_location(ast.Name(id="self", ctx=ast.Load())),
                                        attr="get_paginated_response",
                                        ctx=ast.Load()
                                    )),
                                    args=[add_location(ast.Attribute(
                                        value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
                                        attr="data",
                                        ctx=ast.Load()
                                    ))],
                                    keywords=[]
                                ))
                            ))
                        ],
                        orelse=[
                            add_location(ast.Assign(
                                targets=[add_location(ast.Name(id="serializer", ctx=ast.Store()))],
                                value=add_location(ast.Call(
                                    func=add_location(ast.Attribute(
                                        value=add_location(ast.Name(id="self", ctx=ast.Load())),
                                        attr="get_serializer",
                                        ctx=ast.Load()
                                    )),
                                    args=[add_location(ast.Name(id="queryset", ctx=ast.Load()))],
                                    keywords=[add_location(ast.keyword(arg="many", value=add_location(ast.Constant(value=True))))]
                                ))
                            )),
                            add_location(ast.Return(
                                value=add_location(ast.Call(
                                    func=add_location(ast.Name(id="Response", ctx=ast.Load())),
                                    args=[add_location(ast.Attribute(
                                        value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
                                        attr="data",
                                        ctx=ast.Load()
                                    ))],
                                    keywords=[]
                                ))
                            ))
                        ]
                    ))
                ]
            ))
        ],
        decorator_list=[_create_action_decorator(detail=False, methods=["get"], url_path=url_path)],
        returns=None
    )

    return add_location(method_def)


def _create_m2m_list_method(relation_name: str, target_model: str) -> ast.FunctionDef:
    """Create a method to list M2M related objects."""
    method_name = f"list_{relation_name}"
    url_path = f"{relation_name}"

    method_def = ast.FunctionDef(
        name=method_name,
        args=add_location(ast.arguments(
            posonlyargs=[],
            args=[
                add_location(ast.arg(arg="self", annotation=None)),
                add_location(ast.arg(arg="request", annotation=None))
            ],
            vararg=add_location(ast.arg(arg="args", annotation=None)),
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=add_location(ast.arg(arg="kwargs", annotation=None)),
            defaults=[]
        )),
        body=[
            add_location(ast.Expr(value=add_location(ast.Constant(value=f"List {relation_name} for this instance.")))),
            add_location(ast.Assign(
                targets=[add_location(ast.Name(id="instance", ctx=ast.Store()))],
                value=add_location(ast.Call(
                    func=add_location(ast.Attribute(
                        value=add_location(ast.Name(id="self", ctx=ast.Load())),
                        attr="get_object",
                        ctx=ast.Load()
                    )),
                    args=[],
                    keywords=[]
                ))
            )),
            add_location(ast.Assign(
                targets=[add_location(ast.Name(id="queryset", ctx=ast.Store()))],
                value=add_location(ast.Attribute(
                    value=add_location(ast.Name(id="instance", ctx=ast.Load())),
                    attr=relation_name,
                    ctx=ast.Load()
                ))
            )),
            add_location(ast.Assign(
                targets=[add_location(ast.Name(id="page", ctx=ast.Store()))],
                value=add_location(ast.Call(
                    func=add_location(ast.Attribute(
                        value=add_location(ast.Name(id="self", ctx=ast.Load())),
                        attr="paginate_queryset",
                        ctx=ast.Load()
                    )),
                    args=[add_location(ast.Name(id="queryset", ctx=ast.Load()))],
                    keywords=[]
                ))
            )),
            add_location(ast.If(
                test=add_location(ast.Name(id="page", ctx=ast.Load())),
                body=[
                    add_location(ast.Assign(
                        targets=[add_location(ast.Name(id="serializer", ctx=ast.Store()))],
                        value=add_location(ast.Call(
                            func=add_location(ast.Name(id=f"{target_model}Serializer", ctx=ast.Load())),
                            args=[add_location(ast.Name(id="page", ctx=ast.Load()))],
                            keywords=[add_location(ast.keyword(arg="many", value=add_location(ast.Constant(value=True))))]
                        ))
                    )),
                    add_location(ast.Return(
                        value=add_location(ast.Call(
                            func=add_location(ast.Attribute(
                                value=add_location(ast.Name(id="self", ctx=ast.Load())),
                                attr="get_paginated_response",
                                ctx=ast.Load()
                            )),
                            args=[add_location(ast.Attribute(
                                value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
                                attr="data",
                                ctx=ast.Load()
                            ))],
                            keywords=[]
                        ))
                    ))
                ],
                orelse=[
                    add_location(ast.Assign(
                        targets=[add_location(ast.Name(id="serializer", ctx=ast.Store()))],
                        value=add_location(ast.Call(
                            func=add_location(ast.Name(id=f"{target_model}Serializer", ctx=ast.Load())),
                            args=[add_location(ast.Name(id="queryset", ctx=ast.Load()))],
                            keywords=[add_location(ast.keyword(arg="many", value=add_location(ast.Constant(value=True))))]
                        ))
                    )),
                    add_location(ast.Return(
                        value=add_location(ast.Call(
                            func=add_location(ast.Name(id="Response", ctx=ast.Load())),
                            args=[add_location(ast.Attribute(
                                value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
                                attr="data",
                                ctx=ast.Load()
                            ))],
                            keywords=[]
                        ))
                    ))
                ]
            ))
        ],
        decorator_list=[_create_action_decorator(detail=True, methods=["get"], url_path=url_path)],
        returns=None
    )

    return add_location(method_def)


def _create_m2m_manage_method(relation_name: str, target_model: str) -> ast.FunctionDef:
    """Create a method to add/remove M2M related objects."""
    method_name = f"manage_{relation_name}"
    url_path = f"{relation_name}/{{related_id}}"

    method_def = ast.FunctionDef(
        name=method_name,
        args=add_location(ast.arguments(
            posonlyargs=[],
            args=[
                add_location(ast.arg(arg="self", annotation=None)),
                add_location(ast.arg(arg="request", annotation=None)),
                add_location(ast.arg(arg="related_id", annotation=None))
            ],
            vararg=add_location(ast.arg(arg="args", annotation=None)),
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=add_location(ast.arg(arg="kwargs", annotation=None)),
            defaults=[]
        )),
        body=[
            add_location(ast.Expr(value=add_location(ast.Constant(value=f"Add or remove {target_model} from {relation_name}.")))),
            add_location(ast.Assign(
                targets=[add_location(ast.Name(id="instance", ctx=ast.Store()))],
                value=add_location(ast.Call(
                    func=add_location(ast.Attribute(
                        value=add_location(ast.Name(id="self", ctx=ast.Load())),
                        attr="get_object",
                        ctx=ast.Load()
                    )),
                    args=[],
                    keywords=[]
                ))
            )),
            add_location(ast.Assign(
                targets=[add_location(ast.Name(id="related_instance", ctx=ast.Store()))],
                value=add_location(ast.Call(
                    func=add_location(ast.Name(id="get_object_or_404", ctx=ast.Load())),
                    args=[
                        add_location(ast.Name(id=target_model, ctx=ast.Load()))
                    ],
                    keywords=[add_location(ast.keyword(arg="pk", value=add_location(ast.Name(id="related_id", ctx=ast.Load()))))]
                ))
            )),
            add_location(ast.If(
                test=add_location(ast.Compare(
                    left=add_location(ast.Attribute(
                        value=add_location(ast.Name(id="request", ctx=ast.Load())),
                        attr="method",
                        ctx=ast.Load()
                    )),
                    ops=[ast.Eq()],
                    comparators=[add_location(ast.Constant(value="POST"))]
                )),
                body=[
                    add_location(ast.Expr(
                        value=add_location(ast.Call(
                            func=add_location(ast.Attribute(
                                value=add_location(ast.Attribute(
                                    value=add_location(ast.Name(id="instance", ctx=ast.Load())),
                                    attr=relation_name,
                                    ctx=ast.Load()
                                )),
                                attr="add",
                                ctx=ast.Load()
                            )),
                            args=[add_location(ast.Name(id="related_instance", ctx=ast.Load()))],
                            keywords=[]
                        ))
                    )),
                    add_location(ast.Return(
                        value=add_location(ast.Call(
                            func=add_location(ast.Name(id="Response", ctx=ast.Load())),
                            args=[],
                            keywords=[add_location(ast.keyword(arg="status", value=add_location(ast.Constant(value=201))))]
                        ))
                    ))
                ],
                orelse=[
                    add_location(ast.If(
                        test=add_location(ast.Compare(
                            left=add_location(ast.Attribute(
                                value=add_location(ast.Name(id="request", ctx=ast.Load())),
                                attr="method",
                                ctx=ast.Load()
                            )),
                            ops=[ast.Eq()],
                            comparators=[add_location(ast.Constant(value="DELETE"))]
                        )),
                        body=[
                            add_location(ast.Expr(
                                value=add_location(ast.Call(
                                    func=add_location(ast.Attribute(
                                        value=add_location(ast.Attribute(
                                            value=add_location(ast.Name(id="instance", ctx=ast.Load())),
                                            attr=relation_name,
                                            ctx=ast.Load()
                                        )),
                                        attr="remove",
                                        ctx=ast.Load()
                                    )),
                                    args=[add_location(ast.Name(id="related_instance", ctx=ast.Load()))],
                                    keywords=[]
                                ))
                            )),
                            add_location(ast.Return(
                                value=add_location(ast.Call(
                                    func=add_location(ast.Name(id="Response", ctx=ast.Load())),
                                    args=[],
                                    keywords=[add_location(ast.keyword(arg="status", value=add_location(ast.Constant(value=204))))]
                                ))
                            ))
                        ],
                        orelse=[
                            add_location(ast.Return(
                                value=add_location(ast.Call(
                                    func=add_location(ast.Name(id="Response", ctx=ast.Load())),
                                    args=[],
                                    keywords=[add_location(ast.keyword(arg="status", value=add_location(ast.Constant(value=405))))]
                                ))
                            ))
                        ]
                    ))
                ]
            ))
        ],
        decorator_list=[_create_action_decorator(detail=True, methods=["post", "delete"], url_path=url_path)],
        returns=None
    )

    return add_location(method_def)


def _create_filterset_fields(table_info: TableInfo) -> List[str]:
    """Create filterset_fields configuration for query parameter filtering."""
    filterset_fields = []

    # Add foreign key fields for filtering
    for rel in table_info.relationships:
        if rel["type"] == "many-to-one":
            rel_name = rel["name"]
            filterset_fields.append(f"'{rel_name}': ['exact']")

    # Add indexed fields for filtering
    for index in table_info.meta_indexes:
        for field_name in index.get("fields", []):
            # Skip if already added as relationship filter
            if not any(f"'{field_name}'" in field for field in filterset_fields):
                field_info = next((f for f in table_info.fields if f.get("name") == field_name), None)
                if field_info and not field_info.get("is_pk", False):
                    filterset_fields.append(f"'{field_name}': ['exact', 'icontains']")

    # Add unique fields for filtering
    for field in table_info.fields:
        field_name = field.get("name")
        if (field.get("options", {}).get("unique", False) and
            not field.get("is_pk", False) and
            not any(f"'{field_name}'" in field for field in filterset_fields)):
            filterset_fields.append(f"'{field_name}': ['exact']")

    return filterset_fields


def create_viewset_class(table_info: TableInfo) -> ast.ClassDef:
    """Creates the AST ClassDef node for a DRF ModelViewSet with all custom actions."""
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

        Provides standard CRUD operations and custom constraint-based lookups.
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
        filterset_fields_assign = add_location(ast.Assign(
            targets=[add_location(ast.Name(id="filterset_fields", ctx=ast.Store()))],
            value=add_location(ast.Dict(
                keys=[],
                values=[],
                # We'll add this as a comment for now since it's complex to generate as AST
            ))
        ))
        # Add comment about filterset_fields
        filterset_comment = add_location(ast.Expr(value=add_location(ast.Constant(
            value=f"# filterset_fields = {{{', '.join(filterset_fields)}}}"
        ))))
    else:
        filterset_fields_assign = None
        filterset_comment = None

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

    if filterset_comment:
        viewset_body.append(filterset_comment)

    # Generate custom action methods for constraint-based lookups
    custom_methods = []

    # 1. Generate unique field lookup methods (simplified approach)
    for field in table_info.fields:
        field_name = field.get("name")
        if (field.get("options", {}).get("unique", False) and
            not field.get("is_pk", False) and
            not field.get("is_handled_by_relation", False) and
            not field_name.endswith("_rel")):
            # Create a simple custom action method using string-based approach
            method_name = f"get_by_{field_name}"
            url_path = f"by_{field_name}/{{value}}"

            # Create method using basic AST nodes with proper location info
            method_def = add_location(ast.FunctionDef(
                name=method_name,
                args=add_location(ast.arguments(
                    posonlyargs=[],
                    args=[
                        add_location(ast.arg(arg="self", annotation=None)),
                        add_location(ast.arg(arg="request", annotation=None)),
                        add_location(ast.arg(arg="value", annotation=None))
                    ],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[]
                )),
                body=[
                    add_location(ast.Expr(value=add_location(ast.Constant(value=f"Retrieve by {field_name} lookup endpoint.")))),
                    add_location(ast.Assign(
                        targets=[add_location(ast.Name(id="instance", ctx=ast.Store()))],
                        value=add_location(ast.Call(
                            func=add_location(ast.Name(id="get_object_or_404", ctx=ast.Load())),
                            args=[
                                add_location(ast.Attribute(
                                    value=add_location(ast.Name(id="self", ctx=ast.Load())),
                                    attr="queryset",
                                    ctx=ast.Load()
                                ))
                            ],
                            keywords=[add_location(ast.keyword(arg=field_name, value=add_location(ast.Name(id="value", ctx=ast.Load()))))]
                        ))
                    )),
                    add_location(ast.Assign(
                        targets=[add_location(ast.Name(id="serializer", ctx=ast.Store()))],
                        value=add_location(ast.Call(
                            func=add_location(ast.Attribute(
                                value=add_location(ast.Name(id="self", ctx=ast.Load())),
                                attr="get_serializer",
                                ctx=ast.Load()
                            )),
                            args=[add_location(ast.Name(id="instance", ctx=ast.Load()))],
                            keywords=[]
                        ))
                    )),
                    add_location(ast.Return(
                        value=add_location(ast.Call(
                            func=add_location(ast.Name(id="Response", ctx=ast.Load())),
                            args=[add_location(ast.Attribute(
                                value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
                                attr="data",
                                ctx=ast.Load()
                            ))],
                            keywords=[]
                        ))
                    ))
                ],
                decorator_list=[_create_action_decorator(detail=False, methods=["get"], url_path=url_path)],
                returns=None
            ))
            custom_methods.append(method_def)

    # 2. Generate indexed field filtering methods
    for index in table_info.meta_indexes:
        for field_name in index.get("fields", []):
            field_info = next((f for f in table_info.fields if f.get("name") == field_name), None)
            if (field_info and
                not field_info.get("is_pk", False) and
                not field_info.get("options", {}).get("unique", False) and
                not field_info.get("is_handled_by_relation", False) and
                not field_name.endswith("_rel")):
                custom_methods.append(_create_constraint_lookup_method(field_name, is_unique=False))

    # 3. Generate M2M relationship management methods
    for rel in table_info.relationships:
        if rel["type"] == "many-to-many":
            rel_name = rel["name"]
            target_model = rel["target_model_name"]
            custom_methods.append(_create_m2m_list_method(rel_name, target_model))
            custom_methods.append(_create_m2m_manage_method(rel_name, target_model))

    # Add custom methods to viewset body
    viewset_body.extend(custom_methods)

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
Defines ViewSets for handling API requests with custom constraint-based lookups and M2M management.
""")
    ))

    # Get all model names for imports
    model_names = []
    serializer_names = []
    for table in tables_info:
        if table.primary_key_columns:
            model_name = to_pascal_case(pluralize(table.name))
            model_names.append(model_name)
            serializer_names.append(f"{model_name}Serializer")

    # Create comprehensive imports
    imports = [
        create_import("rest_framework", ["viewsets", "permissions", "filters", "status"]),
        create_import("rest_framework.response", ["Response"]),
        create_import("rest_framework.decorators", ["action"]),
        create_import("django.shortcuts", ["get_object_or_404"]),
        create_import("django_filters.rest_framework", ["DjangoFilterBackend"]),
        create_import(models_module, model_names),
        create_import(serializers_module, serializer_names)
    ]

    # Create viewset classes
    viewset_classes = []
    for table in tables_info:
        if table.primary_key_columns:
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
