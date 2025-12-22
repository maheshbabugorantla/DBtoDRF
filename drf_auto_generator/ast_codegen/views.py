import logging
import ast
from typing import List, Dict, Any, Optional

from drf_auto_generator.ast_codegen.base import (
    create_import, create_assign, create_class_def,
    create_list_of_strings, create_string_constant,
    add_location, pluralize, create_decorator, create_function_def,
    create_keyword, create_boolean_constant, create_attribute, create_call
)
from drf_auto_generator.domain.models import TableInfo
from drf_auto_generator.domain.naming import to_pascal_case


logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS FOR CREATING CUSTOM VIEWSET ACTIONS
# =============================================================================

def _create_action_decorator(
    detail: bool = False,
    methods: List[str] = None,
    url_path: str = None,
    url_name: str = None
) -> ast.expr:
    """Creates an @action decorator for DRF ViewSet custom actions."""
    keywords = [
        create_keyword("detail", create_boolean_constant(detail))
    ]

    if methods:
        methods_list = add_location(ast.List(
            elts=[create_string_constant(m) for m in methods],
            ctx=ast.Load()
        ))
        keywords.append(create_keyword("methods", methods_list))

    if url_path:
        keywords.append(create_keyword("url_path", create_string_constant(url_path)))

    if url_name:
        keywords.append(create_keyword("url_name", create_string_constant(url_name)))

    return create_decorator("action", keywords=keywords)


def _create_response_return(data_expr: ast.expr, status: str = None) -> ast.Return:
    """Creates a return Response(...) statement."""
    keywords = []
    if status:
        keywords.append(create_keyword("status", add_location(
            ast.Attribute(
                value=add_location(ast.Name(id="status", ctx=ast.Load())),
                attr=status,
                ctx=ast.Load()
            )
        )))

    response_call = add_location(ast.Call(
        func=add_location(ast.Name(id="Response", ctx=ast.Load())),
        args=[data_expr],
        keywords=keywords
    ))
    return add_location(ast.Return(value=response_call))


def _create_get_object_or_404(model_name: str, lookup_field: str, lookup_value: ast.expr) -> ast.Call:
    """Creates get_object_or_404(Model, field=value) call."""
    return add_location(ast.Call(
        func=add_location(ast.Name(id="get_object_or_404", ctx=ast.Load())),
        args=[add_location(ast.Name(id=model_name, ctx=ast.Load()))],
        keywords=[create_keyword(lookup_field, lookup_value)]
    ))


def _create_filter_queryset(model_name: str, filters: Dict[str, ast.expr]) -> ast.Call:
    """Creates Model.objects.filter(**filters) call."""
    filter_keywords = [create_keyword(k, v) for k, v in filters.items()]

    return add_location(ast.Call(
        func=add_location(ast.Attribute(
            value=add_location(ast.Attribute(
                value=add_location(ast.Name(id=model_name, ctx=ast.Load())),
                attr="objects",
                ctx=ast.Load()
            )),
            attr="filter",
            ctx=ast.Load()
        )),
        args=[],
        keywords=filter_keywords
    ))


# =============================================================================
# UNIQUE FIELD LOOKUP ACTIONS
# =============================================================================

def _create_unique_field_action(
    field_name: str,
    model_name: str,
    serializer_name: str
) -> ast.FunctionDef:
    """
    Creates an action method for looking up by a unique field.

    Generates:
        @action(detail=False, methods=['get'], url_path='by_<field>/<value>')
        def by_<field>(self, request, value=None):
            instance = get_object_or_404(Model, <field>=value)
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
    """
    action_name = f"by_{field_name}"
    url_path = f"by_{field_name}/(?P<value>[^/.]+)"

    # Create decorator
    decorator = _create_action_decorator(
        detail=False,
        methods=["get"],
        url_path=url_path
    )

    # Create function body
    body = [
        # instance = get_object_or_404(Model, field=value)
        add_location(ast.Assign(
            targets=[add_location(ast.Name(id="instance", ctx=ast.Store()))],
            value=_create_get_object_or_404(
                model_name,
                field_name,
                add_location(ast.Name(id="value", ctx=ast.Load()))
            )
        )),
        # serializer = self.get_serializer(instance)
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
        # return Response(serializer.data)
        _create_response_return(add_location(ast.Attribute(
            value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
            attr="data",
            ctx=ast.Load()
        )))
    ]

    return create_function_def(
        name=action_name,
        args=["self", "request", "value"],
        body=body,
        decorators=[decorator]
    )


