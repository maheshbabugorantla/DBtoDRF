import logging
import ast
from typing import List, Dict, Any, Tuple

from drf_auto_generator.ast_codegen.base import (
    create_import, create_assign, create_call, create_attribute_call,
    create_class_def, create_meta_class, create_list_of_strings,
    create_string_constant, create_boolean_constant, create_integer_constant,
    create_none_constant, create_keyword, create_tuple_of_strings, add_location, pluralize
)
from drf_auto_generator.introspection_django import TableInfo, ColumnInfo
from drf_auto_generator.mapper import to_pascal_case


logger = logging.getLogger(__name__)


DJANGO_FIELD_MAP: Dict[str, str] = {
    "AutoField": "AutoField",
    "BigAutoField": "BigAutoField",
    "BooleanField": "BooleanField",
    "CharField": "CharField",
    "DateField": "DateField",
    "DateTimeField": "DateTimeField",
    "DecimalField": "DecimalField",
    "EmailField": "EmailField",
    "FileField": "FileField",
    "FilePathField": "FilePathField",
    "FloatField": "FloatField",
    "ImageField": "ImageField",
    "IntegerField": "IntegerField",
    "GenericIPAddressField": "GenericIPAddressField",
    "NullBooleanField": "BooleanField", # Map to BooleanField with null=True
    "PositiveBigIntegerField": "PositiveBigIntegerField",
    "PositiveIntegerField": "PositiveIntegerField",
    "PositiveSmallIntegerField": "PositiveSmallIntegerField",
    "SlugField": "SlugField",
    "SmallAutoField": "SmallAutoField",
    "SmallIntegerField": "SmallIntegerField",
    "TextField": "TextField",
    "TimeField": "TimeField",
    "URLField": "URLField",
    "UUIDField": "UUIDField",
    "JSONField": "JSONField",
    # Add more mappings as needed based on database types encountered
    # Example: Map PostgreSQL 'text' to TextField
    "text": "TextField",
    "integer": "IntegerField",
    "boolean": "BooleanField",
    "timestamp with time zone": "DateTimeField",
    "date": "DateField",
    "numeric": "DecimalField",
    "character varying": "CharField",
    "ARRAY": "TextField", # Simple fallback for arrays, consider specific handling
    "tsvector": "TextField", # Fallback for tsvector
    # Add mappings for common types like varchar, int, bool etc.
}

# Options that are handled directly by their presence (True)
BOOLEAN_OPTIONS = {"primary_key", "unique", "null", "blank"}
# Options that need specific value types
NUMERIC_OPTIONS = {"max_length", "max_digits", "decimal_places"}

def _map_db_type_to_django(db_type_string: str) -> str:
    """Maps a raw database type string to a Django field type name."""
    # This function needs refinement based on the actual values from introspection
    # It might need to parse the db_type_string more intelligently
    mapped = DJANGO_FIELD_MAP.get(db_type_string, "TextField") # Default fallback
    if db_type_string == "NullBooleanField": # Explicit handling for NullBooleanField
        mapped = "BooleanField"
    # Add more specific logic if needed
    return mapped


def _create_field_options(col_info: ColumnInfo, django_field_type: str, table_info: TableInfo = None) -> List[ast.keyword]:
    """Creates AST keyword arguments for a Django model field based on ColumnInfo."""
    keywords = []

    # Basic options (null, blank, primary_key, unique)
    if col_info.nullable or django_field_type == "BooleanField" and col_info.db_type_string == "NullBooleanField":
        keywords.append(create_keyword("null", create_boolean_constant(True)))
        # Often, if null is True, blank should also be True for CharField/TextField
        if django_field_type in ("CharField", "TextField"):
             keywords.append(create_keyword("blank", create_boolean_constant(True)))

    # Handle primary key logic - special handling for composite PKs
    if col_info.is_pk:
        # Check if this table has multiple primary key columns (composite PK)
        pk_count = len(table_info.primary_key_columns) if table_info else 1

        if pk_count > 1:
            # For composite primary keys, only mark AutoField/BigAutoField as primary_key=True
            # Other fields should not be marked as primary key to avoid Django errors
            if django_field_type in ("AutoField", "BigAutoField"):
                keywords.append(create_keyword("primary_key", create_boolean_constant(True)))
            # Non-AutoField columns in composite PKs should not have primary_key=True
            # The composite uniqueness will be handled by unique_together in Meta
        else:
            # Single primary key - safe to mark as primary_key=True
            keywords.append(create_keyword("primary_key", create_boolean_constant(True)))

    if col_info.is_unique:
         # Avoid adding unique=True if primary_key=True, as PK implies unique
        if not col_info.is_pk:
            keywords.append(create_keyword("unique", create_boolean_constant(True)))

    # Size/Precision options
    if django_field_type in ("CharField", "TextField") and col_info.internal_size:
        keywords.append(create_keyword("max_length", create_integer_constant(col_info.internal_size)))
    elif django_field_type == "DecimalField":
        if col_info.precision:
            keywords.append(create_keyword("max_digits", create_integer_constant(col_info.precision)))
        if col_info.scale is not None: # scale can be 0
            keywords.append(create_keyword("decimal_places", create_integer_constant(col_info.scale)))

    # Add more field-specific options based on Django field types
    if django_field_type == "BooleanField" and col_info.db_type_string == "NullBooleanField":
        # Ensure null=True for NullBooleanField mapping
        if not any(k.arg == "null" for k in keywords):
            keywords.append(create_keyword("null", create_boolean_constant(True)))

    # Enum choices
    if col_info.enum_values:
        choices_list = ast.List(
            elts=[
                ast.Tuple(elts=[create_string_constant(val), create_string_constant(val)], ctx=ast.Load())
                for val in col_info.enum_values
            ],
            ctx=ast.Load()
        )
        keywords.append(create_keyword("choices", choices_list))
        # Usually need max_length for CharField with choices
        if django_field_type == "CharField" and not any(kw.arg == "max_length" for kw in keywords):
             max_len = max(len(v) for v in col_info.enum_values) if col_info.enum_values else 255
             keywords.append(create_keyword("max_length", create_integer_constant(max_len)))

    return keywords


