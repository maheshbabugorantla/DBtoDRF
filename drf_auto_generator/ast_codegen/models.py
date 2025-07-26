import logging
import ast
from typing import List, Dict, Any, Tuple

from drf_auto_generator.ast_codegen.base import (
    create_import, create_assign, create_call, create_attribute_call,
    create_class_def, create_meta_class, create_list_of_strings,
    create_string_constant, create_boolean_constant, create_integer_constant,
    create_none_constant, create_keyword, create_tuple_of_strings, add_location, pluralize
)
from drf_auto_generator.domain.models import TableInfo, ColumnInfo
from drf_auto_generator.mapper import map_db_type_to_django
from drf_auto_generator.domain.naming import to_pascal_case



logger = logging.getLogger(__name__)


# Options that are handled directly by their presence (True)
BOOLEAN_OPTIONS = {"primary_key", "unique", "null", "blank"}
# Options that need specific value types
NUMERIC_OPTIONS = {"max_length", "max_digits", "decimal_places"}


def create_model_field(col_info: ColumnInfo, table_info: TableInfo = None) -> ast.Assign:
    """Creates an AST assignment node for a Django model field."""
    # Use the proper mapper function that handles composite primary keys
    django_field_type, field_options_dict = map_db_type_to_django(col_info, table_info)

    # Convert the options dict to AST keywords
    field_options = []
    for option_name, option_value in field_options_dict.items():
        if option_name in BOOLEAN_OPTIONS and isinstance(option_value, bool):
            field_options.append(create_keyword(option_name, create_boolean_constant(option_value)))
        elif option_name in NUMERIC_OPTIONS and isinstance(option_value, int):
            field_options.append(create_keyword(option_name, create_integer_constant(option_value)))
        elif isinstance(option_value, str):
            field_options.append(create_keyword(option_name, create_string_constant(option_value)))

    # Add any additional field-specific options that weren't handled by the mapper
    additional_options = _create_additional_field_options(col_info, django_field_type, table_info)
    field_options.extend(additional_options)

    field_call = create_attribute_call(
        obj_name="models",
        attr_name=django_field_type,
        keywords=field_options
    )
    return create_assign(target=col_info.name, value=field_call)


def _create_additional_field_options(col_info: ColumnInfo, django_field_type: str, table_info: TableInfo = None) -> List[ast.keyword]:
    """Creates additional AST keyword arguments for special cases not handled by the main mapper."""
    keywords = []

    # Handle enum choices
    if col_info.enum_values:
        choices_list = ast.List(
            elts=[
                ast.Tuple(elts=[create_string_constant(val), create_string_constant(val)], ctx=ast.Load())
                for val in col_info.enum_values
            ],
            ctx=ast.Load()
        )
        keywords.append(create_keyword("choices", choices_list))
        # Usually need max_length for CharField with choices if not already set
        if django_field_type == "CharField":
            max_len = max(len(v) for v in col_info.enum_values) if col_info.enum_values else 255
            keywords.append(create_keyword("max_length", create_integer_constant(max_len)))

    return keywords