def _get_unique_field_actions(table_info: TableInfo, model_name: str, serializer_name: str) -> List[ast.FunctionDef]:
    """Get all unique field lookup actions for a table."""
    actions = []

    for field in table_info.fields:
        field_name = field.get("name")

        # Skip primary key fields, relationship fields, and non-unique fields
        if (field.get("is_pk", False) or
            field.get("is_handled_by_relation", False) or
            field_name.endswith("_rel") or
            not field.get("options", {}).get("unique", False)):
            continue

        actions.append(_create_unique_field_action(field_name, model_name, serializer_name))
        logger.debug(f"Created unique field action: by_{field_name} for {model_name}")

    return actions


# =============================================================================
# COMPOSITE CONSTRAINT LOOKUP ACTIONS
# =============================================================================

def _create_composite_constraint_action(
    field_names: List[str],
    model_name: str,
    serializer_name: str,
    constraint_name: str
) -> ast.FunctionDef:
    """
    Creates an action method for looking up by composite unique constraint.

    Generates:
        @action(detail=False, methods=['get'], url_path='by_field1_and_field2')
        def by_field1_and_field2(self, request):
            field1 = request.query_params.get('field1')
            field2 = request.query_params.get('field2')
            instance = get_object_or_404(Model, field1=field1, field2=field2)
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
    """
    action_name = f"by_{'_and_'.join(field_names)}"
    url_path = f"by_{'_and_'.join(field_names)}"

    # Create decorator
    decorator = _create_action_decorator(
        detail=False,
        methods=["get"],
        url_path=url_path
    )

    # Create function body
    body = []

    # Extract query params for each field
    for field_name in field_names:
        # field = request.query_params.get('field')
        body.append(add_location(ast.Assign(
            targets=[add_location(ast.Name(id=field_name, ctx=ast.Store()))],
            value=add_location(ast.Call(
                func=add_location(ast.Attribute(
                    value=add_location(ast.Attribute(
                        value=add_location(ast.Name(id="request", ctx=ast.Load())),
                        attr="query_params",
                        ctx=ast.Load()
                    )),
                    attr="get",
                    ctx=ast.Load()
                )),
                args=[create_string_constant(field_name)],
                keywords=[]
            ))
        )))

    # Build filter kwargs
    filter_kwargs = {
        field_name: add_location(ast.Name(id=field_name, ctx=ast.Load()))
        for field_name in field_names
    }

    # instance = get_object_or_404(Model, **filters)
    get_object_call = add_location(ast.Call(
        func=add_location(ast.Name(id="get_object_or_404", ctx=ast.Load())),
        args=[add_location(ast.Name(id=model_name, ctx=ast.Load()))],
        keywords=[create_keyword(k, v) for k, v in filter_kwargs.items()]
    ))
    body.append(add_location(ast.Assign(
        targets=[add_location(ast.Name(id="instance", ctx=ast.Store()))],
        value=get_object_call
    )))

    # serializer = self.get_serializer(instance)
    body.append(add_location(ast.Assign(
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
    )))

    # return Response(serializer.data)
    body.append(_create_response_return(add_location(ast.Attribute(
        value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
        attr="data",
        ctx=ast.Load()
    ))))

    return create_function_def(
        name=action_name,
        args=["self", "request"],
        body=body,
        decorators=[decorator]
    )