def create_model_field(col_info: ColumnInfo, table_info: TableInfo = None) -> ast.Assign:
    """Creates an AST assignment node for a Django model field."""
    django_field_type = _map_db_type_to_django(col_info.db_type_string)
    field_options = _create_field_options(col_info, django_field_type, table_info)

    field_call = create_attribute_call(
        obj_name="models",
        attr_name=django_field_type,
        keywords=field_options
    )
    return create_assign(target=col_info.name, value=field_call)


def create_relationship_field(rel_info: Dict[str, Any]) -> ast.Assign:
    """Creates an AST assignment node for a relationship field (ForeignKey, ManyToManyField)."""
    field_type = rel_info['type']
    field_name = rel_info['name']
    target_table_name = rel_info['target_table']
    target_model = to_pascal_case(pluralize(target_table_name))
    related_name = rel_info.get('related_name')
    options = rel_info.get('django_field_options', {})

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
    if field_type == 'many-to-one':
        django_field_type = "ForeignKey"
        on_delete_action = options.get('on_delete', 'CASCADE')
        on_delete_argument = ast.Attribute(value=ast.Name(id='models', ctx=ast.Load()), attr=on_delete_action, ctx=ast.Load())
        keywords.append(create_keyword("on_delete", on_delete_argument))
    elif field_type == 'many-to-many':
        django_field_type = "ManyToManyField"
        # M2M specific options - rebuild keywords properly
        m2m_keywords = []

        # Add related_name if available
        if related_name:
            m2m_keywords.append(create_keyword("related_name", create_string_constant(related_name)))

        # Add through and through_fields if available
        if options.get('through'):
            m2m_keywords.append(create_keyword("through", create_string_constant(options['through'])))
        if options.get('through_fields'):
            m2m_keywords.append(create_keyword("through_fields", create_tuple_of_strings(options['through_fields'])))

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

    # Handle composite primary keys for any table (not just through tables)
    if len(table_info.primary_key_columns) > 1:
        # For any table with composite PK, we need to find the actual field names that exist in the model
        # Instead of using database column names, use the relationship field names where applicable
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
            # Check if any field in the composite PK is already marked as primary_key=True (AutoField)
            primary_key_field = None
            for pk_col in table_info.primary_key_columns:
                for col in table_info.columns:
                    if col.name == pk_col and col.db_type_string in ("AutoField", "BigAutoField"):
                        # Find the field name for this column
                        for field_dict in table_info.fields:
                            if (field_dict.get("original_column_name") == pk_col and
                                not field_dict.get("is_handled_by_relation", False)):
                                primary_key_field = field_dict["name"]
                                break
                        break

            # Always add unique_together for ALL composite primary key fields
            # This preserves the exact same uniqueness constraint as the original database
            # Even if one field is marked as primary_key=True, the composite constraint is still needed
            meta_options.append(("unique_together", create_tuple_of_strings(actual_pk_fields)))

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
                value=create_attribute_call('self', 'getattr', args=[create_string_constant(str_col.name), create_none_constant()])
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
                        value=create_attribute_call(
                            'self',
                            'getattr',
                            args=[create_string_constant(pk_name), create_string_constant("N/A")]
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

    # Fields - Filter out fields that are handled by relationships
    # (similar to the Jinja2 template: if not field.is_handled_by_relation)
    fields_to_include = []
    for col in table_info.columns:
        # Check if this column is handled by a relationship
        is_handled = False
        for field_dict in table_info.fields:
            if (field_dict.get("original_column_name") == col.name and
                field_dict.get("is_handled_by_relation", False)):
                is_handled = True
                break

        # Include the field if it's not handled by a relationship
        if not is_handled:
            fields_to_include.append(col)

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