def create_relationship_field(rel_info: Dict[str, Any]) -> ast.Assign:
    """Creates an AST assignment node for a relationship field (ForeignKey, ManyToManyField)."""
    field_type = rel_info['type']
    field_name = rel_info['name']
    target_table_name = rel_info['target_table']
    target_model = to_pascal_case(pluralize(target_table_name))
    related_name = rel_info.get('related_name')
    options = rel_info.get('django_field_options', {})

    # Debug logging for M2M fields
    if field_type in ('many-to-many', 'many_to_many'):
        logger.debug(f"Creating M2M field {field_name}: target={target_model}, options={options}")

    keywords = []
    if related_name:
        keywords.append(create_keyword("related_name", create_string_constant(related_name)))
    if options.get('db_column'):
        keywords.append(create_keyword("db_column", create_string_constant(options['db_column'])))
    if options.get('null'):
        keywords.append(create_keyword("null", create_boolean_constant(True)))
    if options.get('blank'): # Often True for FKs if null=True
        keywords.append(create_keyword("blank", create_boolean_constant(True)))

    django_field_type = ""
    if field_type in ('many-to-one', 'many_to_one'):
        django_field_type = "ForeignKey"
        on_delete_action = options.get('on_delete', 'PROTECT')
        on_delete_argument = ast.Attribute(value=ast.Name(id='models', ctx=ast.Load()), attr=on_delete_action, ctx=ast.Load())
        keywords.append(create_keyword("on_delete", on_delete_argument))
    elif field_type in ('one-to-one', 'one_to_one'):
        django_field_type = "OneToOneField"
        on_delete_action = options.get('on_delete', 'PROTECT')
        on_delete_argument = ast.Attribute(value=ast.Name(id='models', ctx=ast.Load()), attr=on_delete_action, ctx=ast.Load())
        keywords.append(create_keyword("on_delete", on_delete_argument))
    elif field_type in ('many-to-many', 'many_to_many'):
        django_field_type = "ManyToManyField"
        # M2M specific options - rebuild keywords properly
        m2m_keywords = []

        # Add related_name if available
        if related_name:
            m2m_keywords.append(create_keyword("related_name", create_string_constant(related_name)))

        # Add through and through_fields if available (check both options and rel_info directly)
        through_model = options.get('through') or rel_info.get('through_model')
        through_table = rel_info.get('through') or rel_info.get('through_table')

        if through_model:
            m2m_keywords.append(create_keyword("through", create_string_constant(through_model)))
        elif through_table:
            # Convert table name to model name using the same convention as other models
            through_model_name = to_pascal_case(pluralize(through_table))
            m2m_keywords.append(create_keyword("through", create_string_constant(through_model_name)))

        through_fields = options.get('through_fields') or rel_info.get('through_fields')
        if through_fields:
            m2m_keywords.append(create_keyword("through_fields", create_tuple_of_strings(through_fields)))

        # Add other M2M specific options
        if options.get('symmetrical') is not None:
            m2m_keywords.append(create_keyword("symmetrical", create_boolean_constant(options['symmetrical'])))

        # M2M usually allows blank
        m2m_keywords.append(create_keyword("blank", create_boolean_constant(True)))

        keywords = m2m_keywords

    if not django_field_type:
        raise ValueError(f"Unsupported relationship type: {field_type}")

    field_call = create_attribute_call(
        obj_name="models",
        attr_name=django_field_type,
        args=[create_string_constant(target_model)],
        keywords=keywords
    )
    return create_assign(target=field_name, value=field_call)


def create_model_meta(table_info: TableInfo) -> ast.ClassDef:
    """Creates the AST node for the inner Meta class of a model."""
    meta_options: List[Tuple[str, ast.expr]] = [
        ("db_table", create_string_constant(table_info.name)),
        ("verbose_name", create_string_constant(table_info.model_name)),
        # Basic pluralization - consider using inflect library
        ("verbose_name_plural", create_string_constant(table_info.model_name + "s")),
    ]

    # Handle composite primary keys - but distinguish between M2M through tables and true composite PKs
    if len(table_info.primary_key_columns) > 1:
        # Check if this is an M2M through table (same logic as in create_model_class)
        is_m2m_through_table = False

        fk_relationships = [rel for rel in table_info.relationships if rel["type"] == "many-to-one"]

        if (len(fk_relationships) == 2 and
            len(table_info.primary_key_columns) == 2):
            # Check if all PK columns are handled by FK relationships
            pk_cols_handled_by_fk = 0
            for pk_col in table_info.primary_key_columns:
                for rel in fk_relationships:
                    if pk_col in rel.get("source_columns", []):
                        pk_cols_handled_by_fk += 1
                        break

            if pk_cols_handled_by_fk == len(table_info.primary_key_columns):
                is_m2m_through_table = True

        # Only add unique_together for M2M through tables
        # Tables with CompositePrimaryKey handle the constraint automatically
        if is_m2m_through_table:
            # For M2M through tables, use unique_together with relationship field names
            actual_pk_fields = []

            for pk_col in table_info.primary_key_columns:
                # Check if this PK column is handled by a relationship
                field_name = None

                # First, check if there's a relationship that handles this column
                for rel in table_info.relationships:
                    if pk_col in rel.get("source_columns", []):
                        field_name = rel["name"]
                        break

                # If not handled by relationship, check if it's a regular field
                if not field_name:
                    for field_dict in table_info.fields:
                        if (field_dict.get("original_column_name") == pk_col and
                            not field_dict.get("is_handled_by_relation", False)):
                            field_name = field_dict["name"]
                            break

                if field_name:
                    actual_pk_fields.append(field_name)
                else:
                    # Fallback to original column name if we can't find the mapped field
                    actual_pk_fields.append(pk_col)

            if actual_pk_fields and len(actual_pk_fields) > 1:
                # Add unique_together for M2M through tables
                meta_options.append(("unique_together", create_tuple_of_strings(actual_pk_fields)))
                logger.debug(f"Added unique_together for M2M through table {table_info.name}: {actual_pk_fields}")
        else:
            logger.debug(f"Skipping unique_together for table {table_info.name} - using CompositePrimaryKey instead")

    # Add Indexes
    if table_info.meta_indexes:
        index_list = []
        for index in table_info.meta_indexes:
            fields = index.get("fields", [])
            index_keywords = [create_keyword("fields", create_list_of_strings(fields))]
            # Add name if available? Django generates one if not.
            # index_name = index.get("name")
            # if index_name:
            #    index_keywords.append(create_keyword("name", create_string_constant(index_name)))
            index_call = create_attribute_call("models", "Index", keywords=index_keywords)
            index_list.append(index_call)
        if index_list:
            meta_options.append(("indexes", ast.List(elts=index_list, ctx=ast.Load())))

    # Add Unique Constraints
    if table_info.meta_constraints:
        constraint_list = []
        for constraint in table_info.meta_constraints:
            if constraint.get("type") == "unique":
                fields = constraint.get("fields", [])
                constraint_keywords = [create_keyword("fields", create_list_of_strings(fields))]
                if constraint.get("name"):
                    constraint_keywords.append(create_keyword("name", create_string_constant(constraint["name"])))
                # TODO: Add condition=models.Q(...) if supported and info available
                constraint_call = create_attribute_call("models", "UniqueConstraint", keywords=constraint_keywords)
                constraint_list.append(constraint_call)
        if constraint_list:
             meta_options.append(("constraints", ast.List(elts=constraint_list, ctx=ast.Load())))

    return create_meta_class(meta_options)