def _get_composite_constraint_actions(table_info: TableInfo, model_name: str, serializer_name: str) -> List[ast.FunctionDef]:
    """Get all composite unique constraint lookup actions for a table."""
    actions = []

    # Handle missing meta_constraints attribute gracefully (for backward compatibility)
    meta_constraints = getattr(table_info, 'meta_constraints', None) or []

    for constraint in meta_constraints:
        if constraint.get("type") != "unique" or len(constraint.get("fields", [])) <= 1:
            continue

        field_names = constraint.get("fields", [])
        # Filter to only include actual database fields
        actual_fields = _filter_db_fields(table_info, field_names)

        if len(actual_fields) > 1:
            actions.append(_create_composite_constraint_action(
                actual_fields, model_name, serializer_name, constraint.get("name", "")
            ))
            logger.debug(f"Created composite constraint action: by_{'_and_'.join(actual_fields)} for {model_name}")

    return actions


def _filter_db_fields(table_info: TableInfo, field_names: List[str]) -> List[str]:
    """Filters field names to only include actual database columns."""
    actual_db_fields = []
    for field_name in field_names:
        field = next((f for f in table_info.fields if f["name"] == field_name), None)
        if field and not field.get("is_handled_by_relation", False) and not field_name.endswith("_rel"):
            actual_db_fields.append(field_name)
    return actual_db_fields


# =============================================================================
# INDEX-BASED FILTER ACTIONS
# =============================================================================

def _create_single_index_filter_action(
    field_name: str,
    model_name: str,
    serializer_name: str
) -> ast.FunctionDef:
    """
    Creates an action method for filtering by a single indexed field.

    Generates:
        @action(detail=False, methods=['get'], url_path='filter_by_<field>/(?P<value>[^/.]+)')
        def filter_by_<field>(self, request, value=None):
            queryset = Model.objects.filter(<field>=value)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
    """
    action_name = f"filter_by_{field_name}"
    url_path = f"filter_by_{field_name}/(?P<value>[^/.]+)"

    # Create decorator
    decorator = _create_action_decorator(
        detail=False,
        methods=["get"],
        url_path=url_path
    )

    # Create function body
    body = [
        # queryset = Model.objects.filter(field=value)
        add_location(ast.Assign(
            targets=[add_location(ast.Name(id="queryset", ctx=ast.Store()))],
            value=_create_filter_queryset(
                model_name,
                {field_name: add_location(ast.Name(id="value", ctx=ast.Load()))}
            )
        )),
        # serializer = self.get_serializer(queryset, many=True)
        add_location(ast.Assign(
            targets=[add_location(ast.Name(id="serializer", ctx=ast.Store()))],
            value=add_location(ast.Call(
                func=add_location(ast.Attribute(
                    value=add_location(ast.Name(id="self", ctx=ast.Load())),
                    attr="get_serializer",
                    ctx=ast.Load()
                )),
                args=[add_location(ast.Name(id="queryset", ctx=ast.Load()))],
                keywords=[create_keyword("many", create_boolean_constant(True))]
            ))
        )),
        # return Response(serializer.data)
        _create_response_return(add_location(ast.Attribute(
            value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
            attr="data",
            ctx=ast.Load()
        )))
    ]

    return create_function_def(
        name=action_name,
        args=["self", "request", "value"],
        body=body,
        decorators=[decorator]
    )


