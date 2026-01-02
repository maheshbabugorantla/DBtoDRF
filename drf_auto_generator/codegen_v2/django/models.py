"""
Django models generator using CodeBuilder.

Generates Django model classes from the database schema IR.
"""

import logging
from typing import Any

from ..code_builder import PythonCodeBuilder
from ..schema import (
    DatabaseSchema,
    TableSchema,
    ColumnSchema,
    RelationshipSchema,
    RelationshipType,
    FieldType,
    _SINGULARIZATION_EXCEPTIONS,
)

logger = logging.getLogger(__name__)


class ModelsGenerator:
    """Generates Django models.py file content."""

    def __init__(self, schema: DatabaseSchema):
        self.schema = schema

    def generate(self) -> str:
        """Generate the complete models.py file."""
        b = PythonCodeBuilder()

        # Imports
        b.import_("django.db", ["models"])
        b.line()
        b.line()

        # Generate model classes
        for table in self.schema.tables:
            if not table.primary_key_columns:
                logger.warning(f"Table {table.name} has no primary key, skipping")
                continue

            self._generate_model_class(b, table)
            b.line()
            b.line()

        return b.build()

    def _generate_model_class(self, b: PythonCodeBuilder, table: TableSchema) -> None:
        """Generate a single model class."""
        model_name = table.model_name

        with b.class_(model_name, bases=["models.Model"]):
            # Docstring
            b.docstring(f"Represents the '{table.name}' table.")
            b.line()

            # Handle composite primary keys (Django 5.2+)
            if table.has_composite_pk and not table.is_m2m_through_table:
                pk_fields = self._get_pk_field_names(table)
                pk_args = ", ".join(f'"{f}"' for f in pk_fields)
                b.line(f"pk = models.CompositePrimaryKey({pk_args})")
                b.line()

            # Generate regular fields (excluding those handled by relationships)
            handled_columns = self._get_relationship_columns(table)
            for column in table.columns:
                if column.name not in handled_columns:
                    self._generate_field(b, column, table)

            if table.columns:
                b.line()

            # Generate relationship fields
            for rel in table.relationships:
                self._generate_relationship_field(b, rel)

            if table.relationships:
                b.line()

            # Meta class
            self._generate_meta_class(b, table)

            b.line()

            # __str__ method
            self._generate_str_method(b, table)

    def _generate_field(self, b: PythonCodeBuilder, column: ColumnSchema, table: TableSchema) -> None:
        """Generate a model field definition."""
        field_type = column.field_type.value
        options = column.get_field_options()

        # Handle composite PK members - they shouldn't be AutoFields
        if column.primary_key and table.has_composite_pk:
            if column.field_type in (FieldType.AUTO, FieldType.BIG_AUTO, FieldType.SMALL_AUTO):
                # Convert auto fields to regular integer fields for composite PKs
                type_map = {
                    FieldType.AUTO: "IntegerField",
                    FieldType.BIG_AUTO: "BigIntegerField",
                    FieldType.SMALL_AUTO: "SmallIntegerField",
                }
                field_type = type_map.get(column.field_type, "IntegerField")
                # Remove primary_key option - it's handled by CompositePrimaryKey
                options.pop("primary_key", None)

        # Format field options
        options_str = self._format_field_options(options)

        if options_str:
            b.line(f"{column.django_field_name} = models.{field_type}({options_str})")
        else:
            b.line(f"{column.django_field_name} = models.{field_type}()")

    def _generate_relationship_field(self, b: PythonCodeBuilder, rel: RelationshipSchema) -> None:
        """Generate a relationship field definition."""
        field_type = rel.django_field_type
        target = rel.target_model or self._to_model_name(rel.target_table)
        options = rel.get_field_options()

        # Format the field call
        options_str = self._format_relationship_options(options, rel.type)

        if options_str:
            b.line(f'{rel.name} = models.{field_type}("{target}", {options_str})')
        else:
            b.line(f'{rel.name} = models.{field_type}("{target}")')

    def _generate_meta_class(self, b: PythonCodeBuilder, table: TableSchema) -> None:
        """Generate the Meta inner class."""
        with b.class_("Meta"):
            b.line(f'db_table = "{table.name}"')
            b.line(f'verbose_name = "{table.model_name}"')
            b.line(f'verbose_name_plural = "{self._get_plural_name(table.model_name)}"')
            # Use managed=False for existing databases
            b.line("managed = False")

            # Add unique_together for M2M through tables
            if table.has_composite_pk and table.is_m2m_through_table:
                pk_fields = self._get_pk_field_names(table)
                if len(pk_fields) > 1:
                    fields_str = ", ".join(f'"{f}"' for f in pk_fields)
                    b.line(f"unique_together = [({fields_str})]")

            # Add indexes
            if table.indexes:
                b.line("indexes = [")
                b.indent()
                for idx in table.indexes:
                    fields_str = ", ".join(f'"{f}"' for f in idx.fields)
                    b.line(f"models.Index(fields=[{fields_str}]),")
                b.dedent()
                b.line("]")

            # Add constraints
            unique_constraints = [c for c in table.constraints if c.type == "unique"]
            if unique_constraints:
                b.line("constraints = [")
                b.indent()
                for constraint in unique_constraints:
                    fields_str = ", ".join(f'"{f}"' for f in constraint.fields)
                    b.line(f'models.UniqueConstraint(fields=[{fields_str}], name="{constraint.name}"),')
                b.dedent()
                b.line("]")

    def _generate_str_method(self, b: PythonCodeBuilder, table: TableSchema) -> None:
        """Generate the __str__ method."""
        with b.method("__str__", returns="str"):
            # Try to find a descriptive field
            str_field = self._find_str_field(table)

            if str_field:
                b.line(f"value = getattr(self, '{str_field}', None)")
                with b.if_("value"):
                    b.return_("str(value)")

            # Fallback to PK
            if table.pk_column:
                pk_field = self._column_to_field_name(table, table.pk_column)
                b.return_(f'f"{table.model_name} {{getattr(self, \'{pk_field}\', \'N/A\')}}"')
            elif table.has_composite_pk:
                b.return_(f'f"{table.model_name} {{self.pk}}"')
            else:
                b.return_(f'"{table.model_name} object"')

    # --- Helper Methods ---

    def _get_relationship_columns(self, table: TableSchema) -> set[str]:
        """Get column names that are handled by relationships."""
        columns = set()
        for rel in table.relationships:
            if rel.source_column:
                columns.add(rel.source_column)
        return columns

    def _get_pk_field_names(self, table: TableSchema) -> list[str]:
        """Get Django field names for primary key columns."""
        pk_fields = []
        for pk_col in table.primary_key_columns:
            # Check if handled by relationship
            rel_name = None
            for rel in table.relationships:
                if rel.source_column == pk_col:
                    rel_name = rel.name
                    break

            if rel_name:
                pk_fields.append(rel_name)
            else:
                # Find the Django field name
                col = table.get_column(pk_col)
                if col:
                    pk_fields.append(col.django_field_name)
                else:
                    pk_fields.append(pk_col)

        return pk_fields

    def _column_to_field_name(self, table: TableSchema, column_name: str) -> str:
        """Convert a column name to its Django field name."""
        col = table.get_column(column_name)
        return col.django_field_name if col else column_name

    def _find_str_field(self, table: TableSchema) -> str | None:
        """Find a suitable field for __str__ representation."""
        preferred = ["name", "title", "username", "email", "description"]
        for pref in preferred:
            for col in table.columns:
                if col.name.lower() == pref:
                    return col.django_field_name
        return None

    def _to_model_name(self, table_name: str) -> str:
        """Convert table name to model name."""
        import inflect
        p = inflect.engine()
        words = table_name.split('_')
        pascal = ''.join(word.capitalize() for word in words)

        # Check for singularization exceptions first
        if pascal in _SINGULARIZATION_EXCEPTIONS:
            return _SINGULARIZATION_EXCEPTIONS[pascal]

        # Try to singularize (users -> User)
        singular = p.singular_noun(pascal)
        # Only use singularized form if it looks valid
        if singular and len(singular) >= len(pascal) - 2:
            return singular
        return pascal

    def _get_plural_name(self, model_name: str) -> str:
        """Get the plural form of a model name for verbose_name_plural."""
        import inflect
        p = inflect.engine()

        # Common pluralization rules
        if model_name.endswith('y'):
            # Category -> Categories, but not if preceded by vowel
            if len(model_name) > 1 and model_name[-2] not in 'aeiouAEIOU':
                return model_name[:-1] + 'ies'
        elif model_name.endswith(('s', 'x', 'z', 'ch', 'sh')):
            return model_name + 'es'
        elif model_name.endswith('f'):
            return model_name[:-1] + 'ves'
        elif model_name.endswith('fe'):
            return model_name[:-2] + 'ves'

        # Try inflect library
        plural = p.plural_noun(model_name)
        if plural:
            return plural

        # Default: just add 's'
        return model_name + 's'

    def _format_field_options(self, options: dict[str, Any]) -> str:
        """Format field options as a string for code generation."""
        parts = []
        for key, value in options.items():
            if value is None:
                continue
            if isinstance(value, bool):
                parts.append(f"{key}={value}")
            elif isinstance(value, str):
                parts.append(f'{key}="{value}"')
            elif isinstance(value, (list, tuple)):
                # Handle choices
                if key == "choices":
                    choices_str = ", ".join(f'("{v[0]}", "{v[1]}")' for v in value)
                    parts.append(f"{key}=[{choices_str}]")
                else:
                    items = ", ".join(f'"{v}"' for v in value)
                    parts.append(f"{key}=[{items}]")
            else:
                parts.append(f"{key}={value}")
        return ", ".join(parts)

    def _format_relationship_options(self, options: dict[str, Any], rel_type: RelationshipType) -> str:
        """Format relationship field options."""
        parts = []

        # on_delete is required for FK and O2O
        if rel_type in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE):
            on_delete = options.pop("on_delete", "CASCADE")
            parts.append(f"on_delete=models.{on_delete}")

        for key, value in options.items():
            if value is None:
                continue
            if isinstance(value, bool):
                parts.append(f"{key}={value}")
            elif isinstance(value, str):
                parts.append(f'{key}="{value}"')
            elif isinstance(value, tuple) and key == "through_fields":
                fields = ", ".join(f'"{f}"' for f in value)
                parts.append(f"{key}=({fields})")
            else:
                parts.append(f"{key}={value}")

        return ", ".join(parts)