def create_str_method(table_info: TableInfo) -> ast.FunctionDef:
    """Creates the AST node for the __str__ method."""
    body: List[ast.stmt] = []
    # Try to find a common descriptive field
    str_field_names = ['name', 'title', 'username', 'email', 'description']
    str_col = next((col for col in table_info.columns if col.name in str_field_names), None)

    if str_col:
        body.extend([
            add_location(ast.Assign(
                targets=[add_location(ast.Name(id='value', ctx=ast.Store()))],
                value=create_call('getattr', args=[
                    add_location(ast.Name(id='self', ctx=ast.Load())),
                    create_string_constant(str_col.name),
                    create_none_constant()
                ])
            )),
            add_location(ast.If(
                test=add_location(ast.Name(id='value', ctx=ast.Load())),
                body=[add_location(ast.Return(value=create_call('str', args=[add_location(ast.Name(id='value', ctx=ast.Load()))])))],
                orelse=[]
            ))
        ])

    # Fallback to PK
    pk_col = next((col for col in table_info.columns if col.is_pk), None)
    if pk_col:
         pk_name = pk_col.name
         body.append(
            add_location(ast.Return(
                value=add_location(ast.JoinedStr(values=[
                    create_string_constant(f"{table_info.model_name} "),
                    add_location(ast.FormattedValue(
                        value=create_call(
                            'getattr',
                            args=[
                                add_location(ast.Name(id='self', ctx=ast.Load())),
                                create_string_constant(pk_name),
                                create_string_constant("N/A")
                            ]
                        ),
                        conversion=-1, # No conversion
                        format_spec=None
                    ))
                ]))
            ))
         )
    else: # Absolute fallback if no PK found (should be rare)
        body.append(
            add_location(ast.Return(value=create_string_constant(f"{table_info.model_name} object")))
        )

    function_def = add_location(ast.FunctionDef(
        name="__str__",
        args=add_location(ast.arguments(
            posonlyargs=[],
            args=[add_location(ast.arg(arg='self', annotation=None))],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        )),
        body=body,
        decorator_list=[],
        returns=add_location(ast.Name(id='str', ctx=ast.Load()))
    ))

    return function_def