def _create_multi_index_filter_action(
    field_names: List[str],
    model_name: str,
    serializer_name: str
) -> ast.FunctionDef:
    """
    Creates an action method for filtering by multiple indexed fields.

    Generates:
        @action(detail=False, methods=['get'], url_path='filter_by_field1_and_field2')
        def filter_by_field1_and_field2(self, request):
            filters = {}
            if 'field1' in request.query_params:
                filters['field1'] = request.query_params['field1']
            ...
            queryset = Model.objects.filter(**filters)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
    """
    action_name = f"filter_by_{'_and_'.join(field_names)}"
    url_path = f"filter_by_{'_and_'.join(field_names)}"

    # Create decorator
    decorator = _create_action_decorator(
        detail=False,
        methods=["get"],
        url_path=url_path
    )

    # Create function body
    body = [
        # filters = {}
        add_location(ast.Assign(
            targets=[add_location(ast.Name(id="filters", ctx=ast.Store()))],
            value=add_location(ast.Dict(keys=[], values=[]))
        ))
    ]

    # Add conditional filter extraction for each field
    for field_name in field_names:
        # if 'field' in request.query_params:
        #     filters['field'] = request.query_params['field']
        body.append(add_location(ast.If(
            test=add_location(ast.Compare(
                left=create_string_constant(field_name),
                ops=[add_location(ast.In())],
                comparators=[add_location(ast.Attribute(
                    value=add_location(ast.Name(id="request", ctx=ast.Load())),
                    attr="query_params",
                    ctx=ast.Load()
                ))]
            )),
            body=[add_location(ast.Assign(
                targets=[add_location(ast.Subscript(
                    value=add_location(ast.Name(id="filters", ctx=ast.Load())),
                    slice=create_string_constant(field_name),
                    ctx=ast.Store()
                ))],
                value=add_location(ast.Subscript(
                    value=add_location(ast.Attribute(
                        value=add_location(ast.Name(id="request", ctx=ast.Load())),
                        attr="query_params",
                        ctx=ast.Load()
                    )),
                    slice=create_string_constant(field_name),
                    ctx=ast.Load()
                ))
            ))],
            orelse=[]
        )))

    # queryset = Model.objects.filter(**filters)
    body.append(add_location(ast.Assign(
        targets=[add_location(ast.Name(id="queryset", ctx=ast.Store()))],
        value=add_location(ast.Call(
            func=add_location(ast.Attribute(
                value=add_location(ast.Attribute(
                    value=add_location(ast.Name(id=model_name, ctx=ast.Load())),
                    attr="objects",
                    ctx=ast.Load()
                )),
                attr="filter",
                ctx=ast.Load()
            )),
            args=[],
            keywords=[add_location(ast.keyword(
                arg=None,
                value=add_location(ast.Name(id="filters", ctx=ast.Load()))
            ))]
        ))
    )))

    # serializer = self.get_serializer(queryset, many=True)
    body.append(add_location(ast.Assign(
        targets=[add_location(ast.Name(id="serializer", ctx=ast.Store()))],
        value=add_location(ast.Call(
            func=add_location(ast.Attribute(
                value=add_location(ast.Name(id="self", ctx=ast.Load())),
                attr="get_serializer",
                ctx=ast.Load()
            )),
            args=[add_location(ast.Name(id="queryset", ctx=ast.Load()))],
            keywords=[create_keyword("many", create_boolean_constant(True))]
        ))
    )))

    # return Response(serializer.data)
    body.append(_create_response_return(add_location(ast.Attribute(
        value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
        attr="data",
        ctx=ast.Load()
    ))))

    return create_function_def(
        name=action_name,
        args=["self", "request"],
        body=body,
        decorators=[decorator]
    )


def _get_index_filter_actions(table_info: TableInfo, model_name: str, serializer_name: str) -> List[ast.FunctionDef]:
    """Get all index-based filter actions for a table."""
    actions = []

    # Handle missing meta_indexes attribute gracefully (for backward compatibility)
    meta_indexes = getattr(table_info, 'meta_indexes', None) or []

    for index in meta_indexes:
        index_fields = index.get("fields", [])
        if not index_fields:
            continue

        actual_fields = _filter_db_fields(table_info, index_fields)
        if not actual_fields:
            continue

        if len(actual_fields) == 1:
            field_name = actual_fields[0]
            # Skip if field is unique (already has by_<field> endpoint)
            field = next((f for f in table_info.fields if f["name"] == field_name), None)
            if field and field.get("options", {}).get("unique", False):
                continue

            actions.append(_create_single_index_filter_action(field_name, model_name, serializer_name))
            logger.debug(f"Created index filter action: filter_by_{field_name} for {model_name}")
        else:
            actions.append(_create_multi_index_filter_action(actual_fields, model_name, serializer_name))
            logger.debug(f"Created multi-index filter action: filter_by_{'_and_'.join(actual_fields)} for {model_name}")

    return actions


# =============================================================================
# M2M RELATIONSHIP MANAGEMENT ACTIONS
# =============================================================================

