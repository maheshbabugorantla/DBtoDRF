"""
Django REST Framework serializers generator using CodeBuilder.

Generates DRF serializer classes from the database schema IR.
"""

import logging

from ..code_builder import PythonCodeBuilder
from ..schema import DatabaseSchema, TableSchema

logger = logging.getLogger(__name__)


class SerializersGenerator:
    """Generates Django REST Framework serializers.py file content."""

    def __init__(self, schema: DatabaseSchema):
        self.schema = schema

    def generate(self) -> str:
        """Generate the complete serializers.py file."""
        b = PythonCodeBuilder()

        # Get non-through tables for import
        tables = self.schema.get_non_through_tables()
        model_names = [t.model_name for t in tables if t.primary_key_columns]

        # Imports
        b.import_("rest_framework", ["serializers"])
        if model_names:
            b.import_(".models", model_names)
        b.line()
        b.line()

        # Generate serializer classes
        for table in tables:
            if not table.primary_key_columns:
                logger.warning(f"Table {table.name} has no primary key, skipping serializer")
                continue

            self._generate_serializer_class(b, table)
            b.line()
            b.line()

        return b.build()

    def _generate_serializer_class(self, b: PythonCodeBuilder, table: TableSchema) -> None:
        """Generate a single serializer class."""
        serializer_name = f"{table.model_name}Serializer"

        with b.class_(serializer_name, bases=["serializers.ModelSerializer"]):
            # Docstring
            b.docstring(f"Serializer for {table.model_name} model.")
            b.line()

            # Meta class
            with b.class_("Meta"):
                b.line(f"model = {table.model_name}")
                b.line('fields = "__all__"')

                # Optionally specify read_only_fields for auto fields
                read_only = self._get_read_only_fields(table)
                if read_only:
                    fields_str = ", ".join(f'"{f}"' for f in read_only)
                    b.line(f"read_only_fields = [{fields_str}]")

    def _get_read_only_fields(self, table: TableSchema) -> list[str]:
        """Get fields that should be read-only (auto-generated PKs)."""
        from ..schema import FieldType

        read_only = []
        for col in table.columns:
            if col.field_type in (FieldType.AUTO, FieldType.BIG_AUTO, FieldType.SMALL_AUTO):
                read_only.append(col.django_field_name)
        return read_only