def create_model_class(table_info: TableInfo) -> ast.ClassDef:
    """Creates the AST ClassDef node for a Django model."""
    model_body: List[ast.stmt] = []

    # Docstring
    model_body.append(add_location(ast.Expr(value=create_string_constant(f"Represents the '{table_info.name}' table."))))

    # Handle composite primary keys - but distinguish between M2M through tables and true composite PKs
    if len(table_info.primary_key_columns) > 1:
        # Check if this is an M2M through table
        is_m2m_through_table = False

        # M2M through tables typically:
        # 1. Have exactly 2 foreign key relationships
        # 2. Have exactly 2 primary key columns
        # 3. Those PK columns are the same as the FK columns
        fk_relationships = [rel for rel in table_info.relationships if rel["type"] == "many-to-one"]

        if (len(fk_relationships) == 2 and
            len(table_info.primary_key_columns) == 2):
            # Check if all PK columns are handled by FK relationships
            pk_cols_handled_by_fk = 0
            for pk_col in table_info.primary_key_columns:
                for rel in fk_relationships:
                    if pk_col in rel.get("source_columns", []):
                        pk_cols_handled_by_fk += 1
                        break

            if pk_cols_handled_by_fk == len(table_info.primary_key_columns):
                is_m2m_through_table = True
                logger.debug(f"Table {table_info.name} identified as M2M through table - using unique_together instead of CompositePrimaryKey")

        # Only use CompositePrimaryKey for true composite primary keys (not M2M through tables)
        if not is_m2m_through_table:
            # Create CompositePrimaryKey field for true composite PKs
            pk_field_names = []
            for pk_col in table_info.primary_key_columns:
                # Find the Django field name for this column
                field_name = None

                # First, check if there's a relationship that handles this column
                for rel in table_info.relationships:
                    if pk_col in rel.get("source_columns", []):
                        field_name = rel["name"]
                        break

                # If not handled by relationship, check if it's a regular field
                if not field_name:
                    for field_dict in table_info.fields:
                        if (field_dict.get("original_column_name") == pk_col and
                            not field_dict.get("is_handled_by_relation", False)):
                            field_name = field_dict["name"]
                            break

                if field_name:
                    pk_field_names.append(field_name)
                else:
                    # Fallback to original column name if we can't find the mapped field
                    pk_field_names.append(pk_col)

            # Create the CompositePrimaryKey field
            composite_pk_call = create_attribute_call(
                obj_name="models",
                attr_name="CompositePrimaryKey",
                args=[create_string_constant(name) for name in pk_field_names]
            )
            pk_assign = create_assign(target="pk", value=composite_pk_call)
            model_body.append(pk_assign)

            logger.info(f"Created CompositePrimaryKey for table {table_info.name} with fields: {pk_field_names}")

    # Fields - Filter out fields that are handled by relationships
    fields_to_include = []
    excluded_by_relation = []

    for col in table_info.columns:
        # Check if this column is handled by a relationship
        is_handled = False
        handling_relation = None

        for field_dict in table_info.fields:
            if (field_dict.get("original_column_name") == col.name and
                field_dict.get("is_handled_by_relation", False)):
                is_handled = True
                # Find which relationship handles this field
                for rel in table_info.relationships:
                    if col.name in rel.get("source_columns", []):
                        handling_relation = rel.get("name")
                        break
                break

        # Include the field if it's not handled by a relationship
        if not is_handled:
            fields_to_include.append(col)
        else:
            excluded_by_relation.append((col.name, handling_relation))
            logger.debug(f"Excluding field {col.name} from model {table_info.model_name} (handled by relationship: {handling_relation})")

    if excluded_by_relation:
        logger.info(f"Model {table_info.model_name}: Excluded {len(excluded_by_relation)} FK fields handled by relationships: {[name for name, _ in excluded_by_relation]}")

    model_body.extend(create_model_field(col, table_info) for col in fields_to_include)

    # Relationships
    model_body.extend(create_relationship_field(rel) for rel in table_info.relationships)

    # Meta class
    model_body.append(create_model_meta(table_info))

    # __str__ method
    model_body.append(create_str_method(table_info))

    return create_class_def(
        name=to_pascal_case(pluralize(table_info.name)),
        bases=["models.Model"],
        body=model_body
    )


def generate_models_ast(tables_info: List[TableInfo]) -> ast.Module:
    """Generates the complete AST Module for the models.py file."""
    imports = [
        create_import("django.db", ["models"]),
        # Add other common imports if needed, e.g., uuid
        # create_import("uuid")
    ]

    model_classes = []
    for table in tables_info:
        if table.primary_key_columns:
            model_classes.append(create_model_class(table))
        else:
            logger.warning(f"Table {table.name} does not have a primary key, skipping...")

    module_body = imports + model_classes
    return add_location(ast.Module(body=module_body, type_ignores=[]))


# --- Main function (Example Usage) ---
def generate_models_code(tables_info: List[TableInfo]) -> str:
    """Generates the Python code string for models.py."""
    module_ast = generate_models_ast(tables_info)
    # Use ast.unparse (Python 3.9+)
    return ast.unparse(module_ast)
    # Or use astor for older Python versions:
    # import astor
    # return astor.to_source(module_ast)