def _create_m2m_list_action(
    rel_name: str,
    target_model_name: str,
    target_serializer_name: str,
    model_name: str
) -> ast.FunctionDef:
    """
    Creates an action method for listing M2M related items.

    Generates:
        @action(detail=True, methods=['get'], url_path='<rel_name>')
        def <rel_name>(self, request, pk=None):
            instance = self.get_object()
            related = getattr(instance, '<rel_name>').all()
            serializer = <TargetSerializer>(related, many=True)
            return Response(serializer.data)
    """
    # Create decorator
    decorator = _create_action_decorator(
        detail=True,
        methods=["get"],
        url_path=rel_name
    )

    # Create function body
    body = [
        # instance = self.get_object()
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
        # related = getattr(instance, '<rel_name>').all()
        add_location(ast.Assign(
            targets=[add_location(ast.Name(id="related", ctx=ast.Store()))],
            value=add_location(ast.Call(
                func=add_location(ast.Attribute(
                    value=add_location(ast.Call(
                        func=add_location(ast.Name(id="getattr", ctx=ast.Load())),
                        args=[
                            add_location(ast.Name(id="instance", ctx=ast.Load())),
                            create_string_constant(rel_name)
                        ],
                        keywords=[]
                    )),
                    attr="all",
                    ctx=ast.Load()
                )),
                args=[],
                keywords=[]
            ))
        )),
        # serializer = TargetSerializer(related, many=True)
        add_location(ast.Assign(
            targets=[add_location(ast.Name(id="serializer", ctx=ast.Store()))],
            value=add_location(ast.Call(
                func=add_location(ast.Name(id=target_serializer_name, ctx=ast.Load())),
                args=[add_location(ast.Name(id="related", ctx=ast.Load()))],
                keywords=[create_keyword("many", create_boolean_constant(True))]
            ))
        )),
        # return Response(serializer.data)
        _create_response_return(add_location(ast.Attribute(
            value=add_location(ast.Name(id="serializer", ctx=ast.Load())),
            attr="data",
            ctx=ast.Load()
        )))
    ]

    return create_function_def(
        name=rel_name,
        args=["self", "request", "pk"],
        body=body,
        decorators=[decorator]
    )


def _create_m2m_add_action(
    rel_name: str,
    target_model_name: str,
    model_name: str
) -> ast.FunctionDef:
    """
    Creates an action method for adding an item to M2M relationship.

    Generates:
        @action(detail=True, methods=['post'], url_path='<rel_name>/(?P<related_pk>[^/.]+)')
        def add_<rel_name>(self, request, pk=None, related_pk=None):
            instance = self.get_object()
            related = get_object_or_404(<TargetModel>, pk=related_pk)
            getattr(instance, '<rel_name>').add(related)
            return Response({'status': 'added'}, status=status.HTTP_201_CREATED)
    """
    action_name = f"add_{rel_name}"
    url_path = f"{rel_name}/(?P<related_pk>[^/.]+)"

    # Create decorator
    decorator = _create_action_decorator(
        detail=True,
        methods=["post"],
        url_path=url_path
    )

    # Create function body
    body = [
        # instance = self.get_object()
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
        # related = get_object_or_404(TargetModel, pk=related_pk)
        add_location(ast.Assign(
            targets=[add_location(ast.Name(id="related", ctx=ast.Store()))],
            value=_create_get_object_or_404(
                target_model_name,
                "pk",
                add_location(ast.Name(id="related_pk", ctx=ast.Load()))
            )
        )),
        # getattr(instance, '<rel_name>').add(related)
        add_location(ast.Expr(value=add_location(ast.Call(
            func=add_location(ast.Attribute(
                value=add_location(ast.Call(
                    func=add_location(ast.Name(id="getattr", ctx=ast.Load())),
                    args=[
                        add_location(ast.Name(id="instance", ctx=ast.Load())),
                        create_string_constant(rel_name)
                    ],
                    keywords=[]
                )),
                attr="add",
                ctx=ast.Load()
            )),
            args=[add_location(ast.Name(id="related", ctx=ast.Load()))],
            keywords=[]
        )))),
        # return Response({'status': 'added'}, status=status.HTTP_201_CREATED)
        _create_response_return(
            add_location(ast.Dict(
                keys=[create_string_constant("status")],
                values=[create_string_constant("added")]
            )),
            status="HTTP_201_CREATED"
        )
    ]

    return create_function_def(
        name=action_name,
        args=["self", "request", "pk", "related_pk"],
        body=body,
        decorators=[decorator]
    )


def _create_m2m_remove_action(
    rel_name: str,
    target_model_name: str,
    model_name: str
) -> ast.FunctionDef:
    """
    Creates an action method for removing an item from M2M relationship.

    Generates:
        @action(detail=True, methods=['delete'], url_path='<rel_name>/(?P<related_pk>[^/.]+)/remove')
        def remove_<rel_name>(self, request, pk=None, related_pk=None):
            instance = self.get_object()
            related = get_object_or_404(<TargetModel>, pk=related_pk)
            getattr(instance, '<rel_name>').remove(related)
            return Response(status=status.HTTP_204_NO_CONTENT)
    """
    action_name = f"remove_{rel_name}"
    url_path = f"{rel_name}/(?P<related_pk>[^/.]+)/remove"

    # Create decorator
    decorator = _create_action_decorator(
        detail=True,
        methods=["delete"],
        url_path=url_path
    )

    # Create function body
    body = [
        # instance = self.get_object()
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
        # related = get_object_or_404(TargetModel, pk=related_pk)
        add_location(ast.Assign(
            targets=[add_location(ast.Name(id="related", ctx=ast.Store()))],
            value=_create_get_object_or_404(
                target_model_name,
                "pk",
                add_location(ast.Name(id="related_pk", ctx=ast.Load()))
            )
        )),
        # getattr(instance, '<rel_name>').remove(related)
        add_location(ast.Expr(value=add_location(ast.Call(
            func=add_location(ast.Attribute(
                value=add_location(ast.Call(
                    func=add_location(ast.Name(id="getattr", ctx=ast.Load())),
                    args=[
                        add_location(ast.Name(id="instance", ctx=ast.Load())),
                        create_string_constant(rel_name)
                    ],
                    keywords=[]
                )),
                attr="remove",
                ctx=ast.Load()
            )),
            args=[add_location(ast.Name(id="related", ctx=ast.Load()))],
            keywords=[]
        )))),
        # return Response(status=status.HTTP_204_NO_CONTENT)
        add_location(ast.Return(value=add_location(ast.Call(
            func=add_location(ast.Name(id="Response", ctx=ast.Load())),
            args=[],
            keywords=[create_keyword("status", add_location(ast.Attribute(
                value=add_location(ast.Name(id="status", ctx=ast.Load())),
                attr="HTTP_204_NO_CONTENT",
                ctx=ast.Load()
            )))]
        ))))
    ]

    return create_function_def(
        name=action_name,
        args=["self", "request", "pk", "related_pk"],
        body=body,
        decorators=[decorator]
    )


def _get_m2m_actions(table_info: TableInfo, model_name: str) -> List[ast.FunctionDef]:
    """Get all M2M management actions for a table."""
    actions = []

    # Handle missing relationships attribute gracefully (for backward compatibility)
    relationships = getattr(table_info, 'relationships', None) or []
    m2m_relationships = [r for r in relationships if r.get("type") == "many-to-many"]

    for rel in m2m_relationships:
        rel_name = rel.get("name")
        target_model_name = rel.get("target_model_name", "")

        if not rel_name or not target_model_name:
            continue

        target_serializer_name = f"{target_model_name}Serializer"

        # List action
        actions.append(_create_m2m_list_action(rel_name, target_model_name, target_serializer_name, model_name))

        # Add action
        actions.append(_create_m2m_add_action(rel_name, target_model_name, model_name))

        # Remove action
        actions.append(_create_m2m_remove_action(rel_name, target_model_name, model_name))

        logger.debug(f"Created M2M actions for {model_name}.{rel_name} -> {target_model_name}")

    return actions


# =============================================================================
# MAIN VIEWSET FIELD UTILITIES
# =============================================================================

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


def create_viewset_class(table_info: TableInfo, config: Dict[str, Any] = None) -> ast.ClassDef:
    """
    Creates the AST ClassDef node for a DRF ModelViewSet with CRUD operations,
    query parameter filtering, and custom actions for constraint/index/M2M endpoints.
    """
    config = config or {}
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

    # Add custom actions based on configuration
    # These actions match the endpoints defined in the OpenAPI spec

    # 1. Unique field lookup actions (by_<field>)
    if config.get("enable_constraint_endpoints", True):
        unique_actions = _get_unique_field_actions(table_info, model_name, serializer_name)
        viewset_body.extend(unique_actions)

        # 2. Composite constraint lookup actions (by_field1_and_field2)
        constraint_actions = _get_composite_constraint_actions(table_info, model_name, serializer_name)
        viewset_body.extend(constraint_actions)

        # 3. Index-based filter actions (filter_by_<field>)
        index_actions = _get_index_filter_actions(table_info, model_name, serializer_name)
        viewset_body.extend(index_actions)

    # 4. M2M relationship management actions
    if config.get("enable_m2m_endpoints", True):
        m2m_actions = _get_m2m_actions(table_info, model_name)
        viewset_body.extend(m2m_actions)

    # Create the class definition
    return create_class_def(
        name=viewset_name,
        bases=["viewsets.ModelViewSet"],
        body=viewset_body
    )


def generate_views_ast(
    tables_info: List[TableInfo],
    models_module: str = ".models",
    serializers_module: str = ".serializers",
    config: Dict[str, Any] = None
) -> ast.Module:
    """
    Generates the complete AST Module for the views.py file.

    Includes custom actions for unique field lookups, constraint-based lookups,
    index-based filtering, and M2M relationship management.
    """
    config = config or {}

    # Create file docstring
    file_docstring = add_location(ast.Expr(
        value=create_string_constant("""
Generated by drf-auto-generator.
Defines ViewSets for handling API requests with:
- Standard CRUD operations
- Query parameter filtering via filterset_fields
- Unique field lookup endpoints (by_<field>)
- Composite constraint lookup endpoints
- Index-based filter endpoints
- M2M relationship management endpoints
""")
    ))

    # Get all model names for imports, excluding M2M through tables
    model_names = []
    serializer_names = []
    m2m_target_models = set()  # Track M2M target models for additional imports

    for table in tables_info:
        if table.primary_key_columns and not table.is_m2m_through_table:
            model_name = to_pascal_case(pluralize(table.name))
            model_names.append(model_name)
            serializer_names.append(f"{model_name}Serializer")

            # Collect M2M target models for imports
            if config.get("enable_m2m_endpoints", True):
                relationships = getattr(table, 'relationships', None) or []
                for rel in relationships:
                    if rel.get("type") == "many-to-many":
                        target_model = rel.get("target_model_name", "")
                        if target_model:
                            m2m_target_models.add(target_model)

    # Add M2M target serializers to imports if not already included
    for target_model in m2m_target_models:
        target_serializer = f"{target_model}Serializer"
        if target_serializer not in serializer_names:
            serializer_names.append(target_serializer)

    # Create comprehensive imports
    imports = [
        # DRF core imports
        create_import("rest_framework", ["viewsets", "permissions", "filters", "status"]),
        create_import("rest_framework.decorators", ["action"]),
        create_import("rest_framework.response", ["Response"]),
        # Django shortcuts
        create_import("django.shortcuts", ["get_object_or_404"]),
        # Django filter
        create_import("django_filters.rest_framework", ["DjangoFilterBackend"]),
        # Local imports
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
            viewset_classes.append(create_viewset_class(table, config))
        else:
            logger.warning(f"Table {table.name} does not have a primary key, skipping viewset generation...")

    # Assemble the module body
    module_body = [file_docstring] + imports + viewset_classes
    return add_location(ast.Module(body=module_body, type_ignores=[]))


def generate_views_code(
    tables_info: List[TableInfo],
    models_module: str = ".models",
    serializers_module: str = ".serializers",
    config: Dict[str, Any] = None
) -> str:
    """Generates the Python code string for views.py."""
    module_ast = generate_views_ast(tables_info, models_module, serializers_module, config)
    return ast.unparse(module_ast)
